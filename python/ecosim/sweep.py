"""Factor sweeps from config files: screen many world/worm factors cheaply, then zoom in on the ones that matter.

A sweep is a TOML file in python/sweeps/. It lists factors (each with a 'low' and a 'high' setting), a design
(fractional or full factorial), how hard to evolve, and how to measure. One command runs every arm, tests the
evolved brains, and writes effect charts. Finished arms are skipped, so an interrupted sweep resumes where it left.

    python -m ecosim.sweep plan    screen1          # print the design table + which effects are mixed up (aliases)
    python -m ecosim.sweep quick   screen1          # tiny CPU/GPU smoke test (2 arms, short worlds), throwaway output
    python -m ecosim.sweep run     screen1          # evolve every arm (resumes)
    python -m ecosim.sweep test    screen1          # fair tests of the final brains (own world + general battery)
    python -m ecosim.sweep analyze screen1          # main effects, p-values, charts -> results/sweep_screen1*
    python -m ecosim.sweep zoom    screen1 [--top 3]  # write sweeps/screen1_zoom.toml: full factorial of the top factors

Words:
  factor      one thing we change (predators, scarce food, mutation rate...), at two levels: low / high.
  arm (run)   one combination of levels. Every arm is evolved on the SAME seeds (paired comparison).
  main effect average result at 'high' minus average at 'low', over all arms (each seed separately, then tested).
  fractional factorial  only a chosen subset of the 2^k combinations. Cheaper, but some effects become ALIASES
              of each other (impossible to tell apart). Resolution IV: main effects are clean; two-factor
              interactions are mixed with other two-factor interactions. That's why we zoom in afterwards.
  general skill  the "intelligence" yardstick: a brain's fitness on a fixed battery of world types, minus what
              random brains get there. Same battery for every arm, so arms are comparable.
"""
import dataclasses
import itertools
import json
import sys
import time
import tomllib
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES

SWEEPS, RUNS, RES = Path('sweeps'), Path('runs/sweeps'), Path('results')


# ------------------------------------------------------------------ config + design
def load(name):
    p = Path(name) if name.endswith('.toml') else SWEEPS / f'{name}.toml'
    c = tomllib.loads(p.read_text())
    c.setdefault('name', p.stem)
    return c


def design(c):
    """(rows, letters): rows = list of {factor: -1/+1}. Letters A, B, C... follow the factor order in the file."""
    names = list(c['factors'])
    letters = [chr(65 + i) for i in range(len(names))]
    d = c.get('design', {})
    if d.get('type', 'full') == 'full':
        base = names
        cols = {n: None for n in names}
        gens = {}
    else:
        gens = {}
        for g in d['generators']:                      # e.g. "E=ABC": factor E = product of A, B and C
            lhs, rhs = g.replace(' ', '').split('=')
            gens[lhs] = rhs
        base = [n for n, L in zip(names, letters) if L not in gens]
    rows = []
    for levels in itertools.product([-1, 1], repeat=len(base)):
        r = dict(zip(base, levels))
        for L, rhs in gens.items():
            r[names[letters.index(L)]] = int(np.prod([r[names[letters.index(x)]] for x in rhs]))
        rows.append({n: r[n] for n in names})
    return rows, dict(zip(names, letters))


def aliases(rows, letters):
    """Which effects can't be told apart in this design. Returns (resolution, {effect: [aliases]}) for main
    effects and two-factor interactions (e.g. 'AB')."""
    names = list(letters)
    X = {letters[n]: np.array([r[n] for r in rows]) for n in names}
    for a, b in itertools.combinations(names, 2):
        X[letters[a] + letters[b]] = X[letters[a]] * X[letters[b]]
    for t in itertools.combinations(names, 3):
        X[''.join(letters[n] for n in t)] = np.prod([X[letters[n]] for n in t], 0)
    out = {}
    for k in [k for k in X if len(k) <= 2]:
        out[k] = [j for j in X if j != k and abs(int(X[j] @ X[k])) == len(rows)]
    res = 2 if any(len(k) == 1 and any(len(j) == 1 for j in v) for k, v in out.items()) else \
        3 if any(len(k) == 1 and any(len(j) == 2 for j in v) for k, v in out.items()) else \
        4 if any(len(k) == 2 and any(len(j) == 2 for j in v) for k, v in out.items()) else 5
    return res, out


def arm_settings(c, row):
    """Config overrides for one arm: base settings + each factor's low/high settings."""
    o = dict(c.get('base', {}).get('config', {}))
    for f, lvl in row.items():
        o.update(c['factors'][f]['high' if lvl > 0 else 'low'])
    return o


def opts_for(c):
    b = c.get('base', {})
    return dataclasses.replace(CONDITIONS[b.get('condition', 'hunger')], fitness=b.get('fitness', 'end'))


def register(c, quick=False):
    """Register every arm as a condition (name <sweep>_rNN) so evolve() can run it."""
    rows, _ = design(c)
    names = []
    for i, row in enumerate(rows):
        n = f"{c['name']}_r{i:02d}"
        CONDITIONS[n] = opts_for(c)
        o = arm_settings(c, row)
        if quick:
            o['ticks_per_generation'] = 100
        CFG_OVERRIDES[n] = o
        names.append(n)
    return rows, names


# ------------------------------------------------------------------ run
def run(c, quick=False, device='cuda'):
    from .batch3_fast import evolve
    rows, names = register(c, quick)
    r = c['run']
    seeds = r['seeds'] if not quick else r['seeds'][:2]
    gens, brains, W = (2, 4, 1) if quick else (r['generations'], r.get('brains', 16), r.get('worlds_per_gen', 1))
    out = RUNS / (c['name'] + ('_quick' if quick else ''))
    todo = [names[0], names[-1]] if quick else names   # quick: first + last arm (last uses most features)
    for n in todo:
        if all((out / f'{n}_s{s}' / 'best_genome.npy').exists() for s in seeds):
            print(f'{n}: already done, skipping', flush=True)
            continue
        t0 = time.perf_counter()
        evolve(n, seeds, gens, out=out, device=device, checkpoint_every=r.get('checkpoint_every', 0),
               clonal=r.get('clonal', 60), brains=brains, eval_worlds=W, quiet=False)
        dt = time.perf_counter() - t0
        print(f'{n}: done in {dt / 60:.1f} min ({dt / gens:.1f} s per generation)', flush=True)
        with open(out / 'timing.txt', 'a') as fh:
            fh.write(f'{n} {dt:.0f} s, {dt / gens:.2f} s/gen\n')


# ------------------------------------------------------------------ test
def score(opts, cfg_kwargs, genomes, worlds, conn, dev, chunk=32):
    """Each genome as a full group of clones on each world. Returns {metric: (n_genomes,)}."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    cfg = Config(**cfg_kwargs)
    P = cfg.worm_population
    out = {k: [] for k in ('fitness', 'food', 'bites')}
    for i in range(0, len(genomes), chunk):
        gs = genomes[i:i + chunk]
        pairs = [(j, wd) for j in range(len(gs)) for wd in worlds]
        G = np.stack([np.repeat(np.asarray(gs[j], np.float32)[None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        fit, st = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen).run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(worlds)
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        for k, key in (('food', 'mean_food'), ('bites', 'bites')):
            out[k] += np.array([x.get(key, np.nan) for x in st], float).reshape(len(gs), nw).mean(1).tolist()
    return {k: np.array(v) for k, v in out.items()}


def test(c, quick=False, device='cuda'):
    from .connectome import Connectome
    from .worm2 import random_genomes
    from .worm2_gpu import pick_device
    rows, names = register(c, quick)
    dev, conn = pick_device(device), Connectome()
    m, r = c['measure'], c['run']
    seeds = r['seeds'] if not quick else r['seeds'][:2]
    if quick:
        names, rows = [names[0], names[-1]], [rows[0], rows[-1]]
    out = RUNS / (c['name'] + ('_quick' if quick else ''))
    opts = opts_for(c)
    qk = dict(ticks_per_generation=100) if quick else {}
    own_w = m.get('own_worlds', list(range(4000, 4006)))
    bat_w = m.get('battery_worlds', list(range(5000, 5003)))
    if quick:
        own_w, bat_w = own_w[:1], bat_w[:1]
    battery = m['battery']                              # {world type: config overrides}
    base_cfg = dict(c.get('base', {}).get('config', {}))
    # random-brain baseline for each battery world type (what a brain with no evolution gets there)
    rand = random_genomes(conn, m.get('random_brains', 16) if not quick else 2, np.random.default_rng(99), opts)
    baseline = {b: float(score(opts, dict(base_cfg, **o, **qk), rand, bat_w, conn, dev)['fitness'].mean())
                for b, o in battery.items()}
    print('random-brain baseline:', {k: round(v, 3) for k, v in baseline.items()}, flush=True)
    res = dict(baseline=baseline, arms={})
    for i, n in enumerate(names):
        gs = [np.load(out / f'{n}_s{s}' / 'best_genome.npy') for s in seeds]
        own = score(opts, dict(CFG_OVERRIDES[n], **qk), gs, own_w, conn, dev)
        bat = {b: score(opts, dict(base_cfg, **o, **qk), gs, bat_w, conn, dev)['fitness'] - baseline[b]
               for b, o in battery.items()}
        general = np.mean([bat[b] for b in battery], 0)
        res['arms'][n] = dict(row=rows[i], own_fitness=own['fitness'].tolist(), own_food=own['food'].tolist(),
                              own_bites=own['bites'].tolist(),
                              battery={b: v.tolist() for b, v in bat.items()}, general_skill=general.tolist())
        print(f'{n}: own {own["fitness"].mean():.3f}  general skill {general.mean():+.3f}', flush=True)
    RES.mkdir(exist_ok=True)
    (RES / f"sweep_{c['name']}{'_quick' if quick else ''}_tests.json").write_text(json.dumps(res, indent=1))
    return res


# ------------------------------------------------------------------ analyze
def effects(res, factors, metric, battery_key=None):
    """Main effect of each factor, per seed (high-arms mean minus low-arms mean), tested over seeds."""
    from .step3d_analyze import paired
    arms = list(res['arms'].values())
    get = (lambda a: np.array(a['battery'][battery_key])) if battery_key else (lambda a: np.array(a[metric]))
    Y = np.stack([get(a) for a in arms])               # (arms, seeds)
    out = {}
    for f in factors:
        hi = Y[[a['row'][f] > 0 for a in arms]].mean(0)
        lo = Y[[a['row'][f] < 0 for a in arms]].mean(0)
        p = paired(hi, lo)
        out[f] = dict(effect=p['mean_diff'], ci95=p['ci95'], p=p['p_value'], seeds_up=p['hunger_wins'], n=p['n'],
                      mean_high=p['mean_hunger'], mean_low=p['mean_nohunger'])
    # Holm correction across factors (8 tests -> fewer false alarms)
    order = sorted(out, key=lambda f: out[f]['p'])
    k, prev = len(order), 0.0
    for i, f in enumerate(order):
        prev = max(prev, min(1.0, out[f]['p'] * (k - i)))
        out[f]['p_holm'] = prev
    return out


def analyze(c, quick=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tag = c['name'] + ('_quick' if quick else '')
    res = json.loads((RES / f'sweep_{tag}_tests.json').read_text())
    rows, letters = design(c)
    factors = list(c['factors'])
    resol, al = aliases(rows, letters)
    E = {'general_skill': effects(res, factors, 'general_skill'), 'own_fitness': effects(res, factors, 'own_fitness')}
    for b in c['measure']['battery']:
        E[f'battery:{b}'] = effects(res, factors, None, b)
    (RES / f'sweep_{tag}_effects.json').write_text(json.dumps(dict(resolution=resol, effects=E,
        aliases={f: al[letters[f]] for f in factors}, letters=letters), indent=1))
    # chart: main effects on general skill and own-world skill, biggest first
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.55 * len(factors) + 2))
    for ax, key, title in ((axes[0], 'general_skill', 'General skill (battery, minus random brains)'),
                           (axes[1], 'own_fitness', 'Own-world skill (each arm in its own world)')):
        e = E[key]
        fs = sorted(factors, key=lambda f: abs(e[f]['effect']))
        y = np.arange(len(fs))
        v = np.array([e[f]['effect'] for f in fs])
        lo = v - np.array([e[f]['ci95'][0] for f in fs]); hi = np.array([e[f]['ci95'][1] for f in fs]) - v
        col = ['#2b8a3e' if (e[f]['p_holm'] < 0.05 and x > 0) else '#c92a2a' if (e[f]['p_holm'] < 0.05) else '#adb5bd'
               for f, x in zip(fs, v)]
        ax.barh(y, v, xerr=[lo, hi], color=col, capsize=3)
        ax.set_yticks(y, [f"{f} ({letters[f]})" for f in fs])
        ax.axvline(0, color='k', lw=0.8)
        for yi, f in zip(y, fs):
            ax.text(ax.get_xlim()[1], yi, f"  p={e[f]['p_holm']:.3f}", va='center', fontsize=8)
        ax.set_title(title, fontsize=10); ax.set_xlabel('effect of switching low -> high (95% CI)')
    fig.suptitle(f"{c['name']}: main effects ({len(rows)} arms, {len(next(iter(res['arms'].values()))['general_skill'])} "
                 f"seeds, resolution {resol}). Green/red = significant after Holm correction", fontsize=10)
    fig.tight_layout(); fig.savefig(RES / f'sweep_{tag}_effects.png', dpi=130); plt.close(fig)
    # short readable summary
    g = E['general_skill']
    lines = [f"# Sweep {c['name']}: what changes general skill", '',
             f"{len(rows)} arms x {len(next(iter(res['arms'].values()))['general_skill'])} seeds. Design resolution {resol} "
             "(IV = main effects clean, two-factor interactions mixed with each other).", '',
             '| factor | letter | effect on general skill | 95% CI | seeds up | p (Holm) | effect on own-world skill |',
             '|---|---|---|---|---|---|---|']
    for f in sorted(factors, key=lambda f: -abs(g[f]['effect'])):
        o = E['own_fitness'][f]
        lines.append(f"| {f} | {letters[f]} | {g[f]['effect']:+.3f} | [{g[f]['ci95'][0]:+.3f}, {g[f]['ci95'][1]:+.3f}] | "
                     f"{g[f]['seeds_up']}/{g[f]['n']} | {g[f]['p_holm']:.3f} | {o['effect']:+.3f} (p {o['p_holm']:.3f}) |")
    lines += ['', 'Random-brain baseline per battery world: ' +
              ', '.join(f'{k} {v:.2f}' for k, v in res['baseline'].items()), '',
              'Two-factor interactions that are mixed up in this design (aliases):']
    seen = set()
    for k, v in al.items():
        if len(k) == 2 and k not in seen:
            grp = [k] + [j for j in v if len(j) == 2]
            seen.update(grp)
            lines.append(f"- {' = '.join(grp)}")
    (RES / f'sweep_{tag}.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return E


def zoom(c, top=3):
    """Write a full-factorial sweep of the `top` factors with the biggest general-skill effects, more seeds and
    generations. The other factors are held at their 'low' setting (edit the file to change that)."""
    tag = c['name']
    E = json.loads((RES / f'sweep_{tag}_effects.json').read_text())['effects']['general_skill']
    pick = sorted(E, key=lambda f: -abs(E[f]['effect']))[:top]
    held = [f for f in c['factors'] if f not in pick]
    q = lambda d: '{ ' + ', '.join(f'{k} = {json.dumps(v)}' for k, v in d.items()) + ' }'
    base_cfg = dict(c.get('base', {}).get('config', {}))
    for f in held:
        base_cfg.update(c['factors'][f]['low'])
    b = c.get('base', {})
    lines = [f'# Zoom-in on the top {top} factors of {tag} (generated by: python -m ecosim.sweep zoom {tag}).',
             f"# Held at low: {', '.join(held)}. Full factorial: every combination, so interactions are clean too.",
             f'name = "{tag}_zoom"', '', '[base]', f'condition = "{b.get("condition", "hunger")}"',
             f'fitness = "{b.get("fitness", "end")}"', f'config = {q(base_cfg)}', '', '[design]', 'type = "full"', '']
    for f in pick:
        lines += [f'[factors.{f}]', f"low = {q(c['factors'][f]['low'])}", f"high = {q(c['factors'][f]['high'])}", '']
    r = c['run']
    lines += ['[run]', f"seeds = {json.dumps(list(range(1, 17)))}", 'generations = 200', f"brains = {r.get('brains', 16)}",
              'worlds_per_gen = 2', 'clonal = 60', 'checkpoint_every = 20', '', '[measure]']
    m = c['measure']
    for k in ('own_worlds', 'battery_worlds', 'random_brains'):
        if k in m:
            lines.append(f'{k} = {json.dumps(m[k])}')
    lines += ['', '[measure.battery]'] + [f'{k} = {q(v)}' for k, v in m['battery'].items()]
    p = SWEEPS / f'{tag}_zoom.toml'
    p.write_text('\n'.join(lines) + '\n')
    print(f'wrote {p}: factors {pick}, {2 ** top} arms x 16 seeds x 200 gens')


def plan(c):
    rows, letters = design(c)
    resol, al = aliases(rows, letters)
    fs = list(c['factors'])
    print(f"{c['name']}: {len(rows)} arms, {len(fs)} factors, resolution {resol}")
    print('   ' + ' '.join(f'{letters[f]:>2}' for f in fs) + '   (' + ', '.join(f'{letters[f]}={f}' for f in fs) + ')')
    for i, r in enumerate(rows):
        print(f'r{i:02d} ' + ' '.join(' +' if r[f] > 0 else ' -' for f in fs))
    print('main-effect aliases (up to 3-way):', {letters[f]: al[letters[f]] for f in fs})
    r = c['run']
    print(f"run: {len(r['seeds'])} seeds x {r.get('brains', 16)} brains x {r.get('worlds_per_gen', 1)} world(s) x "
          f"{r['generations']} gens per arm")


if __name__ == '__main__':
    a = sys.argv[1:]
    cmd, cfg = a[0], load(a[1])
    dev = 'cpu' if '--cpu' in a else 'cuda'
    if cmd == 'plan':
        plan(cfg)
    elif cmd == 'quick':
        run(cfg, True, dev); test(cfg, True, dev); analyze(cfg, True)
    elif cmd == 'run':
        run(cfg, False, dev)
    elif cmd == 'test':
        test(cfg, False, dev)
    elif cmd == 'analyze':
        analyze(cfg)
    elif cmd == 'zoom':
        zoom(cfg, int(a[a.index('--top') + 1]) if '--top' in a else 3)
