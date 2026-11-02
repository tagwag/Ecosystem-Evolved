"""Step 4 on the GPU: does letting the worm brain GROW (new neurons, new synapses) help? 32 seeds.

Same model, world and fitness as step4.py (growth vs no growth, food eaten + survival, normal food),
run with batch3_fast's engine and gpu_brains.GrowBrain. Step 4 (4 seeds, CPU) found growth was neutral:
brains grew 3-6 neurons by drift. This rerun has 8x the seeds to tell "neutral" from "small effect".

    python -m ecosim.step4_gpu run [gens]     # default 60 generations (~15-20 min on an RTX 3080)
    python -m ecosim.step4_gpu analyze        -> results/step4g_*
"""
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from .batch3_fast import FastSim
from .config import Config
from .connectome import Connectome
from .step3d_analyze import paired
from .step4 import CONDITIONS
from . import worm3 as g3
from .worm2_gpu import pick_device

SEEDS = list(range(1, 33))
GENS = 60
OUT, RES = Path('runs/step4g'), Path('results')
WORLDS = list(range(3000, 3006))           # same unseen test worlds as step4.py


def evolve(cond, seeds=SEEDS, generations=GENS, out=OUT, device='cuda'):
    o, conn = CONDITIONS[cond], Connectome()
    cfg = Config(seed=seeds[0])
    dev = pick_device(device)
    names = g3.all_names(conn, o)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng(list(seeds) + [4]).integers(2**62)))
    P = cfg.worm_population
    sim = FastSim(cfg, o, conn, len(seeds), P, dev, True, gen)
    pop = np.stack([g3.random_genomes(conn, P, r, o) for r in rngs]).astype(np.float32)
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist, best = [[] for _ in seeds], [None] * len(seeds)
    print(f'{cond}: {len(seeds)} runs x {P} worms on {dev} (growing brains)', flush=True)
    for g in range(generations):
        t0 = time.perf_counter()
        fit, stats = sim.run(pop, rngs)
        t1 = time.perf_counter()
        new = np.empty_like(pop)
        for k, r in enumerate(rngs):
            order = np.argsort(fit[k])[::-1]
            grown = [g3.n_grown(x, conn, o) for x in pop[k]]
            st = stats[k]
            st.update(gen=g, best_neurons=int(grown[order[0]][0]), best_synapses=int(grown[order[0]][1]),
                      mean_neurons=float(np.mean([x[0] for x in grown])))
            hist[k].append(st)
            best[k] = pop[k, order[0]].copy()
            elites = pop[k, order[:n_elite]]
            kids = [elites[i] for i in range(n_elite)]
            while len(kids) < P:
                kids.append(g3.mutate(elites[r.integers(n_elite)].astype(np.float64), conn, cfg, r, o, names)[0])
            new[k] = np.array(kids)
        pop = new
        fm = np.array([s['fitness'] for s in stats]); nm = np.mean([s['mean_neurons'] for s in stats])
        print(f'{cond} gen {g:2d}  food {fm.mean():6.2f} (min {fm.min():5.2f}, max {fm.max():5.2f})  '
              f'grown neurons {nm:4.1f}  sim {t1 - t0:5.2f} s  evolve {time.perf_counter() - t1:5.2f} s', flush=True)
    for k, s in enumerate(seeds):
        d = out / f'{cond}_s{s}'
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / 'best_genome.npy', best[k])
        (d / 'history.json').write_text(json.dumps(hist[k], indent=1))


def fair(cond, seeds, conn, dev, chunk=8):
    """Each seed's best brain on the same 6 unseen worlds, 60 copies. Chunked: growing brains are big."""
    o, cfg = CONDITIONS[cond], Config()
    P, out = cfg.worm_population, {}
    for i in range(0, len(seeds), chunk):
        ss = seeds[i:i + chunk]
        pairs = [(s, wd) for s in ss for wd in WORLDS]
        G = np.stack([np.repeat(np.load(OUT / f'{cond}_s{s}' / 'best_genome.npy')[None], P, 0) for s, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(777)
        sim = FastSim(cfg, o, conn, len(pairs), P, dev, False, gen)
        _, st = sim.run(G, [np.random.default_rng(wd) for _, wd in pairs])
        for s in ss:
            v = [st[j]['mean_food'] for j, (x, _) in enumerate(pairs) if x == s]
            out[s] = dict(food=float(np.mean(v)), food_sd=float(np.std(v)),
                          neurons=int(g3.n_grown(np.load(OUT / f'{cond}_s{s}' / 'best_genome.npy'), conn, o)[0]))
        del sim; torch.cuda.empty_cache() if dev.type == 'cuda' else None
    return out


def analyze():
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    f = {c: fair(c, SEEDS, conn, dev) for c in ('growth', 'nogrowth')}
    a = np.array([f['growth'][s]['food'] for s in SEEDS]); b = np.array([f['nogrowth'][s]['food'] for s in SEEDS])
    stats = dict(food=paired(a, b), grown_neurons_best=[f['growth'][s]['neurons'] for s in SEEDS])
    (RES / 'step4g_results.json').write_text(json.dumps(f, indent=1))
    (RES / 'step4g_stats.json').write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for cond, col in (('growth', '#2a78d6'), ('nogrowth', '#999999')):
        H = [json.loads((OUT / f'{cond}_s{s}' / 'history.json').read_text()) for s in SEEDS]
        axes[0].plot(np.mean([[g['mean_food'] for g in h] for h in H], 0), color=col, lw=2, label=cond)
        axes[1].plot(np.mean([[g['mean_neurons'] for g in h] for h in H], 0), color=col, lw=2, label=cond)
    axes[0].set_ylabel('food eaten per worm'); axes[1].set_ylabel('grown neurons per brain (population mean)')
    for ax in axes:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend()
    fig.suptitle('Step 4 on the GPU: growth vs no growth (mean of 32 seeds)')
    fig.tight_layout(); fig.savefig(RES / 'step4g_progress.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else GENS
        for c in ('growth', 'nogrowth'):
            evolve(c, generations=n)
    else:
        analyze()
