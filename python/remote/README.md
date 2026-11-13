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

## 6b. Several experiments at once (added 2026-11-13)

Experiments marked `share = true` in `experiments.toml` are **light**: they use only part of the GPU (the small toy
brains mostly wait on Python, not on the GPU). Up to **3 light jobs run at the same time**, each starting whenever it is
picked up from the queue, as long as the GPU is **under 50 % busy and below 80 °C** (checked before each start).

| you want | job file |
|---|---|
| run alongside other light jobs (default for light experiments) | `{"experiment": "toybrain_gpu_fair", "args": {...}}` |
| use the whole GPU, nothing beside it | add `"exclusive": true` |
| force an experiment to share (or not) | add `"share": true` or `"share": false` |

- The queue is **first-in-first-out**: a whole-GPU job at the front waits until the running light jobs finish (and the
  jobs behind it wait too), so a big run is never starved.
- `status.json` now has a `jobs` list (every running job, its minutes, its log) besides the old single-job fields.
- `CANCEL` stops **all** running jobs. To stop just one, remove nothing and ask Claude (or end its python process).
- Limits are at the top of `watcher.py`: `MAX_PARALLEL = 3`, `UTIL_MAX = 50`, `TEMP_MAX = 80`.
- The new code takes effect when the watcher next restarts itself, which it does automatically the next time it is
  idle (no job running).

## 6c. Safety gate (added 2026-11-13): nothing runs if it could harm this computer

Every job passes these checks. The reason is always written to `failed/<job>.json` (`"error"`), `watcher_log.txt`,
and `status.json` (`"waiting"`).

**Refused immediately (the settings themselves are unsafe):**
| check | example message |
|---|---|
| the experiment's own preflight (engine forms: `run.py --preflight` estimates memory and checks every setting) | `needs ~38,880 MB of GPU memory (limit 7,500 MB): 600 worlds x 5000 slots x 80 patches is too big. Lower replicates, world.slots or world.patches.` |
| needs more GPU memory than the card has (minus 1,200 MB kept for Windows) | `needs ~30000 MB GPU memory but this GPU has 10240 MB (1200 MB kept free): it can never fit` |
| absurd run length (engine: > 20 million ticks) | `ticks = ... is over the 20,000,000 safety cap` |

**Waits (temporary), then fails after 1 hour with the reason:**
| check | limit |
|---|---|
| GPU temperature | starts only below 80 °C |
| free GPU memory | the job's need + 1,200 MB margin |
| free disk | ≥ 5 GB |
| free RAM | ≥ 2 GB |

**Stops running jobs:**
| check | action |
|---|---|
| GPU ≥ 90 °C | all jobs stopped immediately |
| GPU ≥ 87 °C for 3 minutes | that job stopped (`overheat`) |
| free disk < 1 GB, or free RAM < 0.5 GB | all jobs stopped before Windows starts struggling |

Each experiment declares its GPU memory need in `experiments.toml` (`vram_mb`) or a `preflight` command that
computes it from the settings. All limits are in the `SAFE` table at the top of `watcher.py` (soon also editable in
the GUI's Watcher page).

## 11. Settings, live view and replay (added 2026-11-13)

All watcher and simulation settings live in **`watcher_settings.toml`**. Edit it, or use the GUI's **Watcher** page
(start `python\gui\start_gui.bat`, click *Watcher*). Changes apply **live** within a few seconds; no restart.
Every value has a **safe range** (`SETTING_RANGES` in `simctl.py`): the GUI refuses values outside it and the watcher
clamps to it, so no setting can make a run dangerous for the computer.

| section | setting | meaning (range) |
|---|---|---|
| display | `theme` | GUI look: system / light / dark |
| display | `refresh_seconds` | GUI refresh interval (1-60) |
| jobs | `max_parallel` | light jobs at once (1-4) |
| jobs | `util_max` | a light job starts beside others only below this % GPU busy (10-90) |
| jobs | `max_wait_minutes` | a job that can't start safely this long fails (1-1440) |
| safety | `start_temp_max`, `overheat_temp` + `overheat_seconds`, `hard_temp_stop` | temperature gates, see 6c (max 83 / 88 / 92 C) |
| safety | `vram_margin_mb`, `min_disk_gb_*`, `min_ram_gb_*` | memory / disk margins, see 6c |
| speed | `quiet` | 0 = full speed .. 0.9 = GPU rests 90 % of the time (quieter fans) |
| speed | `tick_delay_ms` | slow motion for watching (0-1000 ms per tick) |
| live | `enabled`, `frame_every`, `world`, `max_worms_drawn` | live picture of one world of each running simulation |
| replay | `record`, `record_every`, `max_frames` | save frames for playback (capped for disk safety) |

**How the simulations use it:** `simctl.py` (`SimControl.after_tick`) is called once per tick by the engine
(`engine/run.py`) and the equilibrium world (`equilibrium/eqworld.py`). It re-reads the settings every 2 s, applies
quiet mode and slow motion, writes the live frame to `live/<job>.json` and appends replay frames to
`replays/<job>/frames.jsonl`. (The toy brain and the old ecosim don't publish frames; the old ecosim keeps its own
`gpu_throttle.txt` quiet mode.)

**Watcher page in the GUI:** live view (pick a running job; worms orange, dauer grey, food green, predators /
competitors red triangles, traps purple), GPU chart (temperature and % busy, with the safety limits as dashed lines),
running jobs (including light jobs running side by side and any safety wait), replay player (pick a recorded run;
play / pause, 1-30x speed, scrub slider), and the settings form with help text and ranges.

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
