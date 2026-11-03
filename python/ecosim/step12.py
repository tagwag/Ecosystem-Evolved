"""Step 12: earlier key experiments redone under clonal-group scoring (Step 10 found the old scoring rewarded
stealing food from your own kind; Step 11 showed clonal scoring stops the late decline).

    12a  = Step 3d: hunger peptide vs none, scarce food (fitness = energy left at end + survival), 32 seeds, 100 gens
    12b  = Step 8c: peptide x predators that notice motion, + digestion while still, 32 seeds, 100 gens

Each brain is scored by 10 clones in a 1/6-size copy of the world (same food, worm and predator densities).
Fair tests are the usual ones: 60 clones on 6 fixed full-size worlds.

    python -m ecosim.step12 quick      (GPU smoke test)
    python -m ecosim.step12 run        (~3 hours on an RTX 3080)
    python -m ecosim.step12 analyze    -> results/step12a_*, results/step12b_*
"""
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES, SCARCE
from . import step8c  # noqa: F401  registers the Step 8c conditions (pep_/nopep_ x motion/blind, _dig)
from . import step8b as b8

SEEDS = list(range(1, 33))
GENS, GROUP = 100, 10
OUT, RES = Path('runs/step12'), Path('results')

A_ARMS = {'pep': 'hunger', 'nopep': 'nohunger'}
for _a, _base in A_ARMS.items():
    CONDITIONS[f'c3d_{_a}'] = dataclasses.replace(CONDITIONS[_base], fitness='end')
    CFG_OVERRIDES[f'c3d_{_a}'] = dict(SCARCE)
B_ARMS = [b8.cname(p, m) for p, m in b8.ARMS]          # Step 8c condition names (digestion on)


def run(gens=GENS, seeds=SEEDS, out=OUT):
    from .batch3_fast import evolve
    for c in [f'c3d_{a}' for a in A_ARMS] + B_ARMS:
        evolve(c, seeds, gens, out=out, clonal=GROUP)


def analyze(seeds=SEEDS, out=OUT, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import fair_all, paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    F = {c: fair_all(c, seeds, conn, dev, out=out) for c in [f'c3d_{a}' for a in A_ARMS] + B_ARMS}
    get = lambda c, k: np.array([F[c][s][k] for s in seeds])
    ratio = lambda c: get(c, 'speed_full') / get(c, 'speed_hungry')

    def comp(a, b):
        r = dict(fitness=paired(get(a, 'fitness'), get(b, 'fitness')), food=paired(get(a, 'food'), get(b, 'food')),
                 bites=paired(get(a, 'bites'), get(b, 'bites')))
        ra, rb = ratio(a), ratio(b); ok = np.isfinite(ra) & np.isfinite(rb)
        if ok.sum() >= 4:
            r['full_over_hungry'] = paired(ra[ok], rb[ok])
        r['frozen_seeds_first_arm'] = int((get(a, 'food') < 0.5).sum())
        r['frozen_seeds_second_arm'] = int((get(b, 'food') < 0.5).sum())
        return r
    A = {'peptide_vs_none': comp('c3d_pep', 'c3d_nopep')}
    B = {'motion': comp(b8.cname(True, True), b8.cname(False, True)),
         'blind': comp(b8.cname(True, False), b8.cname(False, False))}
    for name, d in (('step12a' + tag, A), ('step12b' + tag, B)):
        d['note'] = 'paired(): "hunger" = first arm (peptide), "nohunger" = second arm (no peptide)'
        (RES / f'{name}_stats.json').write_text(json.dumps(d, indent=1))
        print(name, json.dumps(d, indent=1), flush=True)
    (RES / f'step12{tag}_results.json').write_text(json.dumps(F, indent=1))


if __name__ == '__main__':
    if sys.argv[1] == 'quick':
        q = Path('runs/step12_quick')
        run(3, [1, 2], q); analyze([1, 2], q, '_quick')
    else:
        {'run': run, 'analyze': analyze}[sys.argv[1]]()
