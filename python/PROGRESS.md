# Progress log

## 2026-10-31

### Step 1: evolvable run-and-tumble bacteria ✅
- Bodies follow the rules from `Cell.java`: speed = -5/8000·size + 5, size +10 per food, food = 100 energy.
- Cells sense only the smell **concentration** at their own position, with no food directions (fixes "too smart" from `Notes`).
- Brain: 4 inputs (smell, smell change, energy, bias) → 4 recurrent hidden → tumble probability + swim speed.
- Evolution: leaderboard (top 20%) + Gaussian mutation, one seeded RNG.
- **Result (30 generations, 120 cells):** average food per cell rose 1.8 → 7.0, passing the random walk (~5.4) by generation ~22.
- **Fair test** (best genome vs random walk, 10 unseen worlds, same layouts): **10.3 vs 6.2 food = 1.67×**.
- Files: `results/step1_*`.

### Step 2: real C. elegans brain ✅
- `ecosim/connectome.py` loads the Cook et al. 2019 hermaphrodite wiring (OpenWorm c302 data, MIT):
  300 neurons + 95 body-wall muscles, 4,562 chemical synapses, 2,365 gap junctions.
- Graded rate model; GABAergic neurons (DD, VD, RME, AVL, DVB, RIS) inhibit.
- Sensors: ASEL (concentration up), ASER/AWC (down), AWA (level).
  Motor: AVB vs AVA → forward speed / reversal ("pirouette"); dorsal vs ventral head muscles → steering.
- Genome = one multiplier per chemical synapse (4,562 genes) + 6 gains.
- Stabilized: the raw wiring saturated (94–100% of neurons on). Fixed with input normalization, global
  inhibition, an evolvable sign/strength gene per synapse (silence = ×0, flip = ×−1), and an evolvable
  motor decoder that reads 28 known locomotion neurons.
- Structural mutations: tweak, gain, silence, restore, flip a synapse, knock out a neuron. Every child
  logs its mutations so selection can be measured.
- **Result (40 generations, 60 worms):** mean food 8.0 → 19.0; random walk stays around 6–7.
  The big jump happens in generations 0–5, then a slow climb.
- **What evolution changed** (`results/step2_mutations.md`, `results/step2_brain.png`, `results/step2_brain_evolution.gif`):
  - Mostly **pruning**: 104 synapses weakened and 43 silenced, vs 37 strengthened and 7 flipped.
  - Largest single cut: AIYL → AWAL silenced. AIY is a known chemotaxis interneuron.
  - Sensor gains: the **OFF sensor (ASER/AWC, "smell getting weaker") evolved highest at ×6.5**, above ON (×2.9).
    Real worms do the same: a drop in odor triggers turning ("pirouettes").
  - The motor decoder rediscovered real biology: **AVB → faster and fewer reversals**; **AVD → slower**.
    In real worms AVB drives forward motion and AVA/AVD drive backing up.
- Ecosystem mode (`ecosim/ecosystem.py`): no generations; cells split when well fed and children carry
  mutated brains. `ecosim/lineage.py` traces survivors' family trees and shows which mutation types
  were kept vs weeded out.
- Visual tools (run locally, no AI cost): `ecosim/brainviz.py` (brain picture + per-generation GIF), `plot.py`, `replay.py`.
- **Fair test** (10 unseen worlds): evolved worm brain **26.8 food vs random 6.2 = 4.4×** (Step 1 tiny brain: 1.7×).
- **Ecosystem run** (30,000 ticks, worm brains, `results/eco_lineage.*`): population held steady at about 40 with 620 births.
  Survivors are about 14 generations from their founders.
  Flips and restores were mildly weeded out (kept 0.8× as often as chance); silencing and knockouts were neutral to slightly kept.
  The sample is small (105 ancestral births), so this is a hint, not a result. A longer run is needed.
