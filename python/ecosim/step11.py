"""Step 11: clonal-group scoring (the fix for Step 10's tragedy of the commons) + worm-to-worm scent.

Scoring: every brain is scored by a group of 10 copies of itself sharing a world (food scaled to 1/6 so each
worm faces the same scarcity), all groups of a seed in the same world each generation. This stops evolution
from rewarding stealing food from your own kind, and matches the clone-based fair test.

Arms (Step 8 world without predators: peptide on, scarce food, fitness = energy left at end + survival;
32 seeds, 200 generations, best brain saved every 10 generations):
    nopher   clonal scoring only           -> does the late decline from Step 10 go away?
    pher     clonal scoring + worm scent   -> does herding / clumping evolve (nearest-worm distance drops)?
             Scent = blurred density of living worms; level -> ASK, rising -> ADLL, falling -> ADLR
             (real C. elegans sense ascaroside pheromones mainly through ASK and ADL).

    python -m ecosim.step11 quick     (GPU smoke test, 2 seeds, 10 generations)
    python -m ecosim.step11 run       (~2 hours on an RTX 3080)
    python -m ecosim.step11 analyze   -> results/step11_*

Clumping is measured as the average distance from each living worm to its nearest living neighbour
(lower = more clumped). Worms crowd on food patches anyway, so compare pher vs nopher, not absolute values.
"""
import dataclasses
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from .step3 import CONDITIONS, CFG_OVERRIDES, SCARCE

SEEDS = list(range(1, 33))
GENS, EVERY, GROUP = 200, 10, 10
OUT, RES = Path('runs/step11'), Path('results')
TEST_WORLDS = list(range(2000, 2006))
ARMS = {'nopher': False, 'pher': True}
for _a, _p in ARMS.items():
    CONDITIONS[f'clonal_{_a}'] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[f'clonal_{_a}'] = dict(SCARCE, pheromone=_p)


def run(gens=GENS, seeds=SEEDS, out=None):
    from .batch3_fast import evolve
    for a in ARMS:
        evolve(f'clonal_{a}', seeds, gens, out=out or OUT, checkpoint_every=EVERY, clonal=GROUP)


def test_brains(cond, genomes, conn, dev):
    """True skill + clumping: each genome as 60 clones on the fixed test worlds (normal food)."""
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[cond], Config(**CFG_OVERRIDES[cond])
    P = cfg.worm_population
    pairs = [(i, wd) for i in range(len(genomes)) for wd in TEST_WORLDS]
    G = np.stack([np.repeat(genomes[i][None], P, 0) for i, _ in pairs])
    gen = torch.Generator(device=dev); gen.manual_seed(4242)
    fit, st = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen).run(G, [np.random.default_rng(wd) for _, wd in pairs])
    nw = len(TEST_WORLDS)
    f = fit.mean(1).reshape(len(genomes), nw).mean(1)
    nn = np.array([x['nn_dist'] for x in st]).reshape(len(genomes), nw).mean(1)
    food = np.array([x['mean_food'] for x in st]).reshape(len(genomes), nw).mean(1)
    return f, nn, food


def analyze(seeds=SEEDS, gens=GENS, out=None):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    out = out or OUT
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    cks = list(range(EVERY, gens + 1, EVERY))
    T = {}
    for a in ARMS:
        c = f'clonal_{a}'
        rows = [test_brains(c, [np.load(out / f'{c}_s{s}' / f'ckpt_g{g}.npy') for s in seeds], conn, dev) for g in cks]
        T[a] = dict(fit=np.array([r[0] for r in rows]), nn=np.array([r[1] for r in rows]), food=np.array([r[2] for r in rows]))
        print(a, 'true skill by checkpoint:', np.round(T[a]['fit'].mean(1), 3).tolist(), flush=True)
        print(a, 'nearest-worm distance by checkpoint:', np.round(T[a]['nn'].mean(1), 1).tolist(), flush=True)
    i20 = cks.index(20) if 20 in cks else 0
    stats = {a: dict(true_by_checkpoint=dict(zip(map(str, cks), T[a]['fit'].mean(1).round(4).tolist())),
                     nn_by_checkpoint=dict(zip(map(str, cks), T[a]['nn'].mean(1).round(2).tolist())),
                     last_vs_gen20=paired(T[a]['fit'][-1], T[a]['fit'][i20]),
                     peak_checkpoint=int(cks[int(np.argmax(T[a]['fit'].mean(1)))])) for a in ARMS}
    stats['pher_vs_nopher_fitness_last'] = paired(T['pher']['fit'][-1], T['nopher']['fit'][-1])
    stats['pher_vs_nopher_nn_last'] = paired(T['pher']['nn'][-1], T['nopher']['nn'][-1])
    stats['pher_vs_nopher_food_last'] = paired(T['pher']['food'][-1], T['nopher']['food'][-1])
    stats['note'] = 'paired(): "hunger" = first argument, "nohunger" = second (field names reused)'
    tag = 'step11' if out == OUT else 'step11_quick'
    (RES / f'{tag}_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    cols = {'nopher': '#999999', 'pher': '#2a78d6'}
    for a in ARMS:
        for ax, key in ((axes[0], 'fit'), (axes[1], 'nn')):
            m, se = T[a][key].mean(1), T[a][key].std(1) / np.sqrt(len(seeds))
            ax.errorbar(cks, m, yerr=1.96 * se, color=cols[a], marker='o', capsize=4, lw=2,
                        label=('worm scent' if a == 'pher' else 'no scent'))
    axes[0].set_ylabel('true skill of best brain (60 clones, 6 fixed worlds)')
    axes[1].set_ylabel('nearest-worm distance (lower = more clumped)')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend()
    fig.suptitle('Step 11: clonal-group scoring, with and without worm-to-worm scent (32 seeds, 95% CI)')
    fig.tight_layout(); fig.savefig(RES / f'{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if sys.argv[1] == 'quick':
        q = Path('runs/step11_quick')
        run(10, [1, 2], out=q); analyze([1, 2], 10, out=q)
    else:
        {'run': run, 'analyze': analyze}[sys.argv[1]]()
