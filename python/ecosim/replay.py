"""Render a short video of a genome vs the random walk on the same world.

python -m ecosim.replay runs/step1 brain      -> runs/step1/replay.mp4
python -m ecosim.replay runs/step2_worm worm
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np

from .config import Config
from .sim import run_generation


def record(cfg, genome, controller, seed, conn=None, copies=30):
    rec = []
    g = np.repeat(genome[None, :], copies, axis=0)
    run_generation(cfg, g, np.random.default_rng(seed), controller, record=rec, conn=conn)
    return rec


def main(run_dir, controller, seed=2024, ticks=900):
    run_dir = Path(run_dir)
    cfg = Config(ticks_per_generation=ticks)
    conn = None
    if controller == 'worm':
        from .connectome import Connectome
        conn = Connectome()
    genome = np.load(run_dir / 'best_genome.npy')
    ev = record(cfg, genome, controller, seed, conn)
    rw = record(cfg, np.zeros_like(genome), 'random', seed, conn)
    n = min(len(ev), len(rw))
    fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), facecolor='#0b1a10')
    writer = FFMpegWriter(fps=30)
    out = run_dir / 'replay.mp4'
    with writer.saving(fig, str(out), dpi=90):
        for i in range(n):
            for ax, (pos, alive, food, size), title in ((axs[0], ev[i], f'evolved ({controller})'),
                                                         (axs[1], rw[i], 'random walk')):
                ax.clear(); ax.set_facecolor('#0b1a10')
                ax.scatter(food[:, 0], food[:, 1], s=4, c='#7bd389', alpha=0.6)
                ax.scatter(pos[alive, 0], pos[alive, 1], s=6 + size[alive] * 0.4, c='#ff7a59')
                ax.set_xlim(0, cfg.width); ax.set_ylim(0, cfg.height); ax.set_xticks([]); ax.set_yticks([])
                ax.set_title(f'{title}   alive {alive.sum()}', color='white', fontsize=10)
            writer.grab_frame()
    print(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
