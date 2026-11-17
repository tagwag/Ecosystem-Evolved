# Status board (shared by all Claude sessions working on this repo)

**Every session: read this file and PROJECT_NOTES.txt before starting, update both when you finish something.**
Sessions can't see each other's chats; this file and the git history are how they stay in sync.

## RULE (owner, 2026-11-13 21:40): everything runs on the workstation
Unless the owner explicitly says otherwise, ALL experiments AND all code tests run on this workstation (RTX 3080),
through the watcher (python/remote). Nothing is run in the cloud - not even tiny code checks. Every experiment has a
`*_check` watcher job for that (e.g. `gravity_check`, `reward_hacking_check`). Cloud sessions may edit code, read
results and write documents only.

## RULE (owner, 2026-11-16 12:04): shortest jobs first
Queue experiments in order of expected run time, shortest first (code checks, being minutes long, always go first).
Since 2026-11-17 the WATCHER enforces this itself (sorts by est_minutes every time it starts a job; see
python/remote/README.md). Give every new experiment an est_minutes line in experiments.toml.

## GPU (the user's RTX 3080 desktop) — one experiment at a time
Before launching anything on the GPU, check this section. If a run is listed as RUNNING, queue behind it
(or ask the user) instead of starting a second run: two runs at once both slow down.

| Status | What | Started | Launcher | Log | Est. done |
|---|---|---|---|---|---|
| DONE 07:07 | e3 Step 23 light-gravity arm: H5 skill +1.24 (16/16, Holm p 0.0001), H6 sense NOT used (p 0.13) | 06:08 | watcher | results/step23_stats.txt | done |
| DONE 09:40 | e4 gravity bite test (step24): with 5x cost + sensing worms AVOID heavy ground (+0.195, 14/16, Holm p 0.00045); base and blind: nothing | 07:07 | watcher | results/step24_stats.txt | done |
| DONE 09:39 | code checks: knockout, beacon, fleeing food passed (fleeing-food ratio fix re-checked as k13); combo_check FAILED calibration (intact worms 1.6 % / 14 % arrival) | 09:34 | watcher | remote/logs | done |
| DONE 11:51 | e5 beacon_pilot: smell steers most (+0.017, 14/16); then dopamine, predator, O2; gravity weakest (ranking only) | 09:44 | watcher | results/step25_pilot_stats.txt | done |
| DONE 12:42 | e7b combo screen (Step 28): AVEL only breaking single; 82 confirmed epistatic pairs, 5,683 triples; nearly all involve decoder-read neurons | 11:51 | watcher | results/step28_b4_stats.txt | done |
| DONE 17:23 | e10 eroding gravity (Step 29): NULL - erosion rate does not change avoidance; all arms avoid unseen heavy ground equally | 12:42 | watcher | results/step29_stats.txt | done |
| DONE 18:27 | e6 knockout guide (Step 26): 7/300 single removals change skill; validation vs real worms FAILED (model, not worm) | 17:23 | watcher | results/step26_stats.txt, docs/KNOCKOUT_GUIDE.md | done |
| DONE 03:34 | e8 fleeing food (Step 27): DESIGN FAILURE - worms evolved to stop moving in every moving-food arm (reward hacking); tests meaningless | 18:27 | watcher | results/step27_stats.txt | done |
| RUNNING 03:34 | e9 beacon_full (Step 25), 13 arms x 300 gens, ~13.5 s/gen | 03:34 | watcher | remote/logs/e9_beacon_full.txt | ~18:40 Tue |
| QUEUED (in order) | k17 knockout_pairs_check, k18 fleeing_food2_check (minutes) -> e11 knockout_pairs (98 L+R pairs, ~21 min) -> e12 fleeing_food2 (Step 27b: fixed fleeing food + drift world, 7 arms, ~8 h) | 09:30 | watcher | remote/logs | ~03:20 Wed |

**GPU runs now go through the remote watcher (python/remote): drop a job file in remote/queue/, read remote/status.json.**

## Latest results (one line each; details in PROJECT_NOTES.txt)
- 2026-11-17 FLEEING FOOD (step27): failed as designed - even half-speed food was uncatchable (flee radius 40), so worms evolved to stand still and starve slowest (reward hacking). Needs a redesign.
- 2026-11-16 KNOCKOUT GUIDE (step26): 293/300 neurons removable without detectable skill change; smell-off sensors (ASER, AWCR) + AIY/AIZ/AIB matter; real-worm validation FAILED.
- 2026-11-16 ERODING GRAVITY (step29): no effect of erosion rate; worms avoid never-seen heavy ground as well as their own -> they react to the sense, not to places.
- 2026-11-16 CORRIDOR SCREEN (step28, every single/pair/triple, 4 brains): only AVEL breaks navigation alone; 82 pairs and
  5,683 triples confirmed epistatic (RIAL in most); almost all involve neurons the motor decoder reads = readout artefact.
- 2026-11-16 BEACON PILOT (step25, 50 gens): smell steers most; dopamine/predator/O2 next; gravity/light/CO2 weakest.
- 2026-11-16 index_add speed-up 1.29x but not reproducible -> not adopted (dense default kept).
- 2026-11-16 GRAVITY BITE TEST (step24): worms DO evolve to avoid heavy ground when it is costly (5x) and sensed
  (+0.195, 14/16, Holm p 0.00045); Step 21 rules and blind worms: no response. Erosion experiment now justified.
- 2026-11-16 STEP 23 LIGHT GRAVITY at food: skill +1.24 (16/16) but the gravity sense is NOT used: physics, not cue.
- 2026-11-15 FOOD CIRCLES (step23, 16 seeds x 300 gens): gravity wells at food HURT skill (-0.78, 0/16, Holm p 0.0002)
  but those brains USE the gravity sense (sense cut -0.36, 13/16, Holm p 0.003) = first evolved use of a gravity cue.
  Magnetic circles: no detectable effect, sense not used. Decoys: neither sought nor avoided.
- 2026-11-15 STEP 20b FAIR MUSCLE RE-TEST (same decoder, read muscles vs interneurons, 16 seeds x 300 gens): muscles
  still HURT (-0.61, 2/16 seeds, p 0.0014). Step 20's result was not just the knob count.
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
