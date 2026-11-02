# Lucky lineages

Standout evolved brains, kept so any experiment can start from them. Load with
`from ecosim import lineages; g = lineages.load('<name>')`. Start any step from one with
`lineages.start_population(name, P, rng, mutate)`; move it to another brain type with `lineages.convert`.

**lucky** = fair-test score in the top 3 of its condition AND at least 2x that condition's median
(4+ seeds). **champion** = best seed of its condition, kept so every step has a reusable best brain.
Refresh after any experiment: `python -m ecosim.lineages scan` (or double-click register_lineages.bat).

## Lucky lineages (14)

| name | step | condition | seed | score | condition median | brain | notes |
|---|---|---|---|---|---|---|---|
| `6-curric_mem-s2` | 6 | curric_mem | 2 | 2.55 puzzle food/worm | 1.169 | worm6 | 4 seeds x 60 gens: weak median, treat with care; uses memory pool (CPU only for now) |
| `6-curric_nomem-s3` | 6 | curric_nomem | 3 | 2.012 puzzle food/worm | 0.875 | worm6 | 4 seeds x 60 gens: weak median, treat with care; runs on GPU (step9_gpu) |
| `6-puzzle_nomem-s2` | 6 | puzzle_nomem | 2 | 1.1 puzzle food/worm | 0.519 | worm6 | 4 seeds x 60 gens: weak median, treat with care; runs on GPU (step9_gpu) |
| `6-puzzle_mem-s2` | 6 | puzzle_mem | 2 | 0.737 puzzle food/worm | 0.362 | worm6 | 4 seeds x 60 gens: weak median, treat with care; uses memory pool (CPU only for now) |
| `6b-puzzle_nomem-s12` | 6b | puzzle_nomem | 12 | 3.35 puzzle food/worm | 0.569 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-puzzle_nomem-s9` | 6b | puzzle_nomem | 9 | 2.675 puzzle food/worm | 0.569 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-puzzle_nomem-s5` | 6b | puzzle_nomem | 5 | 2.525 puzzle food/worm | 0.569 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_nomem-s12` | 6b | curric_nomem | 12 | 2.225 puzzle food/worm | 0.575 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_mem-s10` | 6b | curric_mem | 10 | 2.2 puzzle food/worm | 0.637 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6b-curric_nomem-s8` | 6b | curric_nomem | 8 | 2.025 puzzle food/worm | 0.575 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_nomem-s6` | 6b | curric_nomem | 6 | 1.8 puzzle food/worm | 0.575 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_mem-s4` | 6b | curric_mem | 4 | 1.338 puzzle food/worm | 0.637 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6b-puzzle_mem-s8` | 6b | puzzle_mem | 8 | 1.025 puzzle food/worm | 0.481 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6b-puzzle_mem-s9` | 6b | puzzle_mem | 9 | 0.987 puzzle food/worm | 0.481 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |

## Champions (best per condition, not lucky) (16)

| name | step | condition | seed | score | condition median | brain | notes |
|---|---|---|---|---|---|---|---|
| `3-nohunger-s2` | 3 | nohunger | 2 | 8.034 energy fitness | 6.738 | worm2 | 4 seeds; from runs/step3 |
| `3-hunger-s2` | 3 | hunger | 2 | 6.657 energy fitness | 6.098 | worm2 | 4 seeds; from runs/step3 |
| `3b-hunger_scarce-s3` | 3b | hunger_scarce | 3 | 5.658 energy fitness | 5.604 | worm2 | 4 seeds; from runs/step3 |
| `3b-nohunger_scarce-s4` | 3b | nohunger_scarce | 4 | 5.652 energy fitness | 5.435 | worm2 | 4 seeds; from runs/step3 |
| `3c-nohunger_scarce-s8` | 3c | nohunger_scarce | 8 | 5.738 energy fitness | 5.504 | worm2 | 12 seeds; from runs/step3 |
| `3c-hunger_scarce-s8` | 3c | hunger_scarce | 8 | 5.711 energy fitness | 5.45 | worm2 | 12 seeds; from runs/step3 |
| `4-nogrowth-s2` | 4 | nogrowth | 2 | 27.296 food/worm | 25.729 | worm3 | 4 seeds; from runs/step4 |
| `4-growth-s1` | 4 | growth | 1 | 27.208 food/worm | 26.846 | worm3 | 4 seeds; from runs/step4 |
| `5-fixed-s2` | 5 | fixed | 2 | 22.15 food/worm | 18.144 | worm5 | 4 seeds; from runs/step5 |
| `5-hebb-s3` | 5 | hebb | 3 | 20.05 food/worm | 17.631 | worm5 | 4 seeds; from runs/step5 |
| `5-curiosity-s2` | 5 | curiosity | 2 | 18.697 food/worm | 13.747 | worm5 | 4 seeds; from runs/step5 |
| `5-sleep-s4` | 5 | sleep | 4 | 17.219 food/worm | 11.194 | worm5 | 4 seeds; from runs/step5 |
| `5-sprint_rest-s2` | 5 | sprint_rest | 2 | 16.578 food/worm | 14.314 | worm5 | 4 seeds; from runs/step5 |
| `5-dopamine-s2` | 5 | dopamine | 2 | 16.397 food/worm | 12.509 | worm5 | 4 seeds; from runs/step5 |
| `7-seeded-s101` | 7 | seeded | 101 | 27.1 food/worm | 25.469 | worm3 | 6 seeds; from runs/step7 |
| `7-hardware-s1` | 7 | hardware | 1 | 27.042 food/worm | 26.198 | worm3 | 6 seeds; from runs/step7 |

## Qualify, but genome is on another machine

Run `python -m ecosim.lineages scan` on the machine that has these runs (the desktop for GPU steps).

- `3d-hunger_scarce-s22` (champion): runs/step3_fast/hunger_scarce_s22/best_genome.npy
- `3d-nohunger_scarce-s22` (champion): runs/step3_fast/nohunger_scarce_s22/best_genome.npy
- `3f-pep_noash_move0.25-s16` (champion): runs/step3f/pep_noash_move0.25_s16/best_genome.npy
- `3f-pep_ash_move0.25-s31` (champion): runs/step3f/pep_ash_move0.25_s31/best_genome.npy
- `3f-nopep_noash_move0.25-s9` (champion): runs/step3f/nopep_noash_move0.25_s9/best_genome.npy
- `3f-nopep_ash_move0.25-s20` (champion): runs/step3f/nopep_ash_move0.25_s20/best_genome.npy
- `4g-growth-s30` (champion): runs/step4g/growth_s30/best_genome.npy
- `4g-nogrowth-s18` (champion): runs/step4g/nogrowth_s18/best_genome.npy
- `8-nopred-s31` (champion): runs/step8/nopred_s31/best_genome.npy
- `8-pred_touch-s20` (champion): runs/step8/pred_touch_s20/best_genome.npy
- `8-pred_notouch-s1` (champion): runs/step8/pred_notouch_s1/best_genome.npy
- `8b-pep_motion-s13` (champion): runs/step8b/pep_motion_s13/best_genome.npy
- `8b-nopep_motion-s26` (champion): runs/step8b/nopep_motion_s26/best_genome.npy
- `8b-pep_blind-s20` (champion): runs/step8b/pep_blind_s20/best_genome.npy
- `8b-nopep_blind-s31` (champion): runs/step8b/nopep_blind_s31/best_genome.npy
- `8c-pep_motion_dig-s10` (lucky): runs/step8c/pep_motion_dig_s10/best_genome.npy
- `8c-pep_motion_dig-s28` (lucky): runs/step8c/pep_motion_dig_s28/best_genome.npy
- `8c-pep_motion_dig-s19` (lucky): runs/step8c/pep_motion_dig_s19/best_genome.npy
- `8c-nopep_motion_dig-s29` (champion): runs/step8c/nopep_motion_dig_s29/best_genome.npy
- `8c-pep_blind_dig-s28` (lucky): runs/step8c/pep_blind_dig_s28/best_genome.npy
- `8c-pep_blind_dig-s19` (lucky): runs/step8c/pep_blind_dig_s19/best_genome.npy
- `8c-pep_blind_dig-s10` (lucky): runs/step8c/pep_blind_dig_s10/best_genome.npy
- `8c-nopep_blind_dig-s11` (champion): runs/step8c/nopep_blind_dig_s11/best_genome.npy
- `3e-hunger_move0.25-s22` (champion): runs/step3e/hunger_move0.25_s22/best_genome.npy
- `3e-nohunger_move0.25-s22` (champion): runs/step3e/nohunger_move0.25_s22/best_genome.npy
- `3e-hunger_move0.5-s14` (champion): runs/step3e/hunger_move0.5_s14/best_genome.npy
- `3e-nohunger_move0.5-s11` (champion): runs/step3e/nohunger_move0.5_s11/best_genome.npy
- `3e-hunger_move1.0-s14` (champion): runs/step3e/hunger_move1.0_s14/best_genome.npy
- `3e-nohunger_move1.0-s6` (champion): runs/step3e/nohunger_move1.0_s6/best_genome.npy
- `3e-hunger_move2.0-s14` (champion): runs/step3e/hunger_move2.0_s14/best_genome.npy
- `3e-nohunger_move2.0-s20` (lucky): runs/step3e/nohunger_move2.0_s20/best_genome.npy
- `3e2-hunger_move0.25-s16` (champion): runs/step3e2/hunger_move0.25_end_s16/best_genome.npy
- `3e2-nohunger_move0.25-s9` (champion): runs/step3e2/nohunger_move0.25_end_s9/best_genome.npy
- `3e2-hunger_move0.5-s24` (champion): runs/step3e2/hunger_move0.5_end_s24/best_genome.npy
- `3e2-nohunger_move0.5-s31` (champion): runs/step3e2/nohunger_move0.5_end_s31/best_genome.npy
- `3e2-hunger_move1.0-s14` (champion): runs/step3e2/hunger_move1.0_end_s14/best_genome.npy
- `3e2-nohunger_move1.0-s8` (lucky): runs/step3e2/nohunger_move1.0_end_s8/best_genome.npy
- `3e2-nohunger_move1.0-s26` (lucky): runs/step3e2/nohunger_move1.0_end_s26/best_genome.npy
- `3e2-nohunger_move1.0-s14` (lucky): runs/step3e2/nohunger_move1.0_end_s14/best_genome.npy
- `3e2-hunger_move2.0-s14` (champion): runs/step3e2/hunger_move2.0_end_s14/best_genome.npy
- `3e2-nohunger_move2.0-s13` (lucky): runs/step3e2/nohunger_move2.0_end_s13/best_genome.npy

## Brain types

- **worm2**: Step 2-3 connectome brain (ecosim/worm2.py; GPU: gpu_brains.Worm2Brain)
- **worm3**: Step 4 growing brain (ecosim/worm3.py; GPU: gpu_brains.GrowBrain)
- **worm5**: Step 5 learning brain (ecosim/worm5.py)
- **worm2_open**: Step 3 open-readout brain (decoder reads all 300 neurons; cannot be converted)
- **worm6**: Step 6 learning brain + memory-pool genes (ecosim/worm6.py; GPU: step9_gpu.LearnBrainTorch, no memory)

A genome runs as-is only on its own brain type. `lineages.convert(g, to)` moves synapses and
decoder exactly and approximates the rest (details in ecosim/lineages.py).
