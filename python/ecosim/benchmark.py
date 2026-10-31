"""Fair test: one genome (copied to every agent) vs. the random walk, on the same worlds.

Each world seed builds identical food layouts and start positions for both controllers,
so differences come from behavior, not luck.
"""
import numpy as np

from .config import Config
from .sim import run_generation


def evaluate(cfg: Config, genome, controller, seeds, conn=None, copies=40):
    foods = []
    for s in seeds:
        g = np.repeat(genome[None, :], copies, axis=0)
        _, st = run_generation(cfg, g, np.random.default_rng(s), controller, conn=conn)
        foods.append(st['mean_food'])
    return float(np.mean(foods)), float(np.std(foods))


def compare(cfg, genome, controller, seeds=range(1000, 1010), conn=None):
    dummy = np.zeros_like(genome)
    ev = evaluate(cfg, genome, controller, seeds, conn)
    rw = evaluate(cfg, dummy, 'random', seeds, conn)
    return dict(evolved_mean=ev[0], evolved_sd=ev[1], random_mean=rw[0], random_sd=rw[1],
                ratio=ev[0] / max(rw[0], 1e-9))
