"""Which mutations survived in the open-ended ecosystem?

python -m ecosim.lineage runs/eco_worm   -> lineage.md + lineage.png

Walks every survivor's family tree back to its founder and counts the mutations on those
ancestral lines, vs all mutations that ever happened. A mutation type that is over-represented
on surviving lines was favoured by selection; under-represented = mostly harmful.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(run_dir):
    run_dir = Path(run_dir)
    births = json.loads((run_dir / 'births.json').read_text())
    parent = {b[1]: b[2] for b in births}
    muts = {b[1]: b[3] for b in births}
    survivors = np.load(run_dir / 'survivor_ids.npy').tolist()
    on_line = set()
    depth = []
    for s in survivors:
        d, c = 0, s
        while c in parent:
            on_line.add(c); c = parent[c]; d += 1
        depth.append(d)
    all_c, kept_c = Counter(), Counter()
    kept_syn = Counter()
    for cid, ev in muts.items():
        for kind, detail in ev:
            all_c[kind] += 1
            if cid in on_line:
                kept_c[kind] += 1
                if kind in ('silence', 'flip', 'knockout', 'restore'):
                    kept_syn[f'{kind} {detail}'] += 1
    n_all, n_kept = len(muts), max(len(on_line), 1)
    lines = [f'# Lineage report: {run_dir}', '',
             f'Births: {n_all}   survivors: {len(survivors)}   births on surviving lines: {len(on_line)}',
             f'Generations deep (survivor ancestry length): mean {np.mean(depth):.1f}, max {max(depth)}', '',
             '| mutation | per birth (all) | per birth (surviving lines) | ratio |', '|---|---|---|---|']
    kinds = sorted(all_c)
    ratio = {}
    for k in kinds:
        a, b = all_c[k] / n_all, kept_c[k] / n_kept
        ratio[k] = b / a if a else 0
        lines.append(f'| {k} | {a:.3f} | {b:.3f} | {ratio[k]:.2f} |')
    lines += ['', 'ratio > 1: kept more than chance (favoured); < 1: weeded out.', '',
              '## Structural mutations carried by survivors (most shared first)']
    lines += [f'- {k} (on {v} ancestral births)' for k, v in kept_syn.most_common(20)]
    (run_dir / 'lineage.md').write_text('\n'.join(lines))
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(kinds, [ratio[k] for k in kinds], color=['#2a9d8f' if ratio[k] >= 1 else '#e76f51' for k in kinds])
    ax.axhline(1, color='k', lw=1, ls='--')
    ax.set_ylabel('kept vs chance'); ax.set_title('Which mutation types survived (ecosystem mode)')
    fig.tight_layout(); fig.savefig(run_dir / 'lineage.png', dpi=120)
    print('\n'.join(lines))


if __name__ == '__main__':
    main(sys.argv[1])
