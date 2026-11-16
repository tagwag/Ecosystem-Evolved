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
