"""Step 4: does letting the worm brain GROW (new neurons, new synapses) change performance and behaviour?

    python -m ecosim.step4 all          growth vs no growth, 4 seeds, 60 generations
    python -m ecosim.step4 analyze      fair tests, behaviour, charts -> results/step4_*

Same world and fitness as Step 2 (food eaten). Only difference between conditions: growth on/off.
"""
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .config import Config
from .connectome import Connectome
from . import worm3 as g3

CONDITIONS = {'growth': g3.Opts3(growth=True), 'nogrowth': g3.Opts3(growth=False)}
SEEDS = [1, 2, 3, 4]
GENERATIONS = 60
OUT, RES = Path('runs/step4'), Path('results')
WORLDS = range(3000, 3006)


def evolve(cond, seed, generations=GENERATIONS):
    o, cfg, conn = CONDITIONS[cond], Config(seed=seed), Connectome()
    names = g3.all_names(conn, o)
    rng = np.random.default_rng(seed)
    P = cfg.worm_population
    genomes = g3.random_genomes(conn, P, rng, o)
    events = [[] for _ in range(P)]
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist, kept = [], Counter()
    for gen in range(generations):
        fit, st = g3.run_generation(cfg, genomes, rng, conn, o)
        order = np.argsort(fit)[::-1]
        grown = [g3.n_grown(g, conn, o) for g in genomes]
        st.update(gen=gen, best_neurons=grown[order[0]][0], best_synapses=grown[order[0]][1],
                  mean_neurons=float(np.mean([x[0] for x in grown])),
                  elite_neurons=float(np.mean([grown[i][0] for i in order[:n_elite]])))
        # which growth events made it into the winners this generation
        for i in order[:n_elite]:
            for t, d in events[i]:
                if t in ('duplicate', 'new_neuron', 'new_synapse'):
                    kept[(t, d if t == 'duplicate' else '')] += 1
        hist.append(st)
        print(f'{cond} s{seed} gen {gen:2d} food {st["mean_food"]:5.2f} best+neurons {st["best_neurons"]:2d} '
              f'mean+neurons {st["mean_neurons"]:4.1f}', flush=True)
        elites = genomes[order[:n_elite]]
        kids, evs = [elites[i] for i in range(n_elite)], [[] for _ in range(n_elite)]
        while len(kids) < P:
            c, ev = g3.mutate(elites[rng.integers(n_elite)], conn, cfg, rng, o, names)
            kids.append(c); evs.append(ev)
        best = genomes[order[0]].copy()
        genomes, events = np.array(kids), evs
    d = OUT / f'{cond}_s{seed}'
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / 'best_genome.npy', best)
    (d / 'history.json').write_text(json.dumps(hist, indent=1))
    (d / 'kept_growth.json').write_text(json.dumps([[t, n, c] for (t, n), c in kept.most_common()], indent=1))
    return str(d)


def run_all(workers=2):
    jobs = [(c, s) for s in SEEDS for c in CONDITIONS]
    with ProcessPoolExecutor(workers) as ex:
        for d in ex.map(evolve, *zip(*jobs)):
            print('saved', d, flush=True)


# ---------------- analysis ----------------

def behaviour(cond, genome, conn, copies=40):
    o, cfg = CONDITIONS[cond], Config()
    food, spd, rev, trn = [], [], [], []
    for s in WORLDS:
        tr = {}
        _, st = g3.run_generation(cfg, np.repeat(genome[None], copies, 0), np.random.default_rng(s), conn, o, trace=tr)
        food.append(st['mean_food']); spd.append(np.nanmean(tr['speed_frac']))
        rev.append(np.nanmean(tr['reverse'])); trn.append(np.nanmean(tr['turn']))
    return dict(food=float(np.mean(food)), food_sd=float(np.std(food)), speed=float(np.mean(spd)),
                reversal_rate=float(np.mean(rev)), turning=float(np.mean(trn)))


def analyze():
    conn = Connectome()
    RES.mkdir(exist_ok=True)
    out = {}
    for cond in CONDITIONS:
        out[cond] = {}
        for s in SEEDS:
            d = OUT / f'{cond}_s{s}'
            g = np.load(d / 'best_genome.npy')
            b = behaviour(cond, g, conn)
            b['grown_neurons'], b['added_synapses'] = g3.n_grown(g, conn, CONDITIONS[cond])
            L = g3.Layout3(conn, CONDITIONS[cond])
            act = g[L.act] > 0.5
            src = g[L.src][act].round().astype(int)
            b['grown_from'] = [conn.names[i] if i >= 0 else 'blank' for i in src]
            out[cond][s] = b
            print(cond, s, {k: v for k, v in b.items() if k != 'grown_from'}, flush=True)
    rnd = [g3.run_generation(Config(), np.zeros((40, g3.Layout3(conn, CONDITIONS['nogrowth']).size)),
                             np.random.default_rng(s), conn, CONDITIONS['nogrowth'], controller='random')[1]['mean_food']
           for s in WORLDS]
    out['random_food'] = float(np.mean(rnd))
    (RES / 'step4_results.json').write_text(json.dumps(out, indent=1))
    charts(out)


def charts(out):
    col = {'growth': '#2a78d6', 'nogrowth': '#999999'}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5))
    for cond in CONDITIONS:
        H = [json.loads((OUT / f'{cond}_s{s}' / 'history.json').read_text()) for s in SEEDS]
        F = np.array([[g['mean_food'] for g in h] for h in H])
        a1.plot(F.mean(0), color=col[cond], lw=2, label=cond)
        a1.fill_between(range(F.shape[1]), F.min(0), F.max(0), color=col[cond], alpha=0.15)
        if cond == 'growth':
            for s, h in zip(SEEDS, H):
                a2.plot([g['elite_neurons'] for g in h], lw=1.5, label=f'seed {s}')
    a1.set_title('Food per worm (mean of 4 seeds, band = range)'); a1.set_xlabel('generation'); a1.legend(); a1.grid(alpha=0.3)
    a2.set_title('Grown neurons in the top 20% (growth runs)'); a2.set_xlabel('generation')
    a2.set_ylabel('new neurons per brain'); a2.legend(); a2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / 'step4_progress.png', dpi=130); plt.close(fig)

    # behaviour comparison
    keys = [('food', 'food eaten'), ('speed', 'speed command'), ('reversal_rate', 'reversals per tick'), ('turning', 'turning')]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.8))
    for ax, (k, lab) in zip(axs, keys):
        for j, cond in enumerate(CONDITIONS):
            v = [out[cond][s][k] for s in SEEDS]
            ax.scatter([j] * len(v), v, color=col[cond], s=40)
            ax.hlines(np.mean(v), j - 0.25, j + 0.25, color=col[cond], lw=2)
        ax.set_xticks([0, 1], list(CONDITIONS)); ax.set_title(lab); ax.grid(axis='y', alpha=0.3)
    axs[0].axhline(out['random_food'], color='k', ls='--', lw=1)
    fig.suptitle('Behaviour of the best evolved brain per seed (dots) and mean (line); dashed = random walk')
    fig.tight_layout(); fig.savefig(RES / 'step4_behaviour.png', dpi=130); plt.close(fig)

    # which neurons got duplicated and kept
    c = Counter(n for s in SEEDS for n in out['growth'][s]['grown_from'])
    top = c.most_common(20)
    if top:
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.barh([n for n, _ in top][::-1], [v for _, v in top][::-1], color='#2a78d6')
        ax.set_xlabel('copies in the 4 best final brains'); ax.set_title('What the grown neurons were copied from')
        fig.tight_layout(); fig.savefig(RES / 'step4_grown_from.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if sys.argv[1] == 'all':
        run_all()
    elif sys.argv[1] == 'analyze':
        analyze()
    else:
        evolve(sys.argv[2], int(sys.argv[3]))
