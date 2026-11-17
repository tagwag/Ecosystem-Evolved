"""Step 27b = FLEEING FOOD, FIXED (2026-11-17). Step 27 failed as designed: food noticed worms 40 units away and was
uncatchable even at half speed, so the worms evolved to STOP MOVING (the score rewarded surviving longest = reward
hacking). Owner asked to re-run with the fixes, plus one world where the food moves but cannot notice the worms.

FIXES (config.py "Step 27b", batch3_fast fitness mode 'eaten')
  1 food notices a worm only within 15 units (was 40; eating distance is 8);
  2 only HALF the food moves; the other half stays still, so worms can always forage normally;
  3 the score is FOOD EATEN ONLY (no survival tie-break), so standing still earns nothing.

ARMS (16 seeds each, paired by seed, 300 generations; Main Experiment world otherwise; speed = x worm top speed 5)
  b27_still     no food moves (reference)
  b27_slow      movers FLEE at 0.5x      b27_close  0.9x      b27_edge  1.1x      b27_fast  1.5x      b27_veryfast  3x
  b27_drift     movers DRIFT at 0.9x: they wander all the time with a slowly turning heading and cannot sense worms
                (owner's request: food that is just moving). Same speed as b27_close, so close vs drift separates
                "the food runs away" from "the food moves".

MEASURES (each seed's best brain at generation 300, 60 clones x 12 fixed unseen worlds 5450-5461, own arm's world)
  skill (= food eaten per worm), catches of MOVING food per world, group-catch share (another worm within 15 units),
  ambush share (eats by a worm under 20 % speed), mean speed (idling check), and the same brains in the still world.

PRE-REGISTERED RULES (written 2026-11-17 09:40 MT, before any run)
  R1 evolution learns to catch moving food: catches of moving food, evolved vs random starting brains on the same
     worlds, paired sign-flip, Holm over the 6 moving arms (5 fleeing + drift).
  R2 catches fall with flee speed: Spearman correlation of catches per world with speed ratio over the 5 fleeing arms
     x 16 seeds (two-sided).
  R3 running away matters: catches of moving food, b27_close (flees) vs b27_drift (wanders at the same speed), paired
     sign-flip by seed.
  IDLING CHECK (decided now): if any arm's evolved mean speed is below 0.05, that arm is flagged as having idled and its
  catch results are not interpreted.
  Reported, not tested: skill, group share, ambush share, skill in the still world.

    python -m ecosim.step27b full           # all arms (skips finished ones; safe to re-queue) + analysis
    python -m ecosim.step27b analyze
    python -m ecosim.step27b check --test   # 2 seeds, 2 gens, 3 arms + analysis (watcher: fleeing_food2_check)
Results: runs/step27b/<arm>_s<seed>/, results/step27b_stats.txt + .json, results/step27b.png
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
FIX = dict(food_flee_radius=15.0, food_flee_fraction=0.5)
ARMS = {'b27_still': (0.0, 'flee'), 'b27_slow': (0.5, 'flee'), 'b27_close': (0.9, 'flee'), 'b27_edge': (1.1, 'flee'),
        'b27_fast': (1.5, 'flee'), 'b27_veryfast': (3.0, 'flee'), 'b27_drift': (0.9, 'drift')}
SEEDS, GENS, BRAINS, EVERY = list(range(1, 17)), 300, 12, 50
OUT, RES = Path('runs/step27b'), Path('results')
WORLDS = list(range(5450, 5462))
TEST = bool(os.environ.get('STEP27B_TEST')) or '--test' in sys.argv
if TEST:
    SEEDS, GENS, BRAINS, EVERY, OUT, WORLDS = [1, 2], 2, 2, 1, Path('runs/step27b_test'), [5450, 5451]
    ARMS = {k: ARMS[k] for k in ('b27_still', 'b27_close', 'b27_drift')}
    RES = Path('results/_test_artifacts')
for _a, (_r, _m) in ARMS.items():
    CONDITIONS[_a] = dataclasses.replace(CONDITIONS['hunger'], fitness='eaten')
    CFG_OVERRIDES[_a] = dict(s14.PRED, food_flee_speed=_r * WORM_TOP, food_flee_mode=_m, **FIX)


def random_brains(arm):
    from . import worm2 as w
    from .connectome import Connectome
    conn = Connectome()
    return [w.random_genomes(conn, 1, np.random.default_rng(20_000 + s), CONDITIONS[arm])[0] for s in SEEDS]


def test(arm, genomes, conn, dev, world_arm=None):
    """Genomes as 60 clones on the fixed test worlds of world_arm's world (default own). -> {measure: (n,)}"""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[arm], Config(**CFG_OVERRIDES[world_arm or arm])
    P, nw = cfg.worm_population, len(WORLDS)
    out = {k: [] for k in ('skill', 'catches', 'group', 'ambush', 'speed')}
    for i in range(0, len(genomes), 16):
        gs = genomes[i:i + 16]
        pairs = [(j, w) for j in range(len(gs)) for w in WORLDS]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        avg = lambda xs: np.array(xs, float).reshape(len(gs), nw).mean(1).tolist()
        navg = lambda xs: [float(np.nanmean(r)) if np.isfinite(r).any() else float('nan')
                           for r in np.array(xs, float).reshape(len(gs), nw)]
        out['skill'] += avg([x['mean_food'] for x in st])
        out['speed'] += avg([x['mean_speed'] for x in st])
        if sim.flee_on:
            fl = np.array([x['flee'] for x in st], float)
            with np.errstate(invalid='ignore', divide='ignore'):
                out['catches'] += avg(fl[:, 0])
                out['group'] += navg(np.where(fl[:, 0] > 0, fl[:, 1] / fl[:, 0], np.nan))
                out['ambush'] += navg(np.where(fl[:, 2] > 0, fl[:, 3] / fl[:, 2], np.nan))
        else:
            for k in ('catches', 'group', 'ambush'):
                out[k] += [float('nan')] * len(gs)
    return {k: np.array(v) for k, v in out.items()}


def run(device='cuda'):
    from .batch3_fast import evolve
    OUT.mkdir(parents=True, exist_ok=True)
    for arm, (r, m) in ARMS.items():
        if all((OUT / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        print(f'{arm}: half the food {"drifts" if m == "drift" else "flees"} at {r}x worm top speed '
              f'(notices worms within 15), score = food eaten, {len(SEEDS)} seeds x {GENS} gens', flush=True)
        evolve(arm, SEEDS, GENS, out=OUT, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS, eval_worlds=1)
    print('FLEEING_FOOD2_RUN_DONE', flush=True)


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
    RES.mkdir(parents=True, exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    G = {a: [np.load(OUT / f'{a}_s{s}' / 'best_genome.npy') for s in SEEDS] for a in ARMS}
    own = {a: test(a, G[a], conn, dev) for a in ARMS}
    still = {a: test(a, G[a], conn, dev, 'b27_still') for a in ARMS}
    moving = [a for a in ARMS if ARMS[a][0] > 0]
    flee = [a for a in moving if ARMS[a][1] == 'flee']
    rnd = {a: test(a, random_brains(a), conn, dev) for a in moving}
    idle = {a: bool(own[a]['speed'].mean() < 0.05) for a in ARMS}
    d1 = {a: own[a]['catches'] - rnd[a]['catches'] for a in moving}
    p1 = {a: signflip(d) for a, d in d1.items()}; h1 = holm(p1)
    x = np.concatenate([[ARMS[a][0]] * len(SEEDS) for a in flee]); y = np.concatenate([own[a]['catches'] for a in flee])
    rho, p2 = spearmanr(x, y)
    L = [f'Step 27b / Fleeing food, fixed: {len(SEEDS)} seeds, best brains at generation {GENS}, {len(WORLDS)} unseen worlds x 60 clones',
         'arm           speed mode   skill  catches/world  group  ambush  move speed | skill in still world' + '   IDLE?']
    for a in ARMS:
        o = own[a]
        L.append(f'{a:13s} {ARMS[a][0]:4.1f} {ARMS[a][1]:5s}  {o["skill"].mean():6.3f}  {np.nanmean(o["catches"]) if a in moving else float("nan"):10.2f}'
                 f'  {np.nanmean(o["group"]) if a in moving else float("nan"):6.3f} {np.nanmean(o["ambush"]) if a in moving else float("nan"):6.3f}'
                 f'   {o["speed"].mean():6.3f}   | {still[a]["skill"].mean():6.3f}' + ('   IDLED: not interpreted' if idle[a] else ''))
    L += ['PRE-REGISTERED:', '  R1 evolved vs random brains, catches of moving food (paired sign-flip, Holm over 6):']
    for a in moving:
        v = ('PASS: ' + ('evolution learned to catch more' if d1[a].mean() > 0 else 'evolved brains catch LESS')) if h1[a] < 0.05 else 'no detectable difference'
        L.append(f'    {a:12s} {d1[a].mean():+.2f} ({(d1[a] > 0).sum()}/{len(SEEDS)})  p={p1[a]:.3g}  Holm p={h1[a]:.3g} -> {v}'
                 + ('  [IDLED]' if idle[a] else ''))
    L.append(f'  R2 catches vs flee speed (fleeing arms): Spearman rho = {rho:+.3f}, p = {p2:.3g} -> '
             + (('PASS: catches ' + ('fall' if rho < 0 else 'rise') + ' with speed') if p2 < 0.05 else 'no detectable trend'))
    if 'b27_close' in ARMS and 'b27_drift' in ARMS:
        d3 = own['b27_close']['catches'] - own['b27_drift']['catches']; p3 = signflip(d3)
        L.append(f'  R3 fleeing (0.9x) vs drifting (0.9x) food, catches: {d3.mean():+.2f} ({(d3 > 0).sum()}/{len(SEEDS)})  p={p3:.3g} -> '
                 + (('PASS: running away makes food ' + ('EASIER?!' if d3.mean() > 0 else 'harder') + ' to catch') if p3 < 0.05 else 'no detectable difference'))
    else:
        p3 = None
    txt = '\n'.join(L); print(txt)
    (RES / 'step27b_stats.txt').write_text(txt + '\n')
    tl = lambda d: {k: np.asarray(v).tolist() for k, v in d.items()}
    (RES / 'step27b_stats.json').write_text(json.dumps(dict(seeds=SEEDS, R1=dict(p=p1, holm=h1), R2=dict(rho=rho, p=p2), R3=p3,
        idle=idle, own={a: tl(v) for a, v in own.items()}, random={a: tl(v) for a, v in rnd.items()},
        still={a: tl(v) for a, v in still.items()}), default=float))
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
    ax[0].plot([ARMS[a][0] for a in flee], [np.nanmean(own[a]['catches']) for a in flee], 'o-', label='evolved')
    ax[0].plot([ARMS[a][0] for a in flee], [np.nanmean(rnd[a]['catches']) for a in flee], 's--', label='random')
    if 'b27_drift' in ARMS:
        ax[0].plot([0.9], [np.nanmean(own['b27_drift']['catches'])], 'r*', ms=12, label='drift (evolved)')
    ax[0].set(title='Catches of moving food per world', xlabel='food speed / worm top speed'); ax[0].legend()
    ax[1].bar(range(len(ARMS)), [own[a]['speed'].mean() for a in ARMS]); ax[1].axhline(0.05, color='r', lw=0.8)
    ax[1].set_xticks(range(len(ARMS)), [a[4:] for a in ARMS], rotation=30); ax[1].set_title('Mean movement (red line = idling limit)')
    for a in ARMS:
        h = [json.loads((OUT / f'{a}_s{s}' / 'history.json').read_text()) for s in SEEDS]
        n = min(len(r) for r in h)
        ax[2].plot(np.mean([[r['mean_food'] for r in xx[:n]] for xx in h], 0), label=a[4:], lw=0.9)
    ax[2].set(title='Food eaten per worm during evolution', xlabel='generation'); ax[2].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(RES / 'step27b.png', dpi=110)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['full'], ['check']):
        import torch
        run('cuda' if torch.cuda.is_available() else 'cpu'); analyze()
        print('FLEEING_FOOD2_CHECK_OK' if a[0] == 'check' else 'FLEEING_FOOD2_FULL_DONE', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
