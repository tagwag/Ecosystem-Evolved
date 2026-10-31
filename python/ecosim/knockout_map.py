"""Which neurons does the evolved worm depend on? Knock out each neuron (silence all its outputs)
one at a time and measure the drop in food eaten.

python -m ecosim.knockout_map runs/step2_worm   -> knockout_map.md + knockout_map.png
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .config import Config
from .connectome import Connectome, SILENT, READOUT, SENSORS, _is_muscle
from .mutation_effects import score

CHUNK = 40


def main(run_dir):
    run_dir = Path(run_dir)
    cfg, conn = Config(), Connectome()
    best = np.load(run_dir / 'best_genome.npy')
    base = score(cfg, conn, np.repeat(best[None], CHUNK, 0))
    neurons = [i for i, n in enumerate(conn.names) if not _is_muscle(n) and (conn.pre == i).any()]
    eff = {}
    for c in range(0, len(neurons), CHUNK):
        part = neurons[c:c + CHUNK]
        gs = []
        for n in part:
            g = best.copy(); g[np.flatnonzero(conn.pre == n)] = SILENT; gs.append(g)
        for n, s in zip(part, score(cfg, conn, np.array(gs))):
            eff[conn.names[n]] = s - base.mean()
        print(f'{c + len(part)}/{len(neurons)}', flush=True)
    noise = base.std()
    order = sorted(eff, key=eff.get)
    sens = {x for v in SENSORS.values() for x in v}
    tag = lambda n: ' (sensor)' if n in sens else ' (motor readout)' if n in READOUT else ''
    lines = [f'# Neuron knockout map: {run_dir.name}', '',
             f'Unmutated score {base.mean():.2f}, noise ±{noise:.2f} (1 sd). {len(neurons)} neurons knocked out one at a time.',
             f'Clearly harmful (< -2 sd): {sum(eff[n] < -2 * noise for n in eff)}   '
             f'clearly helpful (> +2 sd): {sum(eff[n] > 2 * noise for n in eff)}', '',
             '## Most needed (removing hurts most)'] + [f'- {n}{tag(n)}: {eff[n]:+.2f}' for n in order[:20]]
    lines += ['', '## Removing these helped'] + [f'- {n}{tag(n)}: {eff[n]:+.2f}' for n in order[::-1][:10]]
    (run_dir / 'knockout_map.md').write_text('\n'.join(lines))
    fig, ax = plt.subplots(figsize=(9, 4))
    top = order[:25]
    ax.bar(top, [eff[n] for n in top], color='#e76f51')
    ax.axhline(-2 * noise, color='grey', ls='--', label='noise limit')
    ax.set_ylabel('food change when removed'); ax.set_title('Neurons the evolved worm needs most')
    plt.xticks(rotation=70, fontsize=8); ax.legend(); fig.tight_layout()
    fig.savefig(run_dir / 'knockout_map.png', dpi=120)
    print('\n'.join(lines))


if __name__ == '__main__':
    main(sys.argv[1])
