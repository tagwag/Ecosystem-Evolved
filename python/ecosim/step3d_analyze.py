"""Analyze Step 3d (batch3_fast confirm: hunger vs no hunger, scarce food, seeds 1-32) on the GPU.

Same tests as step3_analyze (Step 3b/3c), run with batch3_fast so all 64 brains x 6 worlds
are tested at once:
1. Fair test: each seed's best brain on the same 6 unseen worlds (2000-2005), 60 copies each.
2. Satiety quiescence: the brain's own speed command when full (>= 80% gut) vs hungry (< 40%).
3. Paired stats over seeds (same seed = same starting worlds for both conditions):
   sign-flip permutation test and bootstrap 95% interval of the mean difference.

    python -m ecosim.step3d_analyze            -> results/step3d_*.json / .png
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from .batch3_fast import FastSim, OUT
from .config import Config
from .connectome import Connectome
from .step3 import CONDITIONS, CFG_OVERRIDES
from .worm2_gpu import pick_device

RES = Path('results')
WORLDS = list(range(2000, 2006))
SEEDS = list(range(1, 33))
CONDS = ('hunger_scarce', 'nohunger_scarce')
TAG = 'step3d'


def fair_all(cond, seeds, conn, dev, out=OUT):
    """Every seed's best genome on every test world, in one GPU batch. Returns {seed: dict}."""
    opts, cfg = CONDITIONS[cond], Config(**CFG_OVERRIDES.get(cond, {}))
    P = cfg.worm_population
    best = {s: np.load(out / f"{cond}_s{s}" / "best_genome.npy") for s in seeds}
    pairs = [(s, wd) for s in seeds for wd in WORLDS]
    genomes = np.stack([np.repeat(best[s][None], P, 0) for s, _ in pairs])
    gen = torch.Generator(device=dev); gen.manual_seed(12345)
    sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
    _, stats = sim.run(genomes, [np.random.default_rng(wd) for _, wd in pairs])
    out = {}
    for s in seeds:
        st = [stats[i] for i, (ss, _) in enumerate(pairs) if ss == s]
        fits = [x['fitness'] for x in st]
        out[s] = dict(fitness=float(np.mean(fits)), fitness_sd=float(np.std(fits)),
                      food=float(np.mean([x['mean_food'] for x in st])),
                      speed_full=float(np.nanmean([x['speed_full'] for x in st])),
                      speed_hungry=float(np.nanmean([x['speed_hungry'] for x in st])),
                      bites=float(np.mean([x.get('bites', 0.0) for x in st])),
                      nn_dist=float(np.mean([x.get('nn_dist', np.nan) for x in st])))
    return out


def paired(a, b):
    diff = a - b
    rng = np.random.default_rng(0)
    flips = rng.choice([-1, 1], (20000, len(diff)))
    p = float((np.abs((flips * diff).mean(1)) >= abs(diff.mean())).mean())
    boot = rng.choice(diff, (20000, len(diff))).mean(1)
    return dict(mean_hunger=float(a.mean()), mean_nohunger=float(b.mean()), mean_diff=float(diff.mean()),
                ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                hunger_wins=int((diff > 0).sum()), p_value=p, n=len(diff))


def main():
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    fair = {c: fair_all(c, SEEDS, conn, dev) for c in CONDS}
    (RES / f'{TAG}_results.json').write_text(json.dumps({'fair': fair}, indent=1))
    stats = {}
    for name, f in (('energy', lambda v: v['fitness']), ('food', lambda v: v['food']),
                    ('full_over_hungry', lambda v: v['speed_full'] / v['speed_hungry'])):
        a = np.array([f(fair['hunger_scarce'][s]) for s in SEEDS])
        b = np.array([f(fair['nohunger_scarce'][s]) for s in SEEDS])
        ok = np.isfinite(a) & np.isfinite(b)
        stats[name] = paired(a[ok], b[ok])
        if name == 'full_over_hungry':
            stats[name]['hunger_below_1'] = int((a[ok] < 1).sum())
            stats[name]['nohunger_below_1'] = int((b[ok] < 1).sum())
    (RES / f'{TAG}_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for cond, col in (('hunger_scarce', '#2a78d6'), ('nohunger_scarce', '#999999')):
        H = np.array([[g['fitness'] for g in json.loads((OUT / f'{cond}_s{s}' / 'history.json').read_text())] for s in SEEDS])
        ax.plot(H.mean(0), color=col, lw=2, label=cond.replace('_scarce', '') + f' (mean of {len(SEEDS)} seeds)')
        ax.fill_between(range(H.shape[1]), np.percentile(H, 10, 0), np.percentile(H, 90, 0), color=col, alpha=0.15)
    ax.set_xlabel('generation'); ax.set_ylabel('average energy held (food units)')
    ax.set_title('Step 3d: hunger peptide vs none, scarce food (band = 10th-90th percentile)')
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / f'{TAG}_progress.png', dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for cond, col in (('hunger_scarce', '#2a78d6'), ('nohunger_scarce', '#999999')):
        x = np.array([fair[cond][s]['fitness'] for s in SEEDS])
        y = np.array([fair[cond][s]['speed_full'] / fair[cond][s]['speed_hungry'] for s in SEEDS])
        ax.scatter(x, y, color=col, label=cond.replace('_scarce', ''), alpha=0.8)
    ax.axhline(1, color='k', lw=1)
    ax.set_xlabel('fair-test energy held'); ax.set_ylabel('speed when full / when hungry\n(below 1 = slows when full)')
    ax.set_title('Step 3d: each dot = one seed\'s best brain'); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / f'{TAG}_quiescence.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    main()
