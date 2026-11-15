# Status board (shared by all Claude sessions working on this repo)

**Every session: read this file and PROJECT_NOTES.txt before starting, update both when you finish something.**
Sessions can't see each other's chats; this file and the git history are how they stay in sync.

## RULE (owner, 2026-11-13 21:40): everything runs on the workstation
Unless the owner explicitly says otherwise, ALL experiments AND all code tests run on this workstation (RTX 3080),
through the watcher (python/remote). Nothing is run in the cloud - not even tiny code checks. Every experiment has a
`*_check` watcher job for that (e.g. `gravity_check`, `reward_hacking_check`). Cloud sessions may edit code, read
results and write documents only.

## GPU (the user's RTX 3080 desktop) — one experiment at a time
Before launching anything on the GPU, check this section. If a run is listed as RUNNING, queue behind it
(or ask the user) instead of starting a second run: two runs at once both slow down.

| Status | What | Started | Launcher | Log | Est. done |
|---|---|---|---|---|---|
| QUEUED 2026-11-14 22:50 | code checks `food_circles_check`, `muscle_fair_check`; then `muscle_fair` (Step 20b, ~2-3 h) and `food_circles_experiment` (Step 23, ~5 h) | 22:50 | watcher | remote/logs/ | ~07:00 |
| ready, NOT queued | gravity bite test (ecosim/step24.py, watcher gravity_bite_test, ~2.5 h); code check passed 12:19; waiting for the owner's go-ahead | - | - | - | - |

**GPU runs now go through the remote watcher (python/remote): drop a job file in remote/queue/, read remote/status.json.**

## Latest results (one line each; details in PROJECT_NOTES.txt)
- 2026-11-14 NEW, not run yet: Step 20b FAIR MUSCLE RE-TEST (ecosim/step20b.py): same evolvable decoder reading 28 interneurons
  vs the 95 muscles + AVA/AVB (Step 20's muscle arm had 3 gains vs 168 decoder weights = unfair). Step 23 FOOD-CIRCLE
  GRAVITY & MAGNETISM (ecosim/step23.py, doc STEP23_FOOD_CIRCLES_EXPERIMENT.md): big feathered field circles with food at
  each centre; 5 arms (ctrl / grav food / grav decoy / mag food / mag decoy) x 16 seeds x 300 gens; rules pre-registered.
- 2026-11-14 REWARD HACKING EXPERIMENT (step22): command LEARNED. go/no-go index 0.96 (true signal) vs 0.19 scrambled /
  -0.07 none, 16/16 seeds, Holm p 0.0001; obedience test passed; 0/16 seeds hacked. Evolved reflex, not learning.
- 2026-11-14 GRAVITY EXPERIMENT (step21, 100 graded seeds): NO trend (rho +0.10, p 0.33). Gravity as modelled is ignored.
- 2026-11-14 ENGINE: all 15 worlds show the same thrift adaptation; no factor changed the kind of evolution in 50k ticks.
  Equilibrium rule (10 %) fails in 10/15 worlds incl. a no-effect world -> the rule is too tight, re-base before reuse.
- 2026-11-14 PREDICTION (analysis/predict_outcomes.py, 544 runs): arm ranking predictable after 20-50 gens (rho 0.95+);
  single seeds are not (noise ~ seed spread); no model beats persistence.
- 2026-11-13 2nd EXPERIMENT interbreeding (3200 gens, fair test, 10 group means vs reference, Holm over 5 brain types):
  helps ONLY the weakest brain (no_smell+frontal+hippo 31.7 -> 49.9, Holm p 4e-05; one pool 66.0 = 1 replicate, hint).
  Other 4 brain types: no detectable difference. Variety kept ~80x higher, plateau NOT broken (3200 gens = 900 gens).
  repro_share cannot see gene flow (stays 1.00) -> needs a new measure for interbreeding runs.
- 2026-11-13 MAIN EXPERIMENT (ecosim/step20.py, doc ecosim/STEP20_MAIN_EXPERIMENT.md): at gen 190, 16 paired seeds, 12 unseen
  worlds: reversal potentials NO detectable effect (-0.003, Holm p 0.97); muscle output HURTS (-0.63, 0/16 seeds, Holm
  p 0.0001). Not proof muscles are worse: the readout has 3 gains vs 168 decoder weights and starts with little drive.
- NAMES since 2026-11-13 15:50: Main Experiment = connectome brain (step20); 2nd Experiment = toy brain (toybrain/).
- GUI: new Builder tab (step-by-step forms) and Analysis tab (study-grade statistics + experiment key). gui/README.md.
- 2026-11-13: FINDINGS BOOK (Claude Doc "Ecosystem-Evolved: Findings Book") = the readable summary of everything.
- World 19 x 10 copies, 600 gens: frozen steady within 5.5 % (equilibrium PASS); real worms 3x slower than frozen, pop 566
  vs 384, 36 families alive vs 2 under chance (shadow). Head-start test NOT supported (fresh 900 >= 300+600).
- Steps 3d-8c (GPU, 32 seeds): peptide = movement "off switch", never a clear fitness gain; in 8c it traps 2/3 of seeds in a freeze.
- Step 4g: growth neutral (p=0.99). Step 3f: ASH alarm null. Step 8: predators costly, touch gives no escape.
- Step 6b (12 seeds): curriculum hint was noise, memory null. Step 9: see PROJECT_NOTES.
- Step 10: the late decline is a TRAGEDY OF THE COMMONS: evolution selects food-competitive brains that do worse as a group
  (late beat early head-to-head 30/32, but alone are worse 29/32). Fixed with CLONAL-GROUP SCORING (batch3_fast evolve(clonal=10)).
- Step 11: under clonal scoring skill rises to gen ~150 and holds; worm scent gave no herding.
- Step 12: under clonal scoring the 8c freeze trap disappears; the peptide stays neutral-to-harmful; brains slow when
  full without it. Use clonal scoring for new experiments.
- Step 13: old nulls redone under clonal scoring, still null: touch +0.14 (p=0.12), growth neutral (p=0.23).
  Alarm hint only without the peptide (+0.20, p=0.068); peptide hurts when the alarm is on (-0.25, p=0.0085).
- Step 14a: peptide is entrenched (knockout -0.70) but not baggage: knocked-out brains recover in 10 gens.
- Step 14b: selfish-herd predators -> weak clumping (-3.5 vs plain, p=0.051). Step 15: lineage takeover in ~7 gens;
  champions plateau ~3.2, below best founder.
- Steps 16-18: new worlds did NOT break the plateau (all arms fell, even the control: small-world training vs
  full-world test mismatch suspected); champions didn't recover; obstacles -> no hiding (near-rock time flat ~8%).
- Step 19: with matched scoring skill keeps climbing slowly (base 2.54 -> 3.33, still rising); all-senses world no faster.
- Sweep screen1: no factor raised general skill; harsher worlds lowered it (all_senses -0.52, digestion -0.47); test could not pass by design (8 seeds).
- Toy brain (300 gens, 30 lineages): no smell -44 food; bigger brains worse (mutation not scaled by genome size = unfair).
- Teacher (curriculum): lost to a single fixed world (intelligence -0.49, p=0.008); = random rotation. Switching hurt.

## How to run things
- GPU code: python/ecosim/batch3_fast.py (worm2 + growing brains, predators, digestion, alarm), launchers python/*.bat
- Results land in python/results/; long runs log to python/*_log.txt (ignored by git)
- Config-file factor sweeps (= stage 1 of the pinned experiment app): python/sweeps/*.toml + ecosim/sweep.py.
  plan / quick / run / test / analyze / zoom. Resumes: finished arms are skipped. GUI (stage 2) still pinned.
