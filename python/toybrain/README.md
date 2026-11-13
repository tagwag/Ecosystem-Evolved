# Toy brain experiment — handbook

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
