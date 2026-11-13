"""Remote experiment watcher. Runs on the workstation; starts experiments from job files.

HOW A JOB IS STARTED
  Put a file in python/remote/queue/ named anything ending in .json, e.g. toy.json:
      {"experiment": "toybrain_gpu", "args": {"seeds": 30, "gens": 300}}
  Only experiments listed in experiments.toml can run. Jobs run one at a time, oldest first.
  Claude writes these files through the desktop app link (also when you ask from your phone).

FILES
  queue/    waiting jobs          running/  the current job      done/ failed/  finished jobs (+ result info)
  logs/     one output log per job                                status.json    what is happening right now
  queue/CANCEL  (empty file)  stops the current job; the file is then removed
  queue/PAUSE   (empty file)  don't start new jobs while it exists

GPU CARE
  A GPU job waits until no other program is using the GPU. GPU temperature is logged every 30 s.
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
        t = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,utilization.gpu,power.draw",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.strip()
        temp, mem, util, power = [x.strip() for x in t.split(",")]
        # Windows lists every desktop app that draws on the GPU; only Python programs count as "experiments".
        rows = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=10).stdout.splitlines()
        pids = []
        for r in rows:
            pid, _, name = r.partition(",")
            if pid.strip().isdigit() and "python" in name.lower():
                pids.append(int(pid))
        return dict(temp_c=int(float(temp)), mem_mib=int(float(mem)), util_pct=int(float(util)),
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
    return name, argv, PY_DIR / spec.get("cwd", "."), bool(spec.get("gpu"))


def finish(path, ok, info):
    dest = (DONE if ok else FAIL) / path.name
    data = json.loads(path.read_text()) if path.exists() else {}
    data["result"] = info
    dest.write_text(json.dumps(data, indent=1))
    path.unlink(missing_ok=True)


def run_job(path, reg):
    job_id = path.stem
    try:
        job = json.loads(path.read_text())
        name, argv, cwd, gpu = build(job, reg)
    except Exception as e:
        say(f"REJECTED {path.name}: {e}")
        finish(path, False, dict(error=str(e), at=now()))
        return
    if gpu:
        while True:                                   # wait for the GPU to be free (other runs, e.g. started by hand)
            g, pids = gpu_info()
            if not pids:
                break
            write_status(state="waiting for GPU", job=job_id, experiment=name, gpu=g, other_gpu_pids=pids)
            if (Q / "CANCEL").exists():
                (Q / "CANCEL").unlink(missing_ok=True)
                say(f"CANCELLED {job_id} while waiting for GPU")
                finish(path, False, dict(error="cancelled", at=now()))
                return
            time.sleep(30)
    log = LOGS / f"{job_id}.txt"
    say(f"START {job_id}: {name} {job.get('args') or {}}  (log: logs/{log.name})")
    t0, hot_since, reason = time.time(), None, None
    with log.open("w", encoding="utf-8") as lf:
        lf.write(f"{now()} {' '.join(argv)}\n(cwd {cwd})\n\n"); lf.flush()
        proc = subprocess.Popen(argv, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        last_g = 0
        while proc.poll() is None:
            time.sleep(POLL)
            if (Q / "CANCEL").exists():
                (Q / "CANCEL").unlink(missing_ok=True); reason = "cancelled"; proc.terminate(); break
            if time.time() - last_g >= 30:
                last_g = time.time()
                g, _ = gpu_info()
                if g:
                    with (HERE / "gpu_temps.csv").open("a") as f:
                        f.write(f"{now()},{job_id},{g['temp_c']},{g['util_pct']},{g['mem_mib']},{g['power_w']}\n")
                    if g["temp_c"] >= HOT_C:
                        hot_since = hot_since or time.time()
                        if time.time() - hot_since >= HOT_SECONDS:
                            reason = f"overheat ({g['temp_c']} C for {HOT_SECONDS} s)"; proc.terminate(); break
                    else:
                        hot_since = None
                write_status(state="running", job=job_id, experiment=name, args=job.get("args") or {},
                             started=datetime.fromtimestamp(t0).strftime("%Y-%m-%d %H:%M:%S"),
                             minutes=round((time.time() - t0) / 60, 1), gpu=g, log=f"logs/{log.name}",
                             queued=sorted(p.name for p in Q.glob("*.json")))
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
    code = proc.returncode
    ok = reason is None and code == 0
    info = dict(exit_code=code, minutes=round((time.time() - t0) / 60, 1), ended=now(), log=f"logs/{log.name}")
    if reason:
        info["error"] = reason
    say(f"{'DONE' if ok else 'FAILED'} {job_id}: {info}")
    finish(path, ok, info)


def main():
    for d in (Q, RUN, DONE, FAIL, LOGS):
        d.mkdir(exist_ok=True)
    for p in RUN.glob("*.json"):                     # left over from a crash / closed window
        finish(p, False, dict(error="watcher stopped", at=now()))
    say(f"watcher started (python: {PY})")
    current = None
    my_mtime = Path(__file__).stat().st_mtime
    try:
        while True:
            reg = tomllib.loads((HERE / "experiments.toml").read_text())   # re-read: new experiments need no restart
            jobs = sorted(Q.glob("*.json"), key=lambda p: p.stat().st_mtime)
            if jobs and not (Q / "PAUSE").exists():
                current = RUN / jobs[0].name
                shutil.move(str(jobs[0]), current)
                run_job(current, reg)
                current = None
                continue
            if Path(__file__).stat().st_mtime != my_mtime:          # code updated -> restart itself (only when idle)
                say("watcher.py changed, restarting")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, "-u", __file__], cwd=HERE,
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
                    return
                os.execv(sys.executable, [sys.executable, "-u", __file__])
            g, pids = gpu_info()
            write_status(state="paused" if (Q / "PAUSE").exists() else "idle", gpu=g, other_gpu_pids=pids,
                         experiments=list(reg))
            time.sleep(POLL)
    except KeyboardInterrupt:
        pass
    except Exception:
        say("WATCHER CRASHED:\n" + traceback.format_exc())
        raise
    finally:
        if current is not None and current.exists():
            finish(current, False, dict(error="watcher stopped", at=now()))


if __name__ == "__main__":
    main()
