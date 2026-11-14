# Main Experiment (Step 20): a more realistic connectome worm brain

*Written 2026-11-13 for anyone picking this up. Code: `ecosim/step20.py`, `ecosim/gpu_brains.py` (Worm2Brain),
`ecosim/worm2.py` (Opts), `ecosim/batch3_fast.py` (deadline). Watcher jobs: `connectome_main`, `connectome_analyze`.*

## 1. What question it answers
The connectome brain (real C. elegans wiring, Cook et al. 2019) was simplified in two ways that matter:
1. **No reversal potentials.** A synapse's current was `weight x presynaptic activity`, no matter how depolarised the
   receiving neuron already was. Real synapses push the neuron toward a fixed voltage (the reversal potential), so
   excitation weakens as the neuron fills up, and inhibition (GABA) clamps toward a low voltage.
2. **No muscles.** Movement was read by an evolved "decoder" from 28 interneurons. The real worm moves through its
   motor neurons and 95 body-wall muscles, which are already in the wiring data but were never read.
**Question:** does adding either (or both) make the worms evolve into better foragers, worse ones, or no different?

## 2. What changed in the brain (both switches OFF = the old model, bit-for-bit)
| switch (worm2.Opts) | default | what it does (gpu_brains.Worm2Brain.step) |
|---|---|---|
| `reversal` | False | synaptic current = abs(w) x activity x (E_rev - v). E_rev = `e_exc` (+1.0) for excitatory synapses, `e_inh` (-1.0) for inhibitory ones. A synapse is inhibitory if its evolved weight is negative (GABA neurons start negative; evolution can flip any synapse). At rest (v = 0) the current equals the old one; the difference is saturation and shunting as v rises. |
| `e_exc`, `e_inh` | 1.0, -1.0 | reversal potentials in model units (rest = 0, activity saturates around v = 2) |
| `muscle_out` | False | speed from the mean activation of all 95 body-wall muscles; reversals from AVA minus AVB command activity; steering from dorsal minus ventral head muscles (worms crawl on their side, so dorsal/ventral bending = left/right turns on the plate). Each of the 3 signals has an evolvable gain (genome: first 3 decoder "dev" genes x 10) and bias (the 3 decoder biases). The other decoder genes are ignored but kept, so genomes stay the same size. |
Still simplified (documented, not hidden): unitless rate model; one time constant (tau = 3 ticks) for everything; the
global-inhibition stand-in for unlabelled synapses stays; muscles are a readout of activation, not a body-wave physics
model; reversals still use the AVA/AVB command neurons because a rate model has no wave direction to read.

## 3. The experiment
- 2 x 2 factorial, 4 arms: `s20_old`, `s20_rev`, `s20_mus`, `s20_both`. Same 16 seeds in every arm (paired by seed).
- World and scoring = Step 19 base: scarce food, 6 predators, touch, hunger peptide on, fitness = energy at the end +
  survival, each brain scored as 60 clones in a full-size world. To fit before 19:00: 12 brains per seed, 1 world per
  generation, best brain of each seed saved every 10 generations (`runs/step20/<arm>_s<seed>/ckpt_g<N>.npy`).
- All 4 arms run AT THE SAME TIME as 4 worker processes (`python -m ecosim.step20 all --until 1900`), so they get the
  same wall-clock time. Arms with reversal potentials are ~35 % slower per generation (one extra synapse product), so
  they reach fewer generations; the analysis therefore compares every arm at the LAST generation ALL arms reached.
- GPU use measured: 99 % busy, ~70 C, ~334 W, 9.8 of 10.2 GB memory (incl. desktop). Exclusive watcher job.

## 4. Pre-registered rule (fixed before the run, 2026-11-13 15:50 MT)
Yardstick = skill on 12 fixed unseen worlds (4000-4011), 60 clones each, of each seed's best brain at the common last
checkpoint. Main effect of a feature = mean over seeds of ((with it) - (without it)) averaged over the other feature.
Sign-flip permutation test, Holm correction over the 2 main effects. HELPS = effect > 0 and Holm p < 0.05; HURTS =
effect < 0 and Holm p < 0.05; otherwise "no detectable effect at this length" (not "no effect").

## 5. How to run / stop / resume / analyse
- Start: queue `{"experiment": "connectome_main", "args": {"gens": 1000, "until": "1900"}}` (or use the GUI).
- Stop: watcher `CANCEL`. The parent process keeps a heartbeat file (`runs/step20/_heartbeat`); workers stop by
  themselves within one generation + 90 s once it goes stale, and save their results. No orphan processes.
- Deadline: workers check the clock before every generation and stop cleanly at `until`.
- There is no mid-run resume for these clonal runs (only best brains are checkpointed); a new run starts fresh.
- Analyse: queue `{"experiment": "connectome_analyze"}` -> `results/step20_stats.txt`, `step20_stats.json`, `step20.png`.
- Quick code check (CPU ok): `STEP20_TEST=1 python -m ecosim.step20 all --gens 2` (2 seeds x 2 brains).

## 6. Results
Stopped at 19:00 on 2026-11-13 after 187.7 minutes. The old-synapse arms reached about 246 generations, the
reversal-potential arms about 190. All four were compared at generation 190, the last checkpoint every arm saved.

| arm | skill (12 unseen worlds) | food | bites |
|---|---|---|---|
| s20_old | 2.652 | 7.60 | 1.22 |
| s20_rev | 2.791 | 7.52 | 1.22 |
| s20_mus | 2.164 | 7.06 | 0.82 |
| s20_both | 2.019 | 7.05 | 0.77 |

- **Reversal potentials: no detectable effect** (main effect -0.003, positive in 8/16 seeds, Holm p = 0.97).
  With the decoder output alone it looks slightly better (+0.14), with muscle output slightly worse (-0.15).
- **Muscle output: HURTS** at this length (main effect -0.630, positive in 0/16 seeds, Holm p = 0.0001).
- Interaction -0.28 (p = 0.028, secondary): reversal potentials help less (or hurt) when combined with muscle output.
- Muscle-output worms were bitten less (0.8 vs 1.2) and ate less: they move less, not smarter.
How to read it: this does NOT show that real muscles are worse than a decoder. It shows that THIS muscle readout
(3 gains on mean muscle activation, AVA-AVB, head dorsal-ventral) gives evolution far fewer and weaker handles than a
decoder with 168 weights reading 28 interneurons, and ~190 generations was not enough to build drive through the
motor circuit. Next steps worth testing: longer runs; start muscle synapses stronger; a body model where alternating
dorsal/ventral activation produces thrust.
