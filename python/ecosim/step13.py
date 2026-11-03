"""Step 13: the old null results redone under clonal-group scoring (Step 10: the old scoring rewarded stealing
food from your own kind; Steps 11-12: clonal scoring fixes that). Each brain is scored by 10 clones in a
1/6-size copy of the world (same food, worm and predator densities). Fair tests: 60 clones, 6 fixed full worlds.

    13a = Step 8:  no predators / 6 predators + touch / 6 predators, no touch   (32 seeds, 100 gens)
    13b = Step 3f: hunger peptide x ASH starvation alarm, 2 x 2                   (32 seeds, 60 gens)
    13c = Step 4:  growing brains vs fixed brains, normal food, food fitness      (16 seeds = 2 batches of 8, 60 gens;
                   growing brains are ~8x bigger, so 32 seeds of clone groups don't fit in 10 GB)

    python -m ecosim.step13 quick           (GPU smoke test of all three)
    python -m ecosim.step13 run a|b|c       python -m ecosim.step13 analyze a|b|c   -> results/step13{a,b,c}_*
"""
import json
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step8 as s8                       # registers nopred / pred_touch / pred_notouch (end fitness)
from . import step3f as s3f
from . import step4 as s4
from . import worm3 as g3

OUT, RES, GROUP = Path('runs/step13'), Path('results'), 10
SEEDS32, SEEDS16 = list(range(1, 33)), list(range(1, 17))
s3f.register(0.25)
F_ARMS = [s3f.cname(p, a, 0.25) for p, a in s3f.ARMS]          # pep_noash, pep_ash, nopep_noash, nopep_ash
G_ARMS = {'c4_growth': s4.CONDITIONS['growth'], 'c4_nogrowth': s4.CONDITIONS['nogrowth']}
for _k, _o in G_ARMS.items():
    CONDITIONS[_k] = _o; CFG_OVERRIDES[_k] = {}; s4.CONDITIONS[_k] = _o


def run(part, seeds32=SEEDS32, seeds16=SEEDS16, gens=None, out=OUT):
    from .batch3_fast import evolve
    if part == 'a':
        for c in s8.ARMS:
            evolve(c, seeds32, gens or 100, out=out / 'a', clonal=GROUP)
    elif part == 'b':
        for c in F_ARMS:
            evolve(c, seeds32, gens or 60, out=out / 'b', clonal=GROUP)
    elif part == 'c':
        for c in G_ARMS:
            for i in range(0, len(seeds16), 8):                       # batches of 8 seeds (GPU memory)
                evolve(c, seeds16[i:i + 8], gens or 60, out=out / 'c', clonal=GROUP)


def analyze(part, seeds32=SEEDS32, seeds16=SEEDS16, out=OUT, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import fair_all, paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    if part == 'a':
        F = {c: fair_all(c, seeds32, conn, dev, out=out / 'a') for c in s8.ARMS}
        g = lambda c, k: np.array([F[c][s][k] for s in seeds32])
        st = dict(mean_fitness={c: float(g(c, 'fitness').mean()) for c in F},
                  mean_bites={c: float(g(c, 'bites').mean()) for c in F},
                  touch_vs_notouch_fitness=paired(g('pred_touch', 'fitness'), g('pred_notouch', 'fitness')),
                  touch_vs_notouch_bites=paired(g('pred_touch', 'bites'), g('pred_notouch', 'bites')),
                  predator_cost=paired(g('pred_touch', 'fitness'), g('nopred', 'fitness')))
    elif part == 'b':
        F = {c: fair_all(c, seeds32, conn, dev, out=out / 'b') for c in F_ARMS}
        E = {c: np.array([F[c][s]['fitness'] for s in seeds32]) for c in F_ARMS}
        n = lambda p, a: s3f.cname(p, a, 0.25)
        st = dict(mean_fitness={c: float(v.mean()) for c, v in E.items()},
                  alarm_with_peptide=paired(E[n(True, True)], E[n(True, False)]),
                  alarm_without_peptide=paired(E[n(False, True)], E[n(False, False)]),
                  peptide_without_alarm=paired(E[n(True, False)], E[n(False, False)]),
                  peptide_with_alarm=paired(E[n(True, True)], E[n(False, True)]))
    else:
        from .step4_gpu import fair as fair4
        F = {c: fair4(c, seeds16, conn, dev, out=out / 'c') for c in G_ARMS}
        a = np.array([F['c4_growth'][s]['food'] for s in seeds16]); b = np.array([F['c4_nogrowth'][s]['food'] for s in seeds16])
        st = dict(food=paired(a, b), grown_neurons_best=sorted(F['c4_growth'][s]['neurons'] for s in seeds16))
    st['note'] = 'paired(): "hunger" = first argument, "nohunger" = second (field names reused)'
    (RES / f'step13{part}{tag}_stats.json').write_text(json.dumps(st, indent=1))
    (RES / f'step13{part}{tag}_results.json').write_text(json.dumps(F, indent=1, default=str))
    print(f'step13{part}', json.dumps(st, indent=1), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'quick':
        q = Path('runs/step13_quick')
        for p in 'abc':
            run(p, [1, 2], [1, 2], 2, q); analyze(p, [1, 2], [1, 2], q, '_quick')
    else:
        {'run': run, 'analyze': analyze}[sys.argv[1]](sys.argv[2])
