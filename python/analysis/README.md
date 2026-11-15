# analysis/ - cross-experiment analyses (no GPU, saved results only)

## predict_outcomes.py: can a run's outcome be predicted from its early generations? (2026-11-14)
Question (owner's secondary goal): can evolution in these closed worlds be measured and forecast?

**Data.** Every run with a per-generation history: connectome Steps 19-22 (`runs/stepNN/<arm>_s<seed>/history.json`,
gathered into `results/_histories_all.json`) and the toy-brain 900- and 3,200-generation runs (their `curves`).
544 runs, 5 experiment families. Target = a run's level at generation 190 (mean of generations 170-189); 190 is the
longest horizon every run reached.

**Predictors** (each sees only the first k generations, k = 10, 20, 50, 100):
| name | idea |
|---|---|
| persistence | it stays where it is now (mean of the last 10 generations seen) |
| family gain | persistence x the average further gain seen in OTHER experiment families |
| ridge | linear model on level, slope, start level, best so far, wobble; trained on other families |
| curve fit | saturating curve a - b*exp(-g/tau) fitted to the run's own first k generations |
**Honest test.** Leave one experiment family out: a model never sees the experiment it predicts.

**Result (results/predict_outcomes.json).**
| generations seen | typical error of a run's final level | which ARM ends higher (rank agreement) | which SEED ends higher inside an arm |
|---|---|---|---|
| 10 | 29-43 % | 0.82 | 0.24 |
| 20 | 22-25 % | 0.82-0.95 | 0.22 |
| 50 | 11-14 % | 0.95-1.00 | 0.39 |
| 100 | 7-8 % | 1.00 | 0.56-0.58 |
- Conditions (arms) are predictable early: a 50-generation pilot ranks the arms as the full run will.
- Individual seeds are not: a finished run wobbles ~11 % generation to generation, seeds of one arm differ by only
  ~10 %, so most seed-to-seed difference is noise and luck.
- No model clearly beats persistence. There is no hidden regularity in these curves for a cleverer algorithm to find.
- Practical algorithm: (1) pilot every arm for 50 generations and rank by current level; (2) run long only to measure
  effect sizes; (3) never read anything into which single seed is ahead.
Limits: training scores (not the unseen-world yardstick), horizon 190 generations, five families.

**Re-run:** rebuild `results/_histories_all.json` (the snippet is in PROJECT_NOTES / the 2026-11-14 session: loops
over runs/step19..22 and stores the `fitness` list of every history.json), then from `python/`:
`python analysis/predict_outcomes.py`. Needs numpy + scipy; seconds on a CPU.
