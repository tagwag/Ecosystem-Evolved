"""Check the GPU setup and compare the CPU (NumPy) and GPU (PyTorch) worm brains.

    python -m ecosim.gpu_check

1. Prints which GPU PyTorch sees.
2. Feeds identical inputs to both brains for 300 ticks and reports the biggest difference
   (should be tiny, ~1e-5: float32 rounding).
3. Times one full generation each way, and the brain alone at bigger population sizes.
"""
import time

import numpy as np
import torch

from .config import Config
from .connectome import Connectome
from . import worm2 as w
from .worm2_gpu import WormBrainsTorch, pick_device


def main():
    dev = pick_device('cuda')
    print('PyTorch', torch.__version__, '| CUDA available:', torch.cuda.is_available())
    if dev.type == 'cuda':
        p = torch.cuda.get_device_properties(0)
        print(f'GPU: {p.name}, {p.total_memory / 2**30:.1f} GB')
    else:
        print('No CUDA GPU found: running the GPU code on the CPU instead (slow, but checks correctness).')

    cfg, conn, opts = Config(seed=1), Connectome(), w.Opts()
    rng = np.random.default_rng(1)
    g = w.random_genomes(conn, cfg.worm_population, rng, opts)
    g[:, w.Layout(conn, opts).rec] = rng.normal(0, 0.5, (len(g), conn.N))    # switch the peptide on
    a, b = w.WormBrains2(conn, g, opts), WormBrainsTorch(conn, g, opts, dev)
    worst = 0.0
    for _ in range(300):
        smell, ds, H = rng.random(len(g)), rng.uniform(-1, 1, len(g)), rng.random(len(g))
        worst = max(worst, max(np.abs(x - y).max() for x, y in zip(a.step(smell, ds, H), b.step(smell, ds, H))))
    print(f'Largest CPU vs GPU output difference over 300 ticks: {worst:.2e}', 'OK' if worst < 1e-3 else 'MISMATCH')

    for name, d in (('CPU (NumPy)', None), (f'GPU ({dev.type})', 'cuda')):
        t0 = time.perf_counter()
        st = w.run_generation(cfg, g, np.random.default_rng(1), conn, opts, device=d)[1]
        print(f'One generation, {len(g)} worms, {name}: {time.perf_counter() - t0:5.1f} s  (food {st["mean_food"]:.2f})')

    print('\nBrain only, 200 ticks:')
    for P in (60, 600, 3000):
        gg = w.random_genomes(conn, P, rng, opts)
        ins = [(rng.random(P), rng.uniform(-1, 1, P), rng.random(P)) for _ in range(200)]
        row = f'  {P:5d} worms:'
        for name, mk in (('CPU', lambda: w.WormBrains2(conn, gg, opts)),
                         ('GPU', lambda: WormBrainsTorch(conn, gg, opts, dev))):
            if name == 'CPU' and P > 600:
                row += '   CPU  (skipped, too slow)'; continue
            br = mk(); t0 = time.perf_counter()
            for x in ins:
                br.step(*x)
            row += f'   {name} {time.perf_counter() - t0:6.2f} s'
        print(row)


if __name__ == '__main__':
    main()
