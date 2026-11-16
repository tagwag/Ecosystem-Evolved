# Food-circle gravity & magnetism experiments (Step 23)

*Written 2026-11-14 for anyone picking this up. Code: `ecosim/step23.py` (experiment + analysis + picture),
`ecosim/batch3_fast.py` (`circle_centres`, `make_circle_field`, the `circ_on` lines in `load`, the `MAG` lines in
`_block`), `ecosim/config.py` ("Step 23"). Watcher jobs: `food_circles_check` (code check, minutes),
`food_circles_experiment` (everything), `food_circles_analyze` (analysis only).*

## 1. The question
If a gravity field or a magnetic field forms large circles with a bunch of food at the centre of each, do worm brains
evolve to **use the field to find food**? And does it matter whether the field also changes the world physically
(gravity: slower and costlier) or is only a signal (magnetism)?

## 2. The world
Exactly the Main Experiment (Step 20) / Gravity experiment (Step 21) world: real C. elegans connectome brain (old
synapses, decoder output), scarce food, 6 predators, touch, hunger peptide, each brain scored as 60 clones in a
full-size world (1920 x 1080), 12 brains per seed. New:

- **Circles**: one per food patch (6 per world). Field = **1** within 100 units of the centre, a **feathered edge**
  (smoothstep fade, like blended paint) down to **0** at 240 units, 0 beyond. Where circles overlap, the larger value
  wins. Distances wrap around the world's edges.
- **Food**: the food patches are the circle centres, and food grows around them (spread 60 units), so every circle
  has a bunch of food at its centre.
- **New layout every generation** (new food places -> new circles). A brain can't memorise where food is; it can
  only learn "field rising = food ahead".
- Picture: `python -m ecosim.step23 picture` -> `results/step23_circles.png` (field + food, food arm and decoy arm).

| | Gravity circles | Magnetic circles |
|---|---|---|
| Value in the world | gravity = 1 g + strength x field (2 g at a centre at strength 1.0: a heavy "gravity well" on the food) | field x strength |
| Sensed by | PVD neurons (Ackley et al., gravitaxis needs PVD + MEC-7/MEC-12/TRPA-1) | AFD neurons (Vidal-Gadea et al. 2015, eLife 4:e07493) |
| Physical effect | slower (0.5x at 2 g) and costlier (+0.3 energy per tick at 2 g; living costs 0.6) | none: a pure cue |
| Sensory input size | strength 1 x gain 3 | strength 1 x gain 3 (the same) |

Magnetoreception in real C. elegans is disputed: a blinded replication found no magnetic sense (Landler et al. 2018,
eLife 7:e30187), and the original authors replied (Vidal-Gadea et al. 2018, eLife 7:e31414). Here magnetism is
simply an assumed extra sense, so the result says what evolution does with such a sense, not whether worms have one.

`circle_sign = +1` puts the heavy ground on the food. Set it to `-1` (config.py) for light ground on the food.

## 3. Arms (16 seeds each, 300 generations, paired by seed)
| arm | circles placed | gravity strength | magnetic strength | what it isolates |
|---|---|---|---|---|
| `s23_ctrl` | on food | 0 | 0 | reference: identical world, no field |
| `s23_grav_food` | on food | 1.0 | 0 | gravity as a food cue (with its cost) |
| `s23_grav_decoy` | away from food | 1.0 | 0 | gravity's cost/slowing without the cue |
| `s23_mag_food` | on food | 0 | 1.0 | magnetism as a food cue |
| `s23_mag_decoy` | away from food | 0 | 1.0 | an extra input that points nowhere useful |

Decoy circles: same number and size, each placed as far from every food patch as possible (best of 200 random tries),
using a random generator seeded from the food layout, so a decoy world has exactly the same food as its food world.
Paired by seed = same seed number gets the same food layouts in every arm.
Runtime estimate: ~80 seed-runs at the Step 21 pace of ~3.6 min each, about 5 hours on the 3080.

## 4. Pre-registered rules (written 2026-11-14 20:30 MT, before any run)
Yardstick: each seed's best brain at generation 300, 60 clones on 12 fixed unseen worlds (5100-5111), in its own
arm's world. **Sense-cut test**: the same, but the field sensor is disconnected (PVD gravity input and AFD magnetic
input set to 0; gravity's slowing and cost stay).

Paired sign-flip permutation tests, Holm-corrected over these 4:
- **H1** gravity circles change skill: `grav_food - ctrl`
- **H2** magnetic circles change skill: `mag_food - ctrl`
- **H3** the gravity-evolved brains use the sense: `grav_food own - grav_food sense-cut`
- **H4** the magnetic-evolved brains use the sense: `mag_food own - mag_food sense-cut`

A test passes if Holm p < 0.05; the sign says helps (+) or hurts (-).
Reported, not tested: decoy - ctrl, food - decoy, sense-cut of the decoy arms, **occupancy** (mean field value under
living worms = how much time they spend inside circles), learning curves.

**How to read it:** H3/H4 are the cleanest evidence the brains learned to use the field (same brains, only the sensor
removed). H1 for gravity mixes the cue's benefit with its cost; compare with the decoy arm to separate them.

### 4b. Added 2026-11-16 06:15 MT, before the run: the LIGHT-gravity arm
Why: section 6 showed gravity wells at the food hurt skill but the brains still used the gravity sense. The cue
came with a price (heavy ground at the food). New arm **s23_grav_light**: the same circles on the food, but
`circle_sign = -1`, so gravity inside a circle is 1 g - strength x value = **0 g at the centre**: worms move up to
1.5x faster there and pay 0.3 less energy per tick. Same cue, opposite price.

A separate test family (Holm over 2), so H1-H4 keep their original correction:
- **H5** light gravity circles change skill: `grav_light - ctrl`
- **H6** the light-gravity brains use the sense: `grav_light own - grav_light sense-cut`

Reported, not tested: `grav_light - grav_food` (does the price decide whether a gravity cue pays off?).
The first 5-arm results are kept as `results/step23_stats_5arms_2026-11-15.txt/.json` and `step23_5arms_2026-11-15.png`;
the new analysis re-tests all arms on the same unseen worlds and overwrites `step23_stats.*` / `step23.png`.

**Known limits, stated in advance:** 16 seeds x 300 generations is short (Step 19 skill was still rising at 300); the
gravity and magnetism effects are model assumptions, so the results describe this rule set, not real worms.

## 5. Commands
```
python -m ecosim.step23 check --test   # code check: 2 seeds, 2 gens, all arms, analysis, picture (runs/step23_test/)
python -m ecosim.step23 full           # all 5 arms (skips finished ones; safe to re-queue), then the analysis
python -m ecosim.step23 analyze        # analysis only
python -m ecosim.step23 picture        # the circle picture only
```
Results: `runs/step23/<arm>_s<seed>/` (ckpt_g50..300.npy, best_genome.npy, history.json),
`results/step23_stats.txt`, `step23_stats.json`, `step23.png`, `step23_circles.png`.

## 6. Results (run 2026-11-14 22:53 to 2026-11-15 05:16 MT on the workstation, 16 seeds x 300 generations)
Files: `results/step23_stats.txt`, `step23_stats.json`, `step23.png` (skill / occupancy / learning curves),
`step23_circles.png` (what the circles look like).

| Arm | Skill (own) | Skill (sense cut) | Food | Occupancy (own) |
|---|---|---|---|---|
| ctrl (no field) | 2.607 | - | 7.64 | 0.569 |
| gravity circles at food | **1.829** | **1.467** | 7.05 | 0.612 |
| gravity circles at decoy | 2.779 | 2.768 | 7.48 | 0.060 |
| magnetic circles at food | 2.730 | 2.665 | 7.60 | 0.580 |
| magnetic circles at decoy | 2.686 | 2.661 | 7.56 | 0.052 |

Pre-registered tests (paired sign-flip, Holm over 4):
- **H1 gravity circles vs control: -0.778, 0/16 seeds, Holm p 0.0002 -> PASS: HURTS.**
- H2 magnetic circles vs control: +0.123, 7/16 seeds, Holm p 0.74 -> no detectable effect.
- **H3 gravity brains use the sense: +0.362, 13/16 seeds, Holm p 0.0033 -> PASS: the sense HELPS them.**
- H4 magnetic brains use the sense: +0.065, 10/16 seeds, Holm p 0.74 -> no detectable effect.

Reported, not tested: gravity decoy vs control +0.172 (11/16, p 0.095, a hint only); gravity food vs decoy -0.950
(0/16, p 0.00005); magnetic food vs decoy +0.044 (p 0.72); decoy arms own vs sense-cut +0.012 / +0.025 (no use).

### What it means (plain words)
1. **Gravity at the food is a cost, not a help.** Food sitting in heavy wells (2 g at the centre) slows the worms and
   costs energy exactly where they need to eat, so those worms ended 30 % below control in skill. The decoy arm (same
   heavy circles, away from food) did not suffer, so the loss comes from where the heavy ground is, not from gravity
   existing.
2. **But the gravity-at-food worms DID learn to use the gravity sense.** Same brains, only the gravity sensor (PVD
   input) unplugged: skill falls from 1.83 to 1.47 in 13/16 seeds. This is the first result in this project where
   evolved brains measurably rely on a gravity cue. Earlier (Step 21) gravity was a pattern with no link to food and
   it was ignored. The difference: here the field predicts where food is.
3. **Magnetism did nothing detectable.** Magnetic circles at food neither helped nor hurt, and unplugging the
   magnetic input (AFD) did not change skill. Likely reason: the circles carry no cost and food is already found by
   smell, so a second food cue adds little; 300 generations may also be too short.
4. Occupancy (time inside circles) is about 0.57-0.61 whenever circles sit on food, including control (control is
   measured against the same circle positions): worms are in the circles because the food is there, not because of
   the field. Decoy circles: about 0.05-0.06 in both gravity and magnetism, own vs sense-cut nearly equal, so the
   worms neither seek nor avoid empty circles.

### Open question this answers for the owner
Whether gravity at the food should be heavy (current, `circle_sign = +1`) or light (`circle_sign = -1`): heavy wells
punish exactly the behaviour being rewarded. A light-at-food version (food on easy ground) would test the cue without
the cost; one extra arm, about 1.5 h. Not queued; owner's call.

### Limits
16 seeds x 300 generations; skill was still creeping up at 300. Gravity and magnetism effects are model rules (PVD
gravity input, AFD magnetic input, invented speed and energy costs), so this says how evolution responds to these
rules, not what real C. elegans would do.
