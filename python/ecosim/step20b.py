"""Step 20b = the FAIR MUSCLE-OUTPUT RE-TEST of the Main Experiment (2026-11-14).

WHY
  In Step 20, "muscle output" lost on 16/16 seeds (-0.63, Holm p 0.0001). But that test was rigged against muscles:
  the muscle version moved the worm with only 3 evolvable gains (+3 biases) reading 3 fixed averages of the muscles,
  while the decoder version had 168 evolvable weights (28 interneurons x 3 outputs x change/level). So Step 20 showed
  "3 knobs lose to 168 knobs", not "reading the body loses to reading interneurons".

WHAT CHANGES
  Both arms now use the SAME kind of evolvable decoder (worm2.readout_names). Only WHAT it reads differs:
    s20b_inter    the 28 locomotion/chemotaxis interneurons                 (= Step 20 s20_old, the old best)
    s20b_body     the 95 body-wall muscles + AVA/AVB command interneurons    (readout = 'muscles', 99 cells)
  The body decoder has more weights (594 vs 168), but its starting strength is scaled down so the total is the same,
  and mutation touches about 8 decoder genes per child whatever the size (worm2.random_genomes / worm2.mutate), so
  neither arm starts stronger or mutates faster. Old synapses (reversal potentials had no effect in Step 20).
  World and scoring = Step 20: scarce food, 6 predators, touch, hunger peptide, fitness = energy at the end +
  survival, each brain = 60 clones in a full-size world, 12 brains per seed, 16 seeds paired by seed, 300 generations.

PRE-REGISTERED RULE (written 2026-11-14 20:30 MT, before any run)
  Yardstick: each seed's best brain at generation 300 on the Step 20 test worlds (4000-4011), 60 clones each
  (step14.test). Effect = mean over seeds of (body - inter), paired sign-flip permutation test (one test, no
  correction). BODY READOUT HELPS if effect > 0 with p < 0.05, HURTS if < 0 with p < 0.05, otherwise no detectable
  effect. Reported, not tested: learning curves, skill at generations 50/100/.../300, food, bites.
  Known limit: reading muscles still is not a body: the muscles drive a point worm through the same speed / reversal
  / turn outputs. A real body model (muscles bending segments) would be a separate experiment.

    python -m ecosim.step20b full          # both arms (skips finished ones; safe to re-queue), then the analysis
    python -m ecosim.step20b analyze
    python -m ecosim.step20b check --test  # tiny version (2 seeds, 2 generations) + analysis: the workstation code check
Watcher: {"experiment": "muscle_fair"}   (code check: {"experiment": "muscle_fair_check"})
Results: runs/step20b/<arm>_s<seed>/, results/step20b_stats.txt + step20b_stats.json + step20b.png
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

SEEDS, GENS, BRAINS, EVERY = list(range(1, 17)), 300, 12, 50
OUT, RES = Path('runs/step20b'), Path('results')
TEST_WORLDS = list(range(4000, 4012))
if os.environ.get('STEP20B_TEST') or '--test' in sys.argv:
    SEEDS, GENS, BRAINS, EVERY, OUT, TEST_WORLDS = [1, 2], 2, 2, 1, Path('runs/step20b_test'), [4000, 4001]
ARMS = {'s20b_inter': dict(readout='known'), 's20b_body': dict(readout='muscles')}
for _c, _o in ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS['hunger'], fitness='end', reversal=False, muscle_out=False, **_o)
    CFG_OVERRIDES[_c] = dict(s14.PRED)


def run(out=OUT, device='cuda'):
    from .batch3_fast import evolve
    out.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        if all((out / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        print(f'{arm}: readout = {ARMS[arm]["readout"]}, {len(SEEDS)} seeds x {GENS} gens', flush=True)
        evolve(arm, SEEDS, GENS, out=out, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS, eval_worlds=1)
    print('MUSCLE_FAIR_RUN_DONE', flush=True)


def analyze(out=OUT):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .connectome import Connectome
    from .step20 import signflip
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    seeds = [s for s in SEEDS if all((out / f'{a}_s{s}' / 'best_genome.npy').exists() for a in ARMS)]
    if len(seeds) < 2:
        raise SystemExit(f'only {len(seeds)} seeds finished in both arms; nothing to analyse yet')
    cks = sorted({EVERY * k for k in range(1, GENS // EVERY + 1)} | {GENS})
    Y = {a: {g: s14.test(a, [np.load(out / f'{a}_s{s}' / f'ckpt_g{g}.npy') for s in seeds], conn, dev, TEST_WORLDS)
             for g in cks} for a in ARMS}
    d = np.asarray(Y['s20b_body'][GENS]['fitness']) - np.asarray(Y['s20b_inter'][GENS]['fitness'])
    p = signflip(d)
    v = 'HELPS' if d.mean() > 0 and p < 0.05 else 'HURTS' if d.mean() < 0 and p < 0.05 else 'no detectable effect'
    lines = [f'Step 20b / fair muscle-output re-test: {len(seeds)} seeds, yardstick at generation {GENS}',
             'arm          skill    food   bites   (skill at ' + ', '.join(f'g{g}' for g in cks) + ')']
    for a in ARMS:
        r = Y[a][GENS]
        lines.append(f'{a:12s} {np.mean(r["fitness"]):6.3f}  {np.mean(r["food"]):6.2f}  {np.mean(r["bites"]):6.2f}   ('
                     + ', '.join(f'{np.mean(Y[a][g]["fitness"]):.3f}' for g in cks) + ')')
    lines.append(f'body - inter = {d.mean():+.3f}  (+ in {(d > 0).sum()}/{len(d)} seeds)  p = {p:.3g}  -> body readout {v}')
    txt = '\n'.join(lines); print(txt)
    (RES / 'step20b_stats.txt').write_text(txt + '\n')
    (RES / 'step20b_stats.json').write_text(json.dumps(dict(
        seeds=seeds, effect=d.tolist(), p=p, checkpoints=cks,
        yardstick={a: {str(g): {k: list(map(float, x)) for k, x in Y[a][g].items()} for g in cks} for a in ARMS})))
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    for a in ARMS:
        ax[0].plot(cks, [np.mean(Y[a][g]['fitness']) for g in cks], marker='o', label=a)
        h = [json.loads((out / f'{a}_s{s}' / 'history.json').read_text()) for s in seeds]
        n = min(len(x) for x in h)
        ax[1].plot(np.mean([[r['fitness'] for r in x[:n]] for x in h], 0), label=a)
    ax[0].set(title='Skill on 12 unseen worlds (yardstick)', xlabel='generation', ylabel='fitness')
    ax[1].set(title='Training fitness (mean over seeds)', xlabel='generation')
    for a_ in ax:
        a_.legend()
    fig.tight_layout(); fig.savefig(RES / 'step20b.png', dpi=120)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['full'], ['check']):
        import torch
        run(device='cuda' if torch.cuda.is_available() else 'cpu'); analyze()
        print('MUSCLE_FAIR_CHECK_OK' if a[0] == 'check' else 'MUSCLE_FAIR_FULL_DONE', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
