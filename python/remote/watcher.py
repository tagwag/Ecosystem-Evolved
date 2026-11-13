"""Remote experiment watcher. Runs on the workstation; starts experiments from job files.

HOW A JOB IS STARTED
  Put a file in python/remote/queue/ named anything ending in .json, e.g. toy.json:
      {"experiment": "toybrain_gpu", "args": {"seeds": 30, "gens": 300}}          (optional: "exclusive": true)
  Only experiments listed in experiments.toml can run. Jobs run one at a time, oldest first.
  Claude writes these files through the desktop app link (also when you ask from your phone).

FILES
  queue/    waiting jobs          running/  the current job      done/ failed/  finished jobs (+ result info)
  logs/     one output log per job                                status.json    what is happening right now
  queue/CANCEL  (empty file)  stops the current job; the file is then removed
  queue/PAUSE   (empty file)  don't start new jobs while it exists

PARALLEL JOBS
  Jobs whose experiment has `share = true` in experiments.toml are LIGHT: up to MAX_PARALLEL of them run at the same
  time (each starting whenever it is picked up), but only while the GPU is under UTIL_MAX % busy and below TEMP_MAX C.
  Any job without share = true runs ALONE (whole GPU). A job file can override: "share": true / false, or
  "exclusive": true (= whole GPU). Queue order is first-in-first-out: a whole-GPU job at the front waits until the
  running light jobs finish, and jobs behind it wait too. CANCEL stops every running job.

SAFETY GATE
  Before a job starts: its experiment's preflight check (or its declared vram_mb) must fit in free GPU memory with a
  margin; GPU < 80 C; >= 5 GB free disk; >= 2 GB free RAM. Settings that can never fit are REJECTED at once with the
  numbers; temporary conditions (hot GPU, memory in use) make it WAIT, and after 1 h it fails with the reason.
  While running: >= 90 C stops all jobs immediately; disk < 1 GB or RAM < 0.5 GB stops them before Windows struggles.

GPU CARE
  A GPU job waits until no other (outside) Python program is using the GPU. GPU temperature is logged every 30 s.
  If it stays at or above 87 C for 3 minutes the job is stopped (marked 'overheat').
SAFE TO CLOSE this window any time: a running job is stopped with it and marked failed ('watcher stopped').
"""
import json, os, re, shutil, subprocess, sys, time, tomllib, traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY_DIR = HERE.parent
PY = str(PY_DIR / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else sys.executable
Q, RUN, DONE, FAIL, LOGS = (HERE / d for d in ("queue", "running", "done", "failed", "logs"))
STATUS = HERE / "status.json"
HOT_C, HOT_SECONDS, POLL = 87, 180, 5
MAX_PARALLEL, UTIL_MAX, TEMP_MAX = 3, 50, 80     # parallel light jobs: at most 3, only while GPU < 50 % busy, < 80 C
# SAFETY GATE (see README section 6c). Nothing starts or keeps running if it could harm this computer.
SAFE = dict(start_temp_max=80,       # C: no job STARTS at or above this (waits)
            hard_temp_stop=90,       # C: running jobs are stopped IMMEDIATELY at or above this
            vram_margin_mb=1200,     # GPU memory kept free for Windows / the desktop
            min_disk_gb_start=5, min_disk_gb_run=1,     # free disk space needed to start / to keep running
            min_ram_gb_start=2, min_ram_gb_run=0.5,     # free system memory needed to start / to keep running
            max_wait_s=3600)         # a job that can't start safely for this long fails with the reason
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def say(msg):
    line = f"{now()} {msg}"
    print(line, flush=True)
    with (HERE / "watcher_log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def gpu_info():
    """(temperature C, used MiB, list of compute-process ids) or (None, None, []) if nvidia-smi fails."""
    try:
        t = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,utilization.gpu,power.draw,memory.total",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.strip()
        temp, mem, util, power, total = [x.strip() for x in t.split(",")]
        # Windows lists every desktop app that draws on the GPU; only Python programs count as "experiments".
        rows = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=10).stdout.splitlines()
        pids = []
        for r in rows:
            pid, _, name = r.partition(",")
            if pid.strip().isdigit() and "python" in name.lower():
                pids.append(int(pid))
        return dict(temp_c=int(float(temp)), mem_mib=int(float(mem)), util_pct=int(float(util)), mem_total_mib=int(float(total)),
                    power_w=float(power) if power not in ("[N/A]", "N/A") else None), pids
    except Exception:
        return None, []


def write_status(**kw):
    kw["updated"] = now()
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(kw, indent=1))
    tmp.replace(STATUS)


def build(job, reg):
    """Validate a job against the registry; return (name, argv, cwd, gpu) or raise ValueError."""
    name = job.get("experiment")
    if name not in reg:
        raise ValueError(f"unknown experiment {name!r}; allowed: {', '.join(reg)}")
    spec, given = reg[name], dict(job.get("args") or {})
    vals = {}
    for a, rule in (spec.get("args") or {}).items():
        v = given.pop(a, rule.get("default"))
        if rule["type"] == "int":
            v = int(v)
            if not rule.get("min", v) <= v <= rule.get("max", v):
                raise ValueError(f"{a}={v} outside {rule.get('min')}..{rule.get('max')}")
        elif rule["type"] == "name":
            v = str(v)
            if not NAME_RE.match(v):
                raise ValueError(f"{a}={v!r} must be letters, digits, _ or -")
        vals[a] = str(v)
    if given:
        raise ValueError(f"unknown args: {', '.join(given)}")
    argv = [w.replace("{py}", PY).format(**vals) if "{" in w else w for w in spec["cmd"]]
    argv = [PY if w == "{py}" else w for w in argv]
    build.last = (spec, vals)                       # for the safety preflight
    return name, argv, PY_DIR / spec.get("cwd", "."), bool(spec.get("gpu")), bool(spec.get("share"))


def finish(path, ok, info):
    dest = (DONE if ok else FAIL) / path.name
    data = json.loads(path.read_text()) if path.exists() else {}
    data["result"] = info
    dest.write_text(json.dumps(data, indent=1))
    path.unlink(missing_ok=True)


def apply_settings():
    """Read watcher_settings.toml (editable in the GUI) into the live limits. Missing/broken file = keep defaults."""
    global MAX_PARALLEL, UTIL_MAX, HOT_C, HOT_SECONDS
    try:
        from simctl import load_settings          # same file, values clamped to the safe ranges (simctl.SETTING_RANGES)
        st = load_settings()
    except Exception:
        return
    j, sf = st.get("jobs", {}), st.get("safety", {})
    MAX_PARALLEL = int(j.get("max_parallel", MAX_PARALLEL)); UTIL_MAX = int(j.get("util_max", UTIL_MAX))
    SAFE["max_wait_s"] = int(j.get("max_wait_minutes", SAFE["max_wait_s"] // 60)) * 60
    HOT_C = int(sf.get("overheat_temp", HOT_C)); HOT_SECONDS = int(sf.get("overheat_seconds", HOT_SECONDS))
    for k in ("start_temp_max", "hard_temp_stop", "vram_margin_mb", "min_disk_gb_start", "min_disk_gb_run",
              "min_ram_gb_start", "min_ram_gb_run"):
        if k in sf:
            SAFE[k] = sf[k]


def free_ram_gb():
    """Free system memory in GB (Windows: GlobalMemoryStatusEx; Linux: /proc/meminfo)."""
    try:
        if os.name == "nt":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 2 ** 30
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) / 2 ** 20
    except Exception:
        pass
    return 99.0


def free_disk_gb():
    return shutil.disk_usage(PY_DIR).free / 2 ** 30


def preflight(spec, vals, cwd):
    """Ask the experiment how much it needs and whether its settings are safe. Experiments with a `preflight` command
    in experiments.toml run it (it must print JSON {ok, errors, gpu_mb}); others declare `vram_mb` (default 1500)."""
    if spec.get("preflight"):
        argv = [PY if w == "{py}" else (w.format(**vals) if "{" in w else w) for w in spec["preflight"]]
        try:
            out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=300,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip().splitlines()
            r = json.loads(out[-1])
            return int(r.get("gpu_mb", 1500)), list(r.get("errors", []))
        except Exception as e:
            return 0, [f"preflight check failed to run: {e}"]
    return int(spec.get("vram_mb", 1500)), []


def start_blockers(need_mb, g, active_need):
    """Reasons a job may NOT start right now (empty list = safe). Temporary conditions only."""
    why = []
    if g:
        if g["temp_c"] >= SAFE["start_temp_max"]:
            why.append(f"GPU is {g['temp_c']} C (jobs only start below {SAFE['start_temp_max']} C)")
        free = g["mem_total_mib"] - g["mem_mib"] - SAFE["vram_margin_mb"]
        if need_mb > free:
            why.append(f"needs ~{need_mb} MB GPU memory, only {max(free, 0)} MB free after the {SAFE['vram_margin_mb']} MB safety margin")
    if free_disk_gb() < SAFE["min_disk_gb_start"]:
        why.append(f"only {free_disk_gb():.1f} GB free disk (needs {SAFE['min_disk_gb_start']} GB to start)")
    if free_ram_gb() < SAFE["min_ram_gb_start"]:
        why.append(f"only {free_ram_gb():.1f} GB free RAM (needs {SAFE['min_ram_gb_start']} GB to start)")
    return why


class Job:
    """One running experiment (a child process) and its bookkeeping."""

    def __init__(self, path, name, argv, cwd, gpu, share, args):
        self.path, self.name, self.gpu, self.share, self.args = path, name, gpu, share, args
        self.id = path.stem; self.t0 = time.time(); self.hot_since = None; self.reason = None
        self.log = LOGS / f"{self.id}.txt"
        self.lf = self.log.open("w", encoding="utf-8")
        self.lf.write(f"{now()} {' '.join(argv)}\n(cwd {cwd})\n\n"); self.lf.flush()
        env = dict(os.environ, SIM_JOB=self.id, PYTHONPATH=str(HERE) + os.pathsep + os.environ.get("PYTHONPATH", ""))
        self.proc = subprocess.Popen(argv, cwd=cwd, stdout=self.lf, stderr=subprocess.STDOUT, env=env,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        say(f"START {self.id}: {name} {args}  (log: logs/{self.log.name}){'  [light, may share GPU]' if share else ''}")

    def stop(self, reason):
        if self.reason is None:
            self.reason = reason
        if self.proc.poll() is None:
            self.proc.terminate()

    def done(self):
        return self.proc.poll() is not None

    def close(self):
        try:
            self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.lf.close()
        code = self.proc.returncode; ok = self.reason is None and code == 0
        info = dict(exit_code=code, minutes=round((time.time() - self.t0) / 60, 1), ended=now(), log=f"logs/{self.log.name}")
        if self.reason:
            info["error"] = self.reason
        say(f"{'DONE' if ok else 'FAILED'} {self.id}: {info}")
        finish(self.path, ok, info)


def main():
    for d in (Q, RUN, DONE, FAIL, LOGS):
        d.mkdir(exist_ok=True)
    for p in RUN.glob("*.json"):                     # left over from a crash / closed window
        finish(p, False, dict(error="watcher stopped", at=now()))
    say(f"watcher started (python: {PY}; up to {MAX_PARALLEL} light jobs in parallel)")
    if (Q / "RELOAD_UNPAUSE").exists():             # set by Claude to switch watcher versions cleanly: the old version
        (Q / "RELOAD_UNPAUSE").unlink(missing_ok=True)   # pauses, goes idle, reloads; the new one unpauses here
        (Q / "PAUSE").unlink(missing_ok=True)
        say("unpaused after code reload")
    active, my_mtime, last_g, g = [], Path(__file__).stat().st_mtime, 0, None
    outside, need_cache, first_seen = [], {}, {}
    apply_settings()
    try:
        while True:
            reg = tomllib.loads((HERE / "experiments.toml").read_text())   # re-read: new experiments need no restart
            apply_settings()                                                 # watcher_settings.toml, applied live
            # ---- running jobs: cancel, finish, temperature guard
            if (Q / "CANCEL").exists():
                (Q / "CANCEL").unlink(missing_ok=True)
                for j in active:
                    j.stop("cancelled")
            for j in [j for j in active if j.done()]:
                j.close(); active.remove(j)
            if time.time() - last_g >= (30 if active else 10):
                last_g = time.time(); g, outside = gpu_info()
                mine = {j.proc.pid for j in active}
                outside = [p for p in outside if p not in mine]
                if active:                                       # SAFETY: hard stops while running
                    hard = []
                    if g and g["temp_c"] >= SAFE["hard_temp_stop"]:
                        hard.append(f"GPU reached {g['temp_c']} C (hard limit {SAFE['hard_temp_stop']} C)")
                    if free_disk_gb() < SAFE["min_disk_gb_run"]:
                        hard.append(f"disk almost full ({free_disk_gb():.2f} GB free)")
                    if free_ram_gb() < SAFE["min_ram_gb_run"]:
                        hard.append(f"system memory almost full ({free_ram_gb():.2f} GB free)")
                    if hard:
                        say("SAFETY STOP: " + "; ".join(hard))
                        for j in active:
                            j.stop("safety stop: " + "; ".join(hard))
                if g and active:
                    with (HERE / "gpu_temps.csv").open("a") as f:
                        f.write(f"{now()},{'+'.join(j.id for j in active)},{g['temp_c']},{g['util_pct']},{g['mem_mib']},{g['power_w']}\n")
                    for j in active:
                        if g["temp_c"] >= HOT_C:
                            j.hot_since = j.hot_since or time.time()
                            if time.time() - j.hot_since >= HOT_SECONDS:
                                j.stop(f"overheat ({g['temp_c']} C for {HOT_SECONDS} s)")
                        else:
                            j.hot_since = None
            # ---- maybe start the next job
            jobs = sorted(Q.glob("*.json"), key=lambda p: p.stat().st_mtime)
            waiting = None
            if jobs and not (Q / "PAUSE").exists():
                path = jobs[0]
                try:
                    job = json.loads(path.read_text()); name, argv, cwd, gpu, share = build(job, reg)
                    if "share" in job:                       # per-job override: {"share": true} = may run alongside
                        share = bool(job["share"])
                    if job.get("exclusive"):                 # {"exclusive": true} = whole GPU, nothing beside it
                        share = False
                except Exception as e:
                    say(f"REJECTED {path.name}: {e}")
                    run_p = RUN / path.name; shutil.move(str(path), run_p); finish(run_p, False, dict(error=str(e), at=now()))
                    continue
                spec, vals = build.last
                key = path.name
                if key not in need_cache:                     # SAFETY preflight (once per job file)
                    need_cache[key] = preflight(spec, vals, cwd)
                    first_seen[key] = time.time()
                need, perm = need_cache[key]
                if g and need > g["mem_total_mib"] - SAFE["vram_margin_mb"]:
                    perm = perm + [f"needs ~{need} MB GPU memory but this GPU has {g['mem_total_mib']} MB "
                                   f"({SAFE['vram_margin_mb']} MB kept free): it can never fit"]
                if perm:                                       # unsafe settings: refuse with the exact reasons
                    say(f"REFUSED {path.name} (unsafe for this computer): {'; '.join(perm)}")
                    run_p = RUN / path.name; shutil.move(str(path), run_p)
                    finish(run_p, False, dict(error="REFUSED (unsafe): " + "; ".join(perm), at=now()))
                    need_cache.pop(key, None); continue
                block = start_blockers(need, g, 0) if gpu else []
                if not active:
                    can = not (gpu and outside) and not block
                    if gpu and outside:
                        block = block + [f"other python programs are using the GPU ({outside})"]
                else:
                    can = (share and all(j.share for j in active) and len(active) < MAX_PARALLEL and g is not None
                           and g["util_pct"] < UTIL_MAX and g["temp_c"] < TEMP_MAX and not outside and not block)
                if block:
                    waiting = "waiting (safety): " + "; ".join(block)
                    if time.time() - first_seen[key] > SAFE["max_wait_s"]:
                        say(f"GAVE UP {path.name}: could not start safely for {SAFE['max_wait_s'] // 60} min: {'; '.join(block)}")
                        run_p = RUN / path.name; shutil.move(str(path), run_p)
                        finish(run_p, False, dict(error="could not start safely: " + "; ".join(block), at=now()))
                        need_cache.pop(key, None); continue
                if can:
                    run_p = RUN / path.name; shutil.move(str(path), run_p)
                    active.append(Job(run_p, name, argv, cwd, gpu, share, job.get("args") or {}))
                    need_cache.pop(path.name, None)
                    last_g = 0
                    continue
            if not active and Path(__file__).stat().st_mtime != my_mtime:     # code updated -> restart itself when idle
                say("watcher.py changed, restarting")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, "-u", __file__], cwd=HERE, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    return
                os.execv(sys.executable, [sys.executable, "-u", __file__])
            first = active[0] if active else None
            write_status(state=("running" if active else ("paused" if (Q / "PAUSE").exists() else "idle")),
                         job=first.id if first else None, experiment=first.name if first else None,
                         minutes=round((time.time() - first.t0) / 60, 1) if first else None,
                         jobs=[dict(job=j.id, experiment=j.name, args=j.args, light=j.share,
                                    minutes=round((time.time() - j.t0) / 60, 1), log=f"logs/{j.log.name}") for j in active],
                         waiting=waiting, gpu=g, queued=sorted(p.name for p in Q.glob("*.json")), experiments=list(reg))
            time.sleep(POLL)
    except KeyboardInterrupt:
        pass
    except Exception:
        say("WATCHER CRASHED:\n" + traceback.format_exc())
        raise
    finally:
        for j in active:
            j.stop("watcher stopped"); j.close()


if __name__ == "__main__":
    main()
