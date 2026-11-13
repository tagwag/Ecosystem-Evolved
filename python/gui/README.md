# Experiment GUI ("Worm Experiment Lab") — handbook

**What it is:** a page in your web browser for filling in experiment forms, checking them and starting runs on the
3080, with three levels of detail. It runs on the workstation; nothing goes to the internet.

**Who should read this:** anyone starting experiments without editing files by hand, and anyone changing the GUI.

---

## 1. Start it
Double-click `start_gui.bat` in this folder. Your browser opens **http://127.0.0.1:8765**. Keep the black window open
(minimize it); closing it stops the GUI (runs already queued keep going; the watcher does the running).

The **remote watcher must be running** for runs to start (it starts by itself at login; the right-hand panel says
"NOT RUNNING" if it isn't; then double-click `python\remote\start_watcher.bat`).

## 2. The three modes
| mode | shows | use it when |
|---|---|---|
| **Easy** | run name, replicates, length; ONE factor picker | isolating a single factor; everything else stays off |
| **Advanced** | all well-supported factors (evidence EVO / EFFECT), any number at once | combining factors (e.g. pathogen + microbiome) |
| **Researcher** | everything: contested and untested factors (magnetic field, radio waves), world physics (food, costs, splitting), arms, seed, founders | full control; changing world physics changes the baseline itself (a warning is shown) |

For every factor: **off** (not in the world), **auto** (realistic autopilot from the research), **custom** (the
settings appear; change any of them).

## 3. Footnotes
Every setting has a green tag like `[F14]`. Click it: the factor guide opens at the explanation of that setting
(what it is, how the engine models it, the autopilot values, the evidence level and the sources). The guide is
`python/engine/FACTOR_GUIDE.md`, rendered at http://127.0.0.1:8765/guide.

## 4. Buttons
| button | does |
|---|---|
| Check form | checks the form exactly like the engine will (unknown or impossible settings are reported) and shows the file it would write |
| Save form | writes `python/engine/configs/<name>.toml` |
| Quick check | saves, then queues a seconds-long test (1 world, 3,000 ticks) to see that it runs |
| Run on the 3080 | saves, then queues the full run (job file in `python/remote/queue/`) |

The right-hand panel refreshes every 5 s: watcher state, current job, GPU temperature and load, waiting jobs, recent
jobs (✓ done / ✗ failed with reason), and the latest result charts (click "stats" for the numbers).

## 5. Phone access (optional, later)
`server.py --lan` makes the GUI reachable from other devices on the same network (or over Tailscale). **Anyone on that
network could then queue runs**, so only do this on a trusted network. Until then, start runs from the phone by
asking Claude in chat.

## 6. Files and how it works
| file | what |
|---|---|
| `server.py` | small web server (Python standard library only). Reads the factor catalog + engine registry to build the form, checks forms with the engine's own loader, writes form files and job files |
| `index.html` | the page (plain HTML + JavaScript, no internet libraries) |
| `start_gui.bat` | starts the server and opens the browser |

Because the page is generated from `python/factors/catalog.toml` and `python/engine/config.py`, adding a factor to the
engine makes it appear in the GUI automatically (after restarting the GUI). Which mode shows a factor is decided by
its evidence tag (`LEVEL` in `engine/make_form.py`).

## 7. Troubleshooting
| symptom | fix |
|---|---|
| page doesn't open | is the black window open? Try http://127.0.0.1:8765 by hand. Port in use? `server.py --port 8766` |
| "GUI server not reachable" in the panel | the black window was closed; start it again |
| "Watcher: NOT RUNNING" | double-click `python\remote\start_watcher.bat` |
| a job shows ✗ | the reason is next to it; full output in `python/remote/logs/<job>.txt` |
