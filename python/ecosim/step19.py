"""Step 19: does the plateau go away with (a) scoring that matches the test and (b) worlds that use every sense?

Scoring (both arms): each brain = 60 clones in FULL-SIZE worlds (exactly like the fair test), on 2 different worlds
per generation, averaged. 16 seeds x 16 brains, 300 generations, best brain saved every 20 generations.
    s19_base   Step 14 world: scarce food, 6 predators, touch                  -> was the plateau our measuring?
    s19_rich   + worm scent, obstacles (nose touch), and every Step 19 sense with something to sense:
               temperature field (AFD), light zones (ASJ), toxic patches (PHA/PHB), predator scent (ASH),
               CO2 from crowds/food (BAG), O2 lower near food (URX/AQR/PQR), on-food touch (CEP/ADE/PDE)
Yardstick: every checkpoint, 60 clones on 12 fixed unseen worlds (4000-4011) of its own world type.
Plateau test: skill at 300 vs 200 and 200 vs 100 (paired by seed), and each seed's slope over the last 100 gens.

    python -m ecosim.step19 quick     python -m ecosim.step19 run [base|rich]     python -m ecosim.step19 analyze
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

SEEDS, BRAINS, WORLDS_PER_GEN = list(range(1, 17)), 16, 2
GENS, EVERY = 300, 20
OUT, RES = Path('runs/step19'), Path('results')
TEST_WORLDS = list(range(4000, 4012))
ARMS = {'s19_base': dict(s14.PRED),
        's19_rich': dict(s14.PRED, pheromone=True, obstacles=True, senses=True)}
for _c, _o in ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_c] = _o


def run(arms=tuple(ARMS), seeds=SEEDS, gens=GENS, out=OUT, brains=BRAINS, every=EVERY):
    from .batch3_fast import evolve
    for c in arms:
        evolve(c, seeds, gens, out=out, checkpoint_every=every, clonal=60, brains=brains, eval_worlds=WORLDS_PER_GEN)


def analyze(seeds=SEEDS, gens=GENS, out=OUT, every=EVERY, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    cks = list(range(every, gens + 1, every))
    C = {}
    for c in ARMS:
        rows = [s14.test(c, [np.load(out / f'{c}_s{s}' / f'ckpt_g{g}.npy') for s in seeds], conn, dev, TEST_WORLDS)
                for g in cks]
        C[c] = {k: np.array([r[k] for r in rows]) for k in rows[0]}               # (n_ckpt, n_seeds)
        print(c, 'yardstick skill:', np.round(C[c]['fitness'].mean(1), 3).tolist(), flush=True)
    at = lambda c, g: C[c]['fitness'][cks.index(g)] if g in cks else None
    st = {}
    for c in ARMS:
        F = C[c]['fitness']
        last = [i for i, g in enumerate(cks) if g > gens - gens // 3] or [len(cks) - 1]
        x = np.array(cks)[last]
        slopes = [float(np.polyfit(x, F[last, j], 1)[0]) * 100 if len(last) > 1 else 0.0 for j in range(F.shape[1])]
        r = dict(checkpoints=cks, skill=F.mean(1).round(4).tolist(),
                 food=C[c]['food'].mean(1).round(3).tolist(), bites=C[c]['bites'].mean(1).round(4).tolist(),
                 peak_checkpoint=int(cks[int(np.argmax(F.mean(1)))]),
                 slope_last_third_per_100_gens=dict(mean=float(np.mean(slopes)), seeds_rising=int(sum(v > 0 for v in slopes)),
                                                    n=len(slopes), per_seed=np.round(slopes, 3).tolist()))
        g3 = [gens // 3, 2 * gens // 3, gens]
        g3 = [max(every, (g // every) * every) for g in g3]
        if all(g in cks for g in g3) and len(set(g3)) == 3:
            r[f'g{g3[1]}_vs_g{g3[0]}'] = paired(at(c, g3[1]), at(c, g3[0]))
            r[f'g{g3[2]}_vs_g{g3[1]}'] = paired(at(c, g3[2]), at(c, g3[1]))
        st[c] = r
    st['note'] = ('skill = fitness on 12 fixed unseen worlds of the arm\'s own type (energy left/100 + survival). '
                  'Arms are different worlds, so compare their SHAPES (still rising or flat), not their levels. '
                  'paired(): "hunger" = first argument, "nohunger" = second.')
    (RES / f'step19{tag}_stats.json').write_text(json.dumps(st, indent=1))
    (RES / f'step19{tag}_curves.json').write_text(json.dumps({c: {k: v.tolist() for k, v in C[c].items()} for c in C}))
    print(json.dumps({c: {k: v for k, v in st[c].items() if k not in ('skill', 'food', 'bites', 'checkpoints')}
                      for c in ARMS}, indent=1), flush=True)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for c in ARMS:
        F = C[c]['fitness']
        axes[0].errorbar(cks, F.mean(1), yerr=1.96 * F.std(1) / np.sqrt(F.shape[1]), marker='o', capsize=3, lw=2, label=c)
        axes[1].plot(cks, F - F[0], color='C0' if c == 's19_base' else 'C1', alpha=0.25, lw=1)
        axes[1].plot(cks, (F - F[0]).mean(1), color='C0' if c == 's19_base' else 'C1', lw=3, label=c)
    axes[0].set_ylabel('yardstick skill (12 fixed unseen worlds)'); axes[1].set_ylabel('gain since first checkpoint (each seed)')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend()
    fig.suptitle(f'Step 19: matched scoring, base world vs all-senses world ({len(seeds)} seeds, 95% CI)')
    fig.tight_layout(); fig.savefig(RES / f'step19{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'quick':
        q = Path('runs/step19_quick')
        run(seeds=[1, 2], gens=4, out=q, brains=4, every=2); analyze([1, 2], 4, q, 2, '_quick')
    elif a == 'run':
        run((f's19_{sys.argv[2]}',) if len(sys.argv) > 2 else tuple(ARMS))
    else:
        analyze()
