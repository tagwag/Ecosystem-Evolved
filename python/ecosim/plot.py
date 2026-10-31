"""Chart a run's history:  python -m ecosim.plot runs/step1 [runs/step2_worm ...]"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(dirs):
    fig, ax = plt.subplots(figsize=(9, 5))
    for d in dirs:
        h = json.loads((Path(d) / 'history.json').read_text())
        g = [x['gen'] for x in h]
        ax.plot(g, [x['mean_food'] for x in h], label=f'{Path(d).name}: evolved (mean)')
        ax.plot(g, [x['baseline_mean_food'] for x in h], '--', alpha=0.6, label=f'{Path(d).name}: random walk')
    ax.set_xlabel('generation'); ax.set_ylabel('food eaten per cell (mean)')
    ax.set_title('Evolution vs random walk'); ax.legend(); ax.grid(alpha=0.3)
    out = Path(dirs[0]) / 'progress.png'
    fig.tight_layout(); fig.savefig(out, dpi=110)
    print(out)


if __name__ == '__main__':
    main(sys.argv[1:])
