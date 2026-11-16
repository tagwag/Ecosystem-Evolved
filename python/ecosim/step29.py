"""Step 29 = ERODING GRAVITY (2026-11-16, owner's idea of 14 Nov): the gravity landscape starts the same in every arm
and then CHANGES slowly over the generations, like erosion reshaping terrain. Does a changing landscape change how
worms evolve to use their gravity sense?

WHY NOW: Step 24 (gravity bite test) showed that with harsh rules (heavy ground costs up to 2.5x the cost of living)
AND the gravity sense, worms evolve to avoid heavy ground (+0.195, 14/16 seeds, Holm p 0.00045); the rule written
before that run said erosion is worth running with those rules if it responded. It did.

WORLD: the Main Experiment world (as Step 24) + the cave-style gravity pattern with the Step 24 BITE rules (strength 1.0,
cost 1.5, slowing 0.5, PVD sensing gain 3). Every world of a generation has the same pattern.

EROSION: the pattern is built from a noise field N(t). N moves smoothly from one independent noise field to the next:
N(t) = cos(phi) N_k + sin(phi) N_(k+1), k = floor(t), phi = (t - k) x 90 degrees (keeps the field's statistics while it
morphs), then shaped into feathered cave walls exactly as Step 21. t = TURNOVERS x generation / 300, so TURNOVERS = how
many times the whole landscape is replaced during the run. Every arm starts from the SAME field N_0.

ARMS (16 seeds each, paired by seed, 300 generations; erosion level on the owner's 0-100 idea, as turnovers per run):
  e29_rate0    0 turnovers  (static landscape: the reference)
  e29_rate1    1 turnover   (slow erosion: the landscape is fully different by the end)
  e29_rate3    3 turnovers
  e29_rate10   10 turnovers (fast: noticeably different every ~30 generations)
  e29_new      a brand-new independent landscape EVERY generation (maximum change)

EXPECTATION, stated before the run: the worms have no sense of position and no memory of places, so they cannot learn
WHERE heavy ground is, only how to react to what PVD feels. If that is all evolution can use, erosion should change
little. An effect would mean the brains tune to features of a particular landscape (e.g. feature size or wall shape)
that a changing landscape does not reward.

TESTS (each seed's best brain at generation 300, 60 clones x 12 fixed unseen worlds 5500-5511, bite rules)
  FRESH: each world gets its own never-seen landscape (noise seeds 9_000_000+i): can the brain avoid heavy ground it
         has never met?  Also on the ORIGINAL landscape N_0, and on the arm's own FINAL landscape.
  Measures: avoidance (-(mean pattern value under living worms); > 0 = stays on light ground), skill, speed.

PRE-REGISTERED RULES (written 2026-11-16 10:20 MT, before any run)
  E1 dose-response: Spearman correlation of FRESH-landscape avoidance with erosion level (ranks 0 < 1 < 3 < 10 < new)
     over 5 arms x 16 seeds, two-sided, p < 0.05.
  E2 each eroding arm vs e29_rate0 on FRESH landscapes: paired sign-flip, Holm over 4, p < 0.05.
  Reported, not tested: avoidance on the original and the final landscape, skill, speed, avoidance during evolution
  (history 'grav_pattern' per generation: how fast evolution tracks the change).

    python -m ecosim.step29 full           # all arms (skips finished ones; safe to re-queue) + analysis (watcher: erosion_experiment)
    python -m ecosim.step29 analyze
    python -m ecosim.step29 picture        # the landscape at generations 0, 100, 200, 300 for each arm -> results/step29_landscapes.png
    python -m ecosim.step29 check --test   # 2 seeds, 4 generations, all arms + analysis (watcher: erosion_check)
Results: runs/step29/<arm>_s<seed>/, results/step29_stats.txt + .json, step29.png, step29_landscapes.png
"""
import dataclasses
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

SEEDS, GENS, BRAINS, EVERY = list(range(1, 17)), 300, 12, 50
OUT, RES = Path('runs/step29'), Path('results')
WORLDS = list(range(5500, 5512))
BITE = dict(gravity=True, grav_cost=1.5)
RATES = {'e29_rate0': 0.0, 'e29_rate1': 1.0, 'e29_rate3': 3.0, 'e29_rate10': 10.0, 'e29_new': None}
LEVEL = {'e29_rate0': 0, 'e29_rate1': 1, 'e29_rate3': 2, 'e29_rate10': 3, 'e29_new': 4}   # rank for E1
NOISE_BASE, FRESH_BASE = 20261116, 9_000_000
TEST = bool(os.environ.get('STEP29_TEST')) or '--test' in sys.argv
if TEST:
    SEEDS, GENS, BRAINS, EVERY, OUT, WORLDS = [1, 2], 4, 2, 2, Path('runs/step29_test'), [5500, 5501]
for _a in RATES:
    CONDITIONS[_a] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_a] = dict(s14.PRED, **BITE)


def _cfg():
    from .config import Config
    return Config(**CFG_OVERRIDES['e29_rate0'])


@lru_cache(maxsize=64)
def _noise(seed):
    from .batch3_fast import gravity_noise
    from .world import World
    cfg = _cfg(); w = World(cfg, np.random.default_rng(0))
    return gravity_noise(cfg, w.gw, w.gh, seed)


def landscape(arm, g):
    """The gravity pattern of arm at generation g, flattened to the smell grid (cells,)."""
    from .batch3_fast import gravity_shape
    cfg = _cfg()
    r = RATES[arm]
    if r is None:                                    # a new independent landscape every generation (g=0: the start one)
        N = _noise(NOISE_BASE) if g == 0 else _noise(NOISE_BASE + 7919 * g)
    else:
        t = r * g / GENS
        k = int(np.floor(t)); phi = (t - k) * np.pi / 2
        N = np.cos(phi) * _noise(NOISE_BASE + 1000 * k) + np.sin(phi) * _noise(NOISE_BASE + 1000 * (k + 1))
    return gravity_shape(cfg, N).reshape(-1)


def run(device='cuda'):
    import torch
    from .batch3_fast import evolve
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in RATES:
        if all((OUT / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        hold = {}

        def setup(sim, cfg, arm=arm):
            hold['sim'] = sim
            sim.grav_s.fill_(1.0)
            sim.gpat.copy_(torch.as_tensor(landscape(arm, 0), device=sim.gpat.device)[None].expand_as(sim.gpat))

        def on_gen(g, k, *_, arm=arm):
            if k == len(SEEDS) - 1:                  # after the last seed of generation g: landscape for g + 1
                sim = hold['sim']
                sim.gpat.copy_(torch.as_tensor(landscape(arm, g + 1), device=sim.gpat.device)[None].expand_as(sim.gpat))
        print(f'{arm}: erosion {RATES[arm] if RATES[arm] is not None else "new landscape every generation"} '
              f'turnovers, {len(SEEDS)} seeds x {GENS} gens', flush=True)
        evolve(arm, SEEDS, GENS, out=OUT, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS,
               eval_worlds=1, setup=setup, on_gen=on_gen)
    print('EROSION_RUN_DONE', flush=True)


def test(arm, genomes, conn, dev, which):
    """which: 'fresh' (a never-seen landscape per world), 'original' (N_0), 'final' (the arm's generation-GENS one)."""
    import torch
    from .batch3_fast import FastSim, gravity_shape
    from .config import Config
    opts, cfg = CONDITIONS[arm], Config(**CFG_OVERRIDES[arm])
    P, nw = cfg.worm_population, len(WORLDS)
    pairs = [(j, w) for j in range(len(genomes)) for w in WORLDS]
    G = np.stack([np.repeat(genomes[j][None], P, 0) for j, _ in pairs])
    gen = torch.Generator(device=dev); gen.manual_seed(4242)
    sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
    sim.grav_s.fill_(1.0)
    if which == 'fresh':
        pats = np.stack([gravity_shape(cfg, _noise(FRESH_BASE + i)).reshape(-1) for i in range(nw)])
        sim.gpat.copy_(torch.as_tensor(np.tile(pats, (len(genomes), 1)), device=sim.gpat.device))
    else:
        p = landscape(arm, 0 if which == 'original' else GENS)
        sim.gpat.copy_(torch.as_tensor(p, device=sim.gpat.device)[None].expand_as(sim.gpat))
    fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
    avg = lambda key: np.array([x[key] for x in st], float).reshape(len(genomes), nw).mean(1)
    return dict(fitness=fit.mean(1).reshape(len(genomes), nw).mean(1), avoidance=-avg('grav_pattern'),
                speed=avg('mean_speed'), food=avg('mean_food'))


def holm(p):
    ks = sorted(p, key=p.get); m = len(ks); adj, run_max = {}, 0.0
    for i, k in enumerate(ks):
        run_max = max(run_max, min(1.0, (m - i) * p[k])); adj[k] = run_max
    return adj


def analyze():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy.stats import spearmanr
    from .connectome import Connectome
    from .step20 import signflip
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    Gm = {a: [np.load(OUT / f'{a}_s{s}' / 'best_genome.npy') for s in SEEDS] for a in RATES}
    T = {a: {w: test(a, Gm[a], conn, dev, w) for w in ('fresh', 'original', 'final')} for a in RATES}
    x = np.concatenate([[LEVEL[a]] * len(SEEDS) for a in RATES])
    y = np.concatenate([T[a]['fresh']['avoidance'] for a in RATES])
    rho, p1 = spearmanr(x, y)
    base = T['e29_rate0']['fresh']['avoidance']
    d = {a: T[a]['fresh']['avoidance'] - base for a in RATES if a != 'e29_rate0'}
    p2 = {a: signflip(v) for a, v in d.items()}; h2 = holm(p2)
    L = [f'Step 29 / Eroding gravity: {len(SEEDS)} seeds, best brains at generation {GENS}, {len(WORLDS)} unseen worlds x 60 clones, bite rules',
         'arm          avoidance: FRESH  original   final  |  skill(fresh)  speed(fresh)']
    for a in RATES:
        f, o, fi = T[a]['fresh'], T[a]['original'], T[a]['final']
        L.append(f'{a:12s}        {f["avoidance"].mean():+.4f}  {o["avoidance"].mean():+.4f}  {fi["avoidance"].mean():+.4f}  |'
                 f'     {f["fitness"].mean():.3f}        {f["speed"].mean():.3f}')
    L += ['PRE-REGISTERED:',
          f'  E1 fresh-landscape avoidance vs erosion level: Spearman rho = {rho:+.3f}, p = {p1:.3g} -> '
          + (('PASS: more erosion, ' + ('MORE' if rho > 0 else 'LESS') + ' avoidance of unseen heavy ground') if p1 < 0.05 else 'no detectable trend'),
          '  E2 each eroding arm vs static (fresh landscapes, paired sign-flip, Holm over 4):']
    for a, v in d.items():
        verdict = ('PASS: ' + ('more' if v.mean() > 0 else 'less') + ' avoidance than static') if h2[a] < 0.05 else 'no detectable difference'
        L.append(f'    {a:11s} {v.mean():+.4f} ({(v > 0).sum()}/{len(SEEDS)})  p={p2[a]:.3g}  Holm p={h2[a]:.3g} -> {verdict}')
    txt = '\n'.join(L); print(txt)
    (RES / 'step29_stats.txt').write_text(txt + '\n')
    tl = lambda r: {k: np.asarray(v).tolist() for k, v in r.items()}
    (RES / 'step29_stats.json').write_text(json.dumps(dict(seeds=SEEDS, E1=dict(rho=rho, p=p1), E2=dict(p=p2, holm=h2),
                                                          tests={a: {w: tl(r) for w, r in T[a].items()} for a in RATES}), default=float))
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    names = list(RATES); xs = np.arange(len(names))
    for i, w in enumerate(('fresh', 'original', 'final')):
        ax[0].bar(xs + (i - 1) * 0.27, [T[a][w]['avoidance'].mean() for a in names], 0.27, label=w)
    ax[0].set_xticks(xs, [a[4:] for a in names]); ax[0].axhline(0, color='k', lw=0.6)
    ax[0].set_title('Avoidance of heavy ground (> 0 = stays on light ground)'); ax[0].legend(fontsize=8)
    for a in names:
        h = [json.loads((OUT / f'{a}_s{s}' / 'history.json').read_text()) for s in SEEDS]
        n = min(len(r) for r in h)
        ax[1].plot([-np.mean([r[i]['grav_pattern'] for r in h]) for i in range(n)], label=a[4:], lw=0.9)
    ax[1].set(title='Avoidance during evolution (own landscape, mean over seeds)', xlabel='generation'); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(RES / 'step29.png', dpi=110)


def picture():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .world import World
    cfg = _cfg(); w = World(cfg, np.random.default_rng(0))
    gens = [0, GENS // 3, 2 * GENS // 3, GENS]
    fig, ax = plt.subplots(len(RATES), len(gens), figsize=(3.2 * len(gens), 1.9 * len(RATES)))
    for i, a in enumerate(RATES):
        for j, g in enumerate(gens):
            ax[i, j].imshow(landscape(a, g).reshape(w.gw, w.gh).T, origin='lower', cmap='magma', vmin=-1, vmax=1)
            ax[i, j].set_xticks([]); ax[i, j].set_yticks([])
            if i == 0: ax[i, j].set_title(f'generation {g}')
            if j == 0: ax[i, j].set_ylabel(a[4:])
    fig.suptitle('Eroding gravity landscapes (bright = heavy)'); fig.tight_layout()
    RES.mkdir(exist_ok=True); fig.savefig(RES / ('step29_test_landscapes.png' if TEST else 'step29_landscapes.png'), dpi=100)
    print('saved landscape picture', flush=True)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['full'], ['check']):
        import torch
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        picture(); run(dev); analyze()
        print('EROSION_CHECK_OK' if a[0] == 'check' else 'EROSION_FULL_DONE', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    elif a[:1] == ['picture']:
        picture()
    else:
        print(__doc__)
