# Status board (shared by all Claude sessions working on this repo)

**Every session: read this file and PROJECT_NOTES.txt before starting, update both when you finish something.**
Sessions can't see each other's chats; this file and the git history are how they stay in sync.

## GPU (the user's RTX 3080 desktop) — one experiment at a time
Before launching anything on the GPU, check this section. If a run is listed as RUNNING, queue behind it
(or ask the user) instead of starting a second run: two runs at once both slow down.

| Status | What | Started | Launcher | Log | Est. done |
|---|---|---|---|---|---|
| idle | (last: teacher experiment, finished 2026-11-09 11:16 MT) | | | | |
| QUEUED (user starts it) | Sweep screen1: 8-factor fractional factorial, 16 arms x 8 seeds x 100 gens | - | run_sweep.bat screen1 (waits for STEP19_DONE) | sweep_screen1_log.txt | ~6-10 h after start (estimate, check timing.txt) |

## Latest results (one line each; details in PROJECT_NOTES.txt)
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
- Teacher (curriculum): lost to a single fixed world (intelligence -0.49, p=0.008); = random rotation. Switching hurt.

## How to run things
- GPU code: python/ecosim/batch3_fast.py (worm2 + growing brains, predators, digestion, alarm), launchers python/*.bat
- Results land in python/results/; long runs log to python/*_log.txt (ignored by git)
- Config-file factor sweeps (= stage 1 of the pinned experiment app): python/sweeps/*.toml + ecosim/sweep.py.
  plan / quick / run / test / analyze / zoom. Resumes: finished arms are skipped. GUI (stage 2) still pinned.
