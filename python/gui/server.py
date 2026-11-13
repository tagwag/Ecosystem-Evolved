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
"""
import html, json, re, sys, time, tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ENGINE = PY / "engine"; REMOTE = PY / "remote"; CATALOG = PY / "factors" / "catalog.toml"
sys.path.insert(0, str(ENGINE))
import config as C          # noqa: E402  (engine registry; importing it is cheap, no GPU work)
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
    return dict(factors=facs,
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
