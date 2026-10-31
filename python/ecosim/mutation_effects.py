"""Direct fitness effect of each structural mutation type on an evolved worm brain.

python -m ecosim.mutation_effects runs/step2_worm   -> mutation_effects.md + .png

For each type, make N single-mutation copies of the best genome, test every copy on the same
worlds as the unmutated original, and report the change in food eaten.
This answers "is silencing/flipping/knocking out usually harmful, neutral or helpful?" directly,
instead of inferring it from who happened to survive.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .config import Config
from .connectome import Connectome, SILENT, FLIPPED
from .sim import run_generation

N, COPIES, SEEDS = 24, 6, (501, 502, 503)


def make(best, conn, kind, rng):
    g = best.copy(); E = conn.n_edges
    if kind == 'silence':
        e = int(rng.integers(E)); g[e] = SILENT; return g, f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'
    if kind == 'flip':
        e = int(rng.integers(E)); g[e] = FLIPPED; return g, f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'
    if kind == 'strengthen':
        e = int(rng.integers(E)); g[e] += 1.0; return g, f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'
    if kind == 'restore':
        s = np.flatnonzero(np.abs(g[:E] - SILENT) < 0.05)
        e = int(rng.choice(s)); g[e] = 0.0; return g, f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'
    if kind == 'knockout':
        n = int(rng.integers(conn.N)); g[np.flatnonzero(conn.pre == n)] = SILENT; return g, conn.names[n]
    return g, '-'


def score(cfg, conn, genomes):
    """mean food per genome, each tested as COPIES agents on every seed."""
    pop = np.repeat(genomes, COPIES, axis=0)
    tot = np.zeros(len(genomes))
    for s in SEEDS:
        fit, _ = run_generation(cfg, pop, np.random.default_rng(s), 'worm', conn=conn)
        tot += fit.reshape(len(genomes), COPIES).mean(1)
    return tot / len(SEEDS)


def main(run_dir):
    run_dir = Path(run_dir)
    cfg, conn, rng = Config(), Connectome(), np.random.default_rng(7)
    best = np.load(run_dir / 'best_genome.npy')
    base = score(cfg, conn, np.repeat(best[None], N, 0))     # control: N unmutated copies (shows noise)
    kinds = ['control', 'strengthen', 'silence', 'flip', 'restore', 'knockout']
    res = {'control': (base - base.mean(), ['-'] * N)}
    for k in kinds[1:]:
        gs, tg = zip(*[make(best, conn, k, rng) for _ in range(N)])
        res[k] = (score(cfg, conn, np.array(gs)) - base.mean(), list(tg))
        print(k, f'{res[k][0].mean():+.2f}')
    noise = res['control'][0].std()
    lines = [f'# Direct mutation effects on {run_dir.name} best brain', '',
             f'Unmutated food score: {base.mean():.2f}. Noise (control spread, 1 sd): ±{noise:.2f}.',
             f'{N} single-mutation copies per type, each tested {COPIES} agents × {len(SEEDS)} worlds.', '',
             '| type | mean change | harmful (< -2sd) | neutral | helpful (> +2sd) |', '|---|---|---|---|---|']
    for k in kinds:
        d = res[k][0]
        lines.append(f'| {k} | {d.mean():+.2f} | {(d < -2 * noise).sum()} | {(np.abs(d) <= 2 * noise).sum()} | {(d > 2 * noise).sum()} |')
    lines += ['', '## Biggest single effects']
    allm = [(d, k, t) for k in kinds[1:] for d, t in zip(*res[k])]
    allm.sort(key=lambda x: x[0])
    lines += [f'- {k} {t}: {d:+.2f}' for d, k, t in allm[:6]] + ['  ...'] + [f'- {k} {t}: {d:+.2f}' for d, k, t in allm[-4:]]
    (run_dir / 'mutation_effects.md').write_text('\n'.join(lines))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.boxplot([res[k][0] for k in kinds], labels=kinds)
    ax.axhspan(-2 * noise, 2 * noise, color='grey', alpha=0.2, label='noise band')
    ax.axhline(0, color='k', lw=0.8)
    ax.set_ylabel('change in food vs unmutated'); ax.set_title('Effect of one mutation on an evolved worm brain')
    ax.legend(); fig.tight_layout(); fig.savefig(run_dir / 'mutation_effects.png', dpi=120)
    print('\n'.join(lines))


if __name__ == '__main__':
    main(sys.argv[1])
