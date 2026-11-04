"""Step 15: LINEAGE TOURNAMENT. The best brains from different seeds compete for dominance in one population.

Arm: whichever Step 14 arm evolved the most (biggest mean gain in true skill from its first to its last checkpoint,
from results/step14{a,b}_stats.json 'evolution_gain'). Override: python -m ecosim.step15 run <cond>.
Founders: that arm's 12 best seeds (true skill at the last checkpoint). Each tournament starts with 60 brains:
every founder + 4 mutants of it, tagged with the founder's lineage. Then 300 generations of normal evolution
(clonal-group scoring, same world as the arm). Children inherit their parent's tag, so we can watch lineages
take over or go extinct. 32 tournaments with different random streams.

Questions: does one lineage take over (time to 50% / 100%)? Is it always the same one (the best founder = skill
decides) or different ones (luck decides)? Do the winners keep improving past their founders?

    python -m ecosim.step15 quick       python -m ecosim.step15 run [cond]       python -m ecosim.step15 analyze
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

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

N_FOUND, COPIES, GROUP = 12, 5, 10
TOURNAMENTS, GENS, EVERY = 32, 300, 50
OUT, RES = Path('runs/step15'), Path('results')


def pick_arm():
    gains = {}
    for p in 'ab':
        f = RES / f'step14{p}_stats.json'
        if f.exists():
            for c, v in json.loads(f.read_text())['evolution_gain'].items():
                gains[c] = (v, p)
    c = max(gains, key=lambda k: gains[k][0])
    return c, gains[c][1], {k: v[0] for k, v in gains.items()}


def founders(cond, part, src=s14.OUT, n=N_FOUND, curves_file=None):
    cur = json.loads((curves_file or RES / f'step14{part}_curves.json').read_text())[cond]
    last = np.array(cur['fitness'][-1])
    seeds = s14.SEEDS[:len(last)]
    top = [seeds[i] for i in np.argsort(last)[::-1][:n]]
    return top, {s: float(last[seeds.index(s)]) for s in top}, \
        [np.load(src / part / f'{cond}_s{s}' / 'best_genome.npy') for s in top]


def tournament(cond, G0, T=TOURNAMENTS, gens=GENS, out=OUT, device='cuda'):
    from .batch3_fast import FastSim
    from .config import Config
    from .connectome import Connectome
    from . import worm2 as w
    from .worm2_gpu import pick_device
    opts, conn = CONDITIONS[cond], Connectome()
    base = Config(seed=1, **CFG_OVERRIDES[cond])
    P, nF = base.worm_population, len(G0)
    f = GROUP / P                                         # same 1/6-size clonal worlds as batch3_fast._evolve_clonal
    cfg = Config(seed=1, **dict(CFG_OVERRIDES[cond], width=base.width * f ** 0.5, height=base.height * f ** 0.5,
                                food_patches=max(1, round(base.food_patches * f)),
                                food_regrow_per_tick=base.food_regrow_per_tick * f,
                                predators=max(1, round(base.predators * f)) if base.predators else 0))
    dev = pick_device(device)
    rngs = [np.random.default_rng([15, t]) for t in range(T)]
    gen = torch.Generator(device=dev); gen.manual_seed(1515)
    sim = FastSim(cfg, opts, conn, T * P, GROUP, dev, True, gen)
    copies = P // nF
    pop, tag = [], []
    for r in rngs:
        b = []
        for i, g in enumerate(G0):
            b += [g] + [w.mutate(g, conn, base, r, opts)[0] for _ in range(copies - 1)]
        pop.append(np.stack(b)); tag.append(np.repeat(np.arange(nF), copies))
    pop, tag = np.stack(pop), np.stack(tag)
    n_elite = max(2, int(P * base.elite_fraction))
    share = np.zeros((T, gens, nF)); fitm = np.zeros((T, gens))
    out.mkdir(parents=True, exist_ok=True)
    print(f'{cond}: {T} tournaments x {nF} founders x {copies} = {P} brains, {gens} generations', flush=True)
    t_all = time.perf_counter()
    for g in range(gens):
        t0 = time.perf_counter()
        wseed = [int(r.integers(2**63)) for r in rngs]
        fitw, _ = sim.run(pop.astype(np.float32).reshape(T * P, 1, -1).repeat(GROUP, 1),
                          [np.random.default_rng(wseed[t]) for t in range(T) for _ in range(P)])
        fit = fitw.mean(1).reshape(T, P)
        new, ntag = np.empty_like(pop), np.empty_like(tag)
        for t, r in enumerate(rngs):
            share[t, g] = np.bincount(tag[t], minlength=nF) / P
            fitm[t, g] = fit[t].mean()
            order = np.argsort(fit[t])[::-1][:n_elite]
            if (g + 1) % EVERY == 0:
                np.save(out / f't{t}_ckpt_g{g + 1}.npy', pop[t, order[0]])
                np.save(out / f't{t}_ckpt_g{g + 1}_tag.npy', np.array(tag[t, order[0]]))
            kids, kt = [pop[t, i] for i in order], [tag[t, i] for i in order]
            while len(kids) < P:
                j = order[r.integers(n_elite)]
                kids.append(w.mutate(pop[t, j], conn, base, r, opts)[0]); kt.append(tag[t, j])
            new[t], ntag[t] = np.array(kids), np.array(kt)
        pop, tag = new, ntag
        alive_lin = (share[:, g] > 0).sum(1)
        print(f'gen {g:3d}  fitness {fitm[:, g].mean():5.2f}  lineages left per tournament: mean {alive_lin.mean():4.1f} '
              f'(min {alive_lin.min()}, max {alive_lin.max()})  {time.perf_counter() - t0:5.1f} s', flush=True)
    np.save(out / 'share.npy', share); np.save(out / 'fitness.npy', fitm)
    print(f'saved {out}  ({time.perf_counter() - t_all:.0f} s total)', flush=True)


def run(cond=None, T=TOURNAMENTS, gens=GENS, out=OUT, src=s14.OUT, curves_file=None):
    if cond:
        part = 'a' if cond in s14.A_ARMS else 'b'
        gains = None
    else:
        cond, part, gains = pick_arm()
    top, skill, G0 = founders(cond, part, src, curves_file=curves_file)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'setup.json').write_text(json.dumps(dict(cond=cond, part=part, gains=gains, founder_seeds=top,
                                                    founder_skill=skill), indent=1))
    print('Step 15 arm:', cond, '| founders (seed: skill):', skill, flush=True)
    tournament(cond, G0, T, gens, out)


def analyze(out=OUT, tag=''):
    from .connectome import Connectome
    from .step3d_analyze import paired
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    setup = json.loads((out / 'setup.json').read_text())
    cond, top = setup['cond'], setup['founder_seeds']
    share, fitm = np.load(out / 'share.npy'), np.load(out / 'fitness.npy')
    T, gens, nF = share.shape
    final = share[:, -1]
    winner = final.argmax(1)
    t50 = [int(np.argmax(share[t, :, winner[t]] >= 0.5)) if (share[t, :, winner[t]] >= 0.5).any() else None for t in range(T)]
    t100 = [int(np.argmax(share[t, :, winner[t]] >= 1.0)) if (share[t, :, winner[t]] >= 1.0).any() else None for t in range(T)]
    wins = np.bincount(winner, minlength=nF)
    # skill: founders vs tournament champions (last checkpoint), on the fixed test worlds
    dev, conn = pick_device('cuda'), Connectome()
    G0 = [np.load(s14.OUT / setup['part'] / f'{cond}_s{s}' / 'best_genome.npy') for s in top] if not tag else None
    cks = list(range(EVERY, gens + 1, EVERY))
    champ = [[np.load(out / f't{t}_ckpt_g{g}.npy') for t in range(T)] for g in cks]
    champ_skill = np.array([s14.test(cond, c, conn, dev)['fitness'] for c in champ])        # (n_ckpt, T)
    st = dict(cond=cond, founder_seeds=top, founder_skill=setup['founder_skill'],
              wins_by_founder={str(top[i]): int(wins[i]) for i in range(nF)},
              distinct_winners=int((wins > 0).sum()),
              winner_is_best_founder=int((winner == 0).sum()),
              gen_to_50pct=t50, gen_to_100pct=t100,
              median_gen_to_100pct=(float(np.median([x for x in t100 if x is not None])) if any(x is not None for x in t100) else None),
              tournaments_fixed=int(sum(x is not None for x in t100)),
              champion_skill_by_checkpoint=dict(zip(map(str, cks), champ_skill.mean(1).round(4).tolist())))
    if G0 is not None:
        fs = s14.test(cond, G0, conn, dev)['fitness']
        st['founder_skill_retest'] = fs.round(4).tolist()
        st['champion_vs_own_founder'] = paired(champ_skill[-1], fs[winner])
        st['champion_vs_best_founder'] = paired(champ_skill[-1], np.full(T, fs.max()))
        # does founder skill predict how often it wins? (Spearman rank correlation)
        from scipy.stats import spearmanr
        rho, p = spearmanr(fs, wins)
        st['founder_skill_vs_wins_spearman'] = dict(rho=float(rho), p=float(p))
    st['note'] = 'founders listed best first; paired(): "hunger" = first argument'
    (RES / f'step15{tag}_stats.json').write_text(json.dumps(st, indent=1))
    print(json.dumps(st, indent=1), flush=True)
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.6))
    cols = plt.cm.tab20(np.linspace(0, 1, nF))
    axes[0].stackplot(np.arange(gens), share[0].T, colors=cols, labels=[f'seed {s}' for s in top])
    axes[0].set_title('tournament 1: lineage share'); axes[0].set_xlabel('generation'); axes[0].set_ylim(0, 1)
    axes[0].legend(fontsize=6, ncol=2, loc='upper right')
    axes[1].bar([str(s) for s in top], wins, color=cols)
    axes[1].set_title(f'winning lineage in {T} tournaments (founders best -> worst)'); axes[1].set_xlabel('founder seed')
    axes[2].plot(np.arange(gens), fitm.mean(0), lw=2, label='population (training score)')
    axes[2].errorbar(cks, champ_skill.mean(1), yerr=1.96 * champ_skill.std(1) / np.sqrt(T), marker='o', capsize=3,
                     label='champion true skill')
    if G0 is not None:
        axes[2].axhline(fs.max(), color='k', ls='--', lw=1, label='best founder')
    axes[2].set_xlabel('generation'); axes[2].legend(fontsize=8); axes[2].grid(alpha=0.3)
    fig.suptitle(f'Step 15: lineage tournament ({cond}, {nF} founders, {T} tournaments)')
    fig.tight_layout(); fig.savefig(RES / f'step15{tag}.png', dpi=130); plt.close(fig)


if __name__ == '__main__':
    if sys.argv[1] == 'quick':
        q = Path('runs/step15_quick')
        run('h14_herd', T=2, gens=EVERY, out=q, src=Path('runs/step14_quick'),
            curves_file=RES / 'step14b_quick_curves.json')
        analyze(q, tag='_quick')
    elif sys.argv[1] == 'run':
        run(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        analyze()
