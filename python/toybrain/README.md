# 2nd Experiment (folder: toybrain) — small evolvable worm brains on the GPU
(Called "Main Experiment" on 13 Nov 2026 15:10-15:50; since then "Main Experiment" = the connectome brain, ecosim/step20.py.)

**Question:** in a simple simulated worm, what happens to foraging if you (a) remove long-range smell, (b) add more
"thinking" neurons, (c) add neurons that are born during life and learn? It is a *toy model*: worms have no frontal
lobe or hippocampus; these are rough analogues, chosen in the 2026-11-12 neurogenesis chat.

| brain type | smell (AWA/AWC-like, long range) | hidden neurons | "hippo" (born during life, Hebbian learning) |
|---|---|---|---|
| `normal` | yes | 8 | — |
| `no_smell` | no (taste only, short range) | 8 | — |
| `no_smell+frontal` | no | 24 | — |
| `no_smell+frontal+hippo` | no | 24 (8 of them born during life) | yes |
| `normal+frontal+hippo` | yes | 24 (8 born during life) | yes |

Baseline: `random_walk` (a brain with all-zero weights).

## How one run works
1. **World:** a 100×100 arena with 5 food patches that regrow (the "sparse" test arena has 2). A worm moves at a
   speed it controls and steers; it eats when within 4 units of a patch.
2. **Senses (5 inputs):** smell level, smell change, taste level, taste change, "eating right now".
3. **Brain:** a small recurrent neural network (hidden neurons feed back into themselves) with 2 outputs: turn and speed.
4. **Evolution (per lineage):** 48 brains; each scored on 3 random arenas (500 steps); top 8 survive unchanged;
   40 children = copies of survivors with random noise added to every gene (connection strength). Repeat for N
   generations.
5. **Fair test:** the best brain of each lineage is tested on 30 *new* arenas (normal and sparse). That is the number
   reported.

## Files
| file | what |
|---|---|
| `sim.py` | the original numpy (CPU) version — the reference implementation |
| `run_cpu.py` | runs `sim.py`'s jobs in parallel on CPU cores (identical numbers to `sim.py`) |
| `sim_gpu.py` | PyTorch port: all lineages of a brain type run at once on the GPU. Statistically equal to `sim.py`, not number-for-number (different random streams). `--fair` switches on the fairness fix. |
| `analyze.py` | means, 95% confidence intervals, planned comparisons (Welch t-test, Holm-corrected), plateau check, chart |
| `run_cpu.bat`, `run_gpu.bat`, `run_both.bat` | double-click launchers (or use the remote watcher: `toybrain_cpu`, `toybrain_gpu`, `toybrain_gpu_fair`) |
| `results_*.json` | raw results: per lineage test scores, evolution curves, best genomes |
| `results_*.png`, `*_stats.txt` | chart + statistics from `analyze.py` |

## Running
- Remote (preferred): job file `{"experiment": "toybrain_gpu_fair", "args": {"seeds": 30, "gens": 300}}` in `python/remote/queue/`.
- By hand: `..\.venv\Scripts\python.exe sim_gpu.py 30 300 all --fair` then `python analyze.py results_gpu_300g_30s_fair.json`.
- Safe to interrupt: finished brain types are saved after each one; a rerun skips them.
- Time on the 3080: ~3-4 min per brain type for 30 lineages × 300 generations. Extra lineages cost almost nothing
  (the GPU is waiting on Python, not doing math — "kernel launch overhead").

## The fairness fix (`--fair`), and why
The first 300-generation run (2026-11-13) found bigger brains worse. Two built-in handicaps explained much of it:
1. **Mutation:** every gene got noise of the same size (0.1). A 24-neuron brain has ~10× more genes (1,347 vs 130),
   so each child was disrupted ~3× more in total. Fix: per-gene noise = 0.1 × √(130 / genes), so the *total* change per
   child is equal for every brain.
2. **Starting weights:** recurrent connections started with the same strength (0.5) regardless of how many there
   were, so a 24-neuron brain started ~1.7× "louder" and its neurons sat at their limits. Fix: recurrent (and plastic)
   starting strength = 0.5 × √(8 / hidden neurons).
The original behaviour stays the default so old results can be reproduced.

## Results so far
See `PROJECT_NOTES.txt` (section 2026-11-11..13) and the `*_stats.txt` files.

## Continuing a run, mutation counts, and "best" (added 2026-11-13)
- **Continue:** `sim_gpu.py 30 600 all --fair --resume results_gpu_300g_30s_fair.json` (watcher: `toybrain_continue`).
  Each lineage restarts from its saved champion + 47 mutants of it (only champions were saved, not whole
  populations) and evolves N more generations. Output: `results_gpu_600g_30s_fair_cont600_from_300g_30s_fair.json`;
  `previous_normal` holds each lineage's score before continuing.
- **Mutation tracking:** every individual carries (1) its gen-0 ancestor, (2) the number of mutation events on its
  line of descent (one per birth; elites copied unchanged add none), (3) the total size of those mutations. Saved per
  lineage as `mutations`, `mutation_size`. In a continuation they count from the continuation start (the first 300
  generations weren't tracked).
- **"Best" = combined score** (owner's choice): `repro_share x fair-test score`, where repro_share = fraction of the
  final population descended from the winner's gen-0 ancestor (how completely its line took over) and fair-test score
  = food on 30 fresh unseen arenas. Tie-break: slope of the training curve over the last 100 generations
  (`slope_last100`, food per 100 generations: is it still rising?). Function `combined_score()` in `sim_gpu.py`.

## Checkpoints, resume and branching (added 2026-11-13)
- Every 50 generations the **whole population** of every lineage (genomes, ancestors, mutation counters, the training
  curve, the random generator) is saved to `checkpoints/<run>_<brain type>_g<gen>.pt`.
- An interrupted run **resumes** from its latest checkpoint automatically (run the same command again).
- **Branch / replay:** `sim_gpu.py 30 600 all --fair --from-gen 300 --as replayA --seed 9` starts a new run from
  generation 300 of the same run (same settings), with new luck if `--seed` is given. Output gets `_replayA` added.
- Runs started before this feature (the first fair run, and the continuation that was running when it was added)
  have no checkpoints.

## Interbreeding between lineages (added 2026-11-13)
Why: in the toy brain every population ends up descended from one ancestor within a few hundred generations
(reproductive share = 1.00 everywhere), so variety collapses and progress plateaus (300 -> 900 generations added
only 0-3 food). Interbreeding brings in genes from other successful lineages every generation.

- `sim_gpu.py 30 900 all --fair --cross-pct 25 --groups 10` (watcher: `toybrain_interbreed`): 25 % of each lineage's
  non-elite children are crosses (each gene 50/50 from the own elite parent or a random elite of another lineage in the
  same group), then mutated. 30 lineages in 10 groups of 3: groups never mix, so there are 10 independent replicates.
  **Analyse group means, not lineages** (lineages in a group share genes).
- Extra cost: one gene-mixing step per generation, negligible on the GPU.
- New measure for every run: `variety` = mean gene variance inside each lineage's final population (higher = more
  variety kept).
- Pre-registered test (2026-11-13): interbreeding helps if the 10 group means of the fair-test score beat the fresh
  900-generation run's lineages grouped the same way (10 groups of 3), Welch t-test p < 0.05.

## 2nd Experiment: the 7pm stop and the three-way interbreeding comparison (added 2026-11-13)
**Name.** From 2026-11-13 15:50 the toy brain is called the **2nd Experiment** (briefly "Main Experiment" before that) in the GUI, the watcher and the docs. The
folder stays `toybrain/` on purpose: old results, checkpoints and the factor engine's founder files point at it.

**`--until HHMM`** (or `HH:MM`): at that clock time the run saves a checkpoint of the lineage it is working on and exits
cleanly with `STOPPED_AT_DEADLINE` in the log. Nothing is lost: queue the exact same job again and it RESUMES from that
checkpoint (finished brain types are skipped). A time already past today means tomorrow. `none` = no limit.

**Watcher entry `main_experiment`** (remote/experiments.toml): args `gens` (default 2500), `cross_pct` (0 = no
interbreeding), `groups` (1 = one shared pool, 10 = ten independent groups of 3), `until` (HHMM or none).

**The 2026-11-13 comparison** (all 2,500 generations, same seeds, 5 brain types, stop at 19:00):
| Job | cross_pct | groups | What it tests |
|---|---|---|---|
| m1_main_reference | 0 | - | the shared reference: no interbreeding |
| m2_main_cross_pool | 25 | 1 | any lineage may cross with any other (most variety; only 1 independent replicate) |
| m3_main_cross_10groups | 25 | 10 | crosses only inside groups of 3 (10 independent replicates) |
Output files: `results_gpu_2500g_30s_fair.json`, `..._cross0.25_g1.json`, `..._cross0.25_g10.json`.
Pre-registered rule: interbreeding helps if m3's 10 group means beat m1's lineages grouped the same way (Welch p < 0.05).
m2 is judged by level and kept variety only (its lineages share genes, so they are not independent).
If a run was stopped by the deadline, compare all three at the same generation (curves are saved per generation).
