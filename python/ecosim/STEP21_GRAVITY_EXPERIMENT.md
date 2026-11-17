# Gravity experiment (Step 21): does a pattern of heavy and light ground shape evolved behaviour?

*Written 2026-11-13 for anyone picking this up. Code: `ecosim/step21.py` (experiment + analysis),
`ecosim/batch3_fast.py` (`make_gravity_pattern`, the `GRAV` lines in `_block`), `ecosim/config.py` ("Step 21").
Watcher jobs: `gravity_experiment`, `gravity_analyze`.*

## 1. The question
Take the Main Experiment exactly as it is (real C. elegans connectome brain, scarce food, predators, 60 clones per
brain) and add one thing: gravity that is not the same everywhere. Does the strength of that pattern change what
behaviour evolves, and how strong does it have to be before evolution "notices"?

## 2. What gravity is in this world (model assumptions, not worm physiology)
`local gravity = 1 g + strength x pattern`
- **Pattern**: made the way the original Java game made its cave walls (`java-original/src/Enviroment/Obstacle.java`):
  simplex noise sampled at a feature size (220 world units here; the game used 14 pixels), "wall" where the noise is
  above a level. Walls = HEAVY ground, open ground = light. Three changes for this world: the noise is cross-faded so
  it tiles across the wrap-around edges; the hard wall edge is replaced by a **feathered edge** (a smooth ramp of
  half-width `grav_feather`, like blending paint; 0 gives back the hard cave edge); the result is shifted to average 0
  and scaled to -1..+1. The SAME layout in every world, every generation, every run (`grav_seed`). Only the strength
  differs. Picture: `python -m ecosim.step21 pattern` -> `results/step21_gravity_pattern.png` (hard caves, feathered
  gravity map, and gravity along a line at four strengths). Same noise family as the game's OpenSimplexNoise, not
  the identical map (different random table).
- **Sensed**: the local offset is fed into the PVD neurons (gain `grav_gain` = 3). PVD and the touch proteins
  MEC-7 / MEC-12 / TRPA-1 are what C. elegans needs to move against gravity (Ackley et al., "Multimodal sensory
  inputs and mechanosensory components mediate C. elegans negative gravitaxis").
- **Slowed**: speed x (1 - 0.5 x offset), limited to 0.25x-1.75x. Heavy ground is slower, light ground faster.
- **Paid**: energy per tick + 0.3 x offset (living costs 0.6). Heavy ground costs more, light ground less.
Because the pattern averages 0, a worm that wanders at random gains and loses about equally: the pattern changes
WHERE it pays to be, not how hard the world is overall.

## 3. The design: a graded series of 100 seeds (dose-response)
| seed | 1 | 2 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|---|
| strength | 0.0010 | 0.00107 | 0.0053 | 0.031 | 0.175 | 1.0 |
| gravity range | 0.999-1.001 g | 0.9989-1.0011 g | 0.995-1.005 g | 0.97-1.03 g | 0.83-1.17 g | 0 g-2 g |
`strength(seed) = 0.001 x 1000^((seed-1)/99)`: each seed is 7.2 % stronger than the one before, so neighbours are
almost identical and the two ends are 1000x apart (a geometric, i.e. logarithmic, series).
- 300 generations, 12 brains per seed, 1 world per generation, best brain saved every 50 generations.
- Runs as 4 batches of 25 seeds one after the other (100 at once needs more than the 10 GB card has). About 6 hours.
- **How to read it:** there are no groups. One seed proves nothing (it also has its own luck); a TREND across the
  100 seeds is the evidence, because luck is independent of strength.

## 4. Pre-registered rules (fixed 2026-11-13 21:30 MT, before any run)
Each seed's best brain is tested as 60 clones on 12 fixed unseen worlds, three ways:
| test | gravity strength | measures |
|---|---|---|
| OWN | the seed's own | skill in the world it evolved in |
| STRONG | 1.0 for every brain | AVOIDANCE = -(mean pattern value under living worms). 0 = ignores gravity, > 0 = stays on light ground |
| FLAT | 0 | skill with no gravity pattern |
1. **Behaviour**: gravity strength shapes behaviour if Spearman correlation(log10 strength, STRONG avoidance) > 0, p < 0.05.
2. **Cost of specialising**: Spearman correlation(log10 strength, FLAT skill), p < 0.05 in either direction.
3. Reported only: 10 bins of 10 seeds with 95 % CIs, and the threshold strength where avoidance first leaves the range
   of the 20 weakest seeds for two bins in a row.
Limit stated in advance: slower movement on heavy ground makes any worm linger there (a passive bias). In the STRONG
test it is the same for every brain, so it cancels out of rule 1.

## 5. Run / stop / resume / analyse
- Start: queue `{"experiment": "gravity_experiment"}` (= `python -m ecosim.step21 full`: all 4 batches, then the analysis runs by itself). It may share the GPU with light engine jobs.
- Stop: watcher `CANCEL`. Safe at any time; the batch in progress is lost (up to ~85 minutes of work), finished
  batches are kept. Re-queue the same job and it skips finished batches.
- Analyse: queue `{"experiment": "gravity_analyze"}` -> `results/step21_stats.txt`, `.json`, `step21.png`.
  It works on whatever seeds are finished, so it can be run after each batch.
- Code check (on the workstation): queue `{"experiment": "gravity_check"}` = `python -m ecosim.step21 check --test`
  (4 seeds, 2 generations, analysis, pattern picture).

## 6. About "graded seeds" as a general method (an option for later, not adopted)
Spacing a setting on a log scale across many seeds finds WHERE an effect starts, which fixed groups cannot. The cost:
it cannot say anything about one level, only about the trend, and it needs many seeds. Keep "seed" meaning luck only;
the graded setting is a separate number that happens to be tied to the seed's position in the series.

## 7. Results
Finished 2026-11-14 04:05 (382 minutes, sharing the GPU with engine runs). 100 seeds, best brains at generation 300.

1. BEHAVIOUR: Spearman rho(log10 strength, STRONG avoidance) = +0.099, p = 0.327 -> no detectable trend.
2. COST: rho(log10 strength, FLAT skill) = +0.034, p = 0.733 -> no detectable trend. (OWN skill: rho +0.006.)
3. Threshold strength: none found.
All 10 bins show NEGATIVE avoidance (-0.05 .. -0.19): worms spend slightly more time on heavy ground than chance,
the passive "slower there, so they linger" bias predicted in section 4. Skill 2.72-2.91 in every bin.
Reading: with these rules gravity is invisible to selection in 300 generations. Not shown: that gravity cannot
matter. Follow-up written but NOT run: `ecosim/step24.py` (harsher cost, with / without sensing, 16 seeds).
A slowly changing ("eroding") pattern was proposed 2026-11-14 and not run for the same reason.

## 8. Follow-up: the GRAVITY BITE TEST (Step 24, ecosim/step24.py), run 2026-11-16 07:07-09:40 MT
Question: is there ANY setting at which gravity matters to evolution here? 4 arms x 16 seeds x 200 generations,
Main Experiment world + the cave-style gravity pattern; every best brain tested on 12 unseen worlds at strength 1.0
with the harsh ("bite") rules. Avoidance = -(mean pattern value under living worms); > 0 = they stay on light ground.

| Arm | Evolved under | Avoidance | Skill (bite world) | Speed |
|---|---|---|---|---|
| s24_flat | no gravity | -0.073 | 1.924 | 0.593 |
| s24_base | Step 21 rules (cost 0.3) | -0.057 | 2.567 | 0.557 |
| **s24_bite** | **cost 1.5 (5x), sensed** | **+0.121** | **2.960** | 0.421 |
| s24_blind | cost 1.5, NOT sensed | -0.092 | 2.151 | 0.635 |

Pre-registered tests (vs s24_flat, paired sign-flip, Holm over 3):
- base: +0.016 (9/16), Holm p 0.96 -> no detectable response (repeats Step 21's null)
- **bite: +0.195 (14/16), Holm p 0.00045 -> RESPONDS TO GRAVITY**
- blind: -0.019 (5/16), Holm p 0.96 -> no detectable response

Plain words: when heavy ground is costly enough (2.5x the cost of living at its heaviest) AND the worms can feel
gravity, evolution makes them avoid heavy ground and move more slowly, and those brains are the best in that world.
Same cost without the sense: no avoidance, so the sense is what gets used (not just a general slowdown).
Decision rule fixed before the run: "if s24_bite responds, the changing-pattern (erosion) experiment is worth running
with the bite rules." It responded, so erosion is now worth designing (owner's call; not built).

## 9. Follow-up: ERODING GRAVITY (Step 29, ecosim/step29.py), run 2026-11-16 12:42-17:23 MT
Same world and harsh ("bite") rules as Step 24; the landscape starts identical in every arm and morphs over 300
generations: static, replaced 1x, 3x, 10x, or a brand-new landscape every generation (16 seeds each). Each best brain
tested on 12 unseen worlds: on never-seen landscapes (FRESH), the original one, and its own final one.

| Arm | Avoidance, FRESH | original | final | Skill (fresh) | Speed (fresh) |
|---|---|---|---|---|---|
| static | +0.140 | +0.136 | +0.136 | 3.172 | 0.366 |
| 1 turnover | +0.125 | +0.118 | +0.119 | 3.127 | 0.397 |
| 3 turnovers | +0.136 | +0.131 | +0.136 | 3.308 | 0.424 |
| 10 turnovers | +0.132 | +0.128 | +0.126 | 3.271 | 0.447 |
| new every generation | +0.147 | +0.141 | +0.138 | 3.340 | 0.394 |

Pre-registered: E1 avoidance on fresh landscapes vs erosion level: Spearman rho +0.07, p 0.53 -> **no detectable trend**.
E2 each eroding arm vs static: all Holm p = 1 -> **no detectable difference**.

Plain words: every arm learned to avoid heavy ground about equally well, and they do it just as well on landscapes
they have never seen as on their own. So the brains react to what the gravity sense feels, not to a remembered
layout; how fast the landscape changes does not matter. This is what was predicted before the run (the worms have no
sense of position and no place memory). Not tested: speed rises somewhat with erosion (0.37 -> 0.45) - a hint only.
Implication: to make a changing landscape matter, the worms would need something that can store places (a memory
or position sense), e.g. the 2nd Experiment's hippocampus layer.
