"""Step 27 = FLEEING FOOD (2026-11-16): food that runs away, from easy to catch to much faster than a worm.
Full design and reasoning: ecosim/STEP27_FLEEING_FOOD_DESIGN.md.  Term: a PURSUIT-EVASION setup; the key number
is the SPEED RATIO = food top speed / worm top speed (worm top speed = config.speed_max = 5 units per tick).

WORLD
  Step 23 control world (connectome, scarce food in 6 patches, predators, touch, hunger peptide, 60 clones, 12 brains
  per seed). NEW (config.py "Step 27"): each living food item checks the nearest living worm; if it is within 40
  units the food moves directly away from it at the arm's speed, plus a random wobble of +-0.35 rad. Food stays
  smellable (the smell map is rebuilt every block of ticks). The world wraps around (no walls, no corners), so food
  faster than a worm can only be caught by running INTO a worm: pincers by several worms, or ambushes.

ARMS (16 seeds each, paired by seed, 300 generations)
  s27_still 0x | s27_slow 0.5x | s27_close 0.9x | s27_edge 1.1x | s27_fast 1.5x | s27_veryfast 3x  (speed ratio)
  FALLBACK decided before the run: before an arm is evolved, 16 random brains are tested in its world. If they catch
  fewer than 1 fleeing food per world per generation, the arm is ALSO run with TIRING food (runs 30 ticks, must
  rest 30): arm name + '_tired'. Both versions are reported. Decisions saved in runs/step27/tiring.json.

MEASURES (each seed's best brain at generation 300, 60 clones x 12 fixed unseen worlds 5400-5411, own arm's world)
  skill, food eaten, catches of fleeing food per world, GROUP-CATCH SHARE (another worm within 40 units of the food
  at the catch: pincer / herding), AMBUSH SHARE (eats by a worm moving under 20 % speed), mean chase length.
  Cross-tests: every arm's brains also in the still-food world and in the 1.1x world.

PRE-REGISTERED RULES (written 2026-11-16 08:20 MT, before any run)
  R1 cost of speed: Spearman correlation of skill with speed ratio over the 6 main arms x 16 seeds (two-sided).
  R2 group hunting: Spearman correlation of group-catch share with speed ratio over the 5 moving main arms x 16
     seeds, one-sided (expected positive).
  R3 evolution helps: in each moving main arm, catches per world of evolved brains vs random starting brains on the
     same worlds, paired sign-flip, Holm over the 5 arms.
  Reported, not tested: ambush share, chase length, cross-tests, tired arms, learning curves.
  Known limit: 60 clones share one brain, so "cooperation" here is copies of one brain helping each other.

    python -m ecosim.step27 full           # all arms (skips finished ones; safe to re-queue) + analysis
    python -m ecosim.step27 analyze
    python -m ecosim.step27 check --test   # 2 seeds, 2 gens, 3 arms + analysis (watcher: fleeing_food_check)
Results: runs/step27/<arm>_s<seed>/, results/step27_stats.txt + .json, results/step27.png
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

WORM_TOP = 5.0
RATIOS = {'s27_still': 0.0, 's27_slow': 0.5, 's27_close': 0.9, 's27_edge': 1.1, 's27_fast': 1.5, 's27_veryfast': 3.0}
SEEDS, GENS, BRAINS, EVERY = list(range(1, 17)), 300, 12, 50
OUT, RES = Path('runs/step27'), Path('results')
WORLDS = list(range(5400, 5412))
TIRE = dict(food_tire_run=30, food_tire_rest=30)
TEST = bool(os.environ.get('STEP27_TEST')) or '--test' in sys.argv
if TEST:
    SEEDS, GENS, BRAINS, EVERY, OUT, WORLDS = [1, 2], 2, 2, 1, Path('runs/step27_test'), [5400, 5401]
    RATIOS = {k: RATIOS[k] for k in ('s27_still', 's27_edge', 's27_veryfast')}


def _register(arm, ratio, tired=False):
    CONDITIONS[arm] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[arm] = dict(s14.PRED, food_flee_speed=ratio * WORM_TOP, **(TIRE if tired else {}))


for _a, _r in RATIOS.items():
    _register(_a, _r)
    if _r > 0:
        _register(_a + '_tired', _r, True)


def random_brains(arm):
    """Random starting brains, one per seed (the same recipe evolution starts from)."""
    from . import worm2 as w
    from .connectome import Connectome
    conn = Connectome()
    return [w.random_genomes(conn, 1, np.random.default_rng(10_000 + s), CONDITIONS[arm])[0] for s in SEEDS]


def test(arm, genomes, conn, dev, world_arm=None):
    """Genomes as 60 clones on the fixed test worlds of world_arm's world (default: their own arm).
    Returns {measure: array (n,)}: fitness, food, catches, group, ambush, chase."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    wa = world_arm or arm
    opts, cfg = CONDITIONS[arm], Config(**CFG_OVERRIDES[wa])
    P = cfg.worm_population
    out = {k: [] for k in ('fitness', 'food', 'catches', 'group', 'ambush', 'chase')}
    for i in range(0, len(genomes), 16):
        gs = genomes[i:i + 16]
        pairs = [(j, w) for j in range(len(gs)) for w in WORLDS]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(WORLDS)
        avg = lambda xs: np.array(xs, float).reshape(len(gs), nw).mean(1).tolist()
        # ratios (group / ambush share, chase length) are undefined in a world with no catches: average over the
        # worlds that had some (nan only if a brain caught nothing anywhere)
        navg = lambda xs: [float(np.nanmean(r)) if np.isfinite(r).any() else float('nan')
                           for r in np.array(xs, float).reshape(len(gs), nw)]
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        out['food'] += avg([x['mean_food'] for x in st])
        if sim.flee_on:
            fl = np.array([x['flee'] for x in st], float)               # (pairs, 6)
            with np.errstate(invalid='ignore', divide='ignore'):
                out['catches'] += avg(fl[:, 0])
                out['group'] += navg(np.where(fl[:, 0] > 0, fl[:, 1] / fl[:, 0], np.nan))
                out['ambush'] += navg(np.where(fl[:, 2] > 0, fl[:, 3] / fl[:, 2], np.nan))
                out['chase'] += navg(np.where(fl[:, 0] > 0, fl[:, 4] / fl[:, 0], np.nan))
        else:
            for k in ('catches', 'group', 'ambush', 'chase'):
                out[k] += [np.nan] * len(gs)
    return {k: np.array(v) for k, v in out.items()}


def arms_to_run():
    """Main arms + the tired version of any moving arm whose random brains catch < 1 fleeing food per world."""
    import torch
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    f = OUT / 'tiring.json'
    if f.exists():
        dec = json.loads(f.read_text())
    else:
        dev, conn = pick_device('cuda'), Connectome()
        dec = {}
        for a, r in RATIOS.items():
            if r > 0:
                c = float(np.nanmean(test(a, random_brains(a), conn, dev)['catches']))
                dec[a] = dict(random_catches_per_world=c, tired_arm_added=c < 1.0)
                print(f'{a}: random brains catch {c:.2f} fleeing food per world -> tired arm '
                      f'{"ADDED" if c < 1.0 else "not needed"}', flush=True)
        OUT.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(dec, indent=1))
    return list(RATIOS) + [a + '_tired' for a, d in dec.items() if d['tired_arm_added']]


def run(device='cuda'):
    from .batch3_fast import evolve
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms_to_run():
        if all((OUT / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        print(f'{arm}: food speed {CFG_OVERRIDES[arm]["food_flee_speed"]:.2f} '
              f'({CFG_OVERRIDES[arm]["food_flee_speed"] / WORM_TOP:.1f}x worm top speed)'
              f'{", tiring" if arm.endswith("_tired") else ""}, {len(SEEDS)} seeds x {GENS} gens', flush=True)
        evolve(arm, SEEDS, GENS, out=OUT, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS, eval_worlds=1)
    print('FLEEING_FOOD_RUN_DONE', flush=True)


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
    arms = [a for a in arms_to_run() if all((OUT / f'{a}_s{s}' / 'best_genome.npy').exists() for s in SEEDS)]
    G = {a: [np.load(OUT / f'{a}_s{s}' / 'best_genome.npy') for s in SEEDS] for a in arms}
    own = {a: test(a, G[a], conn, dev) for a in arms}
    edge = 's27_edge' if 's27_edge' in RATIOS else list(RATIOS)[1]
    cross_still = {a: test(a, G[a], conn, dev, 's27_still') for a in arms}
    cross_edge = {a: test(a, G[a], conn, dev, edge) for a in arms}
    main = [a for a in RATIOS if a in arms]
    moving = [a for a in main if RATIOS[a] > 0]
    rnd = {a: test(a, random_brains(a), conn, dev) for a in moving}
    x1 = np.concatenate([[RATIOS[a]] * len(SEEDS) for a in main]); y1 = np.concatenate([own[a]['fitness'] for a in main])
    r1, p1 = spearmanr(x1, y1)
    x2 = np.concatenate([[RATIOS[a]] * len(SEEDS) for a in moving]); y2 = np.concatenate([own[a]['group'] for a in moving])
    ok = np.isfinite(y2)
    r2, p2two = spearmanr(x2[ok], y2[ok]) if ok.sum() > 2 else (np.nan, np.nan)
    p2 = p2two / 2 if r2 > 0 else 1 - p2two / 2
    d3 = {a: np.nan_to_num(own[a]['catches']) - np.nan_to_num(rnd[a]['catches']) for a in moving}
    p3 = {a: signflip(d) for a, d in d3.items()}; h3 = holm(p3)
    L = [f'Step 27 / Fleeing food: {len(SEEDS)} seeds, best brains at generation {GENS}, {len(WORLDS)} unseen worlds x 60 clones',
         'arm                 ratio  skill   food  catches/world  group share  ambush share  chase ticks | skill in still world  in 1.1x world']
    for a in arms:
        o = own[a]
        L.append(f'{a:19s} {CFG_OVERRIDES[a]["food_flee_speed"] / WORM_TOP:4.1f}  {o["fitness"].mean():6.3f} {o["food"].mean():6.2f}'
                 f'  {np.nanmean(o["catches"]) if moving else 0:10.2f}   {np.nanmean(o["group"]):9.3f}    {np.nanmean(o["ambush"]):9.3f}'
                 f'   {np.nanmean(o["chase"]):8.1f}   | {cross_still[a]["fitness"].mean():8.3f}        {cross_edge[a]["fitness"].mean():8.3f}')
    L += ['PRE-REGISTERED:',
          f'  R1 skill vs speed ratio (main arms): Spearman rho = {r1:+.3f}, p = {p1:.3g} -> '
          + ('PASS: ' + ('skill falls' if r1 < 0 else 'skill rises') + ' with food speed' if p1 < 0.05 else 'no detectable trend'),
          f'  R2 group-catch share vs speed ratio (moving arms, one-sided): rho = {r2:+.3f}, p = {p2:.3g} -> '
          + ('PASS: group hunting rises with food speed' if (p2 < 0.05 and r2 > 0) else 'no detectable rise'),
          '  R3 evolved vs random brains, catches per world (paired sign-flip, Holm over the moving arms):']
    for a in moving:
        v = ('PASS: evolution helps' if d3[a].mean() > 0 else 'PASS: evolved brains catch LESS') if h3[a] < 0.05 else 'no detectable difference'
        L.append(f'    {a:14s} {d3[a].mean():+.2f} ({(d3[a] > 0).sum()}/{len(SEEDS)})  p={p3[a]:.3g}  Holm p={h3[a]:.3g} -> {v}')
    tj = OUT / 'tiring.json'
    if tj.exists():
        L.append('Tiring fallback decisions (random brains, before evolution): ' + ', '.join(
            f'{a} {d["random_catches_per_world"]:.2f}/world{" -> tired arm" if d["tired_arm_added"] else ""}'
            for a, d in json.loads(tj.read_text()).items()))
    txt = '\n'.join(L); print(txt)
    (RES / 'step27_stats.txt').write_text(txt + '\n')
    tl = lambda d: {k: v.tolist() for k, v in d.items()}
    (RES / 'step27_stats.json').write_text(json.dumps(dict(
        seeds=SEEDS, R1=dict(rho=r1, p=p1), R2=dict(rho=r2, p=p2), R3=dict(p=p3, holm=h3, diff=tl(d3)),
        own={a: tl(v) for a, v in own.items()}, random={a: tl(v) for a, v in rnd.items()},
        cross_still={a: tl(v) for a, v in cross_still.items()}, cross_edge={a: tl(v) for a, v in cross_edge.items()}),
        default=float))
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
    rs = [RATIOS[a] for a in main]
    ax[0].errorbar(rs, [own[a]['fitness'].mean() for a in main], [own[a]['fitness'].std() / 4 for a in main], marker='o')
    ax[0].set(title='Skill vs food speed', xlabel='food speed / worm top speed', ylabel='skill')
    ax[1].plot([RATIOS[a] for a in moving], [np.nanmean(own[a]['group']) for a in moving], 'o-', label='group-catch share')
    ax[1].plot([RATIOS[a] for a in moving], [np.nanmean(own[a]['ambush']) for a in moving], 's-', label='ambush share')
    ax[1].set(title='How fleeing food is caught', xlabel='food speed / worm top speed'); ax[1].legend()
    for a in arms:
        h = [json.loads((OUT / f'{a}_s{s}' / 'history.json').read_text()) for s in SEEDS]
        n = min(len(r) for r in h)
        ax[2].plot(np.mean([[r['fitness'] for r in x[:n]] for x in h], 0), label=a[4:], lw=0.9)
    ax[2].set(title='Training fitness (mean over seeds)', xlabel='generation'); ax[2].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(RES / 'step27.png', dpi=110)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['full'], ['check']):
        import torch
        run('cuda' if torch.cuda.is_available() else 'cpu'); analyze()
        print('FLEEING_FOOD_CHECK_OK' if a[0] == 'check' else 'FLEEING_FOOD_FULL_DONE', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
