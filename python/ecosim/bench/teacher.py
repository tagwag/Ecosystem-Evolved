"""Progress-chasing teacher (automatic curriculum): keep evolution climbing by always training where it learns fastest.

A pool of world types. Evolution runs in blocks of `block` generations. After each block the teacher measures that
world's LEARNING PROGRESS (how much the population's score rose during the block) and picks the next world with a
multi-armed bandit (UCB: high recent progress + a bonus for worlds not tried lately + a little randomness). Worlds that
are too easy (already mastered) or too hard (no headway) both show little progress and get picked less.

Arms run side by side for the same number of generations, same seeds:
    teacher   the bandit above
    random    a random world each block            (is it the choosing, or just the variety?)
    fixed     always the first world in the pool    (the Step 19 baseline)
Yardstick every `test_every` generations: best brain per seed on fixed test worlds of (a) every pool world and
(b) HOLDOUT worlds never trained in. Intelligence = mean skill on the holdouts.

    mode = "teacher" in a settings file; see experiments/teacher.toml and experiments/README.md
"""
import copy
import json
import time

import numpy as np

from ..config import Config
from ..step3 import CONDITIONS, CFG_OVERRIDES
from .run import build, setup_fn, lifetime, TEST_WORLDS0

DEFAULT_POOL = [
    dict(name='base'),
    dict(name='scarce', cfg={'food_regrow_per_tick': 0.1}),
    dict(name='moving_food', cfg={'season_every': 300}),
    dict(name='fast_predators', cfg={'pred_speed': 3.5, 'pred_sense': 200.0}),
    dict(name='toxin', features={'toxin': {'a': 1.5}}),
    dict(name='temperature', features={'temperature': {'a': 1.0, 'period': 3000}}),
]
DEFAULT_HOLDOUT = [
    dict(name='rich_food', cfg={'food_regrow_per_tick': 0.4}),
    dict(name='many_predators', cfg={'predators': 10}),
    dict(name='few_big_patches', cfg={'food_patches': 3}),
    dict(name='light_zones', features={'light': {'a': 1.0}}),
]


def world_S(S, opt):
    """Settings for one world option: base + its cfg changes, world features + its feature changes."""
    T = copy.deepcopy(S)
    T.setdefault('base', {}).update(opt.get('cfg') or {})
    feats = T.setdefault('world', {}).setdefault('features', {})
    for name, over in (opt.get('features') or {}).items():
        feats.setdefault(name, {}).update(over or {})
    return T


class Bandit:
    def __init__(self, n, rng, c=0.5, eps=0.1, window=3):
        self.n, self.rng, self.c, self.eps, self.window = n, rng, c, eps, window
        self.prog, self.count, self.t = [[] for _ in range(n)], np.zeros(n), 0

    def pick(self):
        self.t += 1
        untried = np.flatnonzero(self.count == 0)
        if len(untried):
            return int(untried[0])
        if self.rng.random() < self.eps:
            return int(self.rng.integers(self.n))
        lp = np.array([np.mean(p[-self.window:]) for p in self.prog])
        scale = np.std(np.concatenate([p[-self.window:] for p in self.prog])) + 1e-9
        return int(np.argmax(lp / scale + self.c * np.sqrt(np.log(self.t) / self.count)))

    def update(self, i, progress):
        self.prog[i].append(progress); self.count[i] += 1


def run_teacher(S, out, conn, dev):
    from ..batch3_fast import evolve
    from .report import nice  # noqa: F401
    T = S.get('teacher', {})
    ev, te = S.get('evolve', {}), S.get('test', {})
    seeds = list(range(1, ev.get('seeds', 8) + 1))
    gens, block, test_every = T.get('generations', 300), T.get('block', 10), T.get('test_every', 50)
    pool = S.get('world_option') or DEFAULT_POOL
    hold = S.get('holdout') or DEFAULT_HOLDOUT
    arms = T.get('arms', ['teacher', 'random', 'fixed'])
    tw = list(range(TEST_WORLDS0, TEST_WORLDS0 + te.get('worlds', 8)))
    worlds = {}
    for i, opt in enumerate(pool + hold):
        WS = world_S(S, opt)
        opts, over, specs, vals, bset = build(WS, {}, conn)
        cond = f'teach_{S["name"]}_{opt["name"]}'
        CONDITIONS[cond] = opts; CFG_OVERRIDES[cond] = over
        worlds[opt['name']] = dict(S=WS, opts=opts, over=over, specs=specs, vals=vals, bset=bset, cond=cond,
                                   holdout=i >= len(pool))
    pool_names = [o['name'] for o in pool]
    hold_names = [o['name'] for o in hold]

    def yardstick(best):
        G = [best[s] for s in seeds]
        r = {}
        for name, w in worlds.items():
            st = lifetime(conn, dev, w['opts'], w['over'], w['specs'], [(w['vals'], w['bset'])], G, tw, 60)
            n = len(tw)
            r[name] = [float(np.mean([x['fitness'] for x in st[j * n:(j + 1) * n]])) for j in range(len(G))]
        return r

    R = dict(arms={}, pool=pool_names, holdout=hold_names, block=block, generations=gens)
    t_all = time.time()
    for arm in arms:
        rng = np.random.default_rng(T.get('seed', 7))
        bandit = Bandit(len(pool), rng, T.get('explore', 0.5), T.get('random_pick', 0.1))
        pop, best, g = None, None, 0
        choices, progress, tests = [], [], []
        print(f'=== arm {arm}', flush=True)
        while g < gens:
            i = bandit.pick() if arm == 'teacher' else int(rng.integers(len(pool))) if arm == 'random' else 0
            w = worlds[pool_names[i]]
            last, lbest = {}, {}

            def grab(gg, k, fit, per, order, popk, last=last, lbest=lbest, B=min(block, gens - g)):
                if gg == B - 1:
                    last[k] = popk.copy(); lbest[k] = popk[order[0]].copy()
            hist, _ = evolve(w['cond'], seeds, min(block, gens - g), out=out / 'brains' / arm, quiet=True,
                               clonal=60, brains=ev.get('brains', 16), eval_worlds=ev.get('worlds_per_generation', 2),
                               init=pop, setup=setup_fn(conn, w['S'], w['specs'], [(w['vals'], w['bset'])]), on_gen=grab)
            pop = {s: last[k] for k, s in enumerate(seeds)}
            best = {s: lbest[k] for k, s in enumerate(seeds)}
            f = np.array([[h['fitness'] for h in hs] for hs in hist])          # (seeds, block)
            k3 = max(1, f.shape[1] // 3)
            prog = float((f[:, -k3:].mean(1) - f[:, :k3].mean(1)).mean())        # learning progress in this block
            bandit.update(i, prog)
            choices.append(pool_names[i]); progress.append(prog)
            g += min(block, gens - g)
            print(f'{arm} gen {g:4d}  world {pool_names[i]:15s} progress {prog:+.3f}', flush=True)
            if g % test_every == 0 or g >= gens:
                y = yardstick(best)
                tests.append(dict(gen=g, per_world={k: float(np.mean(v)) for k, v in y.items()},
                                  intelligence=float(np.mean([np.mean(y[h]) for h in hold_names])),
                                  pool_skill=float(np.mean([np.mean(y[p]) for p in pool_names])),
                                  intelligence_per_seed=np.mean([y[h] for h in hold_names], 0).tolist(),
                                  pool_skill_per_seed=np.mean([y[p] for p in pool_names], 0).tolist()))
                print(f'   yardstick: intelligence {tests[-1]["intelligence"]:.3f}  pool skill {tests[-1]["pool_skill"]:.3f}', flush=True)
                R['arms'][arm] = dict(choices=choices, progress=progress, tests=tests)
                (out / 'teacher.json').write_text(json.dumps(R, indent=1))
        R['arms'][arm] = dict(choices=choices, progress=progress, tests=tests,
                              choice_counts={p: choices.count(p) for p in pool_names})
    from .surface import fit_all  # noqa: F401
    from ..step3d_analyze import paired
    cmp = {}
    if 'teacher' in R['arms']:
        for other in [a for a in arms if a != 'teacher']:
            a, b = R['arms']['teacher']['tests'][-1], R['arms'][other]['tests'][-1]
            cmp[f'teacher_vs_{other}'] = dict(intelligence=paired(np.array(a['intelligence_per_seed']), np.array(b['intelligence_per_seed'])),
                                              pool_skill=paired(np.array(a['pool_skill_per_seed']), np.array(b['pool_skill_per_seed'])))
    R['comparisons'] = cmp
    R['seconds'] = round(time.time() - t_all)
    (out / 'teacher.json').write_text(json.dumps(R, indent=1))
    teacher_report(S, R, out)
    import shutil
    from pathlib import Path
    Path('results').mkdir(exist_ok=True)
    for f in out.glob('*'):
        if f.is_file() and f.suffix in ('.json', '.png', '.md'):
            shutil.copy(f, Path('results') / f'bench_{S["name"]}_{f.name}')
    print(f'teacher done in {R["seconds"] // 60} min -> {out}', flush=True)


def teacher_report(S, R, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    arms = list(R['arms'])
    L = [f'# Teacher experiment: {S["name"]}', '', S.get('description', ''), '',
         f'{R["generations"]} generations per arm, blocks of {R["block"]}. Time: {R["seconds"] // 60} min.', '',
         'Intelligence = skill on holdout worlds never trained in (' + ', '.join(R['holdout']) + '). '
         'Pool skill = skill across the training worlds (' + ', '.join(R['pool']) + ').', '',
         '## Yardstick over time', '', '| generation | ' + ' | '.join(f'{a} intelligence | {a} pool skill' for a in arms) + ' |',
         '|' + '---|' * (1 + 2 * len(arms))]
    gens = [t['gen'] for t in R['arms'][arms[0]]['tests']]
    for i, g in enumerate(gens):
        row = []
        for a in arms:
            t = R['arms'][a]['tests'][i] if i < len(R['arms'][a]['tests']) else None
            row += [f'{t["intelligence"]:.3f}', f'{t["pool_skill"]:.3f}'] if t else ['', '']
        L.append(f'| {g} | ' + ' | '.join(row) + ' |')
    if R['comparisons']:
        L += ['', '## Teacher vs the others (end, paired by seed)', '']
        for k, v in R['comparisons'].items():
            for m, p in v.items():
                L.append(f'- {k}, {m}: {p["mean_hunger"]:.3f} vs {p["mean_nohunger"]:.3f} '
                         f'(diff {p["mean_diff"]:+.3f}, teacher better in {p["hunger_wins"]}/{p["n"]} seeds, p = {p["p_value"]:.3g})')
    if 'teacher' in R['arms']:
        L += ['', '## Where the teacher sent the worms', '']
        cc = R['arms']['teacher'].get('choice_counts', {})
        L += [f'- {k}: {v} blocks' for k, v in cc.items()]
    L += ['', 'Chart: teacher.png']
    (out / 'summary.md').write_text('\n'.join(L))
    fig, axes = plt.subplots(1, 3, figsize=(18, 4.6))
    for a in arms:
        t = R['arms'][a]['tests']
        x = [q['gen'] for q in t]
        for ax, key in ((axes[0], 'intelligence'), (axes[1], 'pool_skill')):
            m = [q[key] for q in t]
            se = [np.std(q[f'{key}_per_seed']) / np.sqrt(len(q[f'{key}_per_seed'])) for q in t]
            ax.errorbar(x, m, yerr=[1.96 * s for s in se], marker='o', capsize=3, lw=2, label=a)
    axes[0].set_title('intelligence (holdout worlds, never trained in)'); axes[1].set_title('skill across the training worlds')
    for ax in axes[:2]:
        ax.set_xlabel('generation'); ax.grid(alpha=0.3); ax.legend()
    if 'teacher' in R['arms']:
        ch = R['arms']['teacher']['choices']
        idx = [R['pool'].index(c) for c in ch]
        xs = np.arange(len(ch)) * R['block'] + R['block']
        axes[2].scatter(xs, idx, c=R['arms']['teacher']['progress'], cmap='coolwarm', s=40)
        axes[2].set_yticks(range(len(R['pool'])), R['pool']); axes[2].set_xlabel('generation')
        axes[2].set_title("teacher's choice each block (colour = progress made)")
    fig.suptitle(f'Teacher experiment {S["name"]}')
    fig.tight_layout(); fig.savefig(out / 'teacher.png', dpi=110); plt.close(fig)
