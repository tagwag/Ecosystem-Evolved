"""Experiment GUI server: a small local web app for filling in experiment forms, checking them, and starting runs
through the remote watcher. Everything it shows is generated from the factor catalog + the engine registry, so the
GUI always matches what the engine can do.

Start:  start_gui.bat  (or:  ..\\.venv\\Scripts\\python.exe server.py)  then open http://127.0.0.1:8765
Options: --port N    --lan  (also listen on the local network, e.g. to open it from a phone over Tailscale/Wi-Fi;
                              anyone on that network could then queue runs, so only use it on a trusted network)

API (all JSON):
  GET  /api/schema            factors (category, evidence, GUI level, defaults, autopilot, docs), run/world settings
  POST /api/check   {form}    -> {ok, errors, toml}         checks the form exactly like run.py would
  POST /api/save    {form}    -> writes engine/configs/<name>.toml
  POST /api/queue   {form, quick}  -> saves, then drops a job file in remote/queue/
  GET  /api/status            watcher status.json + waiting jobs + recent finished jobs + result files
  GET  /guide                 FACTOR_GUIDE.md rendered as a page (footnote anchors: /guide#F12)
  GET  /results/<file>        a chart or stats file from engine/results/
  GET  /api/settings          watcher_settings.toml + allowed ranges + help text
  POST /api/settings {settings}  validate against the safe ranges, then save (applies live)
  GET  /api/live              running simulations' latest live frames (?job=<name> for one)
  GET  /api/gpu?n=300         recent GPU temperature / load / memory / power samples (from gpu_temps.csv)
  GET  /api/replays           recorded runs;  GET /api/replay?job=<name>&start=0&n=200  frames for playback
  GET  /api/analysis/files     every analysable results file (engine, equilibrium, 2nd Experiment, connectome steps)
  GET  /api/analysis/key        the key: one plain-language line per experiment file + what each group label means
  GET  /api/analysis/info?file=<id>             groups, measures, time axis of one file
  POST /api/analysis/run {file, measure, ref, groups, ti, correction, paired, corr_group}  -> full statistics
       (see gui/analysis.py: describe, compare, omnibus, trend, correlations, write-up)
  GET  /api/analysis/csv?file=<id>&ti=<index>   tidy CSV download of every measure
  POST /api/queue_main {args} -> queues a Main Experiment run (watcher entry main_experiment); args are checked
                                 against the ranges in remote/experiments.toml before the job file is written
The schema also carries `choices` (every setting with a fixed list of allowed words -> a dropdown in the Builder)
and `main_experiment` (the Main Experiment's settings and their ranges).
"""
import html, json, re, sys, time, tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ENGINE = PY / "engine"; REMOTE = PY / "remote"; CATALOG = PY / "factors" / "catalog.toml"
sys.path.insert(0, str(HERE))      # gui/analysis.py
sys.path.insert(0, str(ENGINE))
import config as C          # noqa: E402  (engine registry; importing it is cheap, no GPU work)
sys.path.insert(0, str(REMOTE))
import simctl               # noqa: E402  (watcher settings + their safe ranges)
from make_form import RUN_DOCS, WORLD_DOCS, LEVEL, toml_val  # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def schema():
    cat = tomllib.loads(CATALOG.read_text())
    guide = (ENGINE / "FACTOR_GUIDE.md").read_text()
    tags = dict(re.findall(r"^#### \[(F\d+)\] (\w+)", guide, flags=re.M))
    tag_of = {v: k for k, v in tags.items()}
    facs = []
    for name, (_, default, auto) in C.REGISTRY.items():
        c = cat[name]
        facs.append(dict(name=name, category=c["category"], evidence=c["evidence"], level=LEVEL[c["evidence"]],
                         forms=c["forms"], notes=c.get("notes", ""), default=default, auto=auto,
                         tag=tag_of.get(name, "")))
    reg = tomllib.loads((REMOTE / "experiments.toml").read_text())
    main_args = (reg.get("main_experiment") or {}).get("args", {})
    return dict(choices=dict(field=C.FIELD_CHOICES, factor_mode=C.FACTOR_MODE_CHOICES, sources=C.SOURCE_CHOICES,
                             world=C.WORLD_CHOICES, world_ranges=C.WORLD_RANGES),
                main_experiment=main_args,
                factors=facs,
                run=[dict(key=k, default=v, doc=RUN_DOCS.get(k, ""), tag=f"R{i}") for i, (k, v) in enumerate(C.RUN_DEFAULTS.items(), 1)],
                world=[dict(key=k, default=v, doc=WORLD_DOCS.get(k, ""), tag=f"W{i}") for i, (k, v) in enumerate(C.WORLD_DEFAULTS.items(), 1)])


def to_toml(form):
    """form = {run: {...}, world: {...}, factors: {name: {mode, ...custom}}} -> TOML text (a filled-in form)."""
    sch = schema(); tag = {f["name"]: f["tag"] for f in sch["factors"]}
    rt = {r["key"]: r["tag"] for r in sch["run"]}; wt = {r["key"]: r["tag"] for r in sch["world"]}
    out = [f"# Experiment form written by the GUI on {time.strftime('%Y-%m-%d %H:%M')}. Footnotes [..] -> FACTOR_GUIDE.md", "", "[run]"]
    for k, v in (form.get("run") or {}).items():
        out.append(f"{k} = {toml_val(v)}".ljust(46) + f"# [{rt.get(k, '?')}]")
    if form.get("world"):
        out += ["", "[world]"]
        for k, v in form["world"].items():
            out.append(f"{k} = {toml_val(v)}".ljust(46) + f"# [{wt.get(k, '?')}]")
    for name, sec in (form.get("factors") or {}).items():
        if not sec or sec.get("mode", "off") == "off":
            continue
        out += ["", f"[factors.{name}]".ljust(46) + f"# [{tag.get(name, '?')}]"]
        for k, v in sec.items():
            out.append(f"{k} = {toml_val(v)}")
    return "\n".join(out) + "\n"


def check(form):
    text = to_toml(form)
    name = (form.get("run") or {}).get("name", "")
    errs = []
    if not NAME_RE.match(str(name)):
        errs.append("run.name must be 1-64 letters, digits, _ or - (it becomes a file name)")
    try:
        tmp = ENGINE / "configs" / "_gui_check.toml"; tmp.write_text(text); C.load(tmp); tmp.unlink()
    except Exception as e:
        errs.append(str(e))
    return dict(ok=not errs, errors=errs, toml=text)


def queue_main(args):
    """Queue a Main Experiment run. Only the settings listed in experiments.toml [main_experiment] are accepted, each
    inside its range; the watcher checks them again (whitelist + ranges + safety gate) before anything runs."""
    spec = tomllib.loads((REMOTE / "experiments.toml").read_text()).get("main_experiment")
    if not spec:
        return dict(ok=False, errors=["this watcher has no main_experiment entry"])
    errs, clean = [], {}
    for k, v in args.items():
        rule = spec["args"].get(k)
        if rule is None:
            errs.append(f"unknown setting {k}"); continue
        if rule["type"] == "int":
            try:
                v = int(v)
            except (TypeError, ValueError):
                errs.append(f"{k} must be a whole number"); continue
            if not rule.get("min", v) <= v <= rule.get("max", v):
                errs.append(f"{k}={v} outside {rule.get('min')}..{rule.get('max')}"); continue
        elif not NAME_RE.match(str(v)):
            errs.append(f"{k} must be letters or digits (time as HHMM, e.g. 1900, or none)"); continue
        clean[k] = v
    if errs:
        return dict(ok=False, errors=errs)
    tag = f"cross{clean.get('cross_pct', 0)}_g{clean.get('groups', 0)}_{clean.get('gens', 'd')}g"
    job = f"{time.strftime('%Y%m%d_%H%M%S')}_main_{tag}.json"
    (REMOTE / "queue" / job).write_text(json.dumps(dict(experiment="main_experiment", args=clean, by="gui")))
    return dict(ok=True, queued=job)


def status():
    st = json.loads((REMOTE / "status.json").read_text()) if (REMOTE / "status.json").exists() else {}
    queued = sorted(p.name for p in (REMOTE / "queue").glob("*.json"))
    done = []
    for d in ("done", "failed"):
        for p in (REMOTE / d).glob("*.json"):
            try:
                j = json.loads(p.read_text()); j["_file"] = p.name; j["_state"] = d; j["_mtime"] = p.stat().st_mtime; done.append(j)
            except Exception:
                pass
    done.sort(key=lambda j: -j["_mtime"])
    res = sorted((ENGINE / "results").glob("*.png"), key=lambda p: -p.stat().st_mtime) if (ENGINE / "results").exists() else []
    age = time.time() - (REMOTE / "status.json").stat().st_mtime if (REMOTE / "status.json").exists() else None
    return dict(watcher=st, watcher_seconds_since_update=age, queued=queued, recent=done[:10],
                results=[dict(png=p.name, stats=p.stem + "_stats.txt") for p in res[:10]])


SETTING_HELP = {
    ("display", "theme"): "GUI look: follow Windows, or force light / dark.",
    ("display", "refresh_seconds"): "How often the GUI refreshes status, charts and the live view.",
    ("jobs", "max_parallel"): "Light jobs allowed at the same time (heavy jobs always run alone).",
    ("jobs", "util_max"): "A light job only starts beside others while the GPU is below this % busy.",
    ("jobs", "max_wait_minutes"): "A job that can't start safely for this long fails with the reason.",
    ("safety", "start_temp_max"): "No job starts at or above this GPU temperature (C).",
    ("safety", "overheat_temp"): "A running job is stopped after `overheat_seconds` at or above this (C).",
    ("safety", "overheat_seconds"): "How long the GPU may stay at the overheat temperature.",
    ("safety", "hard_temp_stop"): "Everything stops immediately at or above this (C). Max 92.",
    ("safety", "vram_margin_mb"): "GPU memory always kept free for Windows / the desktop.",
    ("safety", "min_disk_gb_start"): "Free disk needed to start a job (GB).",
    ("safety", "min_disk_gb_run"): "Below this free disk, running jobs are stopped (GB).",
    ("safety", "min_ram_gb_start"): "Free system memory needed to start a job (GB).",
    ("safety", "min_ram_gb_run"): "Below this free memory, running jobs are stopped (GB).",
    ("speed", "quiet"): "0 = full speed .. 0.9 = GPU rests 90% of the time (quieter, slower). Applies live.",
    ("speed", "tick_delay_ms"): "Slow motion: pause after every tick, for watching the live view. 0 = off.",
    ("live", "enabled"): "Running simulations publish a live picture of one world.",
    ("live", "frame_every"): "Ticks between live frames (lower = smoother, slightly slower runs).",
    ("live", "world"): "Which world to show (0 = first world of the first arm).",
    ("live", "max_worms_drawn"): "Cap on worms per frame.",
    ("replay", "record"): "Save frames to remote/replays/<job>/ for playback.",
    ("replay", "record_every"): "Ticks between recorded frames.",
    ("replay", "max_frames"): "Stop recording a run after this many frames (disk safety).",
}


def get_settings():
    st = simctl.load_settings()
    try:
        raw = tomllib.loads((REMOTE / "watcher_settings.toml").read_text())
        for k, v in raw.items():
            st.setdefault(k, {}).update({kk: simctl.clamp_setting(k, kk, vv) for kk, vv in v.items()})
    except Exception:
        pass
    fields = []
    for (sec, key), rng in simctl.SETTING_RANGES.items():
        fields.append(dict(section=sec, key=key, value=st.get(sec, {}).get(key),
                           choices=rng if isinstance(rng, list) else None,
                           min=None if isinstance(rng, list) else rng[0], max=None if isinstance(rng, list) else rng[1],
                           help=SETTING_HELP.get((sec, key), "")))
    return dict(fields=fields)


def save_settings(new):
    errs, out = [], {}
    for (sec, key), rng in simctl.SETTING_RANGES.items():
        v = (new.get(sec) or {}).get(key)
        if v is None:
            continue
        if isinstance(rng, list):
            if v not in rng:
                errs.append(f"{sec}.{key} must be one of {rng}")
        else:
            try:
                v = type(rng[0])(v) if isinstance(rng[0], int) and float(v).is_integer() else float(v)
            except (TypeError, ValueError):
                errs.append(f"{sec}.{key} must be a number"); continue
            if not rng[0] <= v <= rng[1]:
                errs.append(f"{sec}.{key} = {v} is outside the safe range {rng[0]}..{rng[1]}")
        out.setdefault(sec, {})[key] = v
    if errs:
        return dict(ok=False, errors=errs)
    cur = get_settings()
    merged = {}
    for f in cur["fields"]:
        merged.setdefault(f["section"], {})[f["key"]] = out.get(f["section"], {}).get(f["key"], f["value"])
    lines = ["# Watcher + simulation settings. Written by the GUI " + time.strftime("%Y-%m-%d %H:%M") +
             ". Read live; explained in python/remote/README.md section 11.", ""]
    for sec, kv in merged.items():
        lines.append(f"[{sec}]")
        for k, v in kv.items():
            lines.append(f"{k} = {toml_val(v)}".ljust(32) + "# " + SETTING_HELP.get((sec, k), ""))
        lines.append("")
    (REMOTE / "watcher_settings.toml").write_text("\n".join(lines))
    return dict(ok=True)


def live(job=None):
    d = REMOTE / "live"
    files = sorted(d.glob("*.json"), key=lambda p: -p.stat().st_mtime) if d.exists() else []
    now = time.time()
    jobs = [dict(job=p.stem, age_s=round(now - p.stat().st_mtime)) for p in files if now - p.stat().st_mtime < 3600]
    frame = None
    target = (d / f"{job}.json") if job else (files[0] if files else None)
    if target is not None and target.exists():
        try:
            frame = json.loads(target.read_text())
        except Exception:
            frame = None
    return dict(jobs=jobs, frame=frame)


def gpu_history(n=300):
    f = REMOTE / "gpu_temps.csv"
    if not f.exists():
        return dict(rows=[])
    lines = f.read_text().splitlines()[-n:]
    rows = []
    for l in lines:
        p = l.split(",")
        if len(p) >= 6:
            rows.append(dict(time=p[0][11:19], jobs=p[1], temp=float(p[2]), util=float(p[3]), mem=float(p[4]),
                             power=None if p[5] in ("None", "") else float(p[5])))
    return dict(rows=rows)


def replays():
    d = REMOTE / "replays"
    out = []
    for p in sorted(d.glob("*/frames.jsonl"), key=lambda p: -p.stat().st_mtime) if d.exists() else []:
        with p.open() as fh:
            n = sum(1 for _ in fh)
        out.append(dict(job=p.parent.name, frames=n, mb=round(p.stat().st_size / 2 ** 20, 1)))
    return dict(replays=out)


def replay(job, start=0, n=200):
    if not NAME_RE.match(job or ""):
        return dict(frames=[])
    p = REMOTE / "replays" / job / "frames.jsonl"
    frames = []
    if p.exists():
        with p.open() as fh:
            for i, line in enumerate(fh):
                if i >= start + n:
                    break
                if i >= start:
                    frames.append(json.loads(line))
    return dict(frames=frames)


def md_to_html(md):
    """Tiny Markdown renderer for the guide (headings, bold, code, lists, links); anchors on [F12]-style tags."""
    out, code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            out.append("</pre>" if code else "<pre>"); code = not code; continue
        if code:
            out.append(html.escape(line)); continue
        esc = html.escape(line)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"`(.+?)`", r"<code>\1</code>", esc)
        esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" target="_blank">\1</a>', esc)
        m = re.match(r"^(#{1,4}) (.*)", esc)
        if m:
            n = len(m.group(1)); t = re.search(r"\[([RWF]\d+)\]", m.group(2))
            anchor = f' id="{t.group(1)}"' if t else ""
            out.append(f"<h{n}{anchor}>{m.group(2)}</h{n}>")
        elif esc.startswith("- "):
            out.append(f"<li>{esc[2:]}</li>")
        elif esc.strip():
            out.append(f"<p>{esc}</p>")
    return ("<!doctype html><meta charset=utf-8><title>Factor guide</title><style>body{font:15px/1.5 system-ui;"
            "max-width:900px;margin:24px auto;padding:0 16px;background:#fafafa;color:#222}pre{background:#eee;"
            "padding:10px;white-space:pre-wrap}h4{margin-top:32px;border-top:1px solid #ddd;padding-top:12px}"
            "h4:target,h3:target{background:#fff3c4}code{background:#eee;padding:0 3px}</style>" + "\n".join(out))


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        try:
            if p in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if p == "/api/schema":
                return self._send(200, schema())
            if p == "/api/status":
                return self._send(200, status())
            from urllib.parse import parse_qs, urlparse
            q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            if p == "/api/settings":
                return self._send(200, get_settings())
            if p == "/api/live":
                return self._send(200, live(q.get("job")))
            if p == "/api/gpu":
                return self._send(200, gpu_history(int(q.get("n", 300))))
            if p == "/api/replays":
                return self._send(200, replays())
            if p == "/api/replay":
                return self._send(200, replay(q.get("job"), int(q.get("start", 0)), min(int(q.get("n", 200)), 1000)))
            if p == "/api/analysis/files":
                import analysis as AN
                return self._send(200, AN.list_files())
            if p == "/api/analysis/key":
                import analysis as AN
                return self._send(200, AN.key())
            if p == "/api/analysis/info":
                import analysis as AN
                return self._send(200, AN.clean(AN.info(q.get("file", ""))))
            if p == "/api/analysis/csv":
                import analysis as AN
                body = AN.tidy_csv(q.get("file", ""), ti=int(q.get("ti", -1))).encode()
                self.send_response(200); self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{Path(q.get("file", "data")).stem}_tidy.csv"')
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                return
            if p == "/guide":
                return self._send(200, md_to_html((ENGINE / "FACTOR_GUIDE.md").read_text()), "text/html; charset=utf-8")
            if p.startswith("/results/"):
                f = (ENGINE / "results" / Path(p).name)
                if f.exists() and f.suffix in (".png", ".txt"):
                    return self._send(200, f.read_bytes(), "image/png" if f.suffix == ".png" else "text/plain; charset=utf-8")
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/settings":
                r = save_settings(data.get("settings") or {})
                return self._send(200 if r["ok"] else 400, r)
            if self.path == "/api/analysis/run":
                import analysis as AN
                try:
                    r = AN.analyse(data["file"], data["measure"], ref=data.get("ref"), groups=data.get("groups"),
                                   ti=int(data.get("ti", -1)), correction=data.get("correction", "holm"),
                                   paired=data.get("paired"), corr_group=data.get("corr_group"))
                    return self._send(200, AN.clean(dict(ok=True, **r)))
                except (ValueError, KeyError) as e:
                    return self._send(400, dict(ok=False, error=str(e)))
            if self.path == "/api/queue_main":
                r = queue_main(data.get("args") or {})
                return self._send(200 if r["ok"] else 400, r)
            form = data.get("form") or {}
            if self.path == "/api/check":
                return self._send(200, check(form))
            r = check(form)
            if not r["ok"]:
                return self._send(400, r)
            name = form["run"]["name"]
            (ENGINE / "configs" / f"{name}.toml").write_text(r["toml"])
            if self.path == "/api/save":
                return self._send(200, dict(ok=True, saved=f"engine/configs/{name}.toml"))
            if self.path == "/api/queue":
                exp = "form_quick" if data.get("quick") else "form"
                job = f"{time.strftime('%Y%m%d_%H%M%S')}_{name}{'_quick' if data.get('quick') else ''}.json"
                (REMOTE / "queue" / job).write_text(json.dumps(dict(experiment=exp, args=dict(form=name), by="gui")))
                return self._send(200, dict(ok=True, queued=job))
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    print(f"Experiment GUI on http://127.0.0.1:{port}  (Ctrl+C or close this window to stop)", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    main()
