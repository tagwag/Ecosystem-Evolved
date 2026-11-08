"""Step 18b: was rock a shelter or a trap? (Wald / survivorship-bias check on Step 18)

Step 18's "time near rock" only counted living worms and couldn't tell hiding from being stuck. This re-tests the
saved Step 18 brains (generation 10 = nearly random, generation 150 = evolved; 32 seeds each, 60 clones on 12 fresh
full-size worlds) and counts, over ALL worms including those that die:
    bite rate near rock vs in the open   (per 1000 worm-ticks spent there)  -> higher near rock = rock is a trap
    death rate near rock vs in the open
    hidden fraction  = of the time a worm is within a predator's range, how much of it every sight line is blocked
    stuck fraction   = fraction of worm-ticks spent bumping into rock
No new evolution.   python -m ecosim.step18b [quick]   -> results/step18b_stats.json, step18b.png
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step18 as s18

WORLDS = list(range(4000, 4012))
ARMS = ('o18_herd', 'o18_plain')
RES = Path('results')


def diag(cond, genomes, conn, dev, worlds=WORLDS):
    """Summed Step 18b counters per genome (n, 10) over the test worlds."""
    from .batch3_fast import FastSim
    from .config import Config
    opts, cfg = CONDITIONS[cond], Config(**CFG_OVERRIDES[cond])
    P, out = cfg.worm_population, []
    for i in range(0, len(genomes), 16):
        gs = genomes[i:i + 16]
        pairs = [(j, w) for j in range(len(gs)) for w in worlds]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(1818)
        _, st = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen).run(G, [np.random.default_rng(w) for _, w in pairs])
        D = np.array([x['odiag'] for x in st]).reshape(len(gs), len(worlds), 10).sum(1)
        out.append(D)
    return np.concatenate(out)


def rates(D):
    with np.errstate(invalid='ignore', divide='ignore'):
        return dict(rock_time=D[:, 0] / (D[:, 0] + D[:, 1]),
                    bite_near=1000 * D[:, 2] / D[:, 0], bite_open=1000 * D[:, 3] / D[:, 1],
                    death_near=1000 * D[:, 4] / D[:, 0], death_open=1000 * D[:, 5] / D[:, 1],
                    hidden=D[:, 6] / (D[:, 6] + D[:, 7]), stuck=D[:, 8] / D[:, 9])


def main(seeds=s18.SEEDS, gens=(10, 150), out=s18.OUT, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    R = {}
    for c in ARMS:
        for g in gens:
            G = [np.load(out / f'{c}_s{s}' / f'ckpt_g{g}.npy') for s in seeds]
            R[(c, g)] = rates(diag(c, G, conn, dev))
            print(c, g, {k: round(float(np.nanmean(v)), 4) for k, v in R[(c, g)].items()}, flush=True)
    g0, g1 = gens[0], gens[-1]
    ok = lambda a, b: (np.isfinite(a) & np.isfinite(b))
    pr = lambda a, b: paired(a[ok(a, b)], b[ok(a, b)])
    st = {f'{c}_g{g}': {k: float(np.nanmean(v)) for k, v in R[(c, g)].items()} for c in ARMS for g in gens}
    for c in ARMS:
        for g in gens:
            r = R[(c, g)]
            st[f'{c}_g{g}_bite_near_vs_open'] = pr(r['bite_near'], r['bite_open'])
            st[f'{c}_g{g}_death_near_vs_open'] = pr(r['death_near'], r['death_open'])
        for k in ('rock_time', 'hidden', 'stuck', 'bite_near', 'bite_open'):
            st[f'{c}_{k}_g{g1}_vs_g{g0}'] = pr(R[(c, g1)][k], R[(c, g0)][k])
    for k in ('rock_time', 'hidden', 'stuck'):
        st[f'herd_vs_plain_{k}_g{g1}'] = pr(R[('o18_herd', g1)][k], R[('o18_plain', g1)][k])
    st['note'] = ('rates per 1000 worm-ticks; paired(): "hunger" = first argument, "nohunger" = second. '
                  'near rock = within 16 units. All worms counted, including ones that die.')
    (RES / f'step18b{tag}_stats.json').write_text(json.dumps(st, indent=1))
    print(json.dumps(st, indent=1), flush=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.4))
    lab = [f'{c.split("_")[1]} g{g}' for c in ARMS for g in gens]
    x = np.arange(len(lab))
    for ax, (a, b, t) in zip(axes[:2], (('bite_near', 'bite_open', 'bites per 1000 worm-ticks'),
                                         ('death_near', 'death_open', 'deaths per 1000 worm-ticks'))):
        ax.bar(x - 0.2, [np.nanmean(R[(c, g)][a]) for c in ARMS for g in gens], 0.4, label='near rock')
        ax.bar(x + 0.2, [np.nanmean(R[(c, g)][b]) for c in ARMS for g in gens], 0.4, label='open')
        ax.set_xticks(x, lab); ax.set_title(t); ax.legend()
    for i, k in enumerate(('rock_time', 'hidden', 'stuck')):
        axes[2].bar(x + (i - 1) * 0.27, [np.nanmean(R[(c, g)][k]) for c in ARMS for g in gens], 0.27, label=k)
    axes[2].set_xticks(x, lab); axes[2].set_title('fractions of time'); axes[2].legend()
    fig.suptitle('Step 18b: is rock a shelter or a trap? (all worms, incl. ones that die; 12 test worlds)')
    fig.tight_layout(); fig.savefig(RES / f'step18b{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'quick':
        main(list(range(1, 3)), tag='_quick')
    else:
        main()
