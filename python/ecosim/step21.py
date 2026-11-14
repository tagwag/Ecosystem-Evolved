"""Step 21 = the GRAVITY EXPERIMENT: does a pattern of heavy and light ground change how the worms evolve to behave?

Everything is the Main Experiment (Step 20) world and scoring - the real C. elegans connectome brain (old synapses,
decoder output: the version that scored best in Step 20), scarce food, 6 predators, touch, hunger peptide, each brain
scored as 60 clones in a full-size world, 12 brains per seed - plus ONE new thing: a gravity pattern.

THE GRAVITY PATTERN (config.py "Step 21", batch3_fast.make_gravity_pattern)
  local gravity = 1 g + strength x pattern.  The pattern is made like the cave walls of the original Java game
  (simplex noise, "wall" where the noise is high) with feathered edges: walls are heavy ground, open ground is light,
  and one fades into the other. It is IDENTICAL in every world; only the STRENGTH differs.
  `python -m ecosim.step21 pattern` draws it to results/step21_gravity_pattern.png. Worms SENSE the local offset (into the PVD neurons), are SLOWED on heavy
  ground / faster on light ground, and PAY more energy on heavy ground / less on light ground.

THE DESIGN: A DOSE-RESPONSE SERIES ("graded seeds")
  100 seeds x 300 generations. Seed i gets strength  s_i = 0.001 x 1000^((i-1)/99):
      seed 1 = 0.001 (gravity 0.999-1.001 g: not measurably different from flat), seed 2 = 0.00107, ...
      seed 50 = 0.031, seed 75 = 0.175, seed 100 = 1.0 (gravity 0 g to 2 g).
  Each step multiplies the strength by 1.072, so neighbours are almost identical and the ends are 1000x apart
  (a logarithmic / geometric series). There are no "groups": the analysis looks for a TREND along the series.
  Every seed also has its own luck (random start, random food layouts), which is independent of its strength,
  so a trend across 100 seeds cannot come from luck alone - but any SINGLE seed proves nothing.
  Runs as 4 batches of 25 seeds, one after the other (100 at once does not fit the 10 GB card).

PRE-REGISTERED RULES (written 2026-11-13 21:30 MT, before any run)
  Every seed's best brain at generation 300 is tested as 60 clones on 12 fixed unseen worlds (5000-5011) three ways:
    OWN     at its own gravity strength          -> skill there
    STRONG  at strength 1.0, the same for all    -> AVOIDANCE = -(mean pattern value under living worms): 0 = ignores
            gravity, > 0 = stays on light ground. Same world for every brain, so differences are in the brains.
    FLAT    at strength 0                        -> general skill with no gravity pattern at all
  1. BEHAVIOUR: gravity strength shapes behaviour if Spearman rank correlation between log10(strength) and STRONG
     avoidance is > 0 with p < 0.05 (two-sided, 100 seeds).
  2. COST OF SPECIALISING: Spearman correlation between log10(strength) and FLAT skill, p < 0.05 either direction.
  3. Reported, not tested: the curve in 10 bins of 10 seeds with 95 % CIs; where along the series avoidance first
     leaves the range of the 20 weakest seeds (mean +- 2 SD) for 2 bins in a row = the "threshold strength".
  Known limits, stated in advance: the slow / fast effect alone makes worms linger on heavy ground (a passive bias);
  it is the same for every brain in the STRONG test, so it cancels in rule 1. The gravity effects are model
  assumptions (heavier = slower and costlier), so results are about this rule set, not real worm physiology.

    python -m ecosim.step21 run            # all 4 batches (skips finished ones; safe to re-queue after an interrupt)
    python -m ecosim.step21 analyze        # the three tests, statistics, chart
    python -m ecosim.step21 check --test   # tiny version (4 seeds, 2 generations) + analysis + pattern picture:
                                           # the code check, run on the workstation (watcher: gravity_check)
    python -m ecosim.step21 pattern        # just draw the gravity pattern
Watcher: {"experiment": "gravity_experiment"} then {"experiment": "gravity_analyze"}
Results: runs/step21/s21_grav_s<seed>/ (ckpt_g50..300.npy, best_genome.npy, history.json incl. grav_pattern per
         generation), runs/step21/strengths.json, results/step21_stats.json + step21_stats.txt + step21.png
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

N_SEEDS, GENS, BRAINS, BATCH, EVERY = 100, 300, 12, 25, 50
S_MIN, S_MAX = 0.001, 1.0
OUT, RES = Path('runs/step21'), Path('results')
TEST_WORLDS = list(range(5000, 5012))
COND = 's21_grav'
if os.environ.get('STEP21_TEST') or '--test' in sys.argv:   # tiny settings to check the code end to end
    N_SEEDS, GENS, BRAINS, BATCH, EVERY, OUT, TEST_WORLDS = 4, 2, 2, 2, 1, Path('runs/step21_test'), [5000, 5001]
SEEDS = list(range(1, N_SEEDS + 1))
CONDITIONS[COND] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
CFG_OVERRIDES[COND] = dict(s14.PRED, gravity=True)


def strength(seed):
    """Gravity pattern strength of a seed: geometric series from S_MIN (seed 1) to S_MAX (last seed)."""
    return float(S_MIN * (S_MAX / S_MIN) ** ((seed - 1) / max(N_SEEDS - 1, 1)))


def run(out=OUT, device='cuda'):
    import torch
    from .batch3_fast import evolve
    out.mkdir(parents=True, exist_ok=True)
    (out / 'strengths.json').write_text(json.dumps({str(s): strength(s) for s in SEEDS}, indent=1))
    for b in range(0, N_SEEDS, BATCH):
        seeds = SEEDS[b:b + BATCH]
        if all((out / f'{COND}_s{s}' / 'best_genome.npy').exists() for s in seeds):
            print(f'batch seeds {seeds[0]}-{seeds[-1]}: already done, skipped', flush=True); continue
        print(f'batch seeds {seeds[0]}-{seeds[-1]}: gravity strength {strength(seeds[0]):.4g} .. {strength(seeds[-1]):.4g}', flush=True)

        def setup(sim, cfg, seeds=seeds):
            # worlds are ordered seed by seed (K seeds x BRAINS brains x 1 world each): give each its seed's strength
            per = sim.K // len(seeds)
            s = torch.tensor([strength(x) for x in seeds], dtype=torch.float32).repeat_interleave(per)
            sim.grav_s.copy_(s.view(-1, 1).to(sim.grav_s.device))
        evolve(COND, seeds, GENS, out=out, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS,
               eval_worlds=1, setup=setup)
    print('GRAVITY_EXPERIMENT_DONE', flush=True)


def test(genomes, strengths, conn, dev, worlds=TEST_WORLDS):
    """Each genome as 60 clones on the fixed test worlds at the given gravity strength (one per genome).
    Returns {measure: array (n_genomes,)}: fitness (skill), food, speed, grav_pattern, grav_offset."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[COND], Config(**CFG_OVERRIDES[COND])
    P, keys = cfg.worm_population, ('fitness', 'mean_food', 'mean_speed', 'grav_pattern', 'grav_offset')
    out = {k: [] for k in keys}
    for i in range(0, len(genomes), 25):                       # chunks keep GPU memory small
        gs, ss = genomes[i:i + 25], strengths[i:i + 25]
        pairs = [(j, wd) for j in range(len(gs)) for wd in worlds]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
        sim.grav_s.copy_(torch.tensor([ss[j] for j, _ in pairs], dtype=torch.float32, device=dev).view(-1, 1))
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(worlds)
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        for k in keys[1:]:
            out[k] += np.array([x[k] for x in st]).reshape(len(gs), nw).mean(1).tolist()
    return {k: np.array(v) for k, v in out.items()}


def analyze(out=OUT):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy import stats
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    seeds = [s for s in SEEDS if (out / f'{COND}_s{s}' / 'best_genome.npy').exists()]
    if len(seeds) < 4:
        raise SystemExit(f'only {len(seeds)} finished seeds; nothing to analyse yet')
    G = [np.load(out / f'{COND}_s{s}' / 'best_genome.npy') for s in seeds]
    S = np.array([strength(s) for s in seeds]); logS = np.log10(S)
    T = {'own': test(G, S.tolist(), conn, dev), 'strong': test(G, [S_MAX] * len(G), conn, dev),
         'flat': test(G, [0.0] * len(G), conn, dev)}
    avoid = -T['strong']['grav_pattern']
    r1 = stats.spearmanr(logS, avoid); r2 = stats.spearmanr(logS, T['flat']['fitness']); r3 = stats.spearmanr(logS, T['own']['fitness'])
    nb = max(2, len(seeds) // 10); bins = np.array_split(np.arange(len(seeds)), nb)
    ci = lambda x: 1.96 * np.std(x, ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0
    base = avoid[:max(2, len(seeds) // 5)]; lo, hi = base.mean() - 2 * base.std(ddof=1), base.mean() + 2 * base.std(ddof=1)
    outside = [not (lo <= avoid[b].mean() <= hi) for b in bins]
    thr = next((float(S[bins[i][0]]) for i in range(len(bins) - 1) if outside[i] and outside[i + 1]), None)
    verdict = lambda r, pos_only: ('YES' if r.pvalue < 0.05 and (r.statistic > 0 or not pos_only) else 'no detectable trend')
    lines = [f'Step 21 / Gravity experiment: {len(seeds)} seeds, strengths {S[0]:.4g} .. {S[-1]:.4g}, best brains at generation {GENS}',
             f'1. BEHAVIOUR  avoidance of heavy ground (STRONG test, strength {S_MAX}) vs log10(training strength): '
             f'Spearman rho = {r1.statistic:+.3f}, p = {r1.pvalue:.3g} -> {verdict(r1, True)}',
             f'2. COST       FLAT skill (no gravity) vs log10(strength): rho = {r2.statistic:+.3f}, p = {r2.pvalue:.3g} -> {verdict(r2, False)}',
             f'   (reported) OWN-world skill vs log10(strength): rho = {r3.statistic:+.3f}, p = {r3.pvalue:.3g}',
             f'3. threshold strength (avoidance leaves the weakest-fifth range for 2 bins in a row): {thr if thr else "none found"}',
             'bin  strength range        avoidance (STRONG)   skill OWN   skill FLAT']
    for b in bins:
        lines.append(f'{seeds[b[0]]:3d}-{seeds[b[-1]]:<3d} {S[b[0]]:.4f}-{S[b[-1]]:.4f}   {avoid[b].mean():+.4f} +- {ci(avoid[b]):.4f}   '
                     f'{T["own"]["fitness"][b].mean():.3f}       {T["flat"]["fitness"][b].mean():.3f}')
    txt = '\n'.join(lines); print(txt)
    (RES / 'step21_stats.txt').write_text(txt + '\n')
    (RES / 'step21_stats.json').write_text(json.dumps(dict(
        seeds=seeds, strength=S.tolist(), threshold=thr,
        spearman=dict(avoidance=[float(r1.statistic), float(r1.pvalue)], flat_skill=[float(r2.statistic), float(r2.pvalue)],
                      own_skill=[float(r3.statistic), float(r3.pvalue)]),
        tests={k: {m: v.tolist() for m, v in t.items()} for k, t in T.items()})))
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for a, y, ttl in ((ax[0], avoid, f'Avoidance of heavy ground (all tested at strength {S_MAX})'),
                      (ax[1], T['own']['fitness'], 'Skill in its own gravity world'), (ax[2], T['flat']['fitness'], 'Skill with no gravity pattern')):
        a.scatter(S, y, s=14, alpha=0.6)
        a.errorbar([np.sqrt(S[b[0]] * S[b[-1]]) for b in bins], [y[b].mean() for b in bins], yerr=[ci(y[b]) for b in bins], color='k', marker='o')
        a.set(xscale='log', xlabel='gravity pattern strength the seed evolved under (log scale)', title=ttl)
    ax[0].axhline(0, color='gray', lw=0.8)
    fig.tight_layout(); fig.savefig(RES / 'step21.png', dpi=120)


def pattern_png():
    """Draw the gravity pattern (and the hard-edged cave version it comes from) to results/step21_gravity_pattern.png."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .batch3_fast import make_gravity_pattern
    from .config import Config
    from .world import World
    RES.mkdir(exist_ok=True)
    cfg = Config(**CFG_OVERRIDES[COND]); w = World(cfg, np.random.default_rng(0))
    soft = make_gravity_pattern(cfg, w.gw, w.gh)
    hard = make_gravity_pattern(dataclasses.replace(cfg, grav_feather=0.0), w.gw, w.gh)
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.2), gridspec_kw=dict(width_ratios=[1, 1, 0.8]))
    ext = [0, cfg.width, 0, cfg.height]
    ax[0].imshow(hard.T, origin='lower', extent=ext, cmap='Greys'); ax[0].set_title('Original method: hard cave walls (wall = dark)')
    im = ax[1].imshow(1 + soft.T, origin='lower', extent=ext, cmap='RdBu_r', vmin=0, vmax=2)
    ax[1].set_title('Gravity pattern at strength 1.0: feathered edges (g)'); fig.colorbar(im, ax=ax[1], fraction=0.03)
    row = soft[:, w.gh // 2]
    for st, lab in ((1.0, 'seed 100 (1.0)'), (0.175, 'seed 75 (0.175)'), (0.031, 'seed 50 (0.031)'), (0.001, 'seed 1 (0.001)')):
        ax[2].plot((np.arange(w.gw) + 0.5) * cfg.smell_cell, 1 + st * row, label=lab)
    ax[2].set(title='Gravity along a line through the middle', xlabel='x', ylabel='g'); ax[2].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(RES / 'step21_gravity_pattern.png', dpi=110)
    print(f'pattern: min {soft.min():.2f} max {soft.max():.2f} mean {soft.mean():.4f}; heavy (> 0.5) {np.mean(soft > 0.5):.0%} of the world, '
          f'light (< 0) {np.mean(soft < 0):.0%}; saved results/step21_gravity_pattern.png', flush=True)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] == ['pattern']:
        pattern_png()
    elif a[:1] == ['full']:                     # the watcher job: all batches, then the analysis
        import torch
        run(device='cuda' if torch.cuda.is_available() else 'cpu'); analyze(); print('GRAVITY_FULL_DONE', flush=True)
    elif a[:1] == ['check']:                    # workstation code check: tiny run + analysis + the pattern picture
        import torch
        pattern_png(); run(device='cuda' if torch.cuda.is_available() else 'cpu'); analyze()
        print('GRAVITY_CHECK_OK', flush=True)
    elif a[:1] == ['run']:
        import torch
        run(device='cuda' if torch.cuda.is_available() else 'cpu')
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
