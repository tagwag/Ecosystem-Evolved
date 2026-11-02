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

## GPU (NVIDIA, Windows)
One-time: double-click `setup_gpu.bat` (makes `.venv`, installs PyTorch with CUDA, runs `gpu_check`).

| File | What it does |
|---|---|
| `ecosim/worm2_gpu.py` | Step 3 worm brain in PyTorch (same equations as `worm2.py`) |
| `ecosim/batch3_fast.py` | Fastest: `batch3_gpu` + CUDA graphs + sparse synapse math. Use this one. |
| `ecosim/batch3_gpu.py` | Step 3 with brains AND world on the GPU, many seeds at once (reference for batch3_fast) |
| `ecosim/batch3.py` | Step 3 with brains on the GPU, world in NumPy (middle step, kept for checking) |
| `ecosim/gpu_check.py` | Checks the GPU, compares CPU vs GPU brain, times both |

```
python -m ecosim.batch3_fast confirm                         # Step 3d: hunger vs no hunger, seeds 1-32
python -m ecosim.batch3_fast run hunger_scarce 1 2 3 4 --gens 60
python -m ecosim.batch3_fast bench                           # speed test
python -m ecosim.step3 run hunger_scarce 1 --gpu             # old single-run code, brain on GPU
```
Or double-click `run_gpu_confirm.bat`. Results: `runs/step3_fast/`.

Speed (seconds per seed per generation, RTX 3080 / i9-10900K, 2026-11-02):
original CPU 8.0 | brain on GPU 3.3 | everything on GPU 0.75 (8 seeds), 0.20 (32)
| + CUDA graphs 0.13 (8 seeds), 0.076 (32), 0.063 (128 seeds).
Above ~32 seeds the synapse math is the limit (the GPU is fully busy). Use many seeds per batch.

Results are float32 and eating is resolved in parallel, so GPU runs match CPU runs statistically,
not number for number. Compare GPU runs with GPU runs. A seed reproduces only with the same seed list.

## Terms
- **Genome**: the list of numbers that defines one brain (here: one gene per synapse + a few gains).
- **Connectome**: a full wiring map of a nervous system.
- **Chemotaxis**: moving up or down a chemical gradient (smell).
- **Run-and-tumble**: swim straight, randomly re-orient, re-orient more often when things get worse.
- **Structural mutation**: changes wiring itself (silence, restore, flip a synapse; knock out a neuron),
  not just a strength tweak.

## Data
`data/celegans_herm_edgelist.csv`: Cook et al. 2019, *Nature* 571:63, via OpenWorm c302 (MIT License).
