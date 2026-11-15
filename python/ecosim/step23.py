"""Step 23 = the FOOD-CIRCLE GRAVITY and MAGNETISM EXPERIMENTS (2026-11-14): if a gravity or magnetic field forms
large feathered circles with a bunch of food at the centre of each, do the worms evolve to USE the field to find food?

WORLD
  Everything is the Main Experiment (Step 20) world and scoring, the same as the Gravity experiment (Step 21): the real
  C. elegans connectome brain (old synapses, decoder output), scarce food, 6 predators, touch, hunger peptide, each
  brain scored as 60 clones in a full-size world, 12 brains per seed. NEW (config.py "Step 23"): one large FEATHERED
  CIRCLE per food patch (6 per world): field = 1 within 100 units of the centre, fading smoothly to 0 at 240 units.
  The food grows around the circle centres (patch spread 60), so each circle has a bunch of food at its centre.
  A new world (new food layout -> new circles) every generation, so a brain cannot memorise WHERE the food is; it can
  only learn that "field rising = food ahead".

  GRAVITY circles: local gravity = 1 g + strength x field. Strength 1.0 = 2 g at the centre (a heavy "gravity well"
    on the food). As in Step 21: sensed by PVD, slows worms (0.5x at 2 g), costs energy (+0.3 per tick at 2 g; base
    cost 0.6). So the cue comes with a price: the food sits where moving is slow and costly.
  MAGNETIC circles: field x strength sensed by AFD (Vidal-Gadea et al. 2015, eLife 4:e07493; disputed by Landler et
    al. 2018, eLife 7:e30187). A pure cue: no slowing, no cost. Strength 1.0 x gain 3 = the same size of sensory
    input as the gravity arm, so the two senses differ only in the physical side effects.

ARMS (16 seeds each, paired by seed: same seed = same food layouts every generation in every arm)
  s23_ctrl         circles on the food, both strengths 0: identical world, no field          (the reference)
  s23_grav_food    gravity circles centred on the food, strength 1.0
  s23_grav_decoy   gravity circles of the same size and number, placed AWAY from the food
  s23_mag_food     magnetic circles centred on the food, strength 1.0
  s23_mag_decoy    magnetic circles placed away from the food
  Decoy arms separate "the field is a food cue" from "the field changes the world" (cost, slowing, extra input).

PRE-REGISTERED RULES (written 2026-11-14 20:30 MT, before any run)
  Yardstick: each seed's best brain at generation 300, as 60 clones on 12 fixed unseen worlds (5100-5111), in its own
  arm's world. SENSE-CUT test: the same, but the field sensor is disconnected (PVD gravity input or AFD magnetic input
  set to 0); for gravity the slowing and cost stay.
  Paired sign-flip permutation tests (as Step 20), Holm-corrected over these 4:
    H1  gravity circles change skill:        grav_food - ctrl
    H2  magnetic circles change skill:       mag_food  - ctrl
    H3  the gravity-evolved brains USE it:   grav_food own - grav_food sense-cut
    H4  the magnetic-evolved brains USE it:  mag_food  own - mag_food  sense-cut
  A test PASSES if Holm p < 0.05; the sign says helps (+) or hurts (-).
  Reported, not tested: decoy - ctrl and food - decoy for both senses, sense-cut for decoy arms, OCCUPANCY (mean field
  value under living worms = how much time they spend inside the circles), learning curves.
  Known limits, stated in advance: 16 seeds x 300 generations is short (Step 19 skill was still rising at 300); the
  gravity and magnetism effects are model assumptions, so the results are about this rule set, not real worms.

    python -m ecosim.step23 full           # all 5 arms (skips finished ones; safe to re-queue), then the analysis
    python -m ecosim.step23 run            # arms only
    python -m ecosim.step23 analyze        # tests, statistics, chart
    python -m ecosim.step23 picture        # draws the circles + food of one world -> results/step23_circles.png
    python -m ecosim.step23 check --test   # tiny version (2 seeds, 2 generations, all arms) + analysis + picture:
                                           # the code check, run on the workstation (watcher: food_circles_check)
Watcher: {"experiment": "food_circles_experiment"}
Results: runs/step23/<arm>_s<seed>/ (ckpt_g50..300.npy, best_genome.npy, history.json),
         results/step23_stats.txt + step23_stats.json + step23.png + step23_circles.png
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
OUT, RES = Path('runs/step23'), Path('results')
TEST_WORLDS = list(range(5100, 5112))
STRENGTH = 1.0
if os.environ.get('STEP23_TEST') or '--test' in sys.argv:   # tiny settings to check the code end to end
    SEEDS, GENS, BRAINS, EVERY, OUT, TEST_WORLDS = [1, 2], 2, 2, 1, Path('runs/step23_test'), [5100, 5101]

# arm -> (where the circles go, gravity strength, magnetic strength)
ARMS = {'s23_ctrl': ('food', 0.0, 0.0),
        's23_grav_food': ('food', STRENGTH, 0.0), 's23_grav_decoy': ('decoy', STRENGTH, 0.0),
        's23_mag_food': ('food', 0.0, STRENGTH), 's23_mag_decoy': ('decoy', 0.0, STRENGTH)}
for _a, (_place, _g, _m) in ARMS.items():
    CONDITIONS[_a] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    # every arm has both fields switched on (so all worlds are built by identical code); the strengths decide
    CFG_OVERRIDES[_a] = dict(s14.PRED, gravity=True, magnetism=True, field_circles=True, circle_place=_place)


def set_strengths(sim, arm):
    """Give every world of a simulator its arm's gravity and magnetic strengths (before the first run)."""
    _, g, m = ARMS[arm]
    sim.grav_s.fill_(g)
    sim.mag_s.fill_(m)


def run(out=OUT, device='cuda'):
    from .batch3_fast import evolve
    out.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        if all((out / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        place, g, m = ARMS[arm]
        print(f'{arm}: circles at {place}, gravity strength {g}, magnetic strength {m}, {len(SEEDS)} seeds x {GENS} gens',
              flush=True)
        evolve(arm, SEEDS, GENS, out=out, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS,
               eval_worlds=1, setup=lambda sim, cfg, arm=arm: set_strengths(sim, arm))
    print('FOOD_CIRCLES_RUN_DONE', flush=True)


def test(arm, genomes, conn, dev, worlds=TEST_WORLDS, cut=False):
    """Each genome as 60 clones on the fixed test worlds, in its arm's world. cut=True disconnects the field sensor
    (PVD gravity input and AFD magnetic input) but keeps the physics. Returns {measure: array (n_genomes,)}:
    fitness (skill), food, occupancy (mean field value 0..1 under living worms = time inside the circles)."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[arm], Config(**CFG_OVERRIDES[arm])
    P = cfg.worm_population
    out = {'fitness': [], 'food': [], 'occupancy': []}
    for i in range(0, len(genomes), 16):                       # chunks keep GPU memory small
        gs = genomes[i:i + 16]
        pairs = [(j, wd) for j in range(len(gs)) for wd in worlds]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
        set_strengths(sim, arm)
        if cut:
            sim.gmap.zero_(); sim.mmap.zero_()
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(worlds)
        mean = lambda xs: np.array(xs, float).reshape(len(gs), nw).mean(1).tolist()
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        out['food'] += mean([x['mean_food'] for x in st])
        # every arm's gravity pattern IS its circle field (x circle_sign), so this works for all arms
        out['occupancy'] += mean([x['grav_pattern'] * cfg.circle_sign for x in st])
    return {k: np.array(v) for k, v in out.items()}


def holm(p):
    """Holm-Bonferroni correction of a {name: p} dict."""
    ks = sorted(p, key=p.get); m = len(ks); adj, run_max = {}, 0.0
    for i, k in enumerate(ks):
        run_max = max(run_max, min(1.0, (m - i) * p[k])); adj[k] = run_max
    return adj


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
        raise SystemExit(f'only {len(seeds)} seeds finished in every arm; nothing to analyse yet')
    G = {a: [np.load(out / f'{a}_s{s}' / 'best_genome.npy') for s in seeds] for a in ARMS}
    own = {a: test(a, G[a], conn, dev) for a in ARMS}
    cut = {a: test(a, G[a], conn, dev, cut=True) for a in ARMS if a != 's23_ctrl'}
    F = {a: own[a]['fitness'] for a in ARMS}
    diffs = {'H1 gravity circles vs control': F['s23_grav_food'] - F['s23_ctrl'],
             'H2 magnetic circles vs control': F['s23_mag_food'] - F['s23_ctrl'],
             'H3 gravity brains use the sense': F['s23_grav_food'] - cut['s23_grav_food']['fitness'],
             'H4 magnetic brains use the sense': F['s23_mag_food'] - cut['s23_mag_food']['fitness']}
    p = {k: signflip(v) for k, v in diffs.items()}
    ph = holm(p)
    rep = {'gravity decoy vs control': F['s23_grav_decoy'] - F['s23_ctrl'],
           'magnetic decoy vs control': F['s23_mag_decoy'] - F['s23_ctrl'],
           'gravity: food circles vs decoy': F['s23_grav_food'] - F['s23_grav_decoy'],
           'magnetic: food circles vs decoy': F['s23_mag_food'] - F['s23_mag_decoy'],
           'gravity decoy: own vs sense-cut': F['s23_grav_decoy'] - cut['s23_grav_decoy']['fitness'],
           'magnetic decoy: own vs sense-cut': F['s23_mag_decoy'] - cut['s23_mag_decoy']['fitness']}
    lines = [f'Step 23 / Food-circle gravity & magnetism experiments: {len(seeds)} seeds, best brains at generation {GENS}, '
             f'{len(TEST_WORLDS)} unseen worlds x 60 clones',
             'arm              skill   food   occupancy | sense-cut: skill  occupancy']
    for a in ARMS:
        c = cut.get(a)
        lines.append(f'{a:16s} {F[a].mean():6.3f} {own[a]["food"].mean():6.2f}  {own[a]["occupancy"].mean():6.3f}   | '
                     + (f'{c["fitness"].mean():6.3f}  {c["occupancy"].mean():6.3f}' if c else '   -'))
    lines.append('PRE-REGISTERED TESTS (paired sign-flip, Holm over 4):')
    for k, d in diffs.items():
        v = ('PASS: helps' if d.mean() > 0 else 'PASS: hurts') if ph[k] < 0.05 else 'no detectable effect'
        lines.append(f'  {k:34s} {d.mean():+.3f}  (+ in {(d > 0).sum()}/{len(d)} seeds)  p={p[k]:.3g}  Holm p={ph[k]:.3g}  -> {v}')
    lines.append('REPORTED (not tested):')
    for k, d in rep.items():
        lines.append(f'  {k:34s} {d.mean():+.3f}  (+ in {(d > 0).sum()}/{len(d)} seeds)  p={signflip(d):.3g} (uncorrected)')
    txt = '\n'.join(lines); print(txt)
    (RES / 'step23_stats.txt').write_text(txt + '\n')
    (RES / 'step23_stats.json').write_text(json.dumps(dict(
        seeds=seeds, p=p, holm=ph, tests={k: v.tolist() for k, v in diffs.items()},
        reported={k: v.tolist() for k, v in rep.items()},
        own={a: {m: v.tolist() for m, v in t.items()} for a, t in own.items()},
        cut={a: {m: v.tolist() for m, v in t.items()} for a, t in cut.items()})))
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
    names = list(ARMS); x = np.arange(len(names))
    for a_, key, ttl in ((ax[0], 'fitness', 'Skill on 12 unseen worlds'), (ax[1], 'occupancy', 'Time inside the circles (occupancy)')):
        a_.bar(x - 0.2, [own[n][key].mean() for n in names], 0.4, label='sense connected')
        a_.bar(x + 0.2, [cut[n][key].mean() if n in cut else np.nan for n in names], 0.4, label='sense cut')
        a_.set_xticks(x, [n[4:] for n in names], rotation=20); a_.set_title(ttl); a_.legend(fontsize=8)
    for a in ARMS:
        h = [json.loads((out / f'{a}_s{s}' / 'history.json').read_text()) for s in seeds]
        n = min(len(r) for r in h)
        ax[2].plot(np.mean([[r['fitness'] for r in xx[:n]] for xx in h], 0), label=a[4:])
    ax[2].set(title='Training fitness (mean over seeds)', xlabel='generation'); ax[2].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(RES / 'step23.png', dpi=120)


def picture():
    """Draw the circle field and the food of one world, food placement and decoy placement side by side."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .batch3_fast import circle_centres, make_circle_field
    from .config import Config
    from .world import World
    RES.mkdir(exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(15, 4.6))
    for a_, arm in zip(ax, ('s23_grav_food', 's23_grav_decoy')):
        cfg = Config(**CFG_OVERRIDES[arm]); w = World(cfg, np.random.default_rng(TEST_WORLDS[0]))
        F = make_circle_field(cfg, circle_centres(cfg, w.patch_centers), w.gw, w.gh)
        im = a_.imshow(F.T, origin='lower', extent=[0, cfg.width, 0, cfg.height], cmap='magma', vmin=0, vmax=1)
        fd = w.food[w.food_alive]
        a_.scatter(fd[:, 0], fd[:, 1], s=4, c='lime', label='food')
        a_.set_title(f'circles at {cfg.circle_place} (field 0..1; 1 = centre)'); a_.legend(loc='upper right', fontsize=8)
        fig.colorbar(im, ax=a_, fraction=0.025)
    fig.tight_layout(); fig.savefig(RES / 'step23_circles.png', dpi=110)
    print('saved results/step23_circles.png', flush=True)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    dev = None
    if a[:1] in (['full'], ['run'], ['check']):
        import torch
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    if a[:1] == ['full']:                      # the watcher job: all arms, then the analysis
        run(device=dev); analyze(); print('FOOD_CIRCLES_FULL_DONE', flush=True)
    elif a[:1] == ['check']:                   # workstation code check: tiny run + analysis + picture
        picture(); run(device=dev); analyze(); print('FOOD_CIRCLES_CHECK_OK', flush=True)
    elif a[:1] == ['run']:
        run(device=dev)
    elif a[:1] == ['analyze']:
        analyze()
    elif a[:1] == ['picture']:
        picture()
    else:
        print(__doc__)
