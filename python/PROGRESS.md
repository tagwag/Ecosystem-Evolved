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
- **Long ecosystem run** (150,000 ticks, seed 2, `results/eco_long_lineage.*`): 2,664 births. Survivors are about 64 generations deep.
  Every mutation type was kept at 1.0–1.24× chance. The 30k-run hint (flips weeded out) **did not replicate**.
  Reading: one structural mutation is usually close to **neutral**. Survival here is decided mostly by chance
  (genetic drift) plus the slow build-up of small tweaks, not by single big rewiring events.
  This matches real neutral evolution theory. Next test: harsher food scarcity to make selection stronger.
- **Scarcity test** (food regrowth 0.6 → 0.45 per tick):
  - Random-brain founders went **extinct** by tick about 2,100 (and by tick about 3,000 under harsher settings).
  - Founders given the **evolved worm brain survived all 150,000 ticks** (population about 30, 1,895 births, about 75 generations deep).
    Evolved wiring is the difference between extinction and survival.
  - Mutation survival under scarcity: **silencing a synapse was weeded out (0.82×)**; flips and restores were neutral (about 1.07×).
    Once a brain is tuned, cutting connections tends to hurt. Under easy conditions it was neutral (1.01×).
    Still a modest effect from one run; it needs repeat seeds to confirm.
- **Repeat seeds (4 total) under scarcity:** the evolved-brain populations **survived in all 4** (about 30 alive each, 1,800–1,950 births).
  Silencing ratio across seeds: 0.82, 1.10, 0.93, 1.13 (mean about 1.0), so the "silencing weeded out" result **did not replicate**.
  Knockouts swing 0.51–1.77 because they are rare (a handful per run).
  **Conclusion:** with this setup, no single structural mutation type is consistently favoured or removed. Single-run ratios
  vary by ±20% from chance alone. The robust finding is at the brain level, not the mutation level: evolved wiring survives scarcity
  and random wiring does not.
  To find mutation-level effects: many more seeds, or measure each mutation's direct fitness effect (mutate → test → compare).
- **Direct mutation test** (`ecosim/mutation_effects.py`, `results/step2_mutation_effects.md`): 24 single-mutation copies per type,
  each tested on the same worlds as the unmutated brain.
  - **Every type averages within ±0.15 food of no change**, while chance alone moves scores ±2.4. Almost every mutant falls in the noise band.
  - So the evolved worm brain is **robust to single mutations** (biology term: *mutational robustness*). One rewired synapse out of
    4,562 rarely matters, which is why the lineage tests saw neutral ratios.
  - Largest single effects (unconfirmed, near the noise limit): flip SIADL→SIBDL +7.1, restore LUAR→PVR −5.0, knockout ASGR −4.7.
  - Better resolution needs more test agents per mutant, or larger mutations (several synapses or a whole neuron's outputs at once).
- **Neuron knockout map** (`ecosim/knockout_map.py`): each of 295 neurons switched off one at a time.
  - First run showed huge "gains" from removing VD neurons. That was a **bug**: the last test batch had fewer worms, so less
    competition for food. Fixed by padding every batch to the same size.
  - Corrected map: 1 harmful and 8 helpful outliers out of 295, about what chance alone produces.
  - **Fair-test check** (each knockout alone, 40 worms, 6 worlds; normal brain = 26.96 ± 0.52): SIBDR 26.89, DA08 26.96,
    AVEL 27.42, DVA 26.97, AINR 27.39, AVAL 27.08, AVBL 27.18, AIYL 26.96. **No single neuron matters.**
    Even the command neurons AVA/AVB can each be removed, because their left/right partner and the other readout neurons cover for them.
  - Lesson: the mixed-population quick tests are too noisy to rank single changes. Rankings must be confirmed with the fair test.
  - **Overall Step 2 conclusion:** evolved C. elegans wiring is **highly redundant**. Performance comes from many small,
    spread-out changes, not from a few key synapses or neurons. That matches real worms, which survive many single-neuron ablations.

### Step 3: hunger peptide + open readout (2026-10-31 evening)
Code: `ecosim/worm2.py` (model), `ecosim/step3.py` (runs: `python -m ecosim.step3 all`), `ecosim/step3_analyze.py` (fair tests + charts).
Setup: 3 conditions x 4 seeds x 40 generations, 60 worms. Gut limit 1,500 energy (a full worm can't eat).
Hunger peptide H rises as energy falls, drops at each meal, and is broadcast to every neuron through an evolvable
receptor gene per neuron (all start at 0). Decoder now also reads raw neuron levels so slow signals can matter.

- **Q1 Hunger peptide: NO effect in this setup.** Fair test (6 unseen worlds), fitness = average energy held:
  hunger 3.9 / 6.7 / 6.3 / 5.9 (mean 5.7) vs no hunger 7.4 / 8.0 / 6.1 / 5.9 (mean 6.8). Random walk 2.5.
  Satiety quiescence did not emerge: speed command full ÷ hungry = 1.03 / 0.91 / 1.16 / 1.02 (hunger) vs
  1.07 / 1.08 / 1.07 / 1.10 (no hunger). Below 1 would mean slowing down when full.
  Receptor genes drifted (40-50% changed) with no shared pattern across seeds = **genetic drift, no selection**.
  **Likely cause (design flaw):** food is too plentiful. The trace (`results/step3_hunger_trace.png`) shows the evolved
  worm stays almost full the whole run (H near 0), so the hunger signal barely varies and there is nothing to learn from.
  Fix to test next: scarcer or seasonal food so worms actually get hungry, and longer runs.
- **Q2 Open readout: NO, evolution did not pick the command neurons.** With all 300 neurons available, AVA/AVB/AVD
  rank around the middle (40-199 of 300; mostly near chance). Evolution read the **sensory neurons and first
  interneurons** instead: ASE, AWC, AWA (smell sensors) and AIY, AIA, AIZ (first relay). It takes a **shortcut**
  around the command layer. Known-locomotion neurons in the top 28: 4-5 per seed vs about 2.6 by chance.
  Food: 17-23 per worm vs random walk 4.9, so the shortcut works.
  This weakens the Step 2 claim that the decoder "rediscovered" AVB-forward: that only happened when we
  hand-picked the readout. The real chemotaxis pathway (ASE/AWC -> AIY/AIZ) did show up, which is a fairer result.

### Step 3b: hunger peptide under scarce food (food regrowth 0.6 -> 0.2, 60 generations, 4 seeds)
Run: `python -m ecosim.step3 scarce`, analysis `python -m ecosim.step3_analyze scarce` -> `results/step3b_*`.
- Correction to Step 3: with plentiful food the population was hungry ~30% of the time, not "almost never" (that came
  from one long-lived worm). Under scarcity, evolved worms are hungry ~45% of the time.
- **Energy held (fair test):** hunger 5.42 / 5.60 / 5.66 / 5.61 (mean 5.57) vs no hunger 4.90 / 5.35 / 5.52 / 5.65 (mean 5.36).
  Random walk 2.4. Hunger ahead in 3 of 4 seeds by ~4%.
- **Quiescence (speed full ÷ hungry):** hunger 0.94 / 0.89 / 0.95 / 1.03 (mean 0.95) vs no hunger 1.04 / 0.92 / 1.12 / 1.08 (mean 1.04).
  First time the direction matches real worms (slow down when full), but small.
- **Verdict: weak hint, not confirmed.** Needs 10-12 seeds per side.

### Step 4: brain growth (python -m ecosim.step4 all / analyze -> results/step4_*)
Model `ecosim/worm3.py`: 50 empty neuron slots. Growth mutations: duplicate a neuron (inputs copied, outputs and
readout split half/half -> near-neutral; tested: smaller effect than one round of synapse tweaks), blank new neuron
(3 weak in, 3 weak out), new weak synapse. Same world and food fitness as Step 2. 60 generations, 4 seeds each.
- **Food (fair test, 6 unseen worlds):** growth 27.2 / 26.9 / 26.8 / 26.6 (mean 26.9) vs no growth 25.7 / 27.3 / 25.7 / 24.9
  (mean 25.9). Random walk 7.0. Growth ahead in 3 of 4 seeds by ~4%, within the per-world spread (±0.5-1.9).
- **Brains did grow, slowly:** top-20% brains gained 3.5-5.6 neurons in 3 seeds, 0.75 in seed 4. Best final brains:
  0-5 new neurons and 8-16 new synapses. Grown neurons were copies of VA12, SMBDR, SMDDR, I1L, IL2VL, RMDL, VC02,
  ADEL, AWCR, IL1R, plus 3 blank ones: no shared pattern across seeds.
- **Selection:** every growth type reached the top 20% at ~0.2 of attempts (duplicate 0.16-0.20, new neuron 0.15-0.27,
  new synapse 0.17-0.19) = exactly the chance rate (elite fraction 0.2). **Growth is neutral; it accumulates by drift.**
- **Behaviour** (speed, reversals, turning): no consistent difference between growth and no-growth brains.
- **Pushback on the food gap:** in the progress chart the growth runs pull ahead by generation ~4-10, before brains had
  grown even one neuron on average. So the small gap is more likely seed luck than an effect of growth.
- **Verdict:** adding neurons this way neither helps nor hurts in this world; they ride along as neutral passengers,
  consistent with Step 2's mutational robustness. To make growth matter, the world needs a job the existing brain
  can't do (e.g. a new sense to wire in, or a predator) - which is exactly the later experiments.
