"""Picture of how evolution rewired the worm brain.

python -m ecosim.brainviz runs/step2_worm
    -> brain.png        final champion vs the original connectome
    -> brain_evolution.gif   one frame per generation (needs champions.npy, saved by newer runs)

Dots = neurons (and muscles), placed so connected neurons sit near each other.
    blue = sensory (smell)   gold = decoder readout (movement)   grey = other neurons   brown = muscles
Lines = only synapses that evolution changed:
    green = strengthened   orange = weakened   magenta = sign flipped (excite <-> inhibit)
    dotted grey = silenced (removed)
Runs entirely on your computer: no AI/credits involved.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import PillowWriter
from matplotlib.collections import LineCollection
import networkx as nx
import numpy as np

from .connectome import Connectome, READOUT, SENSORS, _is_muscle

BG = '#0e1116'
SENS = {n for v in SENSORS.values() for n in v}


def layout(conn):
    """Columns = how many synapses away from the smell sensors (signal flows left -> right).
    Muscles get the last column. Within a column, neurons are ordered by a spring layout so
    connected neurons sit near each other vertically."""
    g = nx.DiGraph()
    g.add_nodes_from(range(conn.N))
    g.add_edges_from(zip(conn.pre.tolist(), conn.post.tolist()))
    src = [conn.idx[n] for n in SENS if n in conn.idx]
    hops = nx.multi_source_dijkstra_path_length(g, src)
    maxh = max(hops.values())
    col = np.array([hops.get(i, maxh + 1) for i in range(conn.N)], float)
    musc = np.array([_is_muscle(n) for n in conn.names])
    col[musc] = col[~musc].max() + 1.5
    yinit = nx.spring_layout(g.to_undirected(), seed=7, iterations=60)
    yy = np.array([yinit[i][1] for i in range(conn.N)])
    xy = np.zeros((conn.N, 2))
    for c in np.unique(col):
        ids = np.flatnonzero(col == c)
        ids = ids[np.argsort(yy[ids])]
        xy[ids, 0] = c + (np.arange(len(ids)) % 3) * 0.18     # small stagger so labels/dots don't stack
        xy[ids, 1] = np.linspace(0, 1, len(ids)) if len(ids) > 1 else 0.5
    return xy


def classify(m):
    return {'strong': m > 0.5, 'weak': (m < -0.4) & (m > -0.95),
            'silent': np.abs(m + 1) < 0.05, 'flip': m < -1.05}


STYLE = {'strong': ('#3ddc84', '-'), 'weak': ('#ff9f43', '-'), 'flip': ('#e056fd', '-'), 'silent': ('#6b7280', ':')}


def draw(ax, conn, xy, genome, title):
    ax.clear(); ax.set_facecolor(BG); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    m = np.clip(genome[:conn.n_edges], -3, 3)
    # faint original wiring
    seg = np.stack([xy[conn.pre], xy[conn.post]], 1)
    ax.add_collection(LineCollection(seg, colors='#ffffff', alpha=0.03, linewidths=0.4))
    counts = {}
    for k, mask in classify(m).items():
        col, ls = STYLE[k]
        counts[k] = int(mask.sum())
        if mask.any():
            w = 0.6 + 1.2 * np.minimum(np.abs(m[mask]), 2) if k != 'silent' else 0.6
            ax.add_collection(LineCollection(seg[mask], colors=col, linewidths=w, linestyles=ls, alpha=0.8))
    names = conn.names
    col = ['#4dabf7' if n in SENS else '#ffd43b' if n in READOUT else '#8d6e63' if _is_muscle(n) else '#9aa0a6'
           for n in names]
    size = [40 if n in SENS or n in READOUT else 8 for n in names]
    ax.scatter(xy[:, 0], xy[:, 1], c=col, s=size, zorder=3, edgecolors='none')
    for i, n in enumerate(names):
        if n in SENS or n in ('AVAL', 'AVBL', 'AIYL', 'AIBL', 'RIAL'):
            ax.annotate(n, xy[i], color='white', fontsize=6, xytext=(3, 3), textcoords='offset points', zorder=4)
    ax.set_title(title, color='white', fontsize=11)
    legend = (f"strengthened {counts['strong']}   weakened {counts['weak']}   "
              f"flipped {counts['flip']}   silenced {counts['silent']}")
    ax.text(0.5, 1.0, 'blue = smell sensors   gold = movement readout   grey = neurons   brown = muscles   '
            '|   left -> right = synapses away from smell', transform=ax.transAxes, ha='center', va='bottom',
            color='#94a3b8', fontsize=8)
    ax.set_title(title, color='white', fontsize=11, pad=16)
    ax.text(0.5, -0.02, legend, transform=ax.transAxes, ha='center', va='top', color='#cbd5e1', fontsize=9)


def main(run_dir):
    run_dir = Path(run_dir)
    conn = Connectome()
    xy = layout(conn)
    hist = json.loads((run_dir / 'history.json').read_text()) if (run_dir / 'history.json').exists() else []
    fig, ax = plt.subplots(figsize=(10, 8), facecolor=BG)
    draw(ax, conn, xy, np.load(run_dir / 'best_genome.npy'), f'Evolved worm brain vs original wiring ({run_dir.name})')
    fig.savefig(run_dir / 'brain.png', dpi=130, facecolor=BG, bbox_inches='tight')
    print(run_dir / 'brain.png')
    champ = run_dir / 'champions.npy'
    if champ.exists():
        C = np.load(champ)
        w = PillowWriter(fps=3)
        with w.saving(fig, str(run_dir / 'brain_evolution.gif'), dpi=80):
            for gen, g in enumerate(C):
                food = f"   mean food {hist[gen]['mean_food']:.1f} vs random {hist[gen]['baseline_mean_food']:.1f}" \
                    if gen < len(hist) else ''
                draw(ax, conn, xy, g, f'Generation {gen}{food}')
                w.grab_frame()
        print(run_dir / 'brain_evolution.gif')
    else:
        print('(no champions.npy in this run: GIF needs a run made after this script was added)')


if __name__ == '__main__':
    main(sys.argv[1])
