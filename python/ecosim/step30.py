"""Step 30 = SUPER WORM (2026-11-22, owner's idea): take the best ancestor of every past experiment AT ITS PEAK (not
after it degraded), record them in a HALL OF FAME, then run an experiment built only around nurturing those genes to
grow in score. Goal: make a super worm and learn what it takes to MAKE it and to MAINTAIN it.

THE COMMON YARDSTICK ("our criteria")
  Every brain is scored in ONE standard world, the Main Experiment world as used for Step 23 control (s23_ctrl:
  connectome brain, scarce food in 6 patches, 6 predators, touch, hunger peptide, score = energy left at the end +
  time survived), as 60 clones on fixed unseen worlds. Scores from different experiments' own worlds are NOT
  comparable; this puts every brain on the same test.

PHASE A - HARVEST (python -m ecosim.step30 harvest; watcher: super_harvest)
  Candidates: every saved snapshot (ckpt_g*.npy every 10-50 generations, plus best_genome.npy) of every past run
  whose brain has the standard 5,131-gene layout (the hunger connectome brain with the 28-interneuron decoder).
  Excluded: runs whose genes mean something else despite the same length (Step 20 reversal / muscle arms), other
  layouts (no-peptide 4,736, Step 20b body readout, Step 4 growing brains), test and quick runs.
  1 screen:   every snapshot on 4 worlds (5700-5703).
  2 re-test:  the best 300 snapshots on 24 fresh worlds (5710-5733) -> the hall-of-fame score.
  PEAK = for each lineage (one run's seed), the snapshot with the highest re-test score; later, degraded snapshots
  of the same lineage are ignored. HALL OF FAME = lineage peaks ranked by score, at most 2 per experiment arm (so one
  experiment cannot fill the hall with near-copies). Saved: runs/step30/hall/hall_of_fame.csv + the genomes.

PHASE B - NURTURE (python -m ecosim.step30 nurture; watcher: super_nurture)
  Every arm: 16 seeds x 300 generations, 12 brains per seed, 60 clones, standard world, best brain checkpointed every
  25 generations. What differs is what the evolution starts from and how reliably it selects:
    n30_random   random brains (the normal start; the reference)
    n30_pool     the 12 best hall-of-fame champions as the starting population
    n30_best     the single best champion + 11 mutants of it
    n30_pool_x4  the 12 champions, but every brain scored on 4 worlds per generation instead of 1 (less luck in
                 selection; 4x the GPU time)

MEASURES: each seed's checkpoints (every 25 generations) re-tested on the 24 hall-of-fame worlds.
  peak = best checkpoint score, final = generation 300 score, decline = peak - final (the "maintain" question),
  and whether any brain beats the hall's best champion (the "super worm" question).

PRE-REGISTERED RULES (written 2026-11-22 13:55 MT, before any run; paired sign-flip by seed, Holm over S1-S3)
  S1 champions help: n30_pool final > n30_random final.
  S2 reliable selection helps: n30_pool_x4 final > n30_pool final.
  S3 reliable selection maintains: n30_pool_x4 decline < n30_pool decline.
  Reported, not tested: n30_best vs n30_pool (diversity vs one elite line), the best brain overall vs the hall's best
  champion, learning curves.

    python -m ecosim.step30 harvest | nurture | analyze | full
    add --rep to nurture/analyze: an INDEPENDENT REPLICATE with new seeds 17-32 (owner's request 2026-11-23: "do the
      super worm again"); same hall, same arms, same rules S1-S3; outputs tagged _rep.
    python -m ecosim.step30 confirm   (watcher: super_confirm) - FRESH-WORLD CONFIRMATION (pre-registered 2026-11-23
      07:10 MT): the super worm, the 12 hall champions, and every seed's best checkpoint of every arm (chosen on the 24
      hall worlds) re-tested on 48 never-used worlds 5800-5847. Reported: how much each score shrinks (winner's
      curse), whether the super worm still beats the best champion, and the arm ranking on fresh worlds.
    python -m ecosim.step30 check --test     (watcher: super_check)
Results: runs/step30/, results/step30_hall.txt, step30_stats.txt + .json, step30.png. Super worm genome:
runs/step30/SUPER_WORM.npy (the best brain found anywhere, with its score in SUPER_WORM.json).
"""
import csv
import dataclasses
import glob
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from . import step23  # noqa: F401  registers s23_ctrl (the standard world)
from .step3 import CONDITIONS, CFG_OVERRIDES

STD = 's23_ctrl'
OUT, RES = Path('runs/step30'), Path('results')
SCREEN_W, HALL_W = list(range(5700, 5704)), list(range(5710, 5734))
N_RETEST, PER_ARM, POOL = 300, 2, 12
EXCLUDE = {'s20_rev', 's20_mus', 's20_both', 's20b_body'}
SEEDS, GENS, EVERY = list(range(1, 17)), 300, 25
ARMS = {'n30_random': ('random', 1), 'n30_pool': ('pool', 1), 'n30_best': ('best', 1), 'n30_pool_x4': ('pool', 4)}
FRESH_W = list(range(5800, 5848))
REP = '--rep' in sys.argv
TAG = '_rep' if REP else ''
if REP:
    SEEDS = list(range(17, 33))
TEST = bool(os.environ.get('STEP30_TEST')) or '--test' in sys.argv
LIMIT = None
if TEST:
    OUT, RES = Path('runs/step30_test'), Path('results/_test_artifacts')
    SCREEN_W, HALL_W, N_RETEST, SEEDS, GENS, EVERY, LIMIT = [5700], [5710, 5711], 20, [1, 2], 2, 1, 60
    FRESH_W = [5800, 5801]
for _a in ARMS:
    CONDITIONS[_a] = CONDITIONS[STD]
    CFG_OVERRIDES[_a] = dict(CFG_OVERRIDES[STD])


def score(genomes, worlds, dev, conn, chunk=None):
    """Each genome as 60 clones on the given worlds of the standard world -> mean skill per genome (array)."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[STD], Config(**CFG_OVERRIDES[STD])
    P, nw, out = cfg.worm_population, len(worlds), []
    chunk = chunk or max(1, 256 // nw)                       # <= 256 worlds (15,360 worms) on the GPU at once
    sim = None
    for i in range(0, len(genomes), chunk):
        gs = genomes[i:i + chunk]
        pairs = [(j, w) for j in range(len(gs)) for w in worlds]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs]).astype(np.float32)
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        if sim is None or sim.K != len(pairs):
            sim = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen)
        else:
            sim.gen = gen
        fit, _ = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        out += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
    return np.array(out)


def candidates():
    """[(experiment, arm, seed, generation or -1 for best_genome, path)] of every compatible snapshot."""
    c = []
    for d in sorted(glob.glob('runs/*/*_s*')):
        step = d.split(os.sep)[1]
        if 'test' in step or 'quick' in step or step.startswith('step30'):
            continue
        arm, seed = os.path.basename(d).rsplit('_s', 1)
        b = os.path.join(d, 'best_genome.npy')
        if arm in EXCLUDE or not os.path.exists(b) or np.load(b, mmap_mode='r').shape != (5131,):
            continue
        for f in os.listdir(d):
            if f.startswith('ckpt_g') and f.endswith('.npy'):
                c.append((step, arm, seed, int(f[6:-4]), os.path.join(d, f)))
        c.append((step, arm, seed, -1, b))
    return c[:LIMIT] if LIMIT else c


def harvest():
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    (OUT / 'hall').mkdir(parents=True, exist_ok=True); RES.mkdir(parents=True, exist_ok=True)
    C = candidates()
    print(f'harvest: {len(C)} snapshots from {len({(c[0], c[1], c[2]) for c in C})} lineages', flush=True)
    sf = OUT / 'screen.npy'
    S = np.load(sf) if sf.exists() else np.full(len(C), np.nan)
    if len(S) != len(C):
        S = np.full(len(C), np.nan)
    t0, step = time.time(), 512
    for i in range(0, len(C), step):                         # resumable, saved every chunk
        if np.isfinite(S[i:i + step]).all():
            continue
        S[i:i + step] = score([np.load(c[4]) for c in C[i:i + step]], SCREEN_W, dev, conn)
        np.save(sf, S)
        print(f'  screened {min(i + step, len(C))}/{len(C)}  ({(time.time() - t0) / 60:.1f} min)', flush=True)
    top = np.argsort(-S)[:N_RETEST]
    R = score([np.load(C[i][4]) for i in top], HALL_W, dev, conn)
    rows = [dict(experiment=C[i][0], arm=C[i][1], seed=C[i][2], generation=C[i][3], path=C[i][4],
                 screen=float(S[i]), score=float(r)) for i, r in zip(top, R)]
    peak = {}
    for r in rows:                                           # PEAK per lineage: best re-tested snapshot
        k = (r['experiment'], r['arm'], r['seed'])
        if k not in peak or r['score'] > peak[k]['score']:
            peak[k] = r
    hall, per = [], {}
    for r in sorted(peak.values(), key=lambda r: -r['score']):
        a = (r['experiment'], r['arm'])
        if per.get(a, 0) < PER_ARM:
            per[a] = per.get(a, 0) + 1; hall.append(r)
    for n, r in enumerate(hall):
        r['rank'] = n + 1
        np.save(OUT / 'hall' / f'hof_{n + 1:03d}.npy', np.load(r['path']))
    with open(OUT / 'hall' / 'hall_of_fame.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['rank', 'score', 'screen', 'experiment', 'arm', 'seed', 'generation', 'path'])
        w.writeheader(); w.writerows(hall)
    base = score([np.load(b) for b in sorted(glob.glob(f'runs/step23/{STD}_s*/best_genome.npy'))[:16]], HALL_W, dev, conn) \
        if not TEST else np.array([np.nan])
    L = [f'Step 30 HALL OF FAME: {len(C)} snapshots screened on {len(SCREEN_W)} worlds, top {len(top)} re-tested on '
         f'{len(HALL_W)} worlds in the standard world; peak per lineage; at most {PER_ARM} per experiment arm',
         f'reference: Step 23 control best brains (gen 300) on the same worlds: mean {np.nanmean(base):.3f}, best {np.nanmax(base):.3f}',
         'rank  score   experiment      arm                  seed  generation (-1 = final best)']
    L += [f'{r["rank"]:4d}  {r["score"]:.3f}  {r["experiment"]:15s} {r["arm"]:20s} {r["seed"]:>4s}  {r["generation"]}' for r in hall[:40]]
    txt = '\n'.join(L); print(txt)
    (RES / 'step30_hall.txt').write_text(txt + '\n')
    print('SUPER_HARVEST_DONE', flush=True)


def founders(kind, seed):
    """Starting population (12 genomes) for one seed of a nurture arm."""
    from . import worm2 as w
    from .config import Config
    from .connectome import Connectome
    hall = sorted(glob.glob(str(OUT / 'hall' / 'hof_*.npy')))
    champs = [np.load(f).astype(np.float32) for f in hall[:POOL]]
    if kind == 'pool':
        while len(champs) < POOL:
            champs.append(champs[len(champs) % max(1, len(hall))])
        return np.stack(champs)
    if kind == 'best':
        conn, opts, cfg = Connectome(), CONDITIONS[STD], Config(**CFG_OVERRIDES[STD])
        rng = np.random.default_rng(30_000 + seed)
        return np.stack([champs[0]] + [w.mutate(champs[0], conn, cfg, rng, opts)[0] for _ in range(POOL - 1)]).astype(np.float32)
    return None


def nurture(device='cuda'):
    from .batch3_fast import evolve
    for arm, (kind, ew) in ARMS.items():
        if all((OUT / f'{arm}_s{s}' / 'best_genome.npy').exists() for s in SEEDS):
            print(f'{arm}: already done, skipped', flush=True); continue
        init = None if kind == 'random' else {s: founders(kind, s) for s in SEEDS}
        print(f'{arm}: start from {kind}, {ew} world(s) per brain per generation, {len(SEEDS)} seeds x {GENS} gens', flush=True)
        evolve(arm, SEEDS, GENS, out=OUT, device=device, checkpoint_every=EVERY, clonal=60, brains=POOL,
               eval_worlds=ew, init=init)
    print('SUPER_NURTURE_DONE', flush=True)


def analyze():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .connectome import Connectome
    from .step20 import signflip
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    gens = list(range(EVERY, GENS + 1, EVERY))
    curve = {}
    for a in ARMS:
        G = [np.load(OUT / f'{a}_s{s}' / f'ckpt_g{g}.npy') for s in SEEDS for g in gens]
        curve[a] = score(G, HALL_W, dev, conn).reshape(len(SEEDS), len(gens))
    final = {a: c[:, -1] for a, c in curve.items()}
    peak = {a: c.max(1) for a, c in curve.items()}
    decline = {a: peak[a] - final[a] for a in ARMS}
    hall = list(csv.DictReader(open(OUT / 'hall' / 'hall_of_fame.csv')))
    champ = float(hall[0]['score'])
    d = {'S1 champions help (pool - random, final)': final['n30_pool'] - final['n30_random'],
         'S2 reliable selection helps (pool_x4 - pool, final)': final['n30_pool_x4'] - final['n30_pool'],
         'S3 reliable selection maintains (pool decline - pool_x4 decline)': decline['n30_pool'] - decline['n30_pool_x4']}
    p = {k: signflip(v) for k, v in d.items()}
    ks = sorted(p, key=p.get); h, run_ = {}, 0.0
    for i, k in enumerate(ks):
        run_ = max(run_, min(1.0, (len(ks) - i) * p[k])); h[k] = run_
    L = [f'Step 30 SUPER WORM nurture: {len(SEEDS)} seeds x {GENS} gens, checkpoints re-tested on {len(HALL_W)} worlds (standard world)',
         f'hall-of-fame best champion: {champ:.3f} ({hall[0]["experiment"]} {hall[0]["arm"]} seed {hall[0]["seed"]} gen {hall[0]["generation"]})',
         'arm           start   final   peak   decline  best brain   (score at gens ' + ','.join(map(str, gens)) + ')']
    for a in ARMS:
        c = curve[a]
        L.append(f'{a:13s} {c[:, 0].mean():6.3f} {final[a].mean():6.3f} {peak[a].mean():6.3f}  {decline[a].mean():6.3f}   {c.max():6.3f}   '
                 + ' '.join(f'{x:.2f}' for x in c.mean(0)))
    L.append('PRE-REGISTERED (paired sign-flip by seed, Holm over 3):')
    for k, v in d.items():
        verdict = ('PASS' if v.mean() > 0 else 'PASS (opposite direction)') if h[k] < 0.05 else 'no detectable effect'
        L.append(f'  {k}: {v.mean():+.3f} ({(v > 0).sum()}/{len(v)})  p={p[k]:.3g}  Holm p={h[k]:.3g} -> {verdict}')
    dv = final['n30_best'] - final['n30_pool']
    L.append(f'REPORTED: single best champion vs pool (final): {dv.mean():+.3f} ({(dv > 0).sum()}/{len(dv)}) p={signflip(dv):.3g} (uncorrected)')
    best_a = max(ARMS, key=lambda a: curve[a].max()); bi = np.unravel_index(curve[best_a].argmax(), curve[best_a].shape)
    sup = float(curve[best_a].max())
    if sup > champ:
        src = OUT / f'{best_a}_s{SEEDS[bi[0]]}' / f'ckpt_g{gens[bi[1]]}.npy'; who = f'{best_a} seed {SEEDS[bi[0]]} gen {gens[bi[1]]}'
    else:
        src = Path(hall[0]['path']); who = f'hall champion ({hall[0]["experiment"]} {hall[0]["arm"]})'; sup = champ
    np.save(OUT / f'SUPER_WORM{TAG}.npy', np.load(src))
    (OUT / f'SUPER_WORM{TAG}.json').write_text(json.dumps(dict(score=sup, source=who, path=str(src), worlds=HALL_W), indent=1))
    L.append(f'SUPER WORM: {who}, score {sup:.3f} ' + ('(BEATS the best champion)' if sup > champ else '(nurture did not beat the best champion)'))
    txt = '\n'.join(L); print(txt)
    RES.mkdir(parents=True, exist_ok=True)
    (RES / f'step30{TAG}_stats.txt').write_text(txt + '\n')
    (RES / f'step30{TAG}_stats.json').write_text(json.dumps(dict(curve={a: c.tolist() for a, c in curve.items()}, gens=gens,
                                                           p=p, holm=h, champion=champ, super=sup, super_source=who)))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for a in ARMS:
        ax.plot(gens, curve[a].mean(0), marker='o', label=a[4:])
    ax.axhline(champ, color='k', ls='--', lw=0.8, label='best champion')
    ax.set(xlabel='generation', ylabel='skill (standard world, 24 unseen worlds)', title='Super worm: nurturing the hall of fame')
    ax.legend(); fig.tight_layout(); fig.savefig(RES / f'step30{TAG}.png', dpi=110)


def confirm():
    """Fresh-world confirmation of the super worm, the champions, and each seed's best checkpoint per arm."""
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    gens = list(range(EVERY, GENS + 1, EVERY))
    st = json.loads((RES / 'step30_stats.json').read_text())
    hall = list(csv.DictReader(open(OUT / 'hall' / 'hall_of_fame.csv')))[:POOL]
    rows = []                                                   # (group, label, hall-world score, path)
    sw = json.loads((OUT / 'SUPER_WORM.json').read_text())
    rows.append(('super worm', sw['source'], sw['score'], OUT / 'SUPER_WORM.npy'))
    for h in hall:
        rows.append(('champion', f"#{h['rank']} {h['experiment']} {h['arm']} s{h['seed']} g{h['generation']}",
                     float(h['score']), OUT / 'hall' / f"hof_{int(h['rank']):03d}.npy"))
    for a in ARMS:
        c = np.array(st['curve'][a])
        for i, s in enumerate(SEEDS):
            j = int(c[i].argmax())
            rows.append((a, f'{a} s{s} g{gens[j]}', float(c[i, j]), OUT / f'{a}_s{s}' / f'ckpt_g{gens[j]}.npy'))
    fresh = score([np.load(r[3]) for r in rows], FRESH_W, dev, conn)
    L = [f'Step 30 FRESH-WORLD CONFIRMATION: {len(rows)} brains re-tested on {len(FRESH_W)} never-used worlds (standard world)',
         'group           n   on hall worlds  on fresh worlds  shrink']
    groups = ['super worm', 'champion'] + list(ARMS)
    for g in groups:
        idx = [k for k, r in enumerate(rows) if r[0] == g]
        hw = np.mean([rows[k][2] for k in idx]); fw = fresh[idx].mean()
        L.append(f'{g:14s} {len(idx):3d}     {hw:6.3f}          {fw:6.3f}       {hw - fw:+.3f}')
    best = int(np.argmax(fresh))
    champ_best = max(fresh[k] for k, r in enumerate(rows) if r[0] == 'champion')
    L += [f'super worm on fresh worlds: {fresh[0]:.3f} vs best champion on fresh worlds {champ_best:.3f} -> '
          + ('STILL BEATS every champion' if fresh[0] > champ_best else 'does NOT beat every champion on fresh worlds'),
          f'best brain on fresh worlds: {rows[best][1]} ({rows[best][0]}), {fresh[best]:.3f}',
          'top 10 on fresh worlds:']
    for k in np.argsort(-fresh)[:10]:
        L.append(f'  {fresh[k]:.3f}  (hall worlds {rows[k][2]:.3f})  {rows[k][0]:12s} {rows[k][1]}')
    txt = '\n'.join(L); print(txt)
    (RES / 'step30_confirm.txt').write_text(txt + '\n')
    (RES / 'step30_confirm.json').write_text(json.dumps([dict(group=r[0], label=r[1], hall=r[2], fresh=float(f))
                                                         for r, f in zip(rows, fresh)], indent=1))
    np.save(OUT / 'SUPER_WORM_fresh_best.npy', np.load(rows[best][3]))
    print('SUPER_CONFIRM_DONE', flush=True)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x not in ('--test', '--rep')]
    import torch
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    if a[:1] == ['harvest']:
        harvest()
    elif a[:1] == ['nurture']:
        nurture(dev); analyze()
    elif a[:1] == ['analyze']:
        analyze()
    elif a[:1] == ['confirm']:
        confirm()
    elif a[:1] in (['full'], ['check']):
        harvest(); nurture(dev); analyze()
        print('SUPER_CHECK_OK' if a[0] == 'check' else 'SUPER_FULL_DONE', flush=True)
    else:
        print(__doc__)
