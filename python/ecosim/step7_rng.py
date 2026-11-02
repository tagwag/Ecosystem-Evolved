"""Step 7: randomness sanity check. Does evolution come out different with seeded pseudo-random numbers
(PCG64, seeds 101-106) vs unseeded hardware entropy (OS randomness, 6 runs)?

Same model as Step 4 without growth (worm3, food fitness), 40 generations, 60 worms.
The hardware-entropy seeds ARE logged (entropy value) so a surprising result can be debugged.

    python -m ecosim.step7_rng all       12 runs (~45 min on 2 cores)
    python -m ecosim.step7_rng analyze   -> results/step7_*

Rule fixed before results: a difference counts only at p < 0.05 (permutation test, 6 vs 6) on any of:
final food during evolution, fair-test food of the best brain, number of silenced synapses, population diversity,
or the spread (variance) of fair-test food. A difference would point to a bug in how the code uses randomness.
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
from .connectome import Connectome, SILENT
from . import worm3 as g3

OUT, RES = Path('runs/step7'), Path('results')
GENERATIONS = 40
SEEDED = [101, 102, 103, 104, 105, 106]
N_HW = 6
WORLDS = range(3000, 3006)
O = g3.Opts3(growth=False)


def evolve(kind, i):
    conn = Connectome()
    if kind == 'seeded':
        rng = np.random.default_rng(i); entropy = i
    else:
        rng = np.random.default_rng(); entropy = int(rng.bit_generator.seed_seq.entropy)
    cfg = Config()
    names = g3.all_names(conn, O)
    P = cfg.worm_population
    genomes = g3.random_genomes(conn, P, rng, O)
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist = []
    for gen in range(GENERATIONS):
        fit, st = g3.run_generation(cfg, genomes, rng, conn, O)
        hist.append(st['mean_food'])
        print(f'{kind} {i} gen {gen:2d} food {st["mean_food"]:5.2f}', flush=True)
        order = np.argsort(fit)[::-1][:n_elite]
        best, elites = genomes[order[0]].copy(), genomes[order]
        kids = [elites[k] for k in range(n_elite)]
        while len(kids) < P:
            kids.append(g3.mutate(elites[rng.integers(n_elite)], conn, cfg, rng, O, names)[0])
        genomes = np.array(kids)
    d = OUT / f'{kind}_{i}'
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / 'best_genome.npy', best); np.save(d / 'elites.npy', elites)
    (d / 'run.json').write_text(json.dumps(dict(kind=kind, entropy=str(entropy), history=hist), indent=1))
    return str(d)


def run_all(workers=2):
    jobs = [('seeded', s) for s in SEEDED] + [('hardware', k) for k in range(N_HW)]
    with ProcessPoolExecutor(workers) as ex:
        for d in ex.map(evolve, *zip(*jobs)):
            print('saved', d, flush=True)


def measure(path):
    conn, cfg = Connectome(), Config()
    d = Path(path)
    best, elites = np.load(d / 'best_genome.npy'), np.load(d / 'elites.npy')
    run = json.loads((d / 'run.json').read_text())
    E = conn.n_edges
    foods = [g3.run_generation(cfg, np.repeat(best[None], 40, 0), np.random.default_rng(s), conn, O)[1]['mean_food']
             for s in WORLDS]
    syn = elites[:, :E]
    div = float(np.mean([np.abs(syn[a] - syn[b]).mean() for a in range(len(syn)) for b in range(a + 1, len(syn))]))
    return dict(path=path, kind=run['kind'], entropy=run['entropy'],
                final_food=float(np.mean(run['history'][-5:])), fair_food=float(np.mean(foods)),
                silenced=int((np.abs(best[:E] - SILENT) < 1e-6).sum()), diversity=div)


def perm(a, b, stat=lambda x, y: np.mean(x) - np.mean(y)):
    a, b = np.array(a), np.array(b)
    obs = stat(a, b); pool = np.r_[a, b]; rng = np.random.default_rng(0); n = len(a); hits = 0
    for _ in range(20000):
        p = rng.permutation(pool)
        hits += abs(stat(p[:n], p[n:])) >= abs(obs) - 1e-12
    return float(obs), hits / 20000


def analyze(workers=2):
    RES.mkdir(exist_ok=True)
    paths = sorted(str(p) for p in OUT.iterdir() if p.is_dir())
    with ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(measure, paths))
    s = [r for r in rows if r['kind'] == 'seeded']; h = [r for r in rows if r['kind'] == 'hardware']
    tests = {}
    for k in ('final_food', 'fair_food', 'silenced', 'diversity'):
        d, p = perm([r[k] for r in s], [r[k] for r in h])
        tests[k] = dict(seeded_mean=float(np.mean([r[k] for r in s])), hardware_mean=float(np.mean([r[k] for r in h])),
                        diff=d, p_value=p)
    d, p = perm([r['fair_food'] for r in s], [r['fair_food'] for r in h], stat=lambda x, y: np.var(x) - np.var(y))
    tests['fair_food_spread'] = dict(seeded_sd=float(np.std([r['fair_food'] for r in s])),
                                     hardware_sd=float(np.std([r['fair_food'] for r in h])), p_value=p)
    out = dict(runs=rows, tests=tests, any_difference=any(t['p_value'] < 0.05 for t in tests.values()))
    (RES / 'step7_rng_results.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(tests, indent=1), 'any difference:', out['any_difference'])
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.6))
    for ax, k, lab in zip(axs, ('final_food', 'fair_food', 'silenced', 'diversity'),
                          ('food, last 5 generations', 'fair-test food (best brain)', 'silenced synapses (best brain)',
                           'population diversity')):
        for j, (grp, col) in enumerate(((s, '#2a78d6'), (h, '#d6762a'))):
            v = [r[k] for r in grp]
            ax.scatter([j] * len(v), v, color=col, s=36); ax.hlines(np.mean(v), j - 0.25, j + 0.25, color=col, lw=2)
        ax.set_xticks([0, 1], ['seeded', 'hardware']); ax.set_title(f'{lab}\np = {tests[k]["p_value"]:.2f}', fontsize=9)
        ax.grid(axis='y', alpha=0.3)
    fig.suptitle('Seeded pseudo-random vs hardware entropy: 6 evolution runs each')
    fig.tight_layout(); fig.savefig(RES / 'step7_rng.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    {'all': run_all, 'analyze': analyze}[sys.argv[1]]()
