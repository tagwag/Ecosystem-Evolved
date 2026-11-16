"""Side-by-side benchmark (2026-11-16): chemical-synapse sum as a dense matrix multiply (old, 'dense') vs adding each
synapse straight into its target neuron (new, 'index'). Same maths; only float rounding should differ.

Setup: the 16 best Step 23 control brains, each as 60 clones on 12 fixed worlds (5600-5611) = 192 worlds, one full
generation (1500 ticks), CUDA graph on (as in evolution). Runs: dense, dense again (how much a plain re-run differs:
the GPU's own rounding noise), index, index again. Same random seed every run.

PASS RULES (written 2026-11-16 12:00 MT, before running):
  1 mean skill with 'index' within 1 % of 'dense';
  2 per-brain skill differences index-vs-dense no bigger than 2x the dense-vs-dense re-run differences (mean absolute),
    OR correlation of per-brain skill index vs dense >= 0.99;
  3 report the speed-up (seconds per generation, best of 2).
If 1 and 2 pass, 'index' becomes the default (gpu_brains.Worm2Brain.chem_mode) for runs started afterwards.

    python -m ecosim.bench_chem        (watcher: chem_benchmark)  -> results/bench_chem.txt
"""
import json
import time
from pathlib import Path

import numpy as np


def main():
    import torch
    from . import step23  # noqa: F401  registers s23_ctrl
    from .batch3_fast import FastSim
    from .config import Config
    from .connectome import Connectome
    from .gpu_brains import Worm2Brain
    from .step3 import CONDITIONS, CFG_OVERRIDES
    from .worm2_gpu import pick_device
    dev, conn = pick_device('cuda'), Connectome()
    arm = 's23_ctrl'
    genomes = [np.load(Path('runs/step23') / f'{arm}_s{s}' / 'best_genome.npy') for s in range(1, 17)]
    worlds = list(range(5600, 5612))
    cfg, opts = Config(**CFG_OVERRIDES[arm]), CONDITIONS[arm]
    P = cfg.worm_population
    pairs = [(j, w) for j in range(len(genomes)) for w in worlds]
    G = np.stack([np.repeat(genomes[j][None], P, 0) for j, _ in pairs]).astype(np.float32)
    res = {}
    for name, mode in (('dense', 'dense'), ('dense_again', 'dense'), ('index', 'index'), ('index_again', 'index')):
        Worm2Brain.chem_mode = mode
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        sim = FastSim(cfg, opts, conn, len(pairs), P, dev, dev.type == 'cuda', gen)
        sim.run(G, [np.random.default_rng(w) for _, w in pairs])            # first run: CUDA graph capture (not timed)
        gen.manual_seed(4242)
        if dev.type == 'cuda':
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        fit, st = sim.run(G, [np.random.default_rng(w) for _, w in pairs])
        if dev.type == 'cuda':
            torch.cuda.synchronize()
        sec = time.perf_counter() - t0
        res[name] = dict(sec=sec, skill=fit.mean(1).reshape(len(genomes), len(worlds)).mean(1))
        print(f'{name:12s} {sec:6.2f} s per generation, mean skill {res[name]["skill"].mean():.4f}', flush=True)
        del sim; torch.cuda.empty_cache() if dev.type == 'cuda' else None
    d, i = res['dense']['skill'], res['index']['skill']
    rerun = np.abs(d - res['dense_again']['skill']).mean()
    diff = np.abs(i - d).mean()
    corr = float(np.corrcoef(i, d)[0, 1])
    rel = abs(i.mean() - d.mean()) / max(abs(d.mean()), 1e-9)
    td = min(res['dense']['sec'], res['dense_again']['sec']); ti = min(res['index']['sec'], res['index_again']['sec'])
    r1, r2 = rel <= 0.01, (diff <= 2 * max(rerun, 1e-12)) or corr >= 0.99
    L = ['Chemical-synapse benchmark: 16 Step 23 control brains x 12 worlds x 60 clones, 1 generation (1500 ticks), CUDA graph',
         f'mean skill: dense {d.mean():.4f}, index {i.mean():.4f} (difference {rel:.2%}) -> rule 1 {"PASS" if r1 else "FAIL"}',
         f'per-brain |difference|: index vs dense {diff:.4f}; dense re-run vs dense {rerun:.4f}; correlation {corr:.4f} -> rule 2 {"PASS" if r2 else "FAIL"}',
         f'speed: dense {td:.2f} s/generation, index {ti:.2f} s/generation -> {td / ti:.2f}x',
         'VERDICT: ' + ('switch the default to index' if (r1 and r2) else 'keep dense')]
    txt = '\n'.join(L); print(txt)
    Path('results').mkdir(exist_ok=True)
    Path('results/bench_chem.txt').write_text(txt + '\n')
    Path('results/bench_chem.json').write_text(json.dumps({k: dict(sec=v['sec'], skill=v['skill'].tolist()) for k, v in res.items()}))
    print('CHEM_BENCH_DONE', flush=True)


if __name__ == '__main__':
    main()
