"""Step 8b: predators that notice MOVING prey. Does the hunger peptide (the brain's "stop moving when
full" switch) pay off when movement itself attracts predators?

Why: Step 3e2 showed the peptide lets brains switch movement off, but it only helps where resting pays,
and cranking the movement cost just made the world unlivable. Here resting pays for a physical reason:
a predator notices motionless prey only at near-contact range (20 units); the faster the prey moves,
the farther away it is noticed, up to 150 at full speed. Bites still need contact.

2 x 2 (6 predators, touch sense on, scarce food, normal movement cost, fitness = energy left at the
end + survival, 32 seeds, 100 generations):
    peptide on / off   x   predators notice motion / predators blind to motion (Step 8 kind)

    python -m ecosim.step8b run        (~20 min on an RTX 3080)
    python -m ecosim.step8b analyze    -> results/step8b_*

Prediction if the idea is right: the peptide's advantage (fitness, fewer bites, slowing when full)
is larger with motion-sensing predators than with motion-blind ones (an interaction).
"""
import dataclasses
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES, SCARCE

SEEDS = list(range(1, 33))
GENS = 100
RES = Path('results')
ARMS = [(True, True), (False, True), (True, False), (False, False)]     # (peptide, predators notice motion)
TAG = 'step8b'                 # step8c.py sets TAG = 'step8c' and DIGESTION = True, then calls register()
DIGESTION = False
OUT = Path('runs/step8b')


def cname(pep, motion):
    return f"{'pep' if pep else 'nopep'}_{'motion' if motion else 'blind'}" + ('_dig' if DIGESTION else '')


def register():
    for p, m in ARMS:
        CONDITIONS[cname(p, m)] = dataclasses.replace(CONDITIONS['hunger' if p else 'nohunger'], fitness='end')
        CFG_OVERRIDES[cname(p, m)] = dict(SCARCE, predators=6, touch_gain=3.0, pred_sense_still=20.0 if m else -1.0,
                                          digestion=DIGESTION)


register()


def run():
    from .batch3_fast import evolve
    for p, m in ARMS:
        evolve(cname(p, m), SEEDS, GENS, out=OUT)


def analyze():
    from .connectome import Connectome
    from .step3d_analyze import fair_all, paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    fair = {cname(p, m): fair_all(cname(p, m), SEEDS, conn, dev, out=OUT) for p, m in ARMS}
    get = lambda k, key: np.array([fair[k][s][key] for s in SEEDS])
    ratio = lambda k: np.array([fair[k][s]['speed_full'] / fair[k][s]['speed_hungry'] for s in SEEDS])
    stats = {}
    for m in (True, False):
        a, b = cname(True, m), cname(False, m)
        stats['motion' if m else 'blind'] = dict(
            fitness=paired(get(a, 'fitness'), get(b, 'fitness')),
            food=paired(get(a, 'food'), get(b, 'food')),
            bites=paired(get(a, 'bites'), get(b, 'bites')),
            full_over_hungry=paired(ratio(a)[np.isfinite(ratio(a) - ratio(b))], ratio(b)[np.isfinite(ratio(a) - ratio(b))]))
    # interaction: is the peptide's fitness advantage bigger with motion-sensing predators?
    stats['interaction_fitness'] = paired(get(cname(True, True), 'fitness') - get(cname(False, True), 'fitness'),
                                          get(cname(True, False), 'fitness') - get(cname(False, False), 'fitness'))
    (RES / f'{TAG}_results.json').write_text(json.dumps(fair, indent=1))
    (RES / f'{TAG}_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    labels = ['peptide\nmotion', 'no peptide\nmotion', 'peptide\nblind', 'no peptide\nblind']
    for ax, key, lab in ((axes[0], 'fitness', 'fitness (energy left at end + survival)'),
                         (axes[1], 'food', 'food eaten per worm'), (axes[2], 'bites', 'bites per worm')):
        for i, (p, m) in enumerate(ARMS):
            v = get(cname(p, m), key)
            ax.scatter(np.full(len(v), i) + np.random.default_rng(i).uniform(-0.12, 0.12, len(v)), v,
                       color='#2a78d6' if p else '#999999', alpha=0.5, s=16)
            ax.errorbar(i, v.mean(), yerr=1.96 * v.std() / np.sqrt(len(v)), fmt='o', color='k', capsize=6, ms=7)
        ax.set_xticks(range(4), labels); ax.set_ylabel(lab); ax.grid(axis='y', alpha=0.3)
    extra = ' + digestion while still' if DIGESTION else ''
    fig.suptitle(f'{TAG}: hunger peptide x predators that notice motion{extra} (32 seeds, fair test, 95% CI)')
    fig.tight_layout(); fig.savefig(RES / f'{TAG}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    {'run': run, 'analyze': analyze}[sys.argv[1]]()
