"""What did evolution change in the worm brain?

python -m ecosim.analyze runs/step2_worm   -> prints a report and writes mutations.md

Compares the best genome to the unmodified connectome (all multipliers = 1):
  - synapses strengthened / weakened / effectively silenced
  - which neurons gained or lost the most total input/output
  - evolved sensor and motor gains
"""
import sys
from pathlib import Path

import numpy as np

from .connectome import Connectome, N_GAINS

GAIN_NAMES = ['ON-sensor gain (ASEL)', 'OFF-sensor gain (ASER/AWC)', 'level-sensor gain (AWA)',
              'speed gain (AVB-AVA)', 'reversal bias', 'steering gain (head muscles)']


def analyze(run_dir, top=15):
    conn = Connectome()
    g = np.load(Path(run_dir) / 'best_genome.npy')
    logm = np.clip(g[:conn.n_edges], -6, 3)
    base = np.abs(conn.w_chem)
    new = base * np.exp(logm)
    change = new - base
    names = conn.names
    lines = [f'# Mutation report: {run_dir}', '',
             f'Chemical synapses: {conn.n_edges}',
             f'- strengthened >2x: {(logm > np.log(2)).sum()}',
             f'- weakened <0.5x: {(logm < np.log(0.5)).sum()}',
             f'- effectively silenced (<0.05x): {(logm < np.log(0.05)).sum()}', '']

    def edge(i):
        sign = 'inhib' if conn.w_chem[i] < 0 else 'excit'
        return f'{names[conn.pre[i]]:>7} -> {names[conn.post[i]]:<8} ({sign}) x{np.exp(logm[i]):.2f}'

    order = np.argsort(change)
    lines += ['## Most strengthened synapses'] + [f'    {edge(i)}' for i in order[::-1][:top]] + ['']
    lines += ['## Most weakened synapses'] + [f'    {edge(i)}' for i in order[:top]] + ['']

    out_d = np.zeros(conn.N); in_d = np.zeros(conn.N)
    np.add.at(out_d, conn.pre, change); np.add.at(in_d, conn.post, change)
    tot = out_d + in_d
    o = np.argsort(tot)
    lines += ['## Neurons whose wiring changed most (sum of synapse-strength change)']
    lines += [f'    {names[i]:>7}  {tot[i]:+.2f}  (out {out_d[i]:+.2f}, in {in_d[i]:+.2f})' for i in o[::-1][:10]]
    lines += ['    ...'] + [f'    {names[i]:>7}  {tot[i]:+.2f}  (out {out_d[i]:+.2f}, in {in_d[i]:+.2f})' for i in o[:10]] + ['']
    gains = g[conn.n_edges:conn.n_edges + N_GAINS]
    lines += ['## Evolved gains (0 = starting value)'] + [f'    {n:<32} {v:+.2f}' for n, v in zip(GAIN_NAMES, gains)]
    text = '\n'.join(lines)
    (Path(run_dir) / 'mutations.md').write_text(text)
    return text


if __name__ == '__main__':
    print(analyze(sys.argv[1]))
