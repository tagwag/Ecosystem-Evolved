"""Step 8: predators (Pristionchus-style v1). Can worm brains evolve to avoid being eaten?

Predators follow a fixed rule (they don't evolve yet): chase the nearest prey within 150 units at
speed 2.5 (prey max 5), bite on contact (-150 energy = 1.5 food), then pause 60 ticks (handling).
Prey feel a predator by TOUCH within 40 units: in front -> ALM/AVM, behind -> PLM/PVM (the real
gentle-touch neurons; front touch normally triggers backing up, back touch speeds the worm forward).

Arms (hunger peptide on, scarce food, fitness = energy left at the end + survival, 32 seeds, 100 generations):
    nopred        no predators (baseline)
    pred_touch    6 predators per world, prey can feel them
    pred_notouch  6 predators per world, touch input switched off (control: does the sense matter?)

    python -m ecosim.step8 run        (~15 min on an RTX 3080)
    python -m ecosim.step8 analyze    -> results/step8_*

Questions: (1) do predators change what evolves (energy, bites over generations)?
(2) does touch let prey escape (fewer bites with touch than without)?
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
OUT = Path('runs/step8')
RES = Path('results')
ARMS = {'nopred': dict(predators=0), 'pred_touch': dict(predators=6, touch_gain=3.0),
        'pred_notouch': dict(predators=6, touch_gain=0.0)}

for _k, _v in ARMS.items():
    CONDITIONS[_k] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_k] = dict(SCARCE, **_v)


def run():
    from .batch3_fast import evolve
    for k in ARMS:
        evolve(k, SEEDS, GENS, out=OUT)


def analyze():
    from .connectome import Connectome
    from .step3d_analyze import fair_all, paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    fair = {k: fair_all(k, SEEDS, conn, dev, out=OUT) for k in ARMS}
    E = {k: np.array([fair[k][s]['fitness'] for s in SEEDS]) for k in ARMS}
    B = {k: np.array([fair[k][s]['bites'] for s in SEEDS]) for k in ARMS}
    stats = {'mean_energy': {k: float(v.mean()) for k, v in E.items()},
             'mean_bites_per_worm': {k: float(v.mean()) for k, v in B.items()},
             'touch_vs_notouch_energy': paired(E['pred_touch'], E['pred_notouch']),
             'touch_vs_notouch_bites': paired(B['pred_touch'], B['pred_notouch']),
             'predator_cost_energy': paired(E['pred_touch'], E['nopred'])}
    (RES / 'step8_results.json').write_text(json.dumps(fair, indent=1))
    (RES / 'step8_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    cols = {'nopred': '#999999', 'pred_touch': '#2a78d6', 'pred_notouch': '#d6612a'}
    for k in ARMS:
        Hh = np.array([[g['fitness'] for g in json.loads((OUT / f'{k}_s{s}' / 'history.json').read_text())] for s in SEEDS])
        Hb = np.array([[g['bites'] for g in json.loads((OUT / f'{k}_s{s}' / 'history.json').read_text())] for s in SEEDS])
        axes[0].plot(Hh.mean(0), color=cols[k], lw=2, label=k)
        axes[1].plot(Hb.mean(0), color=cols[k], lw=2, label=k)
    axes[0].set_ylabel('fitness (energy left at end + survival)'); axes[1].set_ylabel('bites per worm per generation')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend()
    fig.suptitle('Step 8: evolving with predators (mean of 32 seeds)')
    fig.tight_layout(); fig.savefig(RES / 'step8_progress.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    {'run': run, 'analyze': analyze}[sys.argv[1]]()
