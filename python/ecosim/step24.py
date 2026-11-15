"""Step 24 = GRAVITY BITE TEST: can gravity matter to evolution at all in this world?

WHY: the Gravity experiment (Step 21, 100 seeds, strength 0.001 .. 1.0) found NO trend: worms evolved under a strong
gravity pattern avoided heavy ground no more than worms evolved under almost none (Spearman rho = +0.10, p = 0.33),
and every group sat slightly MORE on heavy ground than chance (they move slower there, so they linger).
Before spending GPU time on changing ("eroding") gravity patterns, this test asks the prior question: is there any
setting of the gravity rules at which evolution responds? If not even a harsh, constant pattern produces avoidance,
a slowly changing one cannot.

ARMS (16 seeds each, paired by seed, 200 generations, Main Experiment world + the Step 21 cave-style pattern,
run one after the other so the GPU stays near half load):
  s24_flat    gravity strength 0 during evolution                     (baseline: brains that never met gravity)
  s24_base    strength 1.0, Step 21 rules (cost 0.3, slow 0.5)        (repeat of the strongest Step 21 setting)
  s24_bite    strength 1.0, cost 1.5 (5x): heaviest ground costs 2.5x the cost of living, light ground is nearly free
  s24_blind   strength 1.0, cost 1.5, but the worm cannot sense gravity (gain 0)   (is sensing needed?)

PRE-REGISTERED RULE (written 2026-11-14 12:30 MT, before any run)
  Every seed's best brain at generation 200 is tested as 60 clones on 12 fixed unseen worlds (5000-5011) at
  strength 1.0 with the s24_bite rules (the same test world for every arm; s24_blind brains are tested blind).
  AVOIDANCE = -(mean pattern value under living worms). An arm RESPONDS TO GRAVITY if its avoidance is higher than
  s24_flat's (paired sign-flip test, Holm over the 3 comparisons, p < 0.05).
  Decision it feeds: if s24_bite responds, the changing-pattern ("erosion") experiment is worth running with the
  bite rules. If nothing responds, gravity as modelled is invisible to selection and the idea needs a different
  mechanism (for example food that grows better on light ground) before any erosion run.

    python -m ecosim.step24 full           # the 4 arms one after another, then the analysis (watcher: gravity_bite_test)
    python -m ecosim.step24 analyze
    python -m ecosim.step24 check --test   # tiny version, run on the workstation (watcher: gravity_bite_check)
Results: runs/step24/<arm>_s<seed>/, results/step24_stats.txt + step24_stats.json
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14
from .step20 import signflip

SEEDS, BRAINS, GENS, EVERY = list(range(1, 17)), 12, 200, 50
OUT, RES = Path('runs/step24'), Path('results')
TEST_WORLDS = list(range(5000, 5012))
if os.environ.get('STEP24_TEST') or '--test' in sys.argv:
    SEEDS, BRAINS, GENS, EVERY, OUT, TEST_WORLDS = [1, 2], 2, 2, 1, Path('runs/step24_test'), [5000, 5001]
BITE = dict(grav_cost=1.5)
ARMS = {'s24_flat': (0.0, {}), 's24_base': (1.0, {}), 's24_bite': (1.0, BITE), 's24_blind': (1.0, dict(BITE, grav_gain=0.0))}
for _c, (_s, _o) in ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_c] = dict(s14.PRED, gravity=True, **_o)
TEST_CFG = {a: dict(s14.PRED, gravity=True, **BITE, **({'grav_gain': 0.0} if a == 's24_blind' else {})) for a in ARMS}


def run(device='cuda'):
    import torch
    from .batch3_fast import evolve
    for arm, (s, _) in ARMS.items():
        if all((OUT / f'{arm}_s{x}' / 'best_genome.npy').exists() for x in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue

        def setup(sim, cfg, s=s):
            sim.grav_s.fill_(s)                              # the same gravity strength in every world of this arm
        evolve(arm, SEEDS, GENS, out=OUT, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS,
               eval_worlds=1, setup=setup)


def test(arm, genomes, conn, dev):
    """Genomes as 60 clones on the test worlds at strength 1.0 with the bite rules -> {measure: array (n,)}."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[arm], Config(**TEST_CFG[arm])
    P, keys = cfg.worm_population, ('mean_food', 'mean_speed', 'grav_pattern')
    out = {k: [] for k in ('fitness',) + keys}
    pairs = [(j, wd) for j in range(len(genomes)) for wd in TEST_WORLDS]
    G = np.stack([np.repeat(genomes[j][None], P, 0) for j, _ in pairs])
    gen = torch.Generator(device=dev); gen.manual_seed(4242)
    sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
    sim.grav_s.fill_(1.0)
    fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
    nw = len(TEST_WORLDS)
    out['fitness'] = fit.mean(1).reshape(len(genomes), nw).mean(1)
    for k in keys:
        out[k] = np.array([x[k] for x in st]).reshape(len(genomes), nw).mean(1)
    out['avoidance'] = -out['grav_pattern']
    return out


def analyze():
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    Y = {a: test(a, [np.load(OUT / f'{a}_s{s}' / 'best_genome.npy') for s in SEEDS], conn, dev) for a in ARMS}
    flat = Y['s24_flat']['avoidance']
    comp = {a: Y[a]['avoidance'] - flat for a in ARMS if a != 's24_flat'}
    p = {a: signflip(d) for a, d in comp.items()}
    order = sorted(p, key=p.get); holm, run_ = {}, 0.0
    for r, a in enumerate(order):
        run_ = max(run_, min(1.0, (len(order) - r) * p[a])); holm[a] = run_
    lines = [f'Step 24 / Gravity bite test: best brains at generation {GENS}, {len(SEEDS)} seeds, tested at strength 1.0 with the bite rules',
             'arm         avoidance   skill    food   speed']
    for a in ARMS:
        r = Y[a]
        lines.append(f'{a:10s}  {r["avoidance"].mean():+.4f}    {r["fitness"].mean():.3f}   {r["mean_food"].mean():.2f}   {r["mean_speed"].mean():.3f}')
    for a in comp:
        v = 'RESPONDS TO GRAVITY' if comp[a].mean() > 0 and holm[a] < 0.05 else 'no detectable response'
        lines.append(f'{a} - s24_flat: avoidance {comp[a].mean():+.4f} (higher in {(comp[a] > 0).sum()}/{len(SEEDS)} seeds), p={p[a]:.3g}, Holm p={holm[a]:.3g} -> {v}')
    txt = '\n'.join(lines); print(txt)
    (RES / 'step24_stats.txt').write_text(txt + '\n')
    (RES / 'step24_stats.json').write_text(json.dumps(dict(seeds=SEEDS, p=p, holm=holm,
                                                           yardstick={a: {k: np.asarray(v).tolist() for k, v in Y[a].items()} for a in ARMS})))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    import torch
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    if a[:1] in (['full'], ['check']):
        run(dev); analyze(); print('GRAVITY_BITE_CHECK_OK' if a[0] == 'check' else 'GRAVITY_BITE_DONE', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
