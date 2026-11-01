# Ecosystem-Evolved — Work Report (Oct 31, 2026, 14:39 → 16:41)

Source: `python/PROGRESS.md` and the git log. 15 commits.

## Bottom line

- A **real C. elegans brain** (300 neurons, 4,562 synapses) now drives cells in your sim, and evolution tunes it.
- Evolved worm brain finds **4.4× more food** than random movement. The tiny hand-built brain only managed 1.7×.
- Under food scarcity, **evolved brains survive; random brains go extinct.**
- The evolved brain is **highly redundant**: no single synapse or neuron matters. Performance comes from many small, spread-out changes, the same as in real worms.

## What was built

| Piece | File | What it does |
|---|---|---|
| Bacteria brain (Step 1) | `ecosim/evolve.py` | 4-input recurrent net, run-and-tumble movement, body rules ported from `Cell.java` |
| Worm brain (Step 2) | `ecosim/connectome.py` | Loads the Cook 2019 wiring (OpenWorm c302 data); smell sensors in, AVA/AVB + head muscles out |
| Structural mutations | `ecosim/connectome.py` | Tweak, gain, silence, restore, flip a synapse; knock out a neuron. Every child logs its mutations |
| Ecosystem mode | `ecosim/ecosystem.py` | No generations: cells eat, split, mutate, die continuously |
| Family-tree analysis | `ecosim/lineage.py` | Which mutation types survivors kept vs lost |
| Direct mutation test | `ecosim/mutation_effects.py` | Mutate → test on same worlds → compare |
| Knockout map | `ecosim/knockout_map.py` | Switch off each of 295 neurons, one at a time |
| Visual tools | `brainviz.py`, `plot.py`, `replay.py` | Brain picture, rewiring GIF, progress chart, replay video. Run locally, no AI cost |

## Results

**Step 1 — bacteria brain:** food per cell 1.8 → 7.0 over 30 generations. Fair test: 10.3 vs 6.2 random (**1.7×**).

![Step 1 progress](python/results/step1_progress.png)

**Step 2 — worm brain:** food 8.0 → 19.0 over 40 generations; most of the gain in generations 0–5. Fair test: 26.8 vs 6.2 (**4.4×**).

![Step 2 progress](python/results/step2_progress.png)
![Evolved worm brain](python/results/step2_brain.png)
![Rewiring over generations](python/results/step2_brain_evolution.gif)

**What evolution changed:**
- Mostly **pruning** (104 weakened + 43 silenced vs 37 strengthened + 7 flipped).
- The **"smell getting weaker" sensor evolved strongest** (×6.5 vs ×2.9). Real worms turn when odor drops.
- The motor readout **rediscovered real biology**: AVB → forward, AVD → slow/back up.

**Ecosystem runs (natural selection, no generations):**
- 150,000 ticks, 2,664 births, survivors ~64 generations deep. Every mutation type kept at roughly chance rate → single mutations are **near-neutral** (genetic drift dominates).
- Scarcity: random-brain founders extinct by ~tick 2,100. Evolved-brain founders survived all 150,000 ticks, **in 4 of 4 seeds**.
- An early "silencing gets weeded out" hint **did not replicate** across seeds. Dropped.

**Robustness tests:**
- Single mutations: every type averages within ±0.15 food of no change (noise is ±2.4). Term: **mutational robustness**.
- Neuron knockouts: after fixing a crowding bug in the test, **no single neuron changes performance**, not even command neurons AVA/AVB. Their left/right partners cover for them.

## Bug found and fixed

The knockout map first showed big "gains" from removing VD neurons. Cause: the last test batch had fewer worms, so less competition for food. Fixed by padding every batch to equal size.

## Lessons

- Mixed-population quick tests are too noisy to rank single changes. Confirm with the fair test (same worlds, same crowding).
- To find mutation-level effects you need bigger mutations (a whole neuron's outputs, several synapses) or many more test runs.

## Logical next steps (not started)

1. Larger mutations: duplicate/delete whole neurons (neuroevolution of structure).
2. Internal states (hunger, fatigue) as brain inputs.
3. Swap in the fruit fly connectome (FlyWire / MaleCNS) once the worm pipeline is settled. Needs the RTX 2080.
