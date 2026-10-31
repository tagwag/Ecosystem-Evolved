# Ecosystem (Python port) — evolvable brains

## Setup (once)
```
pip install numpy scipy matplotlib
```
(For videos, also install **ffmpeg**.)

## PyCharm (one-time)
1. Open the `Ecosystem-Evolved` folder in PyCharm.
2. Bottom-right corner → **Add Interpreter → Add Local Interpreter → Virtualenv → New** → OK.
3. Open `python/requirements.txt` → click **Install requirements** in the yellow bar.
4. Top-right run menu: pick a ready-made run (1 Evolve worm brain, 2 Brain picture + GIF, ...) → green ▶.
   Outputs land in `python/runs/...`.

## What's here
| File | What it does |
|---|---|
| `ecosim/config.py` | Every tunable number (world size, food, energy, mutation rates) |
| `ecosim/world.py` | Food patches, the smell field, eating (fast grid lookup) |
| `ecosim/brain.py` | Step 1 brain: tiny recurrent network (run-and-tumble) |
| `ecosim/connectome.py` | Step 2 brain: real C. elegans wiring (300 neurons, 95 muscles) + structural mutations |
| `ecosim/sim.py` | One generation: move, burn energy, eat, grow, die |
| `ecosim/evolve.py` | Generation-based evolution with a leaderboard + random-walk comparison |
| `ecosim/ecosystem.py` | Open-ended mode: cells split when well fed, children carry mutated brains |
| `ecosim/benchmark.py` | Fair test: one genome vs the random walk on identical worlds |
| `ecosim/analyze.py` | Which synapses/neurons evolution changed in a worm brain |
| `ecosim/plot.py`, `replay.py` | Chart and side-by-side video |
| `ecosim/brainviz.py` | Picture/GIF of which synapses evolution changed |

## Run it (from this `python/` folder)
```
python -m ecosim.evolve --generations 60                     # Step 1, tiny brain
python -m ecosim.evolve --brain worm --generations 40 --out runs/worm   # Step 2, C. elegans
python -m ecosim.plot runs/worm                              # chart -> runs/worm/progress.png
python -m ecosim.analyze runs/worm                           # mutation report -> mutations.md
python -m ecosim.replay runs/worm worm                       # video -> runs/worm/replay.mp4
python -m ecosim.ecosystem --brain worm --ticks 20000        # open-ended ecosystem
```
Each evolution line prints the generation's average food eaten next to a random walk's on the
same settings. Evolution is working when the evolved number pulls ahead.

## Terms
- **Genome**: the list of numbers that defines one brain (here: one gene per synapse + a few gains).
- **Connectome**: a full wiring map of a nervous system.
- **Chemotaxis**: moving up or down a chemical gradient (smell).
- **Run-and-tumble**: swim straight, randomly re-orient, re-orient more often when things get worse.
- **Structural mutation**: changes wiring itself (silence, restore, flip a synapse; knock out a neuron),
  not just a strength tweak.

## Data
`data/celegans_herm_edgelist.csv`: Cook et al. 2019, *Nature* 571:63, via OpenWorm c302 (MIT License).
