"""Step 10 (diagnostic): why does fitness drift DOWN after ~generation 20 (seen in Step 8, all arms)?

World: Step 8 without predators (hunger peptide, scarce food, fitness = energy left at end + survival).
    A  current method: each brain scored on 1 world per generation, 150 generations
    B  each brain scored on 3 worlds per generation (average), 150 generations
Both save every seed's best brain every 10 generations. analyze() re-tests every saved brain on the
same 6 fixed unseen worlds (60 copies each), which removes luck: that is each checkpoint's TRUE skill.

Reading the result:
    true skill falls in A        -> evolution really goes backward (noisy selection lets worse brains win)
    true skill flat/rising in A  -> the falling curve was only noise in the training scores
    B better than A              -> averaging over worlds is the fix

    python -m ecosim.step10 run       (~30 min on an RTX 3080: A ~6 min, B ~18 min)
    python -m ecosim.step10 analyze   -> results/step10_*
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
GENS, EVERY = 150, 10
OUT, RES = Path('runs/step10'), Path('results')
TEST_WORLDS = list(range(2000, 2006))
ARMS = {'A': 1, 'B': 3}                     # arm -> worlds per evaluation
COND = 'diag_nopred'
CONDITIONS[COND] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
CFG_OVERRIDES[COND] = dict(SCARCE)


def run(gens=GENS, seeds=SEEDS):
    from .batch3_fast import evolve
    for arm, W in ARMS.items():
        evolve(COND, seeds, gens, out=OUT / arm, eval_worlds=W, checkpoint_every=EVERY)


def test_brains(genomes, conn, dev):
    """True skill: each genome on the same fixed test worlds, 60 copies each. genomes: list -> list of fitness."""
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[COND], Config(**CFG_OVERRIDES[COND])
    P = cfg.worm_population
    pairs = [(i, wd) for i in range(len(genomes)) for wd in TEST_WORLDS]
    G = np.stack([np.repeat(genomes[i][None], P, 0) for i, _ in pairs])
    gen = torch.Generator(device=dev); gen.manual_seed(4242)
    sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
    fit, _ = sim.run(G, [np.random.default_rng(wd) for _, wd in pairs])
    per = fit.mean(1).reshape(len(genomes), len(TEST_WORLDS))
    return per.mean(1)


def analyze(seeds=SEEDS, gens=GENS):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    cks = list(range(EVERY, gens + 1, EVERY))
    true, train = {}, {}
    for arm in ARMS:
        true[arm] = np.array([test_brains([np.load(OUT / arm / f'{COND}_s{s}' / f'ckpt_g{g}.npy') for s in seeds], conn, dev)
                              for g in cks])                                        # (checkpoints, seeds)
        train[arm] = np.array([[h['fitness'] for h in json.loads((OUT / arm / f'{COND}_s{s}' / 'history.json').read_text())]
                               for s in seeds])                                     # (seeds, gens)
        print(arm, 'true skill by checkpoint:', np.round(true[arm].mean(1), 3).tolist(), flush=True)
    i20 = cks.index(20) if 20 in cks else 1
    stats = {arm: dict(true_by_checkpoint=dict(zip(map(str, cks), true[arm].mean(1).round(4).tolist())),
                       gen20_vs_last=paired(true[arm][-1], true[arm][i20]),
                       peak_checkpoint=int(cks[int(np.argmax(true[arm].mean(1)))]))
             for arm in ARMS}
    stats['B_vs_A_last'] = paired(true['B'][-1], true['A'][-1])
    (RES / 'step10_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    cols = {'A': '#d6612a', 'B': '#2a78d6'}
    for arm in ARMS:
        axes[0].plot(train[arm].mean(0), color=cols[arm], lw=1.5, label=f'{arm}: training score ({ARMS[arm]} world/gen)')
        m, se = true[arm].mean(1), true[arm].std(1) / np.sqrt(len(seeds))
        axes[1].errorbar(cks, m, yerr=1.96 * se, color=cols[arm], marker='o', capsize=4, lw=2,
                         label=f'{arm}: true skill of best brain (6 fixed worlds)')
    axes[0].set_ylabel('population mean fitness during evolution'); axes[1].set_ylabel('fitness on fixed test worlds')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle('Step 10: does evolution really go backward after gen ~20? (32 seeds, no predators)')
    fig.tight_layout(); fig.savefig(RES / 'step10.png', dpi=130); plt.close(fig)


def head_to_head(arm='A', early=30, late=150, seeds=SEEDS):
    """Tragedy-of-the-commons check: early and late best brains share each test world, 30 copies each.
    Late brains beating early ones head-to-head, while doing worse alone, = selection for competing."""
    from .batch3_fast import FastSim
    from .config import Config
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    opts, cfg = CONDITIONS[COND], Config(**CFG_OVERRIDES[COND])
    P, half = cfg.worm_population, cfg.worm_population // 2
    pairs = [(s, wd) for s in seeds for wd in TEST_WORLDS]
    G = np.stack([np.concatenate([np.repeat(np.load(OUT / arm / f'{COND}_s{s}' / f'ckpt_g{early}.npy')[None], half, 0),
                                  np.repeat(np.load(OUT / arm / f'{COND}_s{s}' / f'ckpt_g{late}.npy')[None], P - half, 0)])
                  for s, _ in pairs])
    gen = torch.Generator(device=dev); gen.manual_seed(99)
    fit, _ = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen).run(G, [np.random.default_rng(wd) for _, wd in pairs])
    e = fit[:, :half].mean(1).reshape(len(seeds), -1).mean(1)
    l = fit[:, half:].mean(1).reshape(len(seeds), -1).mean(1)
    alone_e = test_brains([np.load(OUT / arm / f'{COND}_s{s}' / f'ckpt_g{early}.npy') for s in seeds], conn, dev)
    alone_l = test_brains([np.load(OUT / arm / f'{COND}_s{s}' / f'ckpt_g{late}.npy') for s in seeds], conn, dev)
    out = dict(arm=arm, early=early, late=late,
               mixed_late_vs_early=paired(l, e), alone_late_vs_early=paired(alone_l, alone_e))
    print(json.dumps(out, indent=1), flush=True)
    return out


if __name__ == '__main__':
    if sys.argv[1] == 'h2h':
        RES.mkdir(exist_ok=True)
        r = {arm: head_to_head(arm) for arm in ARMS}
        (RES / 'step10_h2h.json').write_text(json.dumps(r, indent=1))
        sys.exit()
    if sys.argv[1] == 'quick':                  # smoke test on the GPU: 2 seeds, 20 generations, both arms
        OUT = Path('runs/step10_quick'); RES = Path('runs/step10_quick')
        run(20, [1, 2]); analyze([1, 2], 20)
    else:
        {'run': run, 'analyze': analyze}[sys.argv[1]]()
