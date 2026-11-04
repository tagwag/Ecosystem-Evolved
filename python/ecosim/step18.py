"""Step 18: selfish herd + OBSTACLES. Can worms evolve to hide from predators behind rock?

World = Step 14b herd world (scarce food, 6 predators that chase loners and miss in crowds, touch, worm scent) plus
pillars, walls and caves (C-shaped walls with an opening). Rock blocks worms and predators, and predators can't see
prey through it. A worm that bumps into rock feels it through its nose-touch neurons (FLP, OLQ), so "stay by the
wall" is a behaviour evolution can find. ~3-4% of the area is rock.

    o18_herd    herd predators + obstacles
    o18_plain   ordinary predators + obstacles      (does hiding need the herd rules?)
    o18_noobs   herd predators, no obstacles         (control, fresh run)

32 seeds x 150 generations, clonal-group scoring, best brain saved every 10 generations. Hiding = more time near
rock (fraction of time within 16 units of rock) than at generation 10, and fewer bites than without rock.

    python -m ecosim.step18 quick     python -m ecosim.step18 run     python -m ecosim.step18 analyze
"""
import dataclasses
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

SEEDS, GENS, EVERY, GROUP = list(range(1, 33)), 150, 10, 10
OUT, RES = Path('runs/step18'), Path('results')
ARMS = {'o18_herd': dict(s14.B_ARMS['h14_herd'], obstacles=True),
        'o18_plain': dict(s14.B_ARMS['h14_plain'], obstacles=True),
        'o18_noobs': dict(s14.B_ARMS['h14_herd'])}
for _c, _o in ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_c] = _o


def run(seeds=SEEDS, gens=GENS, out=OUT):
    from .batch3_fast import evolve
    for c in ARMS:
        evolve(c, seeds, gens, out=out, checkpoint_every=EVERY, clonal=GROUP)


def analyze(seeds=SEEDS, gens=GENS, out=OUT, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    C = {c: s14.curves(c, seeds, gens, conn, dev, out) for c in ARMS}
    last = lambda c, k='fitness': C[c][1][k][-1]
    first = lambda c, k='fitness': C[c][1][k][0]
    st = {c: dict(checkpoints=C[c][0], skill=C[c][1]['fitness'].mean(1).round(4).tolist(),
                  nn=C[c][1]['nn'].mean(1).round(2).tolist(), bites=C[c][1]['bites'].mean(1).round(4).tolist(),
                  near_wall=np.nanmean(C[c][1]['wall'], 1).round(4).tolist()) for c in ARMS}
    for c in ('o18_herd', 'o18_plain'):
        st[f'{c}_near_wall_last_vs_first'] = paired(last(c, 'wall'), first(c, 'wall'))
        st[f'{c}_bites_last_vs_first'] = paired(last(c, 'bites'), first(c, 'bites'))
    for x, y in (('o18_herd', 'o18_noobs'), ('o18_herd', 'o18_plain')):
        st[f'{x}_vs_{y}'] = {k: paired(last(x, k), last(y, k)) for k in ('fitness', 'bites', 'nn', 'food')}
    st['o18_herd_vs_o18_plain']['near_wall'] = paired(last('o18_herd', 'wall'), last('o18_plain', 'wall'))
    # does time near rock go with fewer bites? (across the 32 evolved o18_herd brains)
    from scipy.stats import spearmanr
    r, p = spearmanr(last('o18_herd', 'wall'), last('o18_herd', 'bites'))
    st['o18_herd_wall_vs_bites_spearman'] = dict(rho=float(r), p=float(p))
    st['note'] = 'paired(): "hunger" = first argument, "nohunger" = second. near_wall = fraction of time within 16 units of rock'
    (RES / f'step18{tag}_stats.json').write_text(json.dumps(st, indent=1))
    (RES / f'step18{tag}_curves.json').write_text(json.dumps(
        {c: dict(checkpoints=C[c][0], **{k: v.tolist() for k, v in C[c][1].items()}) for c in ARMS}))
    print(json.dumps({k: v for k, v in st.items() if k not in ARMS}, indent=1), flush=True)
    fig, axes = plt.subplots(1, 4, figsize=(20, 4.4))
    for c in ARMS:
        for ax, k in zip(axes, ('fitness', 'bites', 'nn', 'wall')):
            v = C[c][1][k]
            if k == 'wall' and np.isnan(v).all():
                continue
            m, se = np.nanmean(v, 1), np.nanstd(v, 1) / np.sqrt(len(seeds))
            ax.errorbar(C[c][0], m, yerr=1.96 * se, marker='o', capsize=3, lw=2, label=c)
    for ax, t in zip(axes, ('true skill', 'predator bites per worm', 'nearest-worm distance (lower = clumped)',
                            'fraction of time near rock')):
        ax.set_title(t); ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle(f'Step 18: selfish herd + obstacles ({len(seeds)} seeds, 95% CI)')
    fig.tight_layout(); fig.savefig(RES / f'step18{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if sys.argv[1] == 'quick':
        q = Path('runs/step18_quick')
        run([1, 2], 10, q); analyze([1, 2], 10, q, '_quick')
    else:
        {'run': run, 'analyze': analyze}[sys.argv[1]]()
