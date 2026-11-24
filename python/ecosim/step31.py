"""Step 31 = SUPER WORM WITH THE PEAK-STOP RULE (2026-11-23). First breeding run under the owner's new rule
(ecosim/peakstop.py): when a seed's skill passes its peak, that stretch ends early and the surviving worms are
interbred; evolution continues from them, at most 3 times; then the seed ends. The run ends when all seeds ended.

SET-UP (everything else as the Step 30 recipe that reproduced: champions as founders, 4 worlds per brain)
  arm p31_pool_x4_peak: 16 seeds (41-56, new), 12 brains, 60 clones, standard world (s23_ctrl), founders = the 12
  hall-of-fame champions, 4 worlds per brain per generation, checkpoints every 25 generations re-tested on the 24
  hall worlds (these drive the rule), at most 600 generations.

MEASURES (reported; no pre-registered test, since there is no fixed-length arm in this run)
  - per seed: run peak (checkpoint worlds), generation it ended, number of interbreedings;
  - does interbreeding help? for each interbreeding, the best score of the next segment minus the peak of the one
    before it (positive = the brood climbed past the old peak);
  - FRESH WORLDS 5900-5947 (never used anywhere): each seed's peak brain, the two Step 30 super worms and the 12
    champions, all in ONE scoring call (same batching, so the comparison is fair; noise per brain about +/-0.07).

    python -m ecosim.step31 run        (watcher: breed_peak)
    python -m ecosim.step31 analyze    (run calls it at the end)
    python -m ecosim.step31 check      (watcher: breed_peak_check; tiny, forces interbreeding, ~2 min)
Results: runs/step31/, results/step31_stats.txt + .json.
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

from . import step30 as s30
from .step3 import CONDITIONS, CFG_OVERRIDES
from .peakstop import PeakStop

ARM = 'p31_pool_x4_peak'
OUT, RES = Path('runs/step31'), Path('results')
SEEDS, GENS, EVERY, EW = list(range(41, 57)), 600, 25, 4
FRESH = list(range(5900, 5948))
DROP, CONFIRM, RESTARTS = 0.10, 2, 3
TEST = '--test' in sys.argv or sys.argv[1:2] == ['check']
if TEST:
    OUT, RES = Path('runs/step31_test'), Path('results/_test_artifacts')
    SEEDS, GENS, EVERY, EW, FRESH, DROP = [41, 42], 8, 1, 1, [5900, 5901], -1.0   # DROP<0 forces interbreeding
CONDITIONS[ARM] = CONDITIONS[s30.STD]
CFG_OVERRIDES[ARM] = dict(CFG_OVERRIDES[s30.STD])
CK_W = s30.HALL_W if not TEST else s30.HALL_W[:2]


def run():
    import torch
    from .batch3_fast import evolve
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()

    def ck_score(G):                        # small chunks: this runs beside the evolving simulation on the GPU
        r = s30.score(G, CK_W, dev, conn, chunk=4); torch.cuda.empty_cache(); return r
    ps = PeakStop(ck_score, every=EVERY, drop=DROP, confirm=CONFIRM, restarts=RESTARTS)
    init = {s: s30.founders('pool', s) for s in SEEDS}
    print(f'{ARM}: {len(SEEDS)} seeds, max {GENS} gens, peak-stop drop {DROP} x{CONFIRM} checkpoints, {RESTARTS} restarts', flush=True)
    evolve(ARM, SEEDS, GENS, out=OUT, device='cuda', checkpoint_every=EVERY, clonal=60, brains=s30.POOL,
           eval_worlds=EW, init=init, peakstop=ps)
    print('BREED_PEAK_RUN_DONE', flush=True)


def analyze():
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    RES.mkdir(parents=True, exist_ok=True)
    seeds = [json.loads((OUT / f'{ARM}_s{s}' / 'peakstop.json').read_text()) for s in SEEDS]
    L = [f'Step 31 peak-stop breeding run: {len(SEEDS)} seeds, max {GENS} gens, rule: {DROP} below segment peak at '
         f'{CONFIRM} checkpoints in a row -> interbreed (max {RESTARTS}), then end',
         'seed  run peak (gen)   restarts  ended at   segment peaks']
    gains = []
    for s, d in zip(SEEDS, seeds):
        segs, cur = [], -np.inf
        for e in d['log']:
            if 'score' in e:
                cur = max(cur, e['score'])
            else:
                segs.append(cur); cur = -np.inf
        if np.isfinite(cur):
            segs.append(cur)
        gains += [b - a for a, b in zip(segs, segs[1:])]
        L.append(f'{s:4d}  {d["run_peak"]:.3f} ({d["run_peak_gen"]})     {d["restarts"]}        '
                 f'{d["ended_gen"] or "max gens"}    ' + ' -> '.join(f'{x:.3f}' for x in segs))
    if gains:
        g = np.array(gains)
        L.append(f'interbreeding: next segment peak minus previous segment peak: mean {g.mean():+.3f}, '
                 f'{(g > 0).sum()}/{len(g)} climbed past the old peak (checkpoint worlds; noise ~ +/-0.1)')
    rows = [(f'seed {s} peak', OUT / f'{ARM}_s{s}' / 'peak_genome.npy') for s in SEEDS]
    for tag in ('', '_rep'):
        p = s30.OUT / f'SUPER_WORM{tag}.npy'
        if p.exists():
            rows.append((f'Step 30 super worm{tag}', p))
    hall = sorted((s30.OUT / 'hall').glob('hof_*.npy'))[:s30.POOL]
    rows += [(f'champion {h.stem}', h) for h in hall]
    fr = s30.score([np.load(p) for _, p in rows], FRESH, dev, conn)
    ns = len(SEEDS)
    L += [f'FRESH WORLDS {FRESH[0]}-{FRESH[-1]} (never used), one scoring call:',
          f'  peak-stop seeds: mean {fr[:ns].mean():.3f}, best {fr[:ns].max():.3f} ({rows[int(fr[:ns].argmax())][0]})']
    L += [f'  {n}: {x:.3f}' for (n, _), x in zip(rows[ns:], fr[ns:]) if 'super' in n]
    ch = [x for (n, _), x in zip(rows, fr) if n.startswith('champion')]
    if ch:
        L.append(f'  champions: mean {np.mean(ch):.3f}, best {max(ch):.3f}')
    txt = '\n'.join(L); print(txt)
    (RES / 'step31_stats.txt').write_text(txt + '\n')
    (RES / 'step31_stats.json').write_text(json.dumps(dict(seeds=dict(zip(map(str, SEEDS), seeds)),
                                                           fresh={n: float(x) for (n, _), x in zip(rows, fr)}), indent=1))
    print('BREED_PEAK_ANALYZE_DONE', flush=True)


CONFIRM_W = list(range(6000, 6096))                 # 96 worlds never used anywhere (pre-registered 2026-11-24 02:50 UTC)


def confirm():
    """Second fresh-world test: the 3 best peak-stop seeds on worlds 5900-5947 (picked there, so their 5900 score is
    optimistic) vs both Step 30 super worms, on 96 NEW worlds, in one scoring call. Rule written before the run: a
    peak-stop brain counts as a new super worm only if it beats BOTH super worms here by more than 0.1."""
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    fr = json.loads((RES / 'step31_stats.json').read_text())['fresh']
    top = sorted([n for n in fr if n.endswith(' peak')], key=lambda n: -fr[n])[:3]
    rows = [(n, OUT / f'{ARM}_s{n.split()[1]}' / 'peak_genome.npy') for n in top]
    rows += [(f'Step 30 super worm{t}', s30.OUT / f'SUPER_WORM{t}.npy') for t in ('', '_rep')]
    sc = s30.score([np.load(p) for _, p in rows], CONFIRM_W, dev, conn)
    sup = max(sc[-2:])
    L = [f'Step 31 CONFIRMATION on {len(CONFIRM_W)} new worlds {CONFIRM_W[0]}-{CONFIRM_W[-1]} (one scoring call):']
    L += [f'  {n:24s} {x:.3f}   (worlds 5900-5947: {fr.get(n, float("nan")):.3f})' for (n, _), x in zip(rows, sc)]
    L.append('  verdict: ' + ('NEW SUPER WORM: ' + rows[int(sc[:-2].argmax())][0] if sc[:-2].max() > sup + 0.1
                             else 'no peak-stop brain beats both super worms by > 0.1 (tied within noise or worse)'))
    txt = '\n'.join(L); print(txt); (RES / 'step31_confirm.txt').write_text(txt + '\n')
    print('BREED_PEAK_CONFIRM_DONE', flush=True)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    if a[:1] in (['run'], ['check']):
        run(); analyze()
        if a[0] == 'check':
            d = json.loads((OUT / f'{ARM}_s{SEEDS[0]}' / 'peakstop.json').read_text())
            assert d['restarts'] >= 1, 'interbreeding never triggered'
            print('BREED_PEAK_CHECK_OK', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    elif a[:1] == ['confirm']:
        confirm()
    else:
        print(__doc__)
