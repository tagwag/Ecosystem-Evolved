"""Step 5: lifetime learning ladder (+ sprint & rest branch) in a two-odor world.

    python -m ecosim.step5 all        6 conditions x 4 seeds x 40 generations (~1 h on 2 cores)
    python -m ecosim.step5 analyze    fair test on 8 unseen worlds, learning check, evolved genes, charts

See ecosim/worm5.py for the model. Rule fixed before results: a step "helps" only if it beats the
step before it in all 4 seeds, or p < 0.05 (paired sign-flip test over seeds).
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
from . import worm5 as w

SEEDS = [1, 2, 3, 4]
GENERATIONS = 40
OUT, RES = Path('runs/step5'), Path('results')
WORLDS = [(4000 + i, i % 2 == 0) for i in range(8)]       # 4 worlds where food = odor A, 4 where food = odor B
COMPARE = [('hebb', 'fixed'), ('dopamine', 'hebb'), ('curiosity', 'dopamine'), ('sleep', 'curiosity'),
           ('sprint_rest', 'dopamine')]
GENE_NAMES = ['eta_h', 'eta_r', 'lam', 'curiosity', 'sleep', 'sprint', 'rest']


def evolve(cond, seed, generations=GENERATIONS):
    o, cfg, conn = w.Opts5(cond), Config(seed=seed), Connectome()
    rng = np.random.default_rng(seed)
    P = cfg.worm_population
    genomes = w.random_genomes(conn, P, rng)
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist = []
    for gen in range(generations):
        fit, st = w.run_generation(cfg, genomes, rng, conn, o)
        st['gen'] = gen; hist.append(st)
        print(f'{cond} s{seed} gen {gen:2d} food {st["mean_food"]:5.2f} food=A {st["food_is_a"]}', flush=True)
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
    np.save(d / 'final_elites.npy', elites)
    (d / 'history.json').write_text(json.dumps(hist, indent=1))
    return str(d)


def run_all(workers=2):
    jobs = [(c, s) for s in SEEDS for c in w.CONDITIONS]
    with ProcessPoolExecutor(workers) as ex:
        for d in ex.map(evolve, *zip(*jobs)):
            print('saved', d, flush=True)


# ---------------- analysis ----------------

def fair(args):
    cond, seed = args
    conn, cfg, o = Connectome(), Config(), w.Opts5(cond)
    g = np.load(OUT / f'{cond}_s{seed}' / 'best_genome.npy')
    res = []
    for s, fa in WORLDS:
        _, st = w.run_generation(cfg, np.repeat(g[None], 40, 0), np.random.default_rng(s), conn, o,
                                 food_is_a=fa, halves=True)
        res.append(st)
    return cond, seed, res


def random_walk():
    conn, cfg = Connectome(), Config()
    return [w.run_generation(cfg, np.zeros((40, 1)), np.random.default_rng(s), conn, w.Opts5('fixed'),
                             controller='random', food_is_a=fa, halves=True)[1] for s, fa in WORLDS]


def paired(a, b):
    diff = np.array(a) - np.array(b)
    rng = np.random.default_rng(0)
    flips = rng.choice([-1, 1], (20000, len(diff)))
    p = float((np.abs((flips * diff).mean(1)) >= abs(diff.mean()) - 1e-12).mean())
    return dict(mean_diff=float(diff.mean()), wins=int((diff > 0).sum()), n=len(diff), p_value=p)


def analyze(workers=2):
    RES.mkdir(exist_ok=True)
    jobs = [(c, s) for c in w.CONDITIONS for s in SEEDS]
    raw = {c: {} for c in w.CONDITIONS}
    with ProcessPoolExecutor(workers) as ex:
        for cond, seed, res in ex.map(fair, jobs):
            raw[cond][seed] = res
            print('tested', cond, seed, flush=True)
    rw = random_walk()
    summ = {}
    for c in w.CONDITIONS:
        summ[c] = {}
        for s in SEEDS:
            r = raw[c][s]
            food = float(np.mean([x['mean_food'] for x in r]))
            first = float(np.mean([x['first'] for x in r])); second = float(np.mean([x['second'] for x in r]))
            fa = float(np.mean([x['mean_food'] for x in r if x['food_is_a']]))
            fb = float(np.mean([x['mean_food'] for x in r if not x['food_is_a']]))
            g = np.load(OUT / f'{c}_s{s}' / 'best_genome.npy')
            pp = w.plastic_params(g[None], w.Layout5(Connectome()))
            genes = {k: float(pp[k][0]) for k in pp}
            summ[c][s] = dict(food=food, first_half=first, second_half=second,
                              second_over_first=second / max(first, 1e-9), food_when_A=fa, food_when_B=fb,
                              genes={k: genes[k] for k in ('eta_h', 'eta_r', 'lam', 'curiosity', 'sleep', 'sprint', 'rest')
                                     if GENE_NAMES.index(k) in w.Opts5(c).genes_used()})
            print(c, s, {k: v for k, v in summ[c][s].items()}, flush=True)
    rw_food = float(np.mean([x['mean_food'] for x in rw]))
    rw_ratio = float(np.mean([x['second'] for x in rw]) / np.mean([x['first'] for x in rw]))
    tests = {}
    for new, old in COMPARE:
        tests[f'{new} vs {old}'] = dict(
            food=paired([summ[new][s]['food'] for s in SEEDS], [summ[old][s]['food'] for s in SEEDS]),
            learning=paired([summ[new][s]['second_over_first'] for s in SEEDS],
                            [summ[old][s]['second_over_first'] for s in SEEDS]))
    out = dict(summary=summ, tests=tests, random_food=rw_food, random_second_over_first=rw_ratio,
               worlds=WORLDS, rule='helps = beats previous step in all 4 seeds, or p < 0.05')
    (RES / 'step5_results.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(tests, indent=1))
    charts(out)


def charts(out):
    summ = out['summary']
    conds = w.CONDITIONS
    col = ['#999999', '#7fb3e6', '#2a78d6', '#1b4f91', '#0b2a55', '#d6762a']
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    for i, c in enumerate(conds):
        f = [summ[c][str(s)]['food'] if str(s) in summ[c] else summ[c][s]['food'] for s in SEEDS]
        r = [summ[c][str(s)]['second_over_first'] if str(s) in summ[c] else summ[c][s]['second_over_first'] for s in SEEDS]
        a1.scatter([i] * len(f), f, color=col[i], s=40); a1.hlines(np.mean(f), i - 0.3, i + 0.3, color=col[i], lw=2.5)
        a2.scatter([i] * len(r), r, color=col[i], s=40); a2.hlines(np.mean(r), i - 0.3, i + 0.3, color=col[i], lw=2.5)
    a1.axhline(out['random_food'], color='k', ls='--', lw=1, label='random walk')
    a2.axhline(out['random_second_over_first'], color='k', ls='--', lw=1, label='random walk')
    for a in (a1, a2):
        a.set_xticks(range(len(conds)), [c.replace('_', ' & ') for c in conds]); a.grid(axis='y', alpha=0.3); a.legend()
    a1.set_title('Food eaten, 8 unseen two-odor worlds (dot = seed, line = mean)')
    a2.set_title('Learning check: food in 2nd half of life ÷ 1st half\n(higher = improves during life)')
    fig.tight_layout(); fig.savefig(RES / 'step5_ladder.png', dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, c in enumerate(conds):
        H = np.array([[g['mean_food'] for g in json.loads((OUT / f'{c}_s{s}' / 'history.json').read_text())] for s in SEEDS])
        ax.plot(H.mean(0), color=col[i], lw=1.8, label=c)
    ax.set_xlabel('generation'); ax.set_ylabel('mean food per worm'); ax.grid(alpha=0.3); ax.legend(ncol=3)
    ax.set_title('Evolution in the two-odor world (mean of 4 seeds)')
    fig.tight_layout(); fig.savefig(RES / 'step5_progress.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    {'all': run_all, 'analyze': analyze}[sys.argv[1]]()
