# Step 30: Super worm (results, 2026-11-22)
Design, rules and commands: docstring of `python/ecosim/step30.py`. Files: `python/results/step30_hall.txt`,
`step30_stats.txt/.json`, `step30.png`, `python/runs/step30/hall/hall_of_fame.csv` (+ genomes), and the super worm
genome `python/runs/step30/SUPER_WORM.npy` (+ `SUPER_WORM.json`).

## Phase A: hall of fame (2026-11-22 14:08-15:09)
12,084 snapshots of 2,044 past lineages (every run with the standard 5,131-gene brain) screened in ONE standard world
(Step 23 control rules); top 300 re-tested on 24 unseen worlds; each lineage counted at its PEAK; at most 2 per arm.
Reference on the same worlds: Step 23 control best brains (generation 300) mean 2.743, best 3.171.

| Rank | Score | Experiment / arm | Seed, generation |
|---|---|---|---|
| 1 | 3.692 | Step 29 eroding gravity, new landscape every generation | 11, 100 |
| 2 | 3.691 | Step 25 beacon, vibration cue | 14, 300 |
| 3 | 3.687 | Step 19 base | 8, final |
| 4 | 3.662 | Step 11 sparse, clonal + worm scent | 10, final |
| 5 | 3.660 | Step 19 base | 2, 240 |
| 6 | 3.653 | Step 25 beacon, nociception cue | 11, 300 |
| 7 | 3.632 | Step 24 gravity bite, blind | 8, final |
| 8 | 3.620 | Step 25 beacon, no cue | 3, 300 |
| 9 | 3.597 | Step 25 beacon, gravity cue | 1, 250 |
| 10 | 3.546 | Step 25 beacon, nociception cue | 16, 200 |

## Phase B: nurture (2026-11-22 15:09-21:47)
4 arms x 16 seeds x 300 generations in the standard world; every seed's best brain re-tested every 25 generations
on the 24 hall-of-fame worlds.

| Arm | Start (gen 25) | Peak | Final (gen 300) | Decline | Best brain |
|---|---|---|---|---|---|
| random start | 2.54 | 3.05 | 2.74 | 0.32 | 3.38 |
| 12 champions | 3.49 | 3.62 | 3.19 | 0.44 | 3.77 |
| best champion + mutants | 3.43 | 3.63 | 3.19 | 0.44 | 4.02 |
| **12 champions, scored on 4 worlds** | 3.54 | 3.80 | **3.61** | **0.20** | **4.05** |

Pre-registered (paired sign-flip by seed, Holm over 3) - all PASS:
- **S1 champions help**: final +0.45 vs random start (13/16, Holm p 0.005).
- **S2 reliable selection helps**: scoring each brain on 4 worlds instead of 1: final +0.42 (14/16, Holm p 0.0006).
- **S3 reliable selection maintains**: decline from peak 0.20 vs 0.44 (14/16, Holm p 0.005).
Reported: single best champion vs pool of 12: no difference (+0.004, 8/16).

## What it takes to make and keep a super worm
1. **Start from champions**: a +0.45 head start that random evolution never closes in 300 generations.
2. **Judge each brain on several worlds**: with 1 world per brain, luck decides who breeds, and the champions
   DEGRADE (3.49 -> 3.19 over 300 generations, below where they started). With 4 worlds they hold and improve
   (3.54 -> 3.61, peak 3.80). This is the answer to "why do lineages peak then degrade": noisy selection.
3. Diversity of founders did not matter here (one champion + mutants = pool of 12).

## Super worm
`n30_pool_x4` seed 5, generation 300: **4.045** on the 24 hall worlds, above the best champion (3.692) and ~47 %
above typical evolved brains (2.74). **Caveat (winner's curse):** it was chosen as the best of 768 checkpoints on the
same 24 worlds it is scored on, so 4.045 is optimistic, as were the hall scores (the champions themselves score ~3.5
when re-run as founders). A confirmation on fresh worlds (minutes of GPU) is the next step; not run yet.

## Fresh-world confirmation (2026-11-23 01:03-01:07)
77 brains (super worm, 12 champions, each seed's best checkpoint per arm) re-tested on 48 never-used worlds.

| Group | On the worlds they were picked on | On fresh worlds | Shrink |
|---|---|---|---|
| super worm | 4.045 | **3.929** | 0.12 |
| 12 champions | 3.625 | 3.429 | 0.20 |
| random-start bests | 3.052 | 2.880 | 0.17 |
| pool bests | 3.623 | 3.414 | 0.21 |
| best-champion bests | 3.627 | 3.422 | 0.20 |
| pool x4 bests | 3.801 | **3.601** | 0.20 |

- Every score shrinks by ~0.2 on fresh worlds (winner's curse, as expected), but the ranking holds.
- **The super worm is confirmed**: 3.929 on fresh worlds, above the best champion on the same fresh worlds (3.571)
  and ~43 % above typical evolved brains (2.74). 6 of the top 7 fresh-world brains come from the 4-world arm.


## Independent replicate (seeds 17-32, 2026-11-23 01:07-07:46; fresh-world check 07:51-07:55)
Same hall of fame, arms, worlds and pre-registered rules; only the random seeds are new (`step30.py nurture --rep`,
results in `results/step30_rep_stats.txt` and `results/step30_rep_confirm.txt`).

| Rule | Original (seeds 1-16) | Replicate (seeds 17-32) | Reproduced? |
|---|---|---|---|
| S1 champions help (pool - random, final) | +0.45, pass | +0.19 (9/16), Holm p 0.22 | **no** |
| S2 4-world scoring helps (pool_x4 - pool, final) | +0.42, pass | +0.38 (15/16), Holm p 0.00075 | **yes** |
| S3 4-world scoring loses less from peak | +0.24, pass | +0.11 (10/16), Holm p 0.22 | **no** (same direction, not significant) |
| single best vs pool of 12 | no difference | +0.01, no difference | yes (null) |

Final arm means (replicate): random 3.06, pool 3.24, best 3.26, pool x4 **3.63**. Random-start worms climbed
2.51 -> 3.06 and closed most of the gap to the 1-world champion arms, which again slid from their start (3.44 -> 3.24).

**Fresh worlds (same 48 worlds 5800-5847 as the original confirmation):** replicate super worm (`n30_pool_x4` seed 31,
gen 100; 4.053 on hall worlds) scores **3.832**; the original super worm, re-scored in the same run, **3.861**; best
champion 3.542. Both super worms beat every champion; 10 of the 10 best fresh-world brains come from the 4-world arm.

**Measurement noise (new, important):** the original super worm scored 3.929 on these 48 worlds in the first
confirmation and 3.861 in this one, and the replicate super worm appears twice in this run (as "super worm" and as
its seed's best checkpoint) with 3.832 and 3.767. So one brain's 48-world score varies by about +/-0.07 between runs
(the simulation's random stream depends on how worlds are batched). The two super worms are therefore **tied**;
differences under ~0.1 between single brains should not be read as real.

### Revised answer: what it takes to make and keep a super worm
1. **Judge each brain on several worlds (4 instead of 1).** The only rule that reproduced, and the largest effect
   (+0.38 to +0.42). This is the recipe.
2. Starting from champions gives a head start, but it is unreliable: +0.45 in the original, +0.19 (not significant)
   in the replicate, because with 1-world scoring the champions slide back toward where random evolution reaches.
3. With 1-world scoring, champions decline from their start in both runs (noisy selection lets lucky brains breed).
   4-world scoring keeps them at or above their start; whether it halves the decline is not established.
4. Best brains: ~3.83-3.93 on fresh worlds (about 40 % above typical evolved brains, 2.74), from 4-world lines.
