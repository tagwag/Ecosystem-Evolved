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

## Builder page: fill in a form step by step (added 2026-11-13)
The **Builder** tab (first tab) asks one question at a time and only offers values the engine understands.
Nothing is typed except numbers and the run's name.

| Step | What you choose | How |
|---|---|---|
| 1. Goal | Effect of one factor / Compare levels of one setting / Combine several factors / Change the world itself / Main Experiment run | cards |
| 2. Factor(s) | which factor(s); tick the box to also see contested and untested ones | dropdown per factor, grouped by category, with its research notes and a footnote link |
| 3. Settings | Autopilot or Custom. In Custom: every word setting (field shape, field timing, predator type, food layout...) is a dropdown; every number has a slider + a box; radiation and toxin sources are picked from their list | dropdowns, sliders |
| (compare) | which number to compare and 2-4 values, e.g. `1, 2, 4` -> one run per value, same seed | dropdown + box |
| 4. Run size | Quick check (seconds) / Small 16 worlds / Standard 30 worlds 50k ticks (recommended) / Long 200k ticks; which arms; the name | dropdowns |
| 5. Review and run | the exact form file(s) it will write, already checked like run.py would check them; Save or Run | buttons |

The **Main Experiment** goal asks for generations, interbreeding % (none / 10 / 25 / 50), who may interbreed (one pool,
or 10 / 5 / 3 independent groups), and a stop time (none, or 16:00-23:00). It queues the watcher's `main_experiment`
entry through `POST /api/queue_main`; the server checks every value against the ranges in remote/experiments.toml
first, and the watcher checks again.

Where the dropdown lists come from: `engine/config.py` (`FIELD_CHOICES`, `FACTOR_MODE_CHOICES`, `SOURCE_CHOICES`,
`WORLD_CHOICES`, `WORLD_RANGES`), sent to the page in `/api/schema` -> `choices`. The same lists are enforced when any
form is loaded, so a typo in a hand-written form now fails with the list of allowed words instead of being ignored.

**`factor_mode`.** In a form, `mode` always means off / auto / custom. A factor's own mode (predators: chaser /
pristionchus; food_layout: fixed / moving / seasonal / uniform; pathogen_bacteria: fixed / coevolving; mating_system:
androdioecy / selfing; variability: regular / irregular) is written `factor_mode = "..."`. Before 2026-11-13 the two
clashed and a factor's own mode could not be changed from a form at all; both GUI pages now write `factor_mode`.

**Fixed the same day:** the pages (Builder / Experiments / Watcher) were all drawn at once, one under the other,
because the page CSS (`display:grid`) beat the `hidden` attribute. One CSS line fixes it: `[hidden]{display:none!important}`.

After updating these files, close the GUI window and start `start_gui.bat` again so the server loads the new code.

## Analysis page: study-grade statistics for any result (added 2026-11-13)
Tab **Analysis**. Pick a results file; every table and chart updates when you change a choice. Code: `gui/analysis.py`
(statistics, numpy + scipy only, no GPU) and the "Analysis page" block in `index.html` (drawing only).

**Files it can read** (one dropdown, grouped by source): factor-engine runs (`engine/results`), equilibrium runs
(`equilibrium/results`), the 2nd Experiment (`toybrain/results_*.json`), and connectome steps (`results/`, incl. the
Main Experiment's `step20_stats.json`). Older step files go through a generic reader that picks up any
`{group: {measure: [numbers]}}`; its note says to check that those numbers really are replicates.

**Controls**
| control | meaning |
|---|---|
| Measure | what to compare; "(over time)" = it has a time course |
| Time point | compare the groups at any moment of the run (default: the end). Only for measures recorded over time. |
| Reference group | every other group is compared with it (e.g. `shadow` = chance, so real - shadow = adaptation) |
| Groups to include | untick groups to leave them out of the tests and the multiple-comparison correction |
| Pairing | automatic = paired when replicate i is the same seed/world in every group (engine, equilibrium, Main Experiment), independent otherwise (2nd Experiment lineages). Paired tests are much more sensitive but only valid with shared seeds. |
| Correction | Holm (default: protects against false positives when several groups are tested), Benjamini-Hochberg (false discovery rate, for screens of many factors), none (only for one comparison planned in advance) |
| Download data (CSV) | tidy table (file, group, replicate, measure, time, value) for Excel / R / Python |

**What it shows, top to bottom**
1. Summary: plain-language verdicts after correction + omnibus tests (ANOVA, Kruskal-Wallis, Levene for equal spread, Welch-type ANOVA when spreads differ).
2. Descriptive statistics: n, mean, SD, 95 % CI (t and bootstrap), median [IQR], range, Shapiro-Wilk normality.
3. Distribution plot: box (middle 50 %), median line, every replicate as a dot, mean as a diamond.
4. Forest plot of effect sizes vs the reference with 95 % CIs (Hedges g, or Cohen dz when paired).
5. Comparison table: difference [95 % bootstrap CI], effect [CI], main test (sign-flip permutation when paired;
   Welch t, or Mann-Whitney U when data aren't normal and n < 30, when independent), raw and adjusted p, the other
   tests for cross-checking, achieved power, and the n needed for 80 % power.
6. Time course: mean with 95 % CI band per group, and a dashed line at the compared time point.
7. Trend at the end: slope over the last third of each replicate (per 100 generations or per 10,000 ticks), its CI and
   sign-flip p -> "still rising" / "plateau" / "falling". This is the plateau test used throughout the project.
8. Correlation heatmap (Spearman, BH-adjusted) of all measures inside one group: which measures move together.
9. Methods + Results paragraph with every number, ready to paste into a report (Copy button).

How to read the key numbers: p < 0.05 after correction = a difference this big would appear by chance less than 1 in 20
times. Effect size 0.2 / 0.5 / 0.8 = small / medium / large. A "no detectable difference" with power below 80 % is not
evidence of no effect - it means too few replicates; the table says how many would be needed.
Restart the GUI (close its window, run start_gui.bat) to load this page.

### The key at the bottom of the Analysis page (added 2026-11-13)
A card "Key: every experiment on this page" sits under the results. It lists every results file in the dropdown,
grouped by platform, with one sentence saying what that experiment is, and a second table explaining every group
label (frozen / shadow / real, the brain types, the Main Experiment arms s20_old / rev / mus / both). Clicking a file
name opens it. Where the text comes from (gui/analysis.py): `describe_file()` builds the sentence from the file name
(and, for engine runs, from the first line of its `_stats.txt`); `STEP_KEY` holds the one-liners for the connectome
steps; `ARM_KEY` holds the group labels. New experiment or new arm name -> add a line to STEP_KEY / ARM_KEY.
Served by `GET /api/analysis/key`.
