"""Step 6: exploration -> puzzle curriculum x memory pool (2 x 2), 4 seeds, 60 generations.

    python -m ecosim.step6 all        16 runs (~75 min on 2 cores)
    python -m ecosim.step6 analyze    fair test on 6 unseen puzzle worlds -> results/step6_*

Rule fixed before results:
    curriculum helps  if curriculum conditions beat puzzle-only ones on puzzle food (all seeds, or p < 0.05)
    memory helps      if memory conditions beat no-memory ones, especially on revisit + sequence puzzles
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .config import Config
from .connectome import Connectome
from . import worm6 as w

CONDITIONS = {
    'puzzle_nomem': w.Opts6(memory=False, curriculum=False),
    'puzzle_mem': w.Opts6(memory=True, curriculum=False),
    'curric_nomem': w.Opts6(memory=False, curriculum=True),
    'curric_mem': w.Opts6(memory=True, curriculum=True),
}
SEEDS = [1, 2, 3, 4]
GENERATIONS = 60
OUT, RES = Path('runs/step6'), Path('results')
TAG = 'step6'
WORLDS = range(6000, 6006)


def evolve(cond, seed, generations=None):
    generations = generations or GENERATIONS
    if (OUT / f'{cond}_s{seed}' / 'best_genome.npy').exists():      # resume: skip finished runs
        return str(OUT / f'{cond}_s{seed}')
    o, cfg, conn = CONDITIONS[cond], Config(seed=seed), Connectome()
    rng = np.random.default_rng(seed)
    P = cfg.worm_population
    genomes = w.random_genomes(conn, P, rng, o)
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist = []
    for gen in range(generations):
        phase = 'explore' if (o.curriculum and gen < o.explore_gens) else 'puzzle'
        fit, st = w.run_generation(cfg, genomes, rng, conn, o, phase=phase)
        st.update(gen=gen, phase=phase); hist.append(st)
        print(f'{cond} s{seed} gen {gen:2d} {phase:7s} food {st["mean_food"]:5.2f} puzzle {st["mean_puzzle"]:5.2f} '
              f'cells {st["new_cells"]:5.1f} mem {st["mem_size"]:4.1f}', flush=True)
        order = np.argsort(fit)[::-1][:n_elite]
        best = genomes[order[0]].copy()
        elites = genomes[order]
        kids = [elites[i] for i in range(n_elite)]
        while len(kids) < P:
            kids.append(w.mutate(elites[rng.integers(n_elite)], conn, cfg, rng, o))
        genomes = np.array(kids)
    d = OUT / f'{cond}_s{seed}'
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / 'best_genome.npy', best)
    (d / 'history.json').write_text(json.dumps(hist, indent=1))
    return str(d)


def run_all(workers=2):
    jobs = [(c, s) for s in SEEDS for c in CONDITIONS]
    with ProcessPoolExecutor(workers) as ex:
        for d in ex.map(evolve, *zip(*jobs)):
            print('saved', d, flush=True)


def fair(args):
    cond, seed = args
    conn, cfg, o = Connectome(), Config(), CONDITIONS[cond]
    g = np.load(OUT / f'{cond}_s{seed}' / 'best_genome.npy')
    res = [w.run_generation(cfg, np.repeat(g[None], 40, 0), np.random.default_rng(s), conn, o, detail=True)[1]
           for s in WORLDS]
    keys = ['mean_food', 'mean_puzzle', 'puzzle_linger', 'puzzle_revisit', 'puzzle_seqB', 'mem_size']
    return cond, seed, {k: float(np.mean([r[k] for r in res])) for k in keys}


def paired(a, b):
    diff = np.array(a) - np.array(b)
    flips = np.random.default_rng(0).choice([-1, 1], (20000, len(diff)))
    p = float((np.abs((flips * diff).mean(1)) >= abs(diff.mean()) - 1e-12).mean())
    return dict(mean_diff=float(diff.mean()), wins=int((diff > 0).sum()), n=len(diff), p_value=p)


def analyze(workers=2):
    RES.mkdir(exist_ok=True)
    summ = {c: {} for c in CONDITIONS}
    with ProcessPoolExecutor(workers) as ex:
        for cond, seed, r in ex.map(fair, [(c, s) for c in CONDITIONS for s in SEEDS]):
            summ[cond][seed] = r
            print(cond, seed, r, flush=True)
    conn, cfg = Connectome(), Config()
    rnd = [w.run_generation(cfg, np.zeros((40, 1)), np.random.default_rng(s), conn, CONDITIONS['puzzle_nomem'],
                            controller='random', detail=True)[1] for s in WORLDS]
    rw = {k: float(np.mean([r[k] for r in rnd])) for k in ('mean_food', 'mean_puzzle', 'puzzle_linger', 'puzzle_revisit', 'puzzle_seqB')}
    get = lambda c, k: [summ[c][s][k] for s in SEEDS]
    memk = lambda c: [summ[c][s]['puzzle_revisit'] + summ[c][s]['puzzle_seqB'] for s in SEEDS]
    tests = {
        'curriculum (puzzle food)': paired(get('curric_nomem', 'mean_puzzle') + get('curric_mem', 'mean_puzzle'),
                                           get('puzzle_nomem', 'mean_puzzle') + get('puzzle_mem', 'mean_puzzle')),
        'memory (puzzle food)': paired(get('puzzle_mem', 'mean_puzzle') + get('curric_mem', 'mean_puzzle'),
                                       get('puzzle_nomem', 'mean_puzzle') + get('curric_nomem', 'mean_puzzle')),
        'memory (revisit + sequence)': paired(memk('puzzle_mem') + memk('curric_mem'),
                                              memk('puzzle_nomem') + memk('curric_nomem')),
        'curriculum (total food)': paired([a + b for a, b in zip(get('curric_nomem', 'mean_food') + get('curric_mem', 'mean_food'),
                                                                 get('curric_nomem', 'mean_puzzle') + get('curric_mem', 'mean_puzzle'))],
                                          [a + b for a, b in zip(get('puzzle_nomem', 'mean_food') + get('puzzle_mem', 'mean_food'),
                                                                 get('puzzle_nomem', 'mean_puzzle') + get('puzzle_mem', 'mean_puzzle'))]),
    }
    out = dict(summary=summ, tests=tests, random=rw)
    (RES / f'{TAG}_results.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(tests, indent=1), json.dumps(rw))
    charts(out)


def charts(out):
    summ = out['summary']
    conds = list(CONDITIONS)
    col = {'linger': '#7fb3e6', 'revisit': '#2a78d6', 'seqB': '#0b2a55'}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    x = np.arange(len(conds))
    bottom = np.zeros(len(conds))
    for k, c in col.items():
        v = np.array([np.mean([summ[cd][s][f'puzzle_{k}'] for s in summ[cd]]) for cd in conds])
        a1.bar(x, v, 0.6, bottom=bottom, color=c, label={'seqB': 'sequence'}.get(k, k)); bottom += v
    a1.axhline(out['random']['mean_puzzle'], color='k', ls='--', lw=1, label='random walk')
    a1.set_xticks(x, [c.replace('_', '\n') for c in conds]); a1.set_ylabel(f'puzzle food per worm (mean of {len(SEEDS)} seeds)')
    a1.set_title('Which puzzles each brain solves (6 unseen worlds)'); a1.legend(); a1.grid(axis='y', alpha=0.3)
    for cd, c in (('puzzle_mem', '#2a78d6'), ('curric_mem', '#d6762a')):
        H = np.array([[g['mem_size'] for g in json.loads((OUT / f'{cd}_s{s}' / 'history.json').read_text())] for s in SEEDS])
        a2.plot(H.mean(0), color=c, lw=2, label=cd)
        a2.fill_between(range(H.shape[1]), H.min(0), H.max(0), color=c, alpha=0.15)
    a2.axvline(20, color='#999', ls=':', lw=1); a2.text(21, a2.get_ylim()[1] * 0.95, 'puzzles start (curriculum)', fontsize=8, va='top')
    a2.set_xlabel('generation'); a2.set_ylabel('memory neurons per brain (population mean)')
    a2.set_title('How big evolution makes the memory pool'); a2.legend(); a2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / f'{TAG}_puzzles.png', dpi=130); plt.close(fig)


def use_big():
    """Step 6b (2026-11-02): same experiment, 12 seeds x 100 generations (puzzle phase 80 gens for curriculum).
    Same rules as Step 6, fixed before results: p < 0.05 (paired sign-flip, 24 pairs) or wins in all pairs."""
    global SEEDS, GENERATIONS, OUT, TAG
    SEEDS, GENERATIONS, OUT, TAG = list(range(1, 13)), 100, Path('runs/step6b'), 'step6b'


if __name__ == '__main__':
    if 'big' in sys.argv[2:]:
        use_big()
    {'all': run_all, 'analyze': analyze}[sys.argv[1]]()
