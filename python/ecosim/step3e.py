"""Step 3e: make resting worth it. Does the hunger peptide help once moving is expensive?

Step 3d: the peptide made worms slow down when full, but that cost them energy, because moving was
cheap (move_cost 0.25 per unit of speed) and resting saved almost nothing. Here the same test
(hunger vs no hunger, scarce food, 32 seeds, 60 generations) is repeated at higher movement costs.

    move_cost 0.25  = Step 3d world (baseline, rerun so every point uses the same code)
    move_cost 0.5, 1.0, 2.0 = moving costs 2x, 4x, 8x as much; base cost (0.6/tick) unchanged

    python -m ecosim.step3e run           # evolve all (8 batches of 32 seeds, ~20 min on an RTX 3080)
    python -m ecosim.step3e analyze       # fair test + paired stats per cost -> results/step3e_*

Prediction if "resting doesn't pay" was the reason: the energy gap (hunger - no hunger) turns from
negative toward positive as move_cost rises.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from . import step3
from .step3 import CONDITIONS, CFG_OVERRIDES, SCARCE

MOVE = [0.25, 0.5, 1.0, 2.0]
SEEDS = list(range(1, 33))
GENS = 60
OUT = Path('runs/step3e')
RES = Path('results')


def cname(hunger, m):
    return f"{'hunger' if hunger else 'nohunger'}_move{m}"


for _m in MOVE:                          # register the conditions so batch3_fast / step3d_analyze find them
    for _h in (True, False):
        CONDITIONS[cname(_h, _m)] = CONDITIONS['hunger' if _h else 'nohunger']
        CFG_OVERRIDES[cname(_h, _m)] = dict(SCARCE, move_cost=_m)


def run():
    from .batch3_fast import evolve
    for m in MOVE:
        for h in (True, False):
            evolve(cname(h, m), SEEDS, GENS, out=OUT)


def analyze():
    from .connectome import Connectome
    from .step3d_analyze import fair_all, paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    allfair, stats = {}, {}
    for m in MOVE:
        fh = fair_all(cname(True, m), SEEDS, conn, dev, out=OUT)
        fn = fair_all(cname(False, m), SEEDS, conn, dev, out=OUT)
        allfair[str(m)] = {'hunger': fh, 'nohunger': fn}
        st = {}
        for name, f in (('energy', lambda v: v['fitness']), ('food', lambda v: v['food']),
                        ('full_over_hungry', lambda v: v['speed_full'] / v['speed_hungry'])):
            a = np.array([f(fh[s]) for s in SEEDS]); b = np.array([f(fn[s]) for s in SEEDS])
            ok = np.isfinite(a) & np.isfinite(b)
            st[name] = paired(a[ok], b[ok])
        stats[str(m)] = st
        print(f'move_cost {m}: energy hunger {st["energy"]["mean_hunger"]:.2f} vs {st["energy"]["mean_nohunger"]:.2f} '
              f'(diff {st["energy"]["mean_diff"]:+.2f}, p={st["energy"]["p_value"]:.4f})   '
              f'full/hungry {st["full_over_hungry"]["mean_hunger"]:.3f} vs {st["full_over_hungry"]["mean_nohunger"]:.3f} '
              f'(p={st["full_over_hungry"]["p_value"]:.4f})', flush=True)
    (RES / 'step3e_results.json').write_text(json.dumps(allfair, indent=1))
    (RES / 'step3e_stats.json').write_text(json.dumps(stats, indent=1))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    xs = np.arange(len(MOVE))
    for ax, key, lab in ((axes[0], 'energy', 'energy held: hunger minus no hunger'),
                         (axes[1], 'full_over_hungry', 'full/hungry speed: hunger minus no hunger\n(below 0 = peptide adds slowing)')):
        d = np.array([stats[str(m)][key]['mean_diff'] for m in MOVE])
        lo = np.array([stats[str(m)][key]['ci95'][0] for m in MOVE]); hi = np.array([stats[str(m)][key]['ci95'][1] for m in MOVE])
        ax.errorbar(xs, d, yerr=[d - lo, hi - d], fmt='o', color='#2a78d6', capsize=5, lw=2, ms=7)
        ax.axhline(0, color='k', lw=1)
        for x, m in zip(xs, MOVE):
            ax.annotate(f"p={stats[str(m)][key]['p_value']:.3f}", (x, hi[x]), textcoords='offset points', xytext=(0, 6),
                        ha='center', fontsize=8, color='#555')
        ax.set_xticks(xs, [f'{m}\n({m / 0.25:.0f}x)' for m in MOVE]); ax.set_xlabel('movement cost per unit speed')
        ax.set_ylabel(lab); ax.grid(alpha=0.3)
    fig.suptitle('Step 3e: does the hunger peptide pay off when moving is expensive? (32 seeds, 95% CI)')
    fig.tight_layout(); fig.savefig(RES / 'step3e_sweep.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    {'run': run, 'analyze': analyze}[sys.argv[1]]()
