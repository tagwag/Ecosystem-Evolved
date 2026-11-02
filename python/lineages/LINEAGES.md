# Lucky lineages

Standout evolved brains, kept so any experiment can start from them. Load with
`from ecosim import lineages; g = lineages.load('<name>')`. Rule for adding one: fair-test score in
the top 3 of its condition and at least 2x that condition's median. A genome only runs on its own brain type.

| name | step | condition | seed | score | condition median | brain | notes |
|---|---|---|---|---|---|---|---|
| `6b-puzzle_nomem-s12` | 6b | puzzle_nomem | 12 | 3.35 puzzle food/worm | 0.57 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-puzzle_nomem-s9` | 6b | puzzle_nomem | 9 | 2.68 puzzle food/worm | 0.57 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-puzzle_nomem-s5` | 6b | puzzle_nomem | 5 | 2.52 puzzle food/worm | 0.57 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-puzzle_mem-s8` | 6b | puzzle_mem | 8 | 1.03 puzzle food/worm | 0.48 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6b-puzzle_mem-s9` | 6b | puzzle_mem | 9 | 0.99 puzzle food/worm | 0.48 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6b-curric_nomem-s12` | 6b | curric_nomem | 12 | 2.23 puzzle food/worm | 0.57 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_nomem-s8` | 6b | curric_nomem | 8 | 2.02 puzzle food/worm | 0.57 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_nomem-s6` | 6b | curric_nomem | 6 | 1.8 puzzle food/worm | 0.57 | worm6 | 12 seeds x 100 gens; runs on GPU (step9_gpu) |
| `6b-curric_mem-s10` | 6b | curric_mem | 10 | 2.2 puzzle food/worm | 0.64 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6b-curric_mem-s4` | 6b | curric_mem | 4 | 1.34 puzzle food/worm | 0.64 | worm6 | 12 seeds x 100 gens; uses memory pool (CPU only for now) |
| `6-puzzle_nomem-s2` | 6 | puzzle_nomem | 2 | 1.1 puzzle food/worm | 0.52 | worm6 | 4 seeds x 60 gens: weak median, treat with care; runs on GPU (step9_gpu) |
| `6-puzzle_mem-s2` | 6 | puzzle_mem | 2 | 0.74 puzzle food/worm | 0.36 | worm6 | 4 seeds x 60 gens: weak median, treat with care; uses memory pool (CPU only for now) |
| `6-curric_nomem-s3` | 6 | curric_nomem | 3 | 2.01 puzzle food/worm | 0.88 | worm6 | 4 seeds x 60 gens: weak median, treat with care; runs on GPU (step9_gpu) |
| `6-curric_mem-s2` | 6 | curric_mem | 2 | 2.55 puzzle food/worm | 1.17 | worm6 | 4 seeds x 60 gens: weak median, treat with care; uses memory pool (CPU only for now) |

## Brain types

- **worm2**: Step 2-3 connectome brain (ecosim/worm2.py; GPU: gpu_brains.Worm2Brain)
- **worm3**: Step 4 growing brain (ecosim/worm3.py; GPU: gpu_brains.GrowBrain)
- **worm5**: Step 5 learning brain (ecosim/worm5.py)
- **worm6**: Step 6 learning brain + memory-pool genes (ecosim/worm6.py; GPU: step9_gpu.LearnBrainTorch, no memory)
