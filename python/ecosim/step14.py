"""Step 14: two new experiments, both with clonal-group scoring (10 clones per brain, 1/6-size worlds).

14a  PEPTIDE BAGGAGE. Does the hunger peptide, once evolved, slow later evolution (a "frozen accident")?
     Start from the Step 12a best brains (100 gens in the scarce-food world, peptide vs no peptide), then put them
     in a NEW world (same scarce food + 6 predators, touch on) and evolve 100 more generations:
        b14_keep     peptide brains, receptors keep evolving
        b14_frozen   peptide brains, receptor genes locked (peptide present, can't change)
        b14_knock    peptide brains with the peptide removed (receptors zeroed and locked)
        b14_nopep    no-peptide brains (never had it)
     Baggage = keep adapts slower than knock (same wiring, peptide on vs off) / nopep.
     Also: knock the peptide out of the Step 12a brains in their OWN world (no evolution) = how much they rely on it.

14b  SELFISH HERD. Predators that pick on loners (Hamilton 1971) and miss in crowds (confusion effect):
        h14_plain        6 predators as in Step 13a, worm scent on (ASK/ADL)
        h14_herd         predators chase the loneliest prey in range; bites on prey with n neighbours (within 40)
                         land with chance 1/(1+n)
        h14_herd_noscent same herd predators, no worm scent (can they still clump?)
     150 generations. Herding = nearest-worm distance drops vs plain.

All 32 seeds, best brain saved every 10 generations, true skill tested on 6 fixed full-size worlds (60 clones).

    python -m ecosim.step14 quick         (GPU smoke test)
    python -m ecosim.step14 run a|b       python -m ecosim.step14 analyze a|b   -> results/step14{a,b}_*
"""
import dataclasses
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from .step3 import CONDITIONS, CFG_OVERRIDES, SCARCE
from . import step12  # noqa: F401  registers c3d_pep / c3d_nopep

SEEDS = list(range(1, 33))
GROUP, EVERY = 10, 10
GENS = {'a': 100, 'b': 150}
OUT, RES = Path('runs/step14'), Path('results')
SRC12 = Path('runs/step12')
TEST_WORLDS = list(range(2000, 2006))
PRED = dict(SCARCE, predators=6, touch_gain=3.0)

A_ARMS = {'b14_keep': ('hunger', True, False), 'b14_frozen': ('hunger', False, False),
          'b14_knock': ('hunger', False, True), 'b14_nopep': ('nohunger', True, False)}   # base, rec_mutate, knockout
for _c, (_b, _m, _k) in A_ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS[_b], fitness='end', rec_mutate=_m)
    CFG_OVERRIDES[_c] = dict(PRED)
HERD = dict(pred_loner=1.0, pred_confuse=1.0)
B_ARMS = {'h14_plain': dict(PRED, pheromone=True), 'h14_herd': dict(PRED, pheromone=True, **HERD),
          'h14_herd_noscent': dict(PRED, pheromone=False, **HERD)}
for _c, _o in B_ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS['hunger'], fitness='end')
    CFG_OVERRIDES[_c] = _o


def knockout(g, conn):
    from .worm2 import Layout
    g = g.copy(); g[Layout(conn, CONDITIONS['c3d_pep']).rec] = 0.0
    return g


def start_brains(cond, seeds, conn, src=SRC12):
    base, _, ko = A_ARMS[cond]
    s12 = 'c3d_pep' if base == 'hunger' else 'c3d_nopep'
    G = {s: np.load(src / f'{s12}_s{s}' / 'best_genome.npy') for s in seeds}
    return {s: knockout(g, conn) for s, g in G.items()} if ko else G


def test(cond, genomes, conn, dev, worlds=TEST_WORLDS):
    """Each genome as 60 clones on the fixed test worlds. Returns arrays (n_genomes,): fitness, food, bites, nn,
    wall (fraction of time near an obstacle; nan without obstacles)."""
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[cond], Config(**CFG_OVERRIDES[cond])
    P, out = cfg.worm_population, {k: [] for k in ('fitness', 'food', 'bites', 'nn', 'wall')}
    for i in range(0, len(genomes), 32):                     # chunks keep GPU memory small
        gs = genomes[i:i + 32]
        pairs = [(j, wd) for j in range(len(gs)) for wd in worlds]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        fit, st = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen).run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(worlds)
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        for k, key in (('food', 'mean_food'), ('bites', 'bites'), ('nn', 'nn_dist'), ('wall', 'near_wall')):
            out[k] += np.array([x.get(key, np.nan) for x in st]).reshape(len(gs), nw).mean(1).tolist()
    return {k: np.array(v) for k, v in out.items()}


def run(part, seeds=SEEDS, gens=None, out=OUT, src=SRC12):
    from .batch3_fast import evolve
    from .connectome import Connectome
    conn = Connectome()
    gens = gens or GENS[part]
    if part == 'a':
        for c in A_ARMS:
            evolve(c, seeds, gens, out=out / 'a', checkpoint_every=EVERY, clonal=GROUP,
                   init=start_brains(c, seeds, conn, src))
    else:
        for c in B_ARMS:
            evolve(c, seeds, gens, out=out / 'b', checkpoint_every=EVERY, clonal=GROUP)


def curves(cond, seeds, gens, conn, dev, out, start=None):
    """True skill etc. at every checkpoint (and at the start brains, if given). {key: (n_ckpt, n_seeds)}."""
    cks = list(range(EVERY, gens + 1, EVERY))
    rows = []
    if start is not None:
        rows.append(test(cond, [start[s] for s in seeds], conn, dev))
    for g in cks:
        rows.append(test(cond, [np.load(out / f'{cond}_s{s}' / f'ckpt_g{g}.npy') for s in seeds], conn, dev))
    return ([0] if start is not None else []) + cks, {k: np.array([r[k] for r in rows]) for k in rows[0]}


def analyze(part, seeds=SEEDS, gens=None, out=OUT, src=SRC12, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    gens = gens or GENS[part]
    arms = A_ARMS if part == 'a' else B_ARMS
    C = {}
    for c in arms:
        start = start_brains(c, seeds, conn, src) if part == 'a' else None
        C[c] = curves(c, seeds, gens, conn, dev, out / part, start)
        print(c, 'true skill by checkpoint:', np.round(C[c][1]['fitness'].mean(1), 3).tolist(), flush=True)
    last = lambda c, k='fitness': C[c][1][k][-1]
    first = lambda c: C[c][1]['fitness'][0]
    st = {c: dict(checkpoints=C[c][0], skill=C[c][1]['fitness'].mean(1).round(4).tolist(),
                  nn=C[c][1]['nn'].mean(1).round(2).tolist(), bites=C[c][1]['bites'].mean(1).round(4).tolist(),
                  gain=paired(last(c), first(c))) for c in arms}
    if part == 'a':
        st['keep_vs_knock_last'] = paired(last('b14_keep'), last('b14_knock'))
        st['keep_vs_knock_gain'] = paired(last('b14_keep') - first('b14_keep'), last('b14_knock') - first('b14_knock'))
        st['keep_vs_frozen_last'] = paired(last('b14_keep'), last('b14_frozen'))
        st['keep_vs_nopep_gain'] = paired(last('b14_keep') - first('b14_keep'), last('b14_nopep') - first('b14_nopep'))
        st['keep_vs_nopep_last'] = paired(last('b14_keep'), last('b14_nopep'))
        # reliance: Step 12a peptide brains in their own world, intact vs peptide knocked out (no evolution)
        G = [np.load(src / f'c3d_pep_s{s}' / 'best_genome.npy') for s in seeds]
        a, b = test('c3d_pep', G, conn, dev)['fitness'], test('c3d_pep', [knockout(g, conn) for g in G], conn, dev)['fitness']
        st['step12a_intact_vs_knockout'] = paired(a, b)
    else:
        for x, y in (('h14_herd', 'h14_plain'), ('h14_herd_noscent', 'h14_herd'), ('h14_herd_noscent', 'h14_plain')):
            st[f'{x}_vs_{y}'] = {k: paired(last(x, k), last(y, k)) for k in ('fitness', 'nn', 'bites', 'food')}
        st['h14_herd_nn_last_vs_first'] = paired(C['h14_herd'][1]['nn'][-1], C['h14_herd'][1]['nn'][0])
    # evolution gain per arm, used by Step 15 to pick its arm
    st['evolution_gain'] = {c: float((last(c) - first(c)).mean()) for c in arms}
    st['note'] = 'paired(): "hunger" = first argument, "nohunger" = second (field names reused). checkpoint 0 = start brains'
    (RES / f'step14{part}{tag}_stats.json').write_text(json.dumps(st, indent=1))
    (RES / f'step14{part}{tag}_curves.json').write_text(json.dumps(
        {c: dict(checkpoints=C[c][0], **{k: v.tolist() for k, v in C[c][1].items()}) for c in arms}))
    print(f'step14{part}', json.dumps({k: v for k, v in st.items() if k not in arms}, indent=1), flush=True)
    keys = ('fitness', 'nn') if part == 'b' else ('fitness', 'bites')
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for c in arms:
        for ax, k in zip(axes, keys):
            m, se = C[c][1][k].mean(1), C[c][1][k].std(1) / np.sqrt(len(seeds))
            ax.errorbar(C[c][0], m, yerr=1.96 * se, marker='o', capsize=3, lw=2, label=c)
    axes[0].set_ylabel('true skill (60 clones, 6 fixed worlds)')
    axes[1].set_ylabel('nearest-worm distance (lower = clumped)' if part == 'b' else 'predator bites per worm')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle({'a': 'Step 14a: peptide baggage (new world: scarce food + predators)',
                  'b': 'Step 14b: selfish-herd predators'}[part] + f' — {len(seeds)} seeds, 95% CI')
    fig.tight_layout(); fig.savefig(RES / f'step14{part}{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if sys.argv[1] == 'quick':
        q = Path('runs/step14_quick')
        for p in 'ab':
            run(p, [1, 2], 10, q); analyze(p, [1, 2], 10, q, tag='_quick')
    else:
        {'run': run, 'analyze': analyze}[sys.argv[1]](sys.argv[2])
