# Remote experiment watcher — handbook

**What it is:** a small program that runs in the background on the workstation (the RTX 3080 desktop) and starts
experiments when a *job file* appears in a folder. Instead of someone sitting at the PC double-clicking `.bat` files,
anyone who can put a file in `python/remote/queue/` can start a run: Claude (through the desktop-app link), or the
owner from a phone by asking Claude in chat.

**Who should read this:** anyone who will start, stop, add or debug experiments on the workstation.

---

## 1. The 30-second version

1. The watcher is already running (it starts by itself at every Windows login; its window is minimized and titled
   **"Ecosystem remote watcher"**).
2. To start an experiment, create a file in `python/remote/queue/` ending in `.json`, for example `toy.json`:
   ```json
   {"experiment": "toybrain_gpu", "args": {"seeds": 30, "gens": 300}}
   ```
3. Within ~5 seconds the watcher picks it up, runs it, and writes its output to `python/remote/logs/toy.txt`.
4. When it finishes, the job file moves to `done/` (success) or `failed/` (with the reason inside).
5. At any moment, `python/remote/status.json` says what is happening right now (running/idle, which job,
   minutes so far, GPU temperature, etc.).

---

## 2. Folder map

```
python/remote/
├── README.md            ← this handbook
├── watcher.py           ← the watcher program itself
├── experiments.toml     ← the WHITELIST: the only experiments that can be started remotely
├── start_watcher.bat    ← starts the watcher by hand (double-click)
├── install_autostart.bat← makes the watcher start at every login (run once; already done)
├── queue/               ← put job files here (.json). Also CANCEL and PAUSE control files.
├── running/             ← the job currently running (at most one)
├── done/                ← finished jobs, with a "result" section added
├── failed/              ← rejected / crashed / cancelled jobs, with an "error" explaining why
├── logs/                ← one text log per job: everything the experiment printed
├── status.json          ← live status (rewritten every few seconds)
├── watcher_log.txt      ← the watcher's own diary: starts, finishes, rejections, restarts
└── gpu_temps.csv        ← GPU temperature/load/power every 30 s while a job runs
```
Runtime files (`status.json`, logs, queue contents, …) are ignored by git; only the program and docs are committed.

---

## 3. Job files

A job file is plain JSON (a tiny structured text format). Required: `experiment`. Optional: `args`. Any other fields
(like `"by"` or `"why"`) are allowed and simply kept as notes.

```json
{
  "experiment": "toybrain_gpu_fair",
  "args": {"seeds": 30, "gens": 300},
  "by": "claude",
  "why": "fair re-test of bigger brains"
}
```

- **The file name becomes the job's name** (`toybrain_fair_300g.json` → job `toybrain_fair_300g`, log
  `logs/toybrain_fair_300g.txt`). Use a name that says what it is; don't reuse a name that is already in `done/`
  unless you are happy to overwrite its record.
- **Order:** oldest file first (by the time it was written). Jobs run **one at a time**.
- **Args you leave out** use the default listed in `experiments.toml`.
- **Args are checked** before anything runs: numbers must be whole numbers inside the allowed range; names may only
  contain letters, digits, `_` and `-`. A bad job is never run; it goes to `failed/` with the reason, e.g.
  `"gens=99999 outside 1..5000"`.

---

## 4. The whitelist: `experiments.toml`

Only experiments listed here can be started. This is the safety rule: a job file can choose an experiment and its
settings, but it **cannot run arbitrary commands**. Example entry:

```toml
[toybrain_gpu]
about = "Toy brain experiment on the 3080 ..."     # one line for humans
cwd = "toybrain"                                    # folder to run in, relative to python/
cmd = ["{py}", "-u", "sim_gpu.py", "{seeds}", "{gens}", "all"]
gpu = true                                          # wait for a free GPU before starting
args.seeds = { type = "int", min = 1, max = 500, default = 30 }
args.gens  = { type = "int", min = 1, max = 5000, default = 300 }
```

- `{py}` becomes the project's Python (`python/.venv/Scripts/python.exe`, the one with PyTorch + CUDA).
- `{seeds}`, `{gens}`, … are filled in from the job's `args` after checking.
- `type = "int"` needs `min`, `max`, `default`. `type = "name"` needs `default` (letters/digits/`_`/`-` only).

**Adding a new experiment:** add a new `[section]` like the one above and save. The watcher re-reads this file before
every job, so **no restart is needed**. Then write a job file for it.

### Current experiments
| name | what it does | GPU |
|---|---|---|
| `toybrain_gpu` | toy brain lesion/upgrade experiment, 5 brain types, original (unfair) mutation | yes |
| `toybrain_gpu_fair` | same, but mutation size scaled by genome size and starting weights by brain size | yes |
| `toybrain_cpu` | toy brain, original numpy code, parallel on CPU cores | no |
| `sweep` | config-file factor sweep (`python/sweeps/<config>.toml`), evolve all arms | yes |
| `gpu_check` | prints the PyTorch version and GPU name (a few seconds) | no |

---

## 5. Controlling a run

| You want to… | Do this |
|---|---|
| see what's happening | open `status.json` (or ask Claude "what's the watcher doing?") |
| watch progress | open `logs/<job>.txt`; it grows while the job runs |
| stop the current job | create an empty file named `CANCEL` in `queue/` (no extension). The job stops within ~5 s and is marked `failed` with `"error": "cancelled"`; the `CANCEL` file is removed automatically. |
| stop new jobs from starting (but let the current one finish) | create an empty file named `PAUSE` in `queue/`. Delete it to resume. |
| remove a waiting job | delete its file from `queue/` |
| stop everything | close the watcher window. The running job is stopped and marked `failed` ("watcher stopped"). |

**Interrupting is always safe** in the sense that nothing gets corrupted: experiments save their results only at the
end (or per finished part, e.g. per brain type). A stopped run simply produces no (or partial) results. Re-running a
`toybrain_gpu*` job skips brain types that already finished.

---

## 6. GPU care

- **One GPU job at a time.** Before a GPU job starts, the watcher asks `nvidia-smi` (NVIDIA's monitoring tool) which
  programs are using the GPU. If any **Python** program is (e.g. an experiment started by hand), it waits and
  re-checks every 30 s; `status.json` then says `"waiting for GPU"`. Ordinary desktop apps that draw on the GPU
  (browsers, games' launchers, Windows itself) are ignored, because Windows lists them all.
- **Temperature guard.** While a job runs, GPU temperature, load, memory and power are logged to `gpu_temps.csv`
  every 30 s. If the GPU stays at **87 °C or above for 3 minutes**, the job is stopped and marked
  `"overheat"`. (The RTX 3080's own slowdown point is in the low 90s °C; 87 leaves a margin.) Change `HOT_C` /
  `HOT_SECONDS` at the top of `watcher.py` to adjust.
- **Quiet mode** is separate: `python/gpu_throttle.txt` (0 = full speed … 0.9 = mostly resting) only affects the
  main ecosim (`batch3_fast`). The power cap (`quiet_gpu.bat` / `normal_gpu.bat`, run as administrator) affects
  everything until the next reboot.

---

## 7. How Claude uses it

Claude reaches the workstation's files through the Claude desktop app link (the "device" tools). Claude cannot
double-click things reliably, but it can write files, so:

1. **Start:** write `python/remote/queue/<name>.json`.
2. **Check:** read `status.json`, `logs/<name>.txt`, `watcher_log.txt`.
3. **Results:** read the experiment's own output files (e.g. `python/toybrain/results_*.json`).

From a phone: open the same chat and ask Claude to start something; Claude writes the job file. This works whenever
the workstation is on, logged in, and the Claude desktop app is running.

---

## 8. Starting and auto-start

- **Auto-start:** `install_autostart.bat` put a shortcut named *Ecosystem watcher* in the Windows Startup folder, so
  the watcher starts minimized at every login. To undo: press Win+R, type `shell:startup`, delete the shortcut.
- **By hand:** double-click `start_watcher.bat`. Don't run two watchers at once (they would both grab jobs). If you
  are not sure whether one is running, check `status.json`'s `"updated"` time: if it is within the last few
  seconds, a watcher is running.
- **Self-update:** when `watcher.py` is edited, the watcher notices (while idle), opens a fresh copy of itself in a
  new window, and the old window closes its program (press a key to close that old window). Edits to
  `experiments.toml` need no restart at all.

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Job stays in `queue/` | Watcher not running (old `status.json` time) → double-click `start_watcher.bat`. Or a `PAUSE` file exists. |
| `status.json` says `waiting for GPU` forever | Another Python program is using the GPU. Its process ids are in `other_gpu_pids`; finish or close it. |
| Job in `failed/` with `unknown experiment` | Typo in `"experiment"`, or it isn't in `experiments.toml`. |
| Job in `failed/` with `outside` / `must be letters` | An argument broke the rules in `experiments.toml`. |
| Job in `failed/` with `exit_code` not 0 | The experiment itself crashed: read the end of `logs/<job>.txt` for the Python error. |
| Job `failed` with `overheat` | GPU stayed ≥ 87 °C for 3 min. Check fans/dust/room temperature; see `gpu_temps.csv`. |
| `WATCHER CRASHED` in `watcher_log.txt` | Bug in the watcher; the full error is printed there. Often a broken `experiments.toml` (check the syntax). |

---

## 10. Design decisions (why it works this way)

- **Files, not a web server:** no network ports, no passwords, nothing exposed to the internet. Anything that can write
  into this folder can start jobs, and that is already limited to the owner's PC and Claude's link to it.
- **Whitelist, not commands:** a job can only pick a listed experiment and numbers/names within limits, so a mistaken
  or malicious job file can't delete files or run programs.
- **One at a time:** two GPU experiments at once both run slower and make timing comparisons meaningless.
- **Everything logged:** every start, stop, rejection and temperature reading is written down, so a person (or a
  future Claude session) can reconstruct what happened without having watched it.
