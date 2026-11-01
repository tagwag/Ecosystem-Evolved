"""Analyze Step 3 runs (python -m ecosim.step3_analyze). Writes results/step3_*.

1. Fair test, hunger vs no-hunger: each seed's best brain on 6 unseen worlds, same layouts.
2. Satiety quiescence: the brain's own speed command when full vs hungry.
   Uses speed_frac (the brain's command), not actual speed, because bigger worms are slower by body rules.
3. Open readout: which neurons the evolved decoder actually uses (contribution = spread of each
   neuron's term in the speed and reversal outputs over a run).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .config import Config
from .connectome import Connectome, READOUT
from . import worm2 as w
from .step3 import CONDITIONS, SEEDS, OUT

RES = Path('results')
WORLDS = range(2000, 2006)
FULL, HUNGRY = 0.8, 0.4          # fractions of the gut cap


def best(cond, seed):
    return np.load(OUT / f'{cond}_s{seed}' / 'best_genome.npy')


def fair(cond, genome, conn, copies=40):
    opts, cfg = CONDITIONS[cond], Config()
    fits, foods, sf_full, sf_hungry = [], [], [], []
    for s in WORLDS:
        tr = {}
        f, st = w.run_generation(cfg, np.repeat(genome[None], copies, 0), np.random.default_rng(s), conn, opts, trace=tr)
        fits.append(f.mean()); foods.append(st['mean_food'])
        e, sf = tr['energy'], tr['speed_frac']
        sf_full.append(np.nanmean(np.where(e >= FULL * opts.gut_cap, sf, np.nan)))
        sf_hungry.append(np.nanmean(np.where(e < HUNGRY * opts.gut_cap, sf, np.nan)))
    return dict(fitness=float(np.mean(fits)), fitness_sd=float(np.std(fits)), food=float(np.mean(foods)),
                speed_full=float(np.nanmean(sf_full)), speed_hungry=float(np.nanmean(sf_hungry)))


def random_walk(cond, conn, genome):
    opts, cfg = CONDITIONS[cond], Config()
    fs = [w.run_generation(cfg, np.repeat(genome[None], 40, 0), np.random.default_rng(s), conn, opts,
                           controller='random')[0].mean() for s in WORLDS]
    return float(np.mean(fs))


def contributions(genome, conn, opts):
    cfg = Config()
    names = w.readout_names(conn, opts)
    acc = {'n': 0}

    def hook(b):
        r = np.tanh(np.maximum(b.v, 0))[:, b.rd]
        dev = r - b.rbar          # rbar already updated this tick; close enough for ranking
        term = dev[:, :, None] * b.D + r[:, :, None] * b.Dl            # P x R x 3
        t = term[:, :, :2].reshape(-1, len(names), 2)
        acc.setdefault('s', np.zeros((len(names), 2))); acc.setdefault('ss', np.zeros((len(names), 2)))
        acc['s'] += t.sum(0); acc['ss'] += (t ** 2).sum(0); acc['n'] += t.shape[0]

    for s in WORLDS[:3]:
        w.run_generation(cfg, np.repeat(genome[None], 20, 0), np.random.default_rng(s), conn, opts, hook=hook)
    mean = acc['s'] / acc['n']
    sd = np.sqrt(np.maximum(acc['ss'] / acc['n'] - mean ** 2, 0))
    return names, sd.sum(1)        # spread of each neuron's effect on speed + reversal


def main():
    conn = Connectome()
    RES.mkdir(exist_ok=True)
    out = {'fair': {}, 'open': {}}

    # ---- 1 + 2: hunger vs no hunger ----
    for cond in ('hunger', 'nohunger'):
        out['fair'][cond] = {s: fair(cond, best(cond, s), conn) for s in SEEDS}
        print(cond, json.dumps(out['fair'][cond], indent=0), flush=True)
    out['random_energy_fitness'] = random_walk('hunger', conn, best('hunger', 1))

    # ---- 3: open readout ----
    known = set(READOUT)
    for s in SEEDS:
        names, imp = contributions(best('open', s), conn, CONDITIONS['open'])
        order = np.argsort(imp)[::-1]
        rank = {names[i]: r + 1 for r, i in enumerate(order)}
        top28 = [names[i] for i in order[:28]]
        out['open'][s] = dict(
            top10=[(names[i], round(float(imp[i]), 4)) for i in order[:10]],
            ranks={n: rank[n] for n in ['AVAL', 'AVAR', 'AVBL', 'AVBR', 'AVDL', 'AVDR'] if n in rank},
            known_in_top28=len(known & set(top28)), n_readout=len(names),
            food=fair('open', best('open', s), conn)['food'])
        print('open', s, out['open'][s], flush=True)
    out['open_random_food'] = float(np.mean([w.run_generation(
        Config(), np.zeros((40, 1)), np.random.default_rng(x), conn, CONDITIONS['open'], controller='random')[1]['mean_food']
        for x in WORLDS]))
    (RES / 'step3_results.json').write_text(json.dumps(out, indent=1, default=str))
    charts(out, conn)


def charts(out, conn):
    # progress
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for cond, col in (('hunger', '#2a78d6'), ('nohunger', '#999999')):
        H = np.array([[g['fitness'] for g in json.loads((OUT / f'{cond}_s{s}' / 'history.json').read_text())] for s in SEEDS])
        ax.plot(H.mean(0), color=col, lw=2, label=f'{cond} (mean of {len(SEEDS)} seeds)')
        ax.fill_between(range(H.shape[1]), H.min(0), H.max(0), color=col, alpha=0.15)
    ax.set_xlabel('generation'); ax.set_ylabel('fitness = average energy held (food units)')
    ax.set_title('Evolution with vs without the hunger peptide'); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / 'step3_progress.png', dpi=130); plt.close(fig)

    # quiescence bars
    fig, ax = plt.subplots(figsize=(7, 4.5))
    xs = np.arange(len(SEEDS))
    for k, (cond, col) in enumerate((('hunger', '#2a78d6'), ('nohunger', '#999999'))):
        r = [out['fair'][cond][s]['speed_full'] / out['fair'][cond][s]['speed_hungry'] for s in SEEDS]
        ax.bar(xs + (k - 0.5) * 0.38, r, 0.38, color=col, label=cond)
    ax.axhline(1, color='k', lw=1)
    ax.set_xticks(xs, [f'seed {s}' for s in SEEDS])
    ax.set_ylabel('speed when full / speed when hungry\n(below 1 = slows down when full)')
    ax.set_title('Satiety quiescence check'); ax.legend(); ax.grid(axis='y', alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / 'step3_quiescence.png', dpi=130); plt.close(fig)

    # H vs speed trace for one hunger worm
    opts, cfg = CONDITIONS['hunger'], Config()
    tr = {}
    w.run_generation(cfg, np.repeat(best('hunger', 1)[None], 20, 0), np.random.default_rng(WORLDS[0]), conn, opts, trace=tr)
    i = int(np.argmax(tr['alive'].sum(0)))
    t = np.arange(len(tr['H']))
    fig, a1 = plt.subplots(figsize=(9, 4))
    sm = np.convolve(np.nan_to_num(tr['speed_frac'][:, i]), np.ones(25) / 25, 'same')
    a1.plot(t, sm, color='#2a78d6', lw=1.5, label='speed command (smoothed)')
    a1.set_ylabel('speed command (0-1)', color='#2a78d6'); a1.set_xlabel('tick')
    a2 = a1.twinx(); a2.plot(t, tr['H'][:, i], color='#d64b2a', lw=1.5, label='hunger H')
    a2.set_ylabel('hunger H (0-1)', color='#d64b2a')
    a1.set_title('One evolved worm: hunger vs how fast it chooses to move (seed 1)')
    fig.tight_layout(); fig.savefig(RES / 'step3_hunger_trace.png', dpi=130); plt.close(fig)

    # open readout
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for s in SEEDS:
        ranks = out['open'][s]['ranks']
        ax.scatter([s] * len(ranks), list(ranks.values()), color='#2a78d6')
        for n, r in ranks.items():
            ax.annotate(n, (s, r), xytext=(6, 0), textcoords='offset points', fontsize=7)
    n = out['open'][SEEDS[0]]['n_readout']
    ax.axhline(n / 2, color='#999', ls='--', lw=1, label=f'middle rank (chance), {n} neurons')
    ax.set_ylim(n + 5, 0); ax.set_xticks(SEEDS, [f'seed {s}' for s in SEEDS])
    ax.set_ylabel('importance rank (1 = most used)'); ax.legend()
    ax.set_title('Open readout: where AVA / AVB / AVD rank among all neurons')
    fig.tight_layout(); fig.savefig(RES / 'step3_open_readout.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    main()
