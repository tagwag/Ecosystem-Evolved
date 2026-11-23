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
