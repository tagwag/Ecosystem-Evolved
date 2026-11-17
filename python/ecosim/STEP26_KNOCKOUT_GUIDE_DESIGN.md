# Step 26 (DESIGN, not built yet): single-neuron knockout guide
Written 2026-11-16 07:40 MT. Goal: **a guide to what happens when each neuron is removed, one at a time.**
Status: design only. Nothing below has been coded or run.

## 1. Terms
- **Knockout / ablation:** removing a neuron. Real-worm equivalent: killing one cell with a laser (laser ablation).
- **Removed** (what this design does): the neuron's activity is held at 0 and ALL its chemical synapses and gap
  junctions, in and out, are cut. Matches laser ablation.
- **Silenced** (not done here): activity held at rest but gap junctions left in place, so it still drags its gap-junction
  partners toward rest. Possible follow-up.
- **Acute vs developmental:** acute = remove the neuron from an already-evolved brain (what does that brain depend on?).
  Developmental = evolve brains that never had it (can evolution work around it?). Developmental for 300 neurons would be
  ~300 x 45 min = ~9 days of GPU, so this design is ACUTE; developmental only for a shortlist later.

## 2. Brains tested
- Phase 1: the 16 best brains of Step 23 control (s23_ctrl, generation 300): the plain Main Experiment world.
- Phase 2 (after Step 25 exists): the Step 25 brains, so the guide can also say which neurons each sense's steering
  needs (steering index per knockout).
- Every one of the model's ~300 neurons, one at a time (muscles excluded). Left and right partners (e.g. AVAL, AVAR)
  separately, as asked. Expect small effects for many paired neurons because the partner covers; pairs (~150) are the
  obvious follow-up.

## 3. Measures (each knockout vs the same intact brains on the same worlds)
60 clones x 12 fixed unseen worlds per brain. For every neuron: skill, food eaten, survival, speed, reversal rate,
turn rate, time on food, predator bites. Differences paired over the 16 brains.

## 4. Rules to fix before the run (draft)
- ~300 tests per measure, so false positives are certain without correction: **Benjamini-Hochberg false discovery rate
  5 %** per measure (Holm would be too strict to find anything at this scale).
- **Validation checks** against real-worm ablation results, decided in advance:
  - AVA removal should cut backward movement / reversals (Chalfie et al. 1985, J Neurosci 5:956).
  - AFD removal should remove the temperature (and in this model magnetic) input (Mori & Ohshima 1995, Nature 376:344).
  - ASE removal should weaken chemotaxis (Bargmann & Horvitz 1991, Neuron 7:729).
  If the model fails these, the guide says so on its first page: it then describes this model, not the worm.
- Known artefact, flagged in the guide: the motor decoder reads 28 neurons directly (AVA, AVB, AVD, AVE, PVC, AIB, AIY,
  AIZ, RIA, RIM pairs + SMD/RMD). Removing one of those also removes a decoder input, so their effects are partly the
  readout design.

## 5. Output: the guide
- `results/step26_knockouts.csv`: one row per neuron, every measure, effect, p, FDR-adjusted p.
- `docs/KNOCKOUT_GUIDE.md` (+ a Findings Book chapter, + PDF): neurons grouped by type (sensory / interneuron / motor),
  each with a plain-words line ("without AVAL: 40 % fewer reversals, skill -0.3"), sorted by effect size, plus a chart.
- Possible later: a GUI page where you click a neuron and see what its removal does.

## 6. Cost
Measured: testing 16 brains on 12 worlds takes about 70 s on the RTX 3080 (from the e3 analysis: 11 such tests in
~13 min). ~300 neurons + the intact baseline = **~6 h** on the workstation, one job, safe to stop and resume
(each neuron's result saved as it finishes). Building: a removal mask in `gpu_brains.Worm2Brain` (activity and both
weight matrices), `ecosim/step26.py`, watcher jobs `knockout_check`, `knockout_guide`. Under one session of coding.

## 7. Results (run 2026-11-16 17:23-18:27 MT on the workstation, ~12.6 s per neuron)
Built and run as designed (phase 1): 300 neurons removed one at a time from the 16 best Step 23 control brains,
12 unseen worlds x 60 clones, paired over brains, Benjamini-Hochberg 5 % per measure. Files:
`python/results/step26_stats.txt`, `step26_knockouts.csv` (every neuron, every measure, p and q), `step26.png`,
and the plain-words guide `docs/KNOCKOUT_GUIDE.md`.

Intact brains: skill 2.678, food 7.26, survivors 13.0 of 60, speed 0.574, reversals 0.029 per tick.

| Measure | Knockouts that change it (q < 0.05) | Biggest |
|---|---|---|
| skill | 7 | AIYR -0.61, AIZR -0.40, AIZL -0.38, AWCR -0.34, ASER -0.31, AIBR -0.28, PVCL -0.23 |
| food | 2 | ASER -0.63, SIBDR +0.17 |
| survivors | 2 | AWCR -2.2, ASER -1.8 |
| speed | 1 | AFDR +0.011 |
| reversals, turning, time near food, bites | 0 | - |

- **Robust to single losses:** 293 of 300 neurons can be removed with no detectable change in skill.
- **What matters:** the smell neurons that report smell FALLING (ASER, AWCR; in this model ASER and AWC are the
  "off" sensors) and the interneurons that turn smell into steering (AIY, AIZ, AIB). Near misses (not significant
  after correction): AIYL -0.74 (q 0.08), AVEL -0.52 (q 0.07; the only single that broke corridor navigation in
  Step 28), RIAL -0.35 (q 0.34; the hub of the Step 28 combinations).
- 5 of the 7 significant neurons are read directly by the motor decoder (readout-artefact caveat, as in Step 28).
- **Validation against real worms FAILED (pre-registered):** removing AVAL or AVAR did not reduce reversals
  (-0.0007 / -0.0011, q 0.99), and removing ASEL did not lower food (+0.35, q 0.16; the opposite direction).
  Likely reasons: one-sided removal (the partner AVAR/AVAL covers), and in this model reversals come from the decoder
  reading many neurons, not from AVA alone; ASEL here reports smell RISING, and losing it may be harmless because
  ASER/AWC carry the "falling" signal the evolved brains actually use. **So this guide describes the model, not
  C. elegans.** A paired (left + right) knockout run (~150 pairs, ~30 min) is the natural next check.
