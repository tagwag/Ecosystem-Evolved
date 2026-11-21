# Step 27 (DESIGN, not built yet): fleeing food
Written 2026-11-16 07:45 MT. Owner's idea: food that runs away, from easy to catch, to just faster than a worm, to much
faster. Status: design only. Nothing below has been coded or run.
Term: this is a **pursuit-evasion** setup; the key number is the **speed ratio** = food top speed / worm top speed.

## 1. Facts from the current model that shape the design
- Worm top speed: 5 world units per tick (`config.speed_max`); a worm eats food within 8 units (`eat_radius`).
- The world WRAPS AROUND (a torus: leave the right edge, come in on the left). There are no walls or corners.
- So food faster than a worm, fleeing in a straight line, can NEVER be caught by one worm chasing it. It can only be
  caught if it runs INTO a worm: two or more worms closing in from different sides (a pincer), a worm waiting where the
  food is heading (an ambush), or food changing direction. Each world holds 60 identical clones of one brain, so
  group behaviour is possible and is rewarded together.

## 2. How the food behaves
- Food is placed in the usual 6 patches. Each food item looks for the nearest living worm within its **flee radius**
  (40 units, about 5 eat-radii). If one is there, the food moves directly away from it at its arm's speed, plus a
  small random wobble (+-20 degrees) so its path is not perfectly predictable. Otherwise it stays still.
- Fleeing food stays smellable exactly as now (the smell map is rebuilt every tick from food positions).
- Food does not tire (cleanest version). See section 6 for the fallback if the fastest arms never catch anything.

## 3. Arms (16 seeds each, paired by seed, 300 generations; Main Experiment world otherwise)
| Arm | Food speed | Speed ratio | What it should feel like |
|---|---|---|---|
| s27_still | 0 | 0 | normal food: the reference |
| s27_slow | 2.5 | 0.5 | easy to catch |
| s27_close | 4.5 | 0.9 | catchable, but only by a worm moving almost flat out |
| s27_edge | 5.5 | 1.1 | just faster than a worm: solo chase fails on open ground |
| s27_fast | 7.5 | 1.5 | clearly faster |
| s27_veryfast | 15 | 3.0 | much faster: only pincers / ambushes can work |
Measured timing (2026-11-16): one 16-seed x 300-generation arm alone takes ~45 min, so about 4.5 h plus ~15 min analysis.
Optional finer version (uses the graded-seed idea from the Gravity experiment): 100 seeds with speed ratios spaced on a
log scale from 0.1 to 3, one seed each.

## 4. What is measured (each seed's best brain at generation 300, 60 clones x 12 unseen worlds, in its own arm's world)
- skill and food eaten (as always)
- **catches per worm** and **chase length** (ticks between a food item starting to flee and it being eaten)
- **group-catch share**: fraction of catches where another worm was within 40 units of the food at the moment of the catch
  (pincer / herding)
- **ambush share**: fraction of catches made by a worm moving at under 20 % of top speed (it waited, the food came to it)
- **cross-test**: every arm's brains also tested in the still-food world and in the 1.1x world (do chasers stay good at
  plain foraging? did slow-food brains already have what it takes?)

## 5. Rules to fix BEFORE the run (draft)
- **R1 cost of speed:** skill falls as speed ratio rises (Spearman over the 6 arms x 16 seeds). Expected yes; reported as
  the size of the drop.
- **R2 group hunting appears:** group-catch share rises with speed ratio (Spearman, one-sided). This is the interesting one.
- **R3 evolution helps:** in each moving-food arm, evolved brains catch more than generation-0 brains on the same worlds
  (paired sign-flip, Holm over 5 arms).
- Reported, not tested: ambush share, chase length, cross-tests, learning curves.

## 6. Expected problems, stated in advance
- At 3x (maybe 1.5x) nothing may ever be caught. Then every brain scores the same, selection has nothing to act on, and
  the arm just drifts. That is a real result ("too fast to evolve against"), but a dead end. **Fallback (decided now):**
  if the generation-0 brains catch fewer than 1 food per world per generation in an arm, that arm is also run with TIRING
  food (runs for 30 ticks, must rest 30) and both versions are reported.
- With clones, "cooperation" is really one brain whose copies benefit from each other; it is not proof that unrelated
  worms would cooperate.
- Food fleeing on a torus may bunch up in odd places; a picture of food positions over time is part of the check.

## 7. What it costs to build
Food movement in `batch3_fast.py` (food positions already live on the GPU; add a nearest-worm search like the predator
code uses and a move step), catch bookkeeping, `ecosim/step27.py`, watcher jobs `fleeing_food_check` and
`fleeing_food_experiment`. Under one session of coding, then a workstation code check.

## 8. Results (run 2026-11-16 18:27 - 2026-11-17 03:34 MT, 9 arms x 16 seeds x 300 generations)
Built as designed. Random starting brains caught fewer than 1 fleeing food per world at 1.1x, 1.5x and 3x, so tiring
versions of those three arms were added automatically (9 arms).

**Headline: in EVERY moving-food arm, even the slowest (0.5x), evolution gave up on food and evolved worms that stop
moving.** Mean speed command fell from 0.71 at generation 0 to ~0.10 by generation 20 and ~0.001 by generation 100;
food eaten ~0.01 per worm (still food: 7.4); every worm starves (0 survivors), but standing still makes the energy
last longest, and the fitness rule ("energy left + time survived") rewards exactly that. This is the same kind of
REWARD HACKING as Step 3e: when the task is impossible, the tie-break becomes the goal.

| Arm | Speed ratio | Skill | Food per worm | Catches per world |
|---|---|---|---|---|
| still | 0 | 2.705 | 7.58 | - |
| slow | 0.5 | 0.534 | 0.02 | 1.19 |
| close | 0.9 | 0.534 | 0.01 | 0.58 |
| edge | 1.1 | 0.534 | 0.01 | 0.42 |
| fast | 1.5 | 0.534 | 0.00 | 0.00 |
| very fast | 3.0 | 0.534 | 0.00 | 0.03 |
(Tiring arms gave numbers identical to their non-tiring versions: worms that never chase never make food tire.)

Pre-registered tests, with what they really mean:
- R1 skill falls with food speed: rho -0.49, p 4e-7 -> PASS, but it is a step (still vs any moving), not a slope.
- R2 group-catch share rises with speed: rho +0.33, p 0.009 -> PASS, but **meaningless**: it rests on a handful of
  catches (0.03 per world at 3x), mostly of food that wandered into motionless worms.
- R3 evolved vs random brains: evolved brains catch LESS in all 5 moving arms (Holm p <= 0.009) - because they stopped
  moving.
Cross-test: moving-food brains score 0.536 even in the still-food world: they no longer forage at all.

Why the food was uncatchable even at half speed: food notices a worm 40 units away (5x the eating distance) and runs
straight away at once; a worm's typical speed is ~0.7 x 5 = 3.5, so at 0.5x it closes only ~1 unit per tick and must
hold its heading for ~30 ticks while its brain keeps turning and tumbling; 60 clones compete. Random brains ate 0.05
food each at 0.5x versus 3.8 with still food.

Not re-run. Possible fixes (owner's call): food notices worms only at ~15 units; mix still and fleeing food (worms
keep foraging; does catching fleeing food add anything?); remove the survival tie-break so idling is not rewarded.

## 9. Fixed re-run, Step 27b (run 2026-11-17 16:18-23:18 MT; written up 2026-11-20)
Fixes: flee radius 15 (was 40), half the food moves, score = food eaten only; plus a DRIFT world (food wanders at
0.9x, blind to worms). **No arm idled** (movement 0.67-0.97; idling limit 0.05) - the fixes worked.

| Arm | Speed | Skill (food/worm) | Catches of moving food per world | Group share |
|---|---|---|---|---|
| still | 0 | 9.62 | - | - |
| slow | 0.5x flee | 8.35 | 185.5 | 0.15 |
| close | 0.9x flee | 5.89 | 17.5 | 0.98 |
| edge | 1.1x flee | 5.85 | 11.1 | 0.99 |
| fast | 1.5x flee | 6.03 | 16.3 | 0.90 |
| very fast | 3x flee | 6.25 | 30.5 | 0.14 |
| drift | 0.9x blind | 8.39 | 214.5 | 0.02 |

Pre-registered:
- **R1 evolution learns to catch moving food: PASS in all 6 moving arms** (16/16 seeds each except drift 15/16, Holm p
  0.0003).
- **R2 catches fall with flee speed: PASS** (rho -0.25, p 0.027), though not smoothly: catches rise again at 3x.
- **R3 running away matters: PASS** - at the same 0.9x speed, fleeing food is caught ~12x less than drifting food
  (17.5 vs 214.5 per world, 0/16 seeds the other way).

Reported, not tested (and the most interesting part): at 0.9x-1.5x, **90-99 % of catches happen with another worm
within 15 units** of the food, versus 2 % for drifting food and 15 % at 0.5x. When food is about as fast as a worm,
it is only caught when two worms close in on it: a hint of group (pincer) catching. Caveat, stated before the run:
worms are clones of one brain and the 15-unit radius equals the flee radius, so part of this may simply be that food
fleeing one worm runs into another. A follow-up would compare against randomly placed worms of the same density.
At 3x, group share falls to 14 %: food that fast mostly runs into single worms.
