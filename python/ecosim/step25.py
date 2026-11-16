"""Step 25 = the BEACON SERIES (2026-11-16): which senses can be used to LEAD worms to a place we choose?
Full design and reasoning: ecosim/STEP25_BEACON_SERIES_DESIGN.md.

WHY
  Step 23 showed a cue gets wired in only when it is the ONLY way to find something worth having (gravity at the food:
  used; magnetism at the food: ignored, because smell already found the food), and only if it has no physical side
  effect that selection could credit instead (light gravity at the food: big gain, sense not used).

WORLD (config.py "Step 25")
  Step 23 control world (connectome, scarce food, 6 predators, touch, hunger peptide, 60 clones, 12 brains per seed)
  plus ONE BEACON per world at a random place every generation: a feathered circle (value 1 within 100 units, smooth
  fade to 0 at 240). Inside it a worm gains up to 0.3 energy per tick (cost of living 0.6): the hidden REWARD. The
  circle value x 3 is fed into ONE sense's neurons (the arm's CUE) and into nothing else. No food, smell or physical
  effect marks the zone, so the cue is the only way to find it.

ARMS (16 seeds each, paired by seed): s25_none (no cue: the reference) and one arm per sense, listed in SENSES below.
  Temperature and magnetism both enter AFD in this model, so s25_afd covers both.

PHASES
  pilot  50 generations, all 13 arms (runs/step25_pilot); quick steering test only. Ranks the senses early (arm
         rankings are reliable after 50 generations: analysis/predict_outcomes.py, 14 Nov).
  full   300 generations, all 13 arms (runs/step25), full analysis.

THE STEERING TEST (each seed's best brain, 60 clones x 12 fixed unseen worlds 5300-5311, REWARD OFF)
  steering index = time in the circle (mean field value under living worms) with the cue ON minus with it OFF,
  same brains, same worlds, same circle place. > 0 = the cue alone draws worms to the place we chose.
  Also: arrival tick (half the worms inside), and the MOVING BEACON (circle drifts 1 unit per tick in a straight
  line): mean distance to it, cue off minus cue on (> 0 = they follow it).
  Plus in the training world (reward on): skill, and the sense-cut test (cue off).

PRE-REGISTERED RULES (written 2026-11-16 08:10 MT, before any run)
  For each of the 12 cue arms: steering index > 0, paired sign-flip over 16 seeds (step20.signflip), Holm over the
  12 arms; a sense PASSES if Holm p < 0.05 and the mean is positive. s25_smell must pass (positive control), or the
  setup is judged broken. s25_none's steering index must be ~0 (it has no cue: a check of the method).
  Reported, not tested: arrival tick, moving-beacon distance, skill vs s25_none, skill own vs sense-cut.
  The pilot is reported without formal tests (it only ranks).

    python -m ecosim.step25 pilot          # 50 gens, all arms, quick steering test (watcher: beacon_pilot)
    python -m ecosim.step25 full           # 300 gens, all arms, full analysis (watcher: beacon_full)
    python -m ecosim.step25 analyze        # full analysis only
    python -m ecosim.step25 check --test   # 2 seeds, 2 gens, 3 arms, both analyses (watcher: beacon_check)
Results: runs/step25[_pilot]/<arm>_s<seed>/, results/step25[_pilot]_stats.txt + .json, results/step25.png
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

SENSES = {
    's25_none': '',
    's25_smell': 'ASEL,ASER,AWCL,AWCR,AWAL,AWAR',            # food smell neurons (positive control)
    's25_afd': 'AFDL,AFDR',                                    # temperature = magnetism in this model
    's25_light': 'ASJL,ASJR',
    's25_toxic': 'PHAL,PHAR,PHBL,PHBR',
    's25_predator': 'ASHL,ASHR',
    's25_co2': 'BAGL,BAGR',
    's25_o2': 'URXL,URXR,AQR,PQR',
    's25_dopamine': 'CEPDL,CEPDR,CEPVL,CEPVR,ADEL,ADER,PDEL,PDER',
    's25_pheromone': 'ASKL,ASKR,ADLL,ADLR',
    's25_gravity': 'PVDL,PVDR',
    's25_vibration': 'ALML,ALMR,AVM,PLML,PLMR,PVM',
    's25_nose': 'FLPL,FLPR,OLQDL,OLQDR,OLQVL,OLQVR',
}
SEEDS, BRAINS, EVERY = list(range(1, 17)), 12, 50
GENS = {'pilot': 50, 'full': 300}
OUTS = {'pilot': Path('runs/step25_pilot'), 'full': Path('runs/step25')}
RES = Path('results')
WORLDS = list(range(5300, 5312))
MOVE_SPEED = 1.0
TEST = bool(os.environ.get('STEP25_TEST')) or '--test' in sys.argv
if TEST:
    SEEDS, BRAINS, EVERY, WORLDS = [1, 2], 2, 1, [5300, 5301]
    GENS = {'pilot': 2, 'full': 2}
    OUTS = {'pilot': Path('runs/step25_test_pilot'), 'full': Path('runs/step25_test')}
    SENSES = {k: SENSES[k] for k in ('s25_none', 's25_smell', 's25_afd')}
for _a, _n in SENSES.items():
    CONDITIONS[_a] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_a] = dict(s14.PRED, beacon=True, beacon_neurons=_n)


def run(phase, device='cuda'):
    from .batch3_fast import evolve
    out = OUTS[phase]; out.mkdir(parents=True, exist_ok=True)
    for arm in SENSES:
        if all((out / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        print(f'{arm}: cue into [{SENSES[arm] or "nothing"}], {len(SEEDS)} seeds x {GENS[phase]} gens', flush=True)
        evolve(arm, SEEDS, GENS[phase], out=out, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS,
               eval_worlds=1)
    print('BEACON_RUN_DONE', flush=True)


def test(arm, genomes, conn, dev, cue, rew, moving=False):
    """Genomes as 60 clones on the fixed test worlds. cue / rew: 1 = on, 0 = off. moving: the beacon drifts.
    Returns {measure: array (n_genomes,)}: fitness, food, occ (time in circle), dist, arrival."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    opts = CONDITIONS[arm]
    cfg = Config(**dict(CFG_OVERRIDES[arm], beacon_speed=MOVE_SPEED if moving else 0.0))
    P = cfg.worm_population
    keys = {'food': 'mean_food', 'occ': 'beacon_occ', 'dist': 'beacon_dist', 'arrival': 'beacon_arrival'}
    out = {k: [] for k in ['fitness'] + list(keys)}
    for i in range(0, len(genomes), 16):
        gs = genomes[i:i + 16]
        pairs = [(j, w) for j in range(len(gs)) for w in WORLDS]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
        sim.b_cue.fill_(float(cue)); sim.b_rew.fill_(float(rew))
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(WORLDS)
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        for k, m in keys.items():
            out[k] += np.array([x[m] for x in st], float).reshape(len(gs), nw).mean(1).tolist()
    return {k: np.array(v) for k, v in out.items()}


def holm(p):
    ks = sorted(p, key=p.get); m = len(ks); adj, run_max = {}, 0.0
    for i, k in enumerate(ks):
        run_max = max(run_max, min(1.0, (m - i) * p[k])); adj[k] = run_max
    return adj


def analyze(phase):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .connectome import Connectome
    from .step20 import signflip
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    out = OUTS[phase]
    dev, conn = pick_device('cuda'), Connectome()
    seeds = [s for s in SEEDS if all((out / f'{a}_s{s}' / 'best_genome.npy').exists() for a in SENSES)]
    if len(seeds) < 2:
        raise SystemExit(f'only {len(seeds)} seeds finished in every arm; nothing to analyse yet')
    G = {a: [np.load(out / f'{a}_s{s}' / 'best_genome.npy') for s in seeds] for a in SENSES}
    full = phase == 'full'
    T = {}
    for a in SENSES:
        T[a] = dict(on=test(a, G[a], conn, dev, 1, 0), off=test(a, G[a], conn, dev, 0, 0))
        if full:
            T[a].update(train=test(a, G[a], conn, dev, 1, 1), cut=test(a, G[a], conn, dev, 0, 1),
                        mon=test(a, G[a], conn, dev, 1, 0, True), moff=test(a, G[a], conn, dev, 0, 0, True))
        print(f'{a}: tested', flush=True)
    steer = {a: T[a]['on']['occ'] - T[a]['off']['occ'] for a in SENSES}
    cues = [a for a in SENSES if a != 's25_none']
    p = {a: signflip(steer[a]) for a in SENSES}
    ph = holm({a: p[a] for a in cues})
    tag = 'PILOT (50 generations; ranking only, no formal tests)' if not full else 'FULL (pre-registered tests)'
    lines = [f'Step 25 / Beacon series, {tag}: {len(seeds)} seeds, {len(WORLDS)} unseen worlds x 60 clones, reward OFF',
             'arm             steering index (+ seeds)  occ on  occ off  arrival on/off'
             + ('   moving: dist off-on   skill(train)  skill(cue cut)' if full else '')]
    for a in sorted(SENSES, key=lambda x: -steer[x].mean()):
        on, off = T[a]['on'], T[a]['off']
        s = (f'{a:15s} {steer[a].mean():+.4f} ({(steer[a] > 0).sum():2d}/{len(seeds)})       {on["occ"].mean():.4f}  '
             f'{off["occ"].mean():.4f}   {on["arrival"].mean():6.0f}/{off["arrival"].mean():6.0f}')
        if full:
            mv = T[a]['moff']['dist'] - T[a]['mon']['dist']
            s += f'    {mv.mean():+8.2f} ({(mv > 0).sum():2d})      {T[a]["train"]["fitness"].mean():.3f}        {T[a]["cut"]["fitness"].mean():.3f}'
        lines.append(s)
    if full:
        lines.append('PRE-REGISTERED: steering index > 0, paired sign-flip, Holm over the 12 cue arms')
        for a in sorted(cues, key=lambda x: ph[x]):
            v = 'PASS: the cue leads them' if (ph[a] < 0.05 and steer[a].mean() > 0) else (
                'PASS but NEGATIVE: the cue drives them away' if ph[a] < 0.05 else 'no detectable steering')
            lines.append(f'  {a:15s} {steer[a].mean():+.4f}  p={p[a]:.3g}  Holm p={ph[a]:.3g}  -> {v}')
        ok = ph['s25_smell'] < 0.05 and steer['s25_smell'].mean() > 0
        lines.append(f'  positive control s25_smell: {"PASSED" if ok else "FAILED -> setup judged broken"}')
        lines.append(f'  method check s25_none (no cue): steering {steer["s25_none"].mean():+.4f}, p={p["s25_none"]:.3g} (should be ~0)')
        lines.append('REPORTED: skill vs s25_none (train world)')
        b = T['s25_none']['train']['fitness']
        for a in cues:
            d = T[a]['train']['fitness'] - b
            lines.append(f'  {a:15s} {d.mean():+.3f} ({(d > 0).sum()}/{len(seeds)})  p={signflip(d):.3g} (uncorrected)')
    else:
        lines.append('uncorrected sign-flip p of the steering index (pilot, for ranking only): '
                     + ', '.join(f'{a[4:]} {p[a]:.2g}' for a in cues))
    txt = '\n'.join(lines); print(txt)
    name = 'step25' if full else 'step25_pilot'
    (RES / f'{name}_stats.txt').write_text(txt + '\n')
    (RES / f'{name}_stats.json').write_text(json.dumps(dict(
        seeds=seeds, p=p, holm=ph if full else None, steer={a: v.tolist() for a, v in steer.items()},
        tests={a: {t: {m: v.tolist() for m, v in r.items()} for t, r in T[a].items()} for a in SENSES})))
    fig, ax = plt.subplots(1, 3 if full else 1, figsize=(18 if full else 7, 4.8), squeeze=False)
    ax = ax[0]
    order = sorted(SENSES, key=lambda x: -steer[x].mean())
    ax[0].bar(range(len(order)), [steer[a].mean() for a in order],
              yerr=[steer[a].std() / np.sqrt(len(seeds)) for a in order], color='#e76f51')
    ax[0].set_xticks(range(len(order)), [a[4:] for a in order], rotation=40)
    ax[0].axhline(0, color='k', lw=0.6); ax[0].set_title('Steering index: time in the circle, cue on - cue off')
    if full:
        mv = {a: T[a]['moff']['dist'] - T[a]['mon']['dist'] for a in SENSES}
        ax[1].bar(range(len(order)), [mv[a].mean() for a in order], color='#2a9d8f')
        ax[1].set_xticks(range(len(order)), [a[4:] for a in order], rotation=40); ax[1].axhline(0, color='k', lw=0.6)
        ax[1].set_title('Moving beacon: distance cue off - cue on (+ = follows)')
        for a in SENSES:
            h = [json.loads((out / f'{a}_s{s}' / 'history.json').read_text()) for s in seeds]
            n = min(len(r) for r in h)
            ax[2].plot(np.mean([[r['fitness'] for r in x[:n]] for x in h], 0), label=a[4:], lw=0.8)
        ax[2].set(title='Training fitness (mean over seeds)', xlabel='generation'); ax[2].legend(fontsize=6, ncol=2)
    fig.tight_layout(); fig.savefig(RES / f'{name}.png', dpi=110)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['pilot'], ['full'], ['check']):
        import torch
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    if a[:1] == ['pilot']:
        run('pilot', dev); analyze('pilot'); print('BEACON_PILOT_DONE', flush=True)
    elif a[:1] == ['full']:
        run('full', dev); analyze('full'); print('BEACON_FULL_DONE', flush=True)
    elif a[:1] == ['check']:
        run('pilot', dev); analyze('pilot'); run('full', dev); analyze('full'); print('BEACON_CHECK_OK', flush=True)
    elif a[:1] == ['analyze']:
        analyze('full')
    else:
        print(__doc__)
