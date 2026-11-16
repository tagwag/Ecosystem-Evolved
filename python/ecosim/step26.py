"""Step 26 = SINGLE-NEURON KNOCKOUT GUIDE (2026-11-16): what happens when each neuron is removed, one at a time?

METHOD
  Brains: the 16 best brains of Step 23 control (runs/step23/s23_ctrl_s<seed>/best_genome.npy, generation 300), i.e.
  brains evolved in the plain Main Experiment world (connectome, scarce food, predators, touch, hunger peptide).
  For every neuron of the model (muscles excluded), one at a time: REMOVE it (gpu_brains.Worm2Brain.set_knockout:
  activity held at 0 every tick, all its gap junctions cut; its chemical synapses carry nothing because its activity
  is 0). Then test all 16 brains as 60 clones on 12 fixed unseen worlds (5200-5211), with the same random numbers
  as the intact test (generator re-seeded to 4242 before every run), so every knockout is compared with the intact
  brain on exactly the same worlds: a PAIRED comparison over 16 brains.
  This is an ACUTE knockout (remove from an already-evolved brain: what does this brain depend on?), not a
  developmental one (evolve without the neuron), see ecosim/STEP26_KNOCKOUT_GUIDE_DESIGN.md.

MEASURES per brain (FastSim stats, averaged over the 12 worlds)
  skill (fitness), food eaten, survivors, mean speed, reversal (tumble) rate, turn rate, time near food, predator bites.

PRE-REGISTERED RULES (written 2026-11-16 08:00 MT, before any run)
  For each measure: knockout - intact, paired over the 16 brains, sign-flip test (step20.signflip), then
  Benjamini-Hochberg false discovery rate over all neurons, 5 %. A knockout CHANGES a measure if BH q < 0.05.
  Validation checks against real-worm ablations (stated before the run; reported whatever the outcome):
    V1 removing AVAL or AVAR lowers the reversal rate (Chalfie et al. 1985, J Neurosci 5:956: AVA needed for backward
       movement). Caveat: AVA is also read directly by the motor decoder.
    V2 removing ASEL (the model's "smell rising" neuron) lowers food eaten (Bargmann & Horvitz 1991, Neuron 7:729: ASE
       directs chemotaxis).
    AFD (temperature/magnetism) cannot be checked here: the control world gives AFD no input. It is checked in phase 2
    on the Step 25 beacon brains.
  Known artefact: the decoder reads 28 neurons directly (AVA, AVB, AVD, AVE, PVC, AIB, AIY, AIZ, RIA, RIM pairs +
  SMD/RMD); their effects are partly the readout design. They are flagged in the guide.

    python -m ecosim.step26 run              # all neurons (resumes: each neuron's result is saved as it finishes)
    python -m ecosim.step26 analyze          # tests, CSV, guide, chart
    python -m ecosim.step26 full             # run + analyze (watcher: knockout_guide)
    python -m ecosim.step26 check --test     # 3 neurons, 2 brains, 2 worlds (watcher: knockout_check)
Results: runs/step26/<neuron>.json, results/step26_knockouts.csv, results/step26_stats.txt, results/step26.png,
         docs/KNOCKOUT_GUIDE.md
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from . import step23 as s23
from .step3 import CONDITIONS, CFG_OVERRIDES

ARM, SRC = 's23_ctrl', Path('runs/step23')
SEEDS = list(range(1, 17))
WORLDS = list(range(5200, 5212))
OUT, RES, DOCS = Path('runs/step26'), Path('results'), Path('../docs')
TEST = bool(os.environ.get('STEP26_TEST')) or '--test' in sys.argv
ONLY = None
if TEST:
    SEEDS, WORLDS, OUT, ONLY = [1, 2], [5200, 5201], Path('runs/step26_test'), ['AVAL', 'ASEL', 'RIAL']
MEASURES = ('fitness', 'mean_food', 'survivors', 'mean_speed', 'reversal_rate', 'turn_rate', 'near_food', 'bites')
LABEL = dict(fitness='skill', mean_food='food', survivors='survivors', mean_speed='speed', reversal_rate='reversals',
             turn_rate='turning', near_food='time near food', bites='bites')
READOUT_SET = None


def neurons(conn):
    from .connectome import _is_muscle
    return [n for n in conn.names if not _is_muscle(n)]


def run(device='cuda'):
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device(device), Connectome()
    OUT.mkdir(parents=True, exist_ok=True)
    genomes = [np.load(SRC / f'{ARM}_s{s}' / 'best_genome.npy') for s in SEEDS]
    opts, cfg = CONDITIONS[ARM], Config(**CFG_OVERRIDES[ARM])
    P = cfg.worm_population
    pairs = [(j, w) for j in range(len(genomes)) for w in WORLDS]
    G = np.stack([np.repeat(genomes[j][None], P, 0) for j, _ in pairs])
    gen = torch.Generator(device=dev)
    sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
    s23.set_strengths(sim, ARM)
    sim.brain.enable_knockout()
    todo = ['NONE'] + (ONLY or neurons(conn))
    t0 = time.time()
    for i, n in enumerate(todo):
        f = OUT / f'{n}.json'
        if f.exists():
            continue
        sim.brain.set_knockout([] if n == 'NONE' else conn.ids([n]).tolist())
        gen.manual_seed(4242)
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(WORLDS)
        res = {'fitness': fit.mean(1).reshape(len(genomes), nw).mean(1).tolist()}
        for m in MEASURES[1:]:
            res[m] = np.array([x[m] for x in st], float).reshape(len(genomes), nw).mean(1).tolist()
        f.write_text(json.dumps(dict(neuron=n, seeds=SEEDS, worlds=WORLDS, **res)))
        el = time.time() - t0
        print(f'{i + 1}/{len(todo)} {n:6s} skill {np.mean(res["fitness"]):.3f}  reversals {np.mean(res["reversal_rate"]):.4f}'
              f'  ({el / 60:.1f} min so far)', flush=True)
    print('KNOCKOUT_RUN_DONE', flush=True)


def bh(p):
    """Benjamini-Hochberg adjusted p-values (q) of an array."""
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    q = np.empty(n); prev = 1.0
    for r, i in reversed(list(enumerate(o))):
        prev = min(prev, p[i] * n / (r + 1)); q[i] = prev
    return q


def kind(n):
    """Rough neuron class from the name (for grouping the guide): sensory / interneuron / motor / other."""
    SENS = ('ASE', 'AWC', 'AWA', 'AWB', 'ASH', 'ASK', 'ADL', 'AFD', 'ASJ', 'ASI', 'ASG', 'ADF', 'PHA', 'PHB', 'BAG',
            'URX', 'AQR', 'PQR', 'ALM', 'AVM', 'PLM', 'PVM', 'FLP', 'OLQ', 'OLL', 'IL1', 'IL2', 'CEP', 'ADE', 'PDE',
            'PVD', 'URY', 'URB', 'PHC', 'URA')
    MOTOR = ('DA', 'DB', 'DD', 'VA', 'VB', 'VD', 'VC', 'AS', 'RMD', 'RME', 'RMF', 'RMG', 'RMH', 'SMB', 'SMD', 'RIV',
             'URA', 'IL1')
    if n.startswith(SENS):
        return 'sensory'
    if n.startswith(MOTOR):
        return 'motor'
    return 'interneuron'


def analyze():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .connectome import Connectome, READOUT
    from .step20 import signflip
    RES.mkdir(exist_ok=True)
    conn = Connectome()
    base = json.loads((OUT / 'NONE.json').read_text())
    names = [n for n in (ONLY or neurons(conn)) if (OUT / f'{n}.json').exists()]
    R = {n: json.loads((OUT / f'{n}.json').read_text()) for n in names}
    rows = []
    D, Pm = {}, {}
    for m in MEASURES:
        b = np.array(base[m])
        D[m] = np.array([np.array(R[n][m]) - b for n in names])          # (neurons, seeds)
        Pm[m] = np.array([signflip(d) if np.any(d != 0) else 1.0 for d in D[m]])
    Q = {m: bh(Pm[m]) for m in MEASURES}
    for i, n in enumerate(names):
        row = dict(neuron=n, kind=kind(n), decoder_reads_it=n in READOUT)
        for m in MEASURES:
            row[f'{m}_intact'] = float(np.mean(base[m])); row[f'{m}_change'] = float(D[m][i].mean())
            row[f'{m}_p'] = float(Pm[m][i]); row[f'{m}_q'] = float(Q[m][i])
        rows.append(row)
    import csv
    with open(RES / 'step26_knockouts.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    hits = {m: [(names[i], D[m][i].mean(), Q[m][i]) for i in np.argsort(Q[m]) if Q[m][i] < 0.05] for m in MEASURES}
    lines = [f'Step 26 / single-neuron knockouts: {len(names)} neurons x {len(SEEDS)} brains (Step 23 control, gen 300),'
             f' {len(WORLDS)} unseen worlds x 60 clones; paired sign-flip, BH FDR 5 % per measure',
             'intact: ' + ', '.join(f'{LABEL[m]} {np.mean(base[m]):.4g}' for m in MEASURES)]
    for m in MEASURES:
        lines.append(f'{LABEL[m]}: {len(hits[m])} knockouts change it (q < 0.05)'
                     + ('; biggest: ' + ', '.join(f'{n} {c:+.4g}' for n, c, _ in sorted(hits[m], key=lambda h: -abs(h[1]))[:8])
                        if hits[m] else ''))
    def val(n, m, sign):
        if n not in names:
            return f'{n}: not tested'
        i = names.index(n); c, q = D[m][i].mean(), Q[m][i]
        ok = q < 0.05 and np.sign(c) == sign
        return f'{n}: {LABEL[m]} {c:+.4g} (q={q:.3g}) -> {"MATCHES the real worm" if ok else "does NOT match"}'
    lines += ['VALIDATION (pre-registered):',
              '  V1 ' + val('AVAL', 'reversal_rate', -1), '  V1 ' + val('AVAR', 'reversal_rate', -1),
              '  V2 ' + val('ASEL', 'mean_food', -1)]
    txt = '\n'.join(lines); print(txt)
    (RES / 'step26_stats.txt').write_text(txt + '\n')
    # chart: skill change per neuron, sorted, coloured by class
    order = np.argsort(D['fitness'].mean(1))
    col = {'sensory': '#2a9d8f', 'interneuron': '#e76f51', 'motor': '#457b9d'}
    fig, ax = plt.subplots(2, 1, figsize=(16, 8))
    ax[0].bar(range(len(names)), D['fitness'].mean(1)[order], color=[col[kind(names[i])] for i in order])
    ax[0].set(title='Skill change when one neuron is removed (sorted; colour = sensory / interneuron / motor)',
              ylabel='skill change'); ax[0].set_xticks([])
    worst = order[:25]
    ax[1].barh([names[i] for i in worst][::-1], D['fitness'].mean(1)[worst][::-1],
               color=[col[kind(names[i])] for i in worst][::-1])
    ax[1].set(title='The 25 knockouts that hurt skill most', xlabel='skill change')
    fig.tight_layout(); fig.savefig(RES / 'step26.png', dpi=110)
    guide(names, D, Q, base)


def guide(names, D, Q, base):
    """docs/KNOCKOUT_GUIDE.md: one plain-words line per neuron, grouped by class, biggest skill effect first."""
    from .connectome import READOUT
    out = ['# Knockout guide: what happens when one neuron is removed', '',
           f'Generated by `python -m ecosim.step26 analyze` from {len(names)} neurons x {len(SEEDS)} evolved brains '
           f'(Step 23 control, generation 300), each tested on {len(WORLDS)} unseen worlds as 60 clones. '
           'Method and rules: python/ecosim/step26.py and python/ecosim/STEP26_KNOCKOUT_GUIDE_DESIGN.md.', '',
           '**How to read a line:** the change in each measure when that neuron is removed, versus the same intact '
           'brains on the same worlds. Only changes that pass the 5 % false-discovery-rate test are listed; '
           '"no detectable effect" means none passed. (D) = the motor decoder reads this neuron directly, so part of '
           'its effect comes from the readout design, not the wiring.', '',
           'Intact brains: ' + ', '.join(f'{LABEL[m]} {np.mean(base[m]):.4g}' for m in MEASURES), '']
    for k in ('sensory', 'interneuron', 'motor'):
        idx = [i for i, n in enumerate(names) if kind(n) == k]
        idx.sort(key=lambda i: D['fitness'][i].mean())
        out += [f'## {k.capitalize()} neurons ({len(idx)})', '']
        for i in idx:
            sig = [f'{LABEL[m]} {D[m][i].mean():+.3g}' for m in MEASURES if Q[m][i] < 0.05]
            tag = ' (D)' if names[i] in READOUT else ''
            out.append(f'- **{names[i]}**{tag}: ' + ('; '.join(sig) if sig else 'no detectable effect'))
        out.append('')
    if not TEST:
        DOCS.mkdir(exist_ok=True)
        (DOCS / 'KNOCKOUT_GUIDE.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    else:
        (RES / 'step26_test_guide.md').write_text('\n'.join(out) + '\n', encoding='utf-8')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['run'], ['full'], ['check']):
        import torch
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        run(dev)
        if a[0] != 'run':
            analyze()
        print({'check': 'KNOCKOUT_CHECK_OK', 'full': 'KNOCKOUT_FULL_DONE', 'run': ''}[a[0]], flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
