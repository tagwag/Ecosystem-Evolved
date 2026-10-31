"""Evolution loop: run a generation, keep the leaderboard, mutate, repeat.

Run:  python -m ecosim.evolve            (from the python/ folder)
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .brain import genome_size
from .config import Config
from .sim import run_generation


def mutate(parent, cfg, rng):
    child = parent.copy()
    mask = rng.random(child.shape) < cfg.mutation_rate
    child[mask] += rng.normal(0, cfg.mutation_sigma, mask.sum())
    return child


def next_generation(genomes, fitness, cfg, rng):
    P = len(genomes)
    n_elite = max(2, int(P * cfg.elite_fraction))
    leaderboard = np.argsort(fitness)[::-1][:n_elite]
    elites = genomes[leaderboard]
    children = [elites[i % n_elite] for i in range(n_elite)]          # elites survive unchanged
    while len(children) < P:
        children.append(mutate(elites[rng.integers(n_elite)], cfg, rng))
    return np.array(children), genomes[leaderboard[0]]


def evolve(cfg: Config, out_dir: Path, log=print):
    rng = np.random.default_rng(cfg.seed)                 # ONE seeded RNG -> reproducible runs
    G = genome_size(cfg.hidden)
    genomes = rng.normal(0, 0.5, (cfg.population, G))
    history = []
    best = genomes[0]
    for gen in range(cfg.generations):
        fit, stats = run_generation(cfg, genomes, rng)
        # random-walk baseline on the same settings, for comparison
        _, base = run_generation(cfg, genomes, rng, controller='random')
        stats.update(gen=gen, baseline_mean_food=base['mean_food'])
        history.append(stats)
        log(f"gen {gen:3d}  mean food {stats['mean_food']:6.2f}  best {stats['best_food']:4.0f}  "
            f"survivors {stats['survivors']:3d}  | random-walk mean {base['mean_food']:6.2f}")
        genomes, best = next_generation(genomes, fit, cfg, rng)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / 'best_genome.npy', best)
    (out_dir / 'history.json').write_text(json.dumps(history, indent=1, default=float))
    return best, history


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--generations', type=int, default=Config.generations)
    ap.add_argument('--population', type=int, default=Config.population)
    ap.add_argument('--seed', type=int, default=Config.seed)
    ap.add_argument('--out', default='runs/latest')
    a = ap.parse_args()
    evolve(Config(generations=a.generations, population=a.population, seed=a.seed), Path(a.out))
