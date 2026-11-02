"""Step 3f: starvation alarm into ASH. Does a "pain when starving" signal help, and does it interact
with the hunger peptide?

ASH = the worm's main nociceptor (pain/danger sensor). In the real wiring it feeds AVA/AVD, the
backward-command neurons, so an alarm there pushes reversals. Real worms: hunger turns DOWN the
response to aversive cues (Ghosh et al. 2016), so the peptide and the alarm might cancel out.

Alarm: input into ASHL/ASHR = ash_alarm (3.0, like the smell sensors) x a level that is 0 above 20% of
the gut and rises linearly to 1 at zero energy. Its effect on behaviour is left to evolution (synapses).

Fitness = energy left at the end + survival ('end'; see Step 3e2: average energy can be gamed by idling).
2 x 2 design at one movement cost (scarce food, 32 seeds, 60 generations):
    peptide on/off  x  ASH alarm on/off

    python -m ecosim.step3f run [move_cost]       # default move_cost 0.25 (Step 3d world)
    python -m ecosim.step3f analyze [move_cost]   -> results/step3f_m<cost>_*
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
GENS = 60
GAIN = 3.0
OUT = Path('runs/step3f')
RES = Path('results')
ARMS = [(True, False), (True, True), (False, False), (False, True)]     # (peptide, alarm)


def cname(pep, alarm, m):
    return f"{'pep' if pep else 'nopep'}_{'ash' if alarm else 'noash'}_move{m}"


def register(m):
    for pep, alarm in ARMS:
        base = CONDITIONS['hunger' if pep else 'nohunger']
        CONDITIONS[cname(pep, alarm, m)] = dataclasses.replace(base, ash_alarm=GAIN if alarm else 0.0, fitness='end')
        CFG_OVERRIDES[cname(pep, alarm, m)] = dict(SCARCE, move_cost=m)


def run(m):
    from .batch3_fast import evolve
    register(m)
    for pep, alarm in ARMS:
        evolve(cname(pep, alarm, m), SEEDS, GENS, out=OUT)


def analyze(m):
    from .connectome import Connectome
    from .step3d_analyze import fair_all, paired
    from .worm2_gpu import pick_device
    register(m)
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    fair = {cname(p, a, m): fair_all(cname(p, a, m), SEEDS, conn, dev, out=OUT) for p, a in ARMS}
    E = {k: np.array([v[s]['fitness'] for s in SEEDS]) for k, v in fair.items()}
    stats = {
        'mean_energy': {k: float(v.mean()) for k, v in E.items()},
        'alarm_effect_with_peptide': paired(E[cname(True, True, m)], E[cname(True, False, m)]),
        'alarm_effect_without_peptide': paired(E[cname(False, True, m)], E[cname(False, False, m)]),
        'peptide_effect_without_alarm': paired(E[cname(True, False, m)], E[cname(False, False, m)]),
        'peptide_effect_with_alarm': paired(E[cname(True, True, m)], E[cname(False, True, m)]),
        # interaction: does the alarm help less (or hurt) when the peptide is present?
        'interaction': paired(E[cname(True, True, m)] - E[cname(True, False, m)],
                              E[cname(False, True, m)] - E[cname(False, False, m)]),
    }
    tag = f'step3f_m{m}'
    (RES / f'{tag}_results.json').write_text(json.dumps(fair, indent=1))
    (RES / f'{tag}_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    labels = ['peptide\nno alarm', 'peptide\n+ alarm', 'no peptide\nno alarm', 'no peptide\n+ alarm']
    for i, (p, a) in enumerate(ARMS):
        v = E[cname(p, a, m)]
        ax.scatter(np.full(len(v), i) + np.random.default_rng(i).uniform(-0.12, 0.12, len(v)), v,
                   color='#2a78d6' if p else '#999999', alpha=0.5, s=18)
        ax.errorbar(i, v.mean(), yerr=1.96 * v.std() / np.sqrt(len(v)), fmt='o', color='k', capsize=6, ms=8)
    ax.set_xticks(range(4), labels); ax.set_ylabel('fair-test fitness (energy left at end + survival)')
    ax.set_title(f'Step 3f: starvation alarm x hunger peptide (move cost {m}, 32 seeds)'); ax.grid(axis='y', alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / f'{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    m = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
    {'run': run, 'analyze': analyze}[sys.argv[1]](m)
