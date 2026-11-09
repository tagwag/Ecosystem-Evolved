# Teacher experiment: teacher

Does chasing learning progress across a pool of worlds keep evolution climbing, and make worms better on worlds they never trained in?

300 generations per arm, blocks of 10. Time: 259 min.

Intelligence = skill on holdout worlds never trained in (rich_food, many_predators, few_big_patches, light_zones). Pool skill = skill across the training worlds (base, scarce, moving_food, fast_predators, toxin, temperature).

## Yardstick over time

| generation | teacher intelligence | teacher pool skill | random intelligence | random pool skill | fixed intelligence | fixed pool skill |
|---|---|---|---|---|---|---|
| 50 | 2.554 | 1.938 | 2.758 | 1.965 | 2.906 | 2.105 |
| 100 | 2.674 | 1.947 | 2.584 | 2.021 | 2.984 | 2.131 |
| 150 | 2.402 | 1.907 | 2.458 | 1.908 | 2.833 | 2.147 |
| 200 | 2.405 | 1.832 | 2.557 | 1.959 | 2.880 | 2.155 |
| 250 | 2.422 | 1.839 | 2.382 | 1.904 | 3.032 | 2.253 |
| 300 | 2.456 | 1.853 | 2.390 | 1.765 | 2.944 | 2.203 |

## Teacher vs the others (end, paired by seed)

- teacher_vs_random, intelligence: 2.456 vs 2.390 (diff +0.066, teacher better in 3/8 seeds, p = 0.62)
- teacher_vs_random, pool_skill: 1.853 vs 1.765 (diff +0.088, teacher better in 3/8 seeds, p = 0.604)
- teacher_vs_fixed, intelligence: 2.456 vs 2.944 (diff -0.487, teacher better in 0/8 seeds, p = 0.0081)
- teacher_vs_fixed, pool_skill: 1.853 vs 2.203 (diff -0.350, teacher better in 1/8 seeds, p = 0.0147)

## Where the teacher sent the worms

- base: 5 blocks
- scarce: 1 blocks
- moving_food: 2 blocks
- fast_predators: 9 blocks
- toxin: 10 blocks
- temperature: 3 blocks

Chart: teacher.png