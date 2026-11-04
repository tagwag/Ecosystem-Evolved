"""Steps 16-17: can new worlds push past the plateau (~3.2-3.5 true skill in the Step 14 world)?

Worlds (all: scarce food, 6 predators, touch on, fitness = energy left at end + survival, clonal-group scoring,
hunger-receptor genes locked so only the brain wiring evolves):
    w_base      the Step 14 world (control: just keep evolving where they plateaued)
    w_seasons   food patches jump to new random spots every 300 ticks (5 times per generation) -> tracking pays
    w_fastpred  predators faster (3.5 vs prey max 5) and see farther (200) -> escaping pays more
    w_digest    food digests fastest when still + predators notice moving prey (Step 8c rules) -> timing rest pays

Step 16 (PEAKS): every last-checkpoint brain of Step 14 (6 arms x 32 seeds = 192) is re-tested on 18 worlds
    (2000-2017) and the 16 best are the peaks. Each peak is evolved twice (32 runs) in each world, 150 generations.
Step 17 (RECOVERY): the 32 Step 15 tournament champions (generation 300, which ended below their best founder)
    are evolved in each world, 100 generations.
Both: every checkpoint is tested in its own world AND in w_base, on 12 fresh worlds (4000-4011, not the ranking
worlds, so the start is not inflated by picking lucky brains). Breaking the plateau = w_base skill goes up past
the start (and, for new worlds, past the w_base control).

    python -m ecosim.step16 quick        python -m ecosim.step16 peaks
    python -m ecosim.step16 run 16|17    python -m ecosim.step16 analyze 16|17   -> results/step16_*, step17_*
"""
import dataclasses
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

SEEDS = list(range(1, 33))
GROUP = 10
OUT, RES = Path('runs/step16'), Path('results')
RANK_WORLDS = list(range(2000, 2018))
TEST_WORLDS = list(range(4000, 4012))
WORLDS = {'w_base': {}, 'w_seasons': dict(season_every=300), 'w_fastpred': dict(pred_speed=3.5, pred_sense=200.0),
          'w_digest': dict(digestion=True, pred_sense_still=20.0)}
for _w, _o in WORLDS.items():
    CONDITIONS[_w] = dataclasses.replace(CONDITIONS['hunger'], fitness='end', rec_mutate=False)
    CFG_OVERRIDES[_w] = dict(s14.PRED, **_o)
SRC_ARMS = ['b14_keep', 'b14_frozen', 'b14_knock', 'h14_plain', 'h14_herd', 'h14_herd_noscent']   # same genome layout
SETUP = {16: dict(gens=150, every=10, test_every=30), 17: dict(gens=100, every=25, test_every=25)}


def candidates(src=s14.OUT, seeds=SEEDS, gens=None):
    out = []
    for c in SRC_ARMS:
        part = 'a' if c in s14.A_ARMS else 'b'
        g = gens or s14.GENS[part]
        for s in seeds:
            out.append((f'{c}_s{s}', np.load(src / part / f'{c}_s{s}' / f'ckpt_g{g}.npy')))
    return out


def peaks(n=16, src=s14.OUT, seeds=SEEDS, tag='', gens=None):
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    cand = candidates(src, seeds, gens)
    sk = s14.test('w_base', [g for _, g in cand], conn, dev, RANK_WORLDS)['fitness']
    order = np.argsort(sk)[::-1]
    top = [(cand[i][0], float(sk[i])) for i in order[:n]]
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / f'peaks{tag}.npy', np.stack([cand[i][1] for i in order[:n]]))
    info = dict(peaks=top, n_candidates=len(cand), candidate_mean=float(sk.mean()),
                by_arm={c: float(np.mean([sk[i] for i, (nm, _) in enumerate(cand) if nm.rsplit('_s', 1)[0] == c]))
                        for c in SRC_ARMS})
    (OUT / f'peaks{tag}.json').write_text(json.dumps(info, indent=1))
    print('peaks (18 ranking worlds):', json.dumps(info, indent=1), flush=True)


def starts(step, seeds=SEEDS, tag='', src15=Path('runs/step15'), g15=300):
    if step == 16:
        P = np.load(OUT / f'peaks{tag}.npy')
        return {s: P[(s - 1) % len(P)] for s in seeds}                # each peak evolved twice
    return {s: np.load(src15 / f't{s - 1}_ckpt_g{g15}.npy') for s in seeds}


def run(step, seeds=SEEDS, gens=None, out=OUT, tag='', src15=Path('runs/step15'), g15=300):
    from .batch3_fast import evolve
    st = SETUP[step]
    init = starts(step, seeds, tag, src15, g15)
    for w in WORLDS:
        evolve(w, seeds, gens or st['gens'], out=out / str(step), checkpoint_every=st['every'], clonal=GROUP, init=init)


def analyze(step, seeds=SEEDS, gens=None, out=OUT, tag='', src15=Path('runs/step15'), g15=300):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    st0 = SETUP[step]
    gens = gens or st0['gens']
    te = min(st0['test_every'], gens)
    cks = [0] + list(range(te, gens + 1, te))
    init = starts(step, seeds, tag, src15, g15)
    T = lambda cond, G: s14.test(cond, G, conn, dev, TEST_WORLDS)['fitness']
    C = {}
    for w in WORLDS:
        own, base = [], []
        for g in cks:
            G = [init[s] for s in seeds] if g == 0 else [np.load(out / str(step) / f'{w}_s{s}' / f'ckpt_g{g}.npy') for s in seeds]
            own.append(T(w, G)); base.append(T('w_base', G) if w != 'w_base' else own[-1])
        C[w] = dict(own=np.array(own), base=np.array(base))
        print(w, 'own-world skill:', np.round(C[w]['own'].mean(1), 3).tolist(),
              '| base-world skill:', np.round(C[w]['base'].mean(1), 3).tolist(), flush=True)
    start_base = C['w_base']['base'][0]
    res = dict(checkpoints=cks, start_base_skill=float(start_base.mean()))
    for w in WORLDS:
        r = dict(own_skill=C[w]['own'].mean(1).round(4).tolist(), base_skill=C[w]['base'].mean(1).round(4).tolist(),
                 own_gain=paired(C[w]['own'][-1], C[w]['own'][0]),
                 base_end_vs_start=paired(C[w]['base'][-1], start_base),
                 base_peak_checkpoint=int(cks[int(np.argmax(C[w]['base'].mean(1)))]),
                 best_single_brain_base=float(C[w]['base'][-1].max()))
        if w != 'w_base':
            r['base_end_vs_control'] = paired(C[w]['base'][-1], C['w_base']['base'][-1])
        res[w] = r
    if step == 17:      # the bar the champions fell below: the best Step 15 founder, re-tested on the same worlds
        su = json.loads((src15 / 'setup.json').read_text())
        part = 'a' if su['cond'] in s14.A_ARMS else 'b'
        F = [np.load(s14.OUT / part / f"{su['cond']}_s{s}" / 'best_genome.npy') for s in su['founder_seeds']]
        fs = T('w_base', F)
        res['founders_base_skill'] = dict(zip(map(str, su['founder_seeds']), fs.round(4).tolist()))
        best = float(fs.max()); res['best_founder_base'] = best
        for w in WORLDS:
            res[w]['base_end_vs_best_founder'] = paired(C[w]['base'][-1], np.full(len(seeds), best))
            res[w]['runs_above_best_founder'] = int((C[w]['base'][-1] > best).sum())
    else:
        pk = json.loads((OUT / f'peaks{tag}.json').read_text())
        res['peaks'] = pk['peaks']
    res['note'] = 'paired(): "hunger" = first argument, "nohunger" = second. checkpoint 0 = start brains. ' \
                  'own = skill in the world it evolved in; base = skill in w_base (the plateau world)'
    name = f'step{step}{tag}'
    (RES / f'{name}_stats.json').write_text(json.dumps(res, indent=1))
    (RES / f'{name}_curves.json').write_text(json.dumps({w: {k: v.tolist() for k, v in C[w].items()} for w in C}))
    print(name, json.dumps({w: {k: v for k, v in res[w].items() if 'skill' not in k} for w in WORLDS}, indent=1), flush=True)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for w in WORLDS:
        for ax, k in zip(axes, ('own', 'base')):
            m, se = C[w][k].mean(1), C[w][k].std(1) / np.sqrt(len(seeds))
            ax.errorbar(cks, m, yerr=1.96 * se, marker='o', capsize=3, lw=2, label=w)
    if step == 17:
        axes[1].axhline(res['best_founder_base'], color='k', ls='--', lw=1, label='best founder')
    axes[0].set_ylabel('skill in the world it evolves in'); axes[1].set_ylabel('skill in the plateau world (w_base)')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle({16: 'Step 16: plateau peaks moved to new worlds', 17: 'Step 17: tournament champions moved to new worlds'}[step]
                 + f' — {len(seeds)} runs, 12 test worlds, 95% CI')
    fig.tight_layout(); fig.savefig(RES / f'{name}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'quick':
        q, s15q = Path('runs/step16_quick'), Path('runs/step15_quick')
        peaks(4, Path('runs/step14_quick'), [1, 2], tag='_quick', gens=10)
        for step, g in ((16, 10), (17, 25)):     # quick tournament saved t0/t1 at generation 50
            run(step, [1, 2], g, q, '_quick', s15q, 50)
            analyze(step, [1, 2], g, q, '_quick', s15q, 50)
    elif a == 'peaks':
        peaks()
    else:
        {'run': run, 'analyze': analyze}[a](int(sys.argv[2]))
