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

### Step 2: real C. elegans brain (in progress)
- `ecosim/connectome.py` loads the Cook et al. 2019 hermaphrodite wiring (OpenWorm c302 data, MIT):
  300 neurons + 95 body-wall muscles, 4,562 chemical synapses, 2,365 gap junctions.
- Graded rate model; GABAergic neurons (DD, VD, RME, AVL, DVB, RIS) inhibit.
- Sensors: ASEL (concentration up), ASER/AWC (down), AWA (level).
  Motor: AVB vs AVA → forward speed / reversal ("pirouette"); dorsal vs ventral head muscles → steering.
- Genome = one multiplier per chemical synapse (4,562 genes) + 6 gains.
