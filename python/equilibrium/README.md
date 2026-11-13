# Equilibrium world — handbook

**What it is:** the project's *zero point*. A stable, food-limited world where worms live, split in two and die on
their own, with no generations and no scoring function. Every later experiment (adding a factor from
`python/factors/catalog.toml`) can be compared against it: "how much did evolution change things *beyond* what this
calm world does on its own?"

**Why it exists (decided 2026-11-12):** the earlier experiments kept changing the world, the scoring and the
yardstick at the same time, so nothing could be compared. Restart plan: first build a world in equilibrium,
measure everything in it, and only then add one factor at a time.

**Who should read this:** anyone running or extending the equilibrium experiments.

---

## 1. Key idea: you can't switch evolution off, but you can measure it

Anything that copies itself with errors evolves. Even with no selection, random luck about who has offspring
changes the gene pool (**genetic drift**). So instead of a world "without evolution", this runs three versions of the
same world side by side:

| arm | mutation | who has children / who dies | what it measures |
|---|---|---|---|
| **frozen** | off (exact copies) | the worm's own energy | must show **zero** genetic change: checks the code |
| **shadow** | on | **random**: copies the real arm's number of births and deaths each tick, but picks parents and victims at random | change from **chance alone** (drift + mutation) |
| **real** | on | the worm's own energy (split at 20, die at 0 or old age) | drift + mutation + **natural selection** |

**Adaptation = real minus shadow.** Because the shadow has exactly the same population size and turnover as the real
arm, any difference between them comes from selection. This is the *neutral shadow* method from artificial-life
research (Bedau, Snyder & Packard 1998, "A Classification of Long-Term Evolutionary Dynamics",
https://people.reed.edu/~mab/papers/alife6.pdf).

## 2. The world

| setting (in `W` at the top of `eqworld.py`) | value | meaning |
|---|---|---|
| `size` | 400 | arena is 400 × 400 units |
| `patches` | 80 | food patches at fixed random spots (same spots in all 3 arms of a replicate) |
| `patch_r` | 4 | a worm eats when within 4 units of a patch centre |
| `food_max` | 20 | most food a patch can hold |
| `regrow` | 0.01 | each tick a patch regrows 1 % of what's missing → this sets the **carrying capacity** |
| `bite` | 0.5 | most food one worm eats per tick; worms crowding one patch share it |
| `sig_smell`, `sig_taste` | 25, 5 | how far smell and taste reach (same as the toy-brain arena, so the founders' brains read the world as they evolved to) |
| `e_start` | 10 | founders' energy |
| `e_split` | 20 | a worm with ≥ 20 energy splits; parent and child get half each |
| `cost_base`, `cost_move` | 0.02, 0.02 | energy burned per tick: living + speed × 0.02 |
| `max_age` | 6000 | death of old age (same for every genome, so it isn't selection). Founders start at random ages so they don't all die at once. |
| `mut_sigma` | 0.1 | mutation size per gene for a child (shadow and real arms only) |

Carrying capacity comes out at ~380 worms per world (measured; not set directly).

**Brain:** the toy-brain recurrent network (8 hidden neurons; inputs smell, smell change, taste, taste change,
eating; outputs turn and speed). **Founders:** each replicate world starts with 160 copies of one evolved champion
from the toy-brain run (`python/toybrain/results_gpu_300g_30s_fair.json`, brain type `normal`, lineage = replicate
number), or random genomes if that file is missing (random founders starve; that's expected).

## 3. What is measured (every 500 ticks, every world)
| measure | meaning |
|---|---|
| `pop` | living worms |
| `births`, `deaths` | in the last 500 ticks |
| `energy` | mean energy of the living |
| `food` | total food on the map |
| `gdist` | mean genetic distance from the founder (length of the difference between genome and founder genome) |
| `diversity` | genetic variance inside the population |
| `lineages` | how many of the founding worms still have living descendants |
| `eat_rate` | food eaten per worm per tick |
| `speed`, `turn` | mean speed and mean absolute turning (behaviour) |
| `age` | mean age |

## 4. Success rules (fixed before the first full run)
- **EQUILIBRIUM:** the frozen arm's population stays within ±10 % of its own mean over the last 75 % of the run,
  in every replicate world.
- **ZERO POINT:** the frozen arm's genetic distance is exactly 0 for the whole run.
- **ADAPTATION:** real vs shadow, paired by replicate, sign-flip permutation test; "selection changes X" only if p < 0.05.

## 5. Running it
- **Remote (preferred):** job file in `python/remote/queue/`:
  `{"experiment": "eq_world", "args": {"replicates": 30, "ticks": 50000}}`
- **By hand:** `..\.venv\Scripts\python.exe eqworld.py 30 50000` then `python analyze_eq.py results/eq_50000t_30s.json`
- **Quick check** (CPU, seconds): `python eqworld.py 1 4000 --quick`
- **Safe to interrupt**: results are written only at the end, so a stopped run leaves no file (nothing breaks).

## 6. Files
| file | what |
|---|---|
| `eqworld.py` | the simulation (all three arms batched on the GPU; each world has 640 worm *slots*, alive or empty) |
| `analyze_eq.py` | applies the success rules, prints a table, draws the chart |
| `eq_log.txt` | progress log |
| `results/eq_<ticks>t_<replicates>s.json` | time series for every world + all settings used |
| `results/*.png`, `*_stats.txt` | chart and statistics |

## 7. Known limits
- Brain is the toy brain, not the C. elegans connectome. The connectome can be swapped in later; the toy brain makes
  thousands of worms per world cheap.
- Reproduction is asexual splitting (real C. elegans mostly self-fertilise, which behaves similarly here).
- "Genetic distance" is in genome units (connection strengths). It shows *how much* changed, not whether it matters;
  the behaviour columns show whether it matters.
- The shadow's worms still move and eat with their own brains (so food on the map behaves the same), but their
  success never depends on it.

## 8. Snapshots, replays and continuing one world (added 2026-11-13)
- `--save-at 13000,20000` saves the complete state of every world at those ticks to `snapshots/eq<tag>_t<tick>.pt`
  (worm positions, genomes, energy, ages, food, random-generator state, mutation counters).
- `--resume FILE` continues from a snapshot. With `--pick r --copies k` it keeps only replicate world r (all 3 arms)
  and makes k copies of it; each copy continues with its own random luck (same world, same moment, different futures).
- Why: the first 50k run had one frozen world (#19) whose population dipped 12.6 % at tick 13,000. Because the run is
  seeded, re-running it reproduces the same history (`eq_replay`; the stats should show the same dip) and saves a
  snapshot at tick 13,000; `eq_continue` then follows world #19 from that moment for 600 generations
  (1.6 M ticks; one generation is ~2,700 ticks in the real arm).
- **Mutation tracking:** every worm carries `nmut` (mutation events on its line of descent since its founder) and
  `msize` (total size of those mutations). Measured every sample: `mutations`, `mutation_size` (population means),
  `top_family` (the founder slot whose descendants are most numerous), `top_family_share`, `top_family_mutations`.
- Watcher experiments: `eq_replay` (args: ticks) and `eq_continue` (args: at, world, copies, ticks). eq_continue waits
  for the snapshot if the replay is still running.
