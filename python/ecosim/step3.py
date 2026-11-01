"""Step 3 experiments: hunger peptide and open readout.

One command reruns everything (about 20 minutes on 2 CPU cores):
    python -m ecosim.step3 all
Or a single run:
    python -m ecosim.step3 run hunger 1

Conditions (all on the same seeds):
    hunger     peptide on,  28 known readout neurons, fitness = energy held
    nohunger   peptide off, 28 known readout neurons, fitness = energy held   (control)
    open       peptide off, readout from ALL neurons, fitness = food eaten     (Step 2 setup, open readout)
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .config import Config
from .connectome import Connectome
from . import worm2 as w

CONDITIONS = {
    'hunger': w.Opts(hunger=True, readout='known', fitness='energy'),
    'nohunger': w.Opts(hunger=False, readout='known', fitness='energy'),
    'open': w.Opts(hunger=False, readout='all', fitness='food'),
}
SEEDS = [1, 2, 3, 4]
GENERATIONS = 40
OUT = Path('runs/step3')


def evolve(cond, seed, generations=GENERATIONS, out=OUT):
    opts, cfg, conn = CONDITIONS[cond], Config(seed=seed), Connectome()
    rng = np.random.default_rng(seed)
    P = cfg.worm_population
    genomes = w.random_genomes(conn, P, rng, opts)
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist = []
    for gen in range(generations):
        fit, st = w.run_generation(cfg, genomes, rng, conn, opts)
        st['gen'] = gen; hist.append(st)
        print(f'{cond} s{seed} gen {gen:2d} fitness {st["fitness"]:6.2f} food {st["mean_food"]:5.2f} '
              f'energy {st["mean_energy"]:6.1f} alive {st["survivors"]}', flush=True)
        order = np.argsort(fit)[::-1][:n_elite]
        best = genomes[order[0]].copy()
        elites = genomes[order]
        kids = [elites[i] for i in range(n_elite)]
        while len(kids) < P:
            kids.append(w.mutate(elites[rng.integers(n_elite)], conn, cfg, rng, opts)[0])
        genomes = np.array(kids)
    d = out / f'{cond}_s{seed}'
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / 'best_genome.npy', best)
    (d / 'history.json').write_text(json.dumps(hist, indent=1))
    return str(d)


def run_all(workers=2):
    jobs = [(c, s) for s in SEEDS for c in CONDITIONS]
    with ProcessPoolExecutor(workers) as ex:
        for d in ex.map(evolve, *zip(*jobs)):
            print('saved', d, flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'all':
        run_all()
    else:
        evolve(sys.argv[2], int(sys.argv[3]))
