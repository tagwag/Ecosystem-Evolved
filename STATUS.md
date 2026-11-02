# Status board (shared by all Claude sessions working on this repo)

**Every session: read this file and PROJECT_NOTES.txt before starting, update both when you finish something.**
Sessions can't see each other's chats; this file and the git history are how they stay in sync.

## GPU (the user's RTX 3080 desktop) — one experiment at a time
Before launching anything on the GPU, check this section. If a run is listed as RUNNING, queue behind it
(or ask the user) instead of starting a second run: two runs at once both slow down.

| Status | What | Started | Launcher | Log | Est. done |
|---|---|---|---|---|---|
| RUNNING | Step 11: clonal-group scoring + worm scent (2 arms x 32 seeds x 150 gens) | 2026-11-02 ~16:05 MT | run_step11.bat | step11_log.txt | ~17:30 MT |

## Latest results (one line each; details in PROJECT_NOTES.txt)
- Steps 3d-8c (GPU, 32 seeds): peptide = movement "off switch", never a clear fitness gain; in 8c it traps 2/3 of seeds in a freeze.
- Step 4g: growth neutral (p=0.99). Step 3f: ASH alarm null. Step 8: predators costly, touch gives no escape.
- Step 6b (12 seeds): curriculum hint was noise, memory null. Step 9: see PROJECT_NOTES.
- Step 10: the late decline is a TRAGEDY OF THE COMMONS: evolution selects food-competitive brains that do worse as a group
  (late beat early head-to-head 30/32, but alone are worse 29/32). Fair tests used clones = measured something else. Fix pending.

## How to run things
- GPU code: python/ecosim/batch3_fast.py (worm2 + growing brains, predators, digestion, alarm), launchers python/*.bat
- Results land in python/results/; long runs log to python/*_log.txt (ignored by git)
- Pinned (not started): IDE-like experiment app (config-file runner, then GUI). See PROJECT_NOTES.
