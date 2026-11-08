# Experiment: brain_dials

Step 19 base-world brains; command-layer gain x serotonin-like modulator x ASH (nociceptor) knockout.

Mode: **behave** (brains + dials -> one lifetime -> behaviour)  
Combinations: 18, time: 4 min

## Factors

- `brain.gain.command`: [0.5, 1.0, 1.5]
- `brain.mod.serotonin`: [0.0, 1.0, 2.0]
- `brain.knockout.ASH`: [0, 1]

## Results per combination

| brain.gain.command | brain.mod.serotonin | brain.knockout.ASH | skill (energy left/100 + survival) | food eaten per worm | predator bites per worm | worms alive at the end |
|---|---|---|---|---|---|---|
| 0.5 | 0.0 | 0 | 2.361 | 6.970 | 1.254 | 11.885 |
| 0.5 | 0.0 | 1 | 2.395 | 7.122 | 1.292 | 12.198 |
| 0.5 | 1.0 | 0 | 2.210 | 6.530 | 1.273 | 10.995 |
| 0.5 | 1.0 | 1 | 2.190 | 6.504 | 1.275 | 10.818 |
| 0.5 | 2.0 | 0 | 1.958 | 5.685 | 1.222 | 9.135 |
| 0.5 | 2.0 | 1 | 1.976 | 5.885 | 1.256 | 9.443 |
| 1.0 | 0.0 | 0 | 2.385 | 7.187 | 1.199 | 12.271 |
| 1.0 | 0.0 | 1 | 2.446 | 7.398 | 1.225 | 12.609 |
| 1.0 | 1.0 | 0 | 2.384 | 7.167 | 1.273 | 12.510 |
| 1.0 | 1.0 | 1 | 2.379 | 7.252 | 1.309 | 12.266 |
| 1.0 | 2.0 | 0 | 2.057 | 6.083 | 1.254 | 10.089 |
| 1.0 | 2.0 | 1 | 2.104 | 6.256 | 1.271 | 10.188 |
| 1.5 | 0.0 | 0 | 0.261 | 1.769 | 0.404 | 0.000 |
| 1.5 | 0.0 | 1 | 0.260 | 1.825 | 0.401 | 0.000 |
| 1.5 | 1.0 | 0 | 2.459 | 7.338 | 1.215 | 12.812 |
| 1.5 | 1.0 | 1 | 2.475 | 7.531 | 1.247 | 13.036 |
| 1.5 | 2.0 | 0 | 2.210 | 6.530 | 1.273 | 10.995 |
| 1.5 | 2.0 | 1 | 2.190 | 6.504 | 1.275 | 10.818 |

## What the quadratic fit says

"Clear" = bigger than twice its uncertainty. Values in the units of each result.

**skill (energy left/100 + survival)**
```
  fit explains 48% of the variation (R^2 = 0.48, 288 data points)
  - raising brain.gain.command decreases it (-0.270 from middle to top of the range)
  - raising brain.mod.serotonin increases it (+0.199 from middle to top of the range)
  - brain.gain.command: peaks inside the tested range (curve -0.380)
  - brain.mod.serotonin: peaks inside the tested range (curve -0.466)
  - brain.gain.command x brain.mod.serotonin: interact (+0.588): the effect of one depends on the other
  - predicted best: brain.gain.command = 0.8, brain.mod.serotonin = 1, brain.knockout.ASH = 1 -> 2.659 (worst in range 0.692)
```
**food eaten per worm**
```
  fit explains 39% of the variation (R^2 = 0.39, 288 data points)
  - raising brain.gain.command decreases it (-0.600 from middle to top of the range)
  - raising brain.mod.serotonin increases it (+0.389 from middle to top of the range)
  - brain.gain.command: peaks inside the tested range (curve -1.041)
  - brain.mod.serotonin: peaks inside the tested range (curve -1.286)
  - brain.gain.command x brain.mod.serotonin: interact (+1.495): the effect of one depends on the other
  - predicted best: brain.gain.command = 0.85, brain.mod.serotonin = 1, brain.knockout.ASH = 1 -> 7.893 (worst in range 2.882)
```
**predator bites per worm**
```
  fit explains 70% of the variation (R^2 = 0.70, 288 data points)
  - raising brain.gain.command decreases it (-0.146 from middle to top of the range)
  - raising brain.mod.serotonin increases it (+0.148 from middle to top of the range)
  - brain.gain.command: peaks inside the tested range (curve -0.139)
  - brain.mod.serotonin: peaks inside the tested range (curve -0.155)
  - brain.gain.command x brain.mod.serotonin: interact (+0.227): the effect of one depends on the other
  - predicted best: brain.gain.command = 0.8, brain.mod.serotonin = 1.2, brain.knockout.ASH = 1 -> 1.411 (worst in range 0.536)
```
**worms alive at the end**
```
  fit explains 44% of the variation (R^2 = 0.44, 288 data points)
  - raising brain.gain.command decreases it (-1.401 from middle to top of the range)
  - raising brain.mod.serotonin increases it (+0.975 from middle to top of the range)
  - brain.gain.command: peaks inside the tested range (curve -2.311)
  - brain.mod.serotonin: peaks inside the tested range (curve -2.937)
  - brain.gain.command x brain.mod.serotonin: interact (+3.415): the effect of one depends on the other
  - predicted best: brain.gain.command = 0.85, brain.mod.serotonin = 1, brain.knockout.ASH = 1 -> 13.874 (worst in range 2.535)
```

Charts: effects.png, surface.png