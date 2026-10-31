"""Evolution loop: run a generation, keep the leaderboard, mutate, repeat.

Run:  python -m ecosim.evolve            (from the python/ folder)
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .brain import genome_size
from . import connectome as cx
from .config import Config
from .sim import run_generation


def mutate(parent, cfg, rng, rate=None):
    child = parent.copy()
    mask = rng.random(child.shape) < (cfg.mutation_rate if rate is None else rate)
    child[mask] += rng.normal(0, cfg.mutation_sigma, mask.sum())
    return child


def next_generation(genomes, fitness, cfg, rng, rate=None, conn=None):
    """Returns (children, best_genome, events) -- events[i] = mutations carried by child i."""
    P = len(genomes)
    n_elite = max(2, int(P * cfg.elite_fraction))
    leaderboard = np.argsort(fitness)[::-1][:n_elite]
    elites = genomes[leaderboard]
    children = [elites[i % n_elite] for i in range(n_elite)]          # elites survive unchanged
    events = [[] for _ in range(n_elite)]
    while len(children) < P:
        parent = elites[rng.integers(n_elite)]
        if conn is not None:
            c, ev = cx.mutate_worm(parent, conn, cfg, rng)
        else:
            c, ev = mutate(parent, cfg, rng, rate), [('tweak', 0)]
        children.append(c); events.append(ev)
    return np.array(children), genomes[leaderboard[0]], events


def selection_stats(events, fitness, cfg):
    """For each mutation type: how often it appears in all children vs in the winners."""
    P = len(fitness)
    top = set(np.argsort(fitness)[::-1][:max(2, int(P * cfg.elite_fraction))].tolist())
    out = {}
    for i, ev in enumerate(events):
        for t, _ in ev:
            d = out.setdefault(t, [0, 0]); d[0] += 1; d[1] += i in top
    return {t: dict(born=b, won=w) for t, (b, w) in out.items()}


def evolve(cfg: Config, out_dir: Path, log=print, controller='brain'):
    rng = np.random.default_rng(cfg.seed)                 # ONE seeded RNG -> reproducible runs
    conn, rate = None, None
    if controller == 'worm':
        conn = cx.Connectome()
        genomes = cx.random_genomes(conn, cfg.worm_population, rng)
        rate = cfg.worm_mutation_rate
    else:
        genomes = rng.normal(0, 0.5, (cfg.population, genome_size(cfg.hidden)))
    history = []
    best = genomes[0]
    events = [[] for _ in range(len(genomes))]
    winners_log = []
    champions = []
    for gen in range(cfg.generations):
        fit, stats = run_generation(cfg, genomes, rng, controller, conn=conn)
        # random-walk baseline on the same settings, for comparison
        _, base = run_generation(cfg, genomes, rng, controller='random', conn=conn)
        stats.update(gen=gen, baseline_mean_food=base['mean_food'],
                     selection=selection_stats(events, fit, cfg))
        top = np.argsort(fit)[::-1][:3]
        winners_log.append({'gen': gen, 'top_mutations': [events[i] for i in top]})
        history.append(stats)
        log(f"gen {gen:3d}  mean food {stats['mean_food']:6.2f}  best {stats['best_food']:4.0f}  "
            f"survivors {stats['survivors']:3d}  | random-walk mean {base['mean_food']:6.2f}")
        champions.append(genomes[int(np.argmax(fit))].astype(np.float32))   # for brainviz animation
        genomes, best, events = next_generation(genomes, fit, cfg, rng, rate, conn)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / 'best_genome.npy', best)
    np.save(out_dir / 'champions.npy', np.array(champions))
    (out_dir / 'history.json').write_text(json.dumps(history, indent=1, default=float))
    (out_dir / 'winners.json').write_text(json.dumps(winners_log, indent=1, default=str))
    return best, history


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--generations', type=int, default=Config.generations)
    ap.add_argument('--population', type=int, default=Config.population)
    ap.add_argument('--seed', type=int, default=Config.seed)
    ap.add_argument('--out', default='runs/latest')
    ap.add_argument('--brain', choices=['brain', 'worm'], default='brain',
                    help="'brain' = tiny network (step 1), 'worm' = C. elegans connectome (step 2)")
    a = ap.parse_args()
    evolve(Config(generations=a.generations, population=a.population, seed=a.seed), Path(a.out),
           controller=a.brain)
