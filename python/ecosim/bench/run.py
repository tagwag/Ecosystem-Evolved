"""Run a test-bench experiment from a settings file (TOML). See experiments/README.md.

    python -m ecosim.bench.run experiments/<name>.toml [--quick]

mode = "evolve"  world/brain dials -> evolution -> what changed in the brain, how good it got   (environment -> brain)
mode = "behave"  given brains + world/brain dials -> one lifetime -> what the worm does         (brain -> behaviour)
Every combination of the [[factor]] levels is run (full factorial design); then a quadratic is fitted to each
result (response surface) and its best point is reported. Output: runs/bench/<name>/ and results/bench_<name>_*.
"""
import dataclasses
import itertools
import json
import shutil
import sys
import time
import tomllib
from pathlib import Path

import numpy as np
import torch

from ..config import Config
from ..step3 import CONDITIONS
from . import dials as D
from .formula import feature_specs, FIELDS
from .layers import LAYERS, layer_of, resolve
from .surface import fit_all
from .traits import Tracker, battery_worlds, sense_groups

RES = Path('results')
TEST_WORLDS0 = 4000
BRAIN_KEYS = ('hunger', 'fitness', 'ash_alarm', 'gut_cap', 'receptor_scale')


def load(path, quick=False):
    S = tomllib.loads(Path(path).read_text())
    S.setdefault('name', Path(path).stem)
    S.setdefault('factor', [])
    if quick:
        ev = S.setdefault('evolve', {})
        ev.update(seeds=2, brains=4, worlds_per_generation=1, generations=2)
        S.setdefault('test', {})['worlds'] = 2
        bh = S.setdefault('behave', {})
        bh['worlds'] = 2; bh['clones'] = 10; bh['max_brains'] = 2
        for f in S['factor']:
            if 'levels' in f:
                f['levels'] = f['levels'][:2]
        S.setdefault('campaign', {}).update(zoom_rounds=1, ml_runs=2)
        S['name'] += '_quick'
    return S


def combos(S):
    names = [f['name'] for f in S['factor']]
    for p in names:
        D.split(p)
    levels = [f['levels'] for f in S['factor']]
    return names, [dict(zip(names, vals)) for vals in itertools.product(*levels)] if names else [{}]


def build(S, combo, conn):
    """One combination -> (opts, cfg overrides, feature specs, per-feature dial values, brain factor settings)."""
    base = dict(S.get('base', {}))
    brain_opts = {k: base.pop(k) for k in list(base) if k in BRAIN_KEYS}
    brain_opts.setdefault('fitness', 'end')
    opts = dataclasses.replace(CONDITIONS['hunger' if brain_opts.pop('hunger', True) else 'nohunger'], **brain_opts)
    specs = feature_specs((S.get('world') or {}).get('features'))
    vals = {sp['name']: {k: float(sp[k]) for k in FIELDS} for sp in specs}
    bset = {}
    for path, v in combo.items():
        kind, a, b = D.split(path)
        if kind == 'cfg':
            d0 = getattr(Config(), a)
            if isinstance(d0, bool):
                v = bool(round(v))
            elif isinstance(d0, int):
                v = int(round(v))
                if a in ('season_every', 'ticks_per_generation'):       # must be a multiple of the 10-tick block
                    v = int(round(v / 10)) * 10
            base[a] = v
        elif kind == 'world':
            if a not in vals:
                raise ValueError(f'factor {path}: feature {a!r} is not in [world.features]')
            vals[a][b] = float(v)
        else:
            bset[(a, b)] = v
    return opts, base, specs, vals, bset


def setup_fn(conn, S, specs, rows):
    """rows = list per world k of (feature dial values, brain factor settings). Returns setup(sim, cfg)."""
    def setup(sim, cfg):
        K, P = sim.K, sim.P
        rep = K // len(rows)                                     # rows repeat in blocks if K is a multiple
        if specs:
            pw = {k: np.array([[rows[i // rep][0][sp['name']][k] for sp in specs] for i in range(K)]) for k in FIELDS}
            sim.set_formula(specs, pw)
        sim.brain.enable_dials(K * P, conn.N)
        G, Kp, St = (np.stack([np.repeat(a[None], P, 0) for a in arrs]).reshape(K * P, -1)
                     for arrs in zip(*[D.brain_rows(conn, S.get('brain'), rows[i // rep][1]) for i in range(K)]))
        d = sim.brain.dials
        f = dict(dtype=torch.float32, device=sim.dev)
        d['gain'].copy_(torch.as_tensor(G, **f)); d['keep'].copy_(torch.as_tensor(Kp, **f)); d['set'].copy_(torch.as_tensor(St, **f))
        tc = D.timed_clamp(conn, S.get('brain'))
        if tc:
            d['keep_w'].copy_(torch.as_tensor(np.tile(tc[0], (K * P, 1)), **f))
            d['set_w'].copy_(torch.as_tensor(np.tile(tc[1], (K * P, 1)), **f))
            d['window'].copy_(torch.as_tensor(tc[2], device=sim.dev))
    return setup


def lifetime(conn, dev, opts, cfg_over, specs, rows, genomes, worlds, clones, extra_brain=None, seed=4242):
    """Each (row, genome) pair as `clones` clones on each test world. rows: list per (row) of (vals, bset).
    Returns stats list ordered (row, genome, world). Chunked to keep GPU memory small."""
    from ..batch3_fast import FastSim
    cfg = Config(**cfg_over)
    jobs = [(r, g, w) for r in range(len(rows)) for g in range(len(genomes)) for w in worlds]
    out = []
    chunk = max(1, 384 * 60 // clones)
    for i in range(0, len(jobs), chunk):
        J = jobs[i:i + chunk]
        G = np.stack([np.repeat(genomes[g][None], clones, 0) for _, g, _ in J]).astype(np.float32)
        gen = torch.Generator(device=dev); gen.manual_seed(seed)
        sim = FastSim(cfg, opts, conn, len(J), clones, dev, False, gen)
        jr = [rows[r] if extra_brain is None else (rows[r][0], {**rows[r][1], **extra_brain}) for r, _, _ in J]
        setup_fn(conn, {'brain': S_BRAIN[0]}, specs, jr)(sim, cfg)
        _, st = sim.run(G, [np.random.default_rng(w) for _, _, w in J])
        out += st
        del sim
        if dev.type == 'cuda':
            torch.cuda.empty_cache()
    return out


S_BRAIN = [None]          # the experiment's fixed [brain] table (set in main; used by lifetime)
METRICS = ('fitness', 'mean_food', 'bites', 'survivors', 'speed_full', 'speed_hungry', 'nn_dist')


def summarize(st, specs):
    import warnings; warnings.filterwarnings('ignore', 'Mean of empty slice')
    m = {k: float(np.nanmean([x[k] for x in st])) for k in METRICS}
    if specs:
        fe = np.nanmean([x['feature_exposure'] for x in st], 0)
        fc = np.nanmean([x['feature_cost'] for x in st], 0)
        for i, sp in enumerate(specs):
            m[f'exposure_{sp["name"]}'] = float(fe[i]); m[f'energy_lost_to_{sp["name"]}'] = float(fc[i])
    return m


def brain_change(g, conn, opts, lay):
    """How far each layer's incoming synapses moved from the original connectome strengths (mean |gene|)."""
    E = conn.n_edges
    post = lay[conn.post]
    return {L: float(np.abs(g[:E][post == L]).mean()) for L in LAYERS if (post == L).any()}


def measure_traits(S, conn, dev, opts, over, specs, vals, bset, start, best, tw, tr, per_seed):
    """Adds S/R/h2 per every-generation trait, intelligence (unseen-world battery) and sense importance,
    at the start and end, to each seed's metrics."""
    n = len(tw)
    fit_of = lambda st: [float(np.mean([x['fitness'] for x in st[j * n:(j + 1) * n]])) for j in range(len(best))]
    for j in range(len(best)):
        per_seed[j].update(tr.per_seed(j))
    bw = battery_worlds(over, specs, vals, S.get('battery'))
    groups = sense_groups(S.get('base', {}), specs)
    for which, G in (('start', start), ('end', best)):
        own = fit_of(lifetime(conn, dev, opts, over, specs, [(vals, bset)], G, tw, 60))
        intel = np.mean([fit_of(lifetime(conn, dev, opts, bo, bsp, [(bvv, bset)], G, tw, 60))
                         for _, bo, bsp, bvv in bw], 0) if bw else np.full(len(G), np.nan)
        imps = {name: np.array(own) - fit_of(lifetime(conn, dev, opts, over, specs,
                                                      [(vals, {**bset, ('knockout', tuple(ids)): 1})], G, tw, 60))
                for name, ids in groups.items()}
        for j in range(len(G)):
            per_seed[j][f'intelligence_{which}'] = float(intel[j])
            for name, v in imps.items():
                per_seed[j][f'sense_{name}_{which}'] = float(v[j])
    for p in per_seed:
        p['intelligence_gain'] = p['intelligence_end'] - p['intelligence_start']
        for name in groups:
            p[f'sense_{name}_gain'] = p[f'sense_{name}_end'] - p[f'sense_{name}_start']


def eval_combo(S, combo, ci, out, conn, dev, label=None):
    """Evolve under one combination of settings and measure everything. Used by run_evolve and the campaign."""
    from ..batch3_fast import evolve
    from ..step3 import CFG_OVERRIDES
    ev, te = S.get('evolve', {}), S.get('test', {})
    seeds = list(range(1, ev.get('seeds', 8) + 1))
    tw = list(range(TEST_WORLDS0, TEST_WORLDS0 + te.get('worlds', 12)))
    lay = layer_of(conn)
    t0 = time.time()
    opts, over, specs, vals, bset = build(S, combo, conn)
    cond = f'bench_{S["name"]}_{ci}'
    CONDITIONS[cond] = opts; CFG_OVERRIDES[cond] = over
    fz = D.freeze_mask(conn, opts, (S.get('brain') or {}).get('freeze'))
    init = None
    if ev.get('start', 'random') != 'random':
        src = Path(ev['start'])
        init = {s: np.load(sorted(src.glob(f'*_s{s}'))[0] / 'best_genome.npy') for s in seeds}
    print(f'[{label or ci + 1}] {combo}', flush=True)
    tr = Tracker(specs)
    hist, _ = evolve(cond, seeds, ev.get('generations', 100), out=out / 'brains', quiet=True,
                     checkpoint_every=ev.get('checkpoint_every', 0), clonal=60, brains=ev.get('brains', 16),
                     eval_worlds=ev.get('worlds_per_generation', 2), init=init, setup=setup_fn(conn, S, specs, [(vals, bset)]),
                     freeze=fz if fz.any() else None, on_gen=tr)
    best = [np.load(out / 'brains' / f'{cond}_s{s}' / 'best_genome.npy') for s in seeds]
    st = lifetime(conn, dev, opts, over, specs, [(vals, bset)], best, tw, 60)
    per_seed = [summarize(st[j * len(tw):(j + 1) * len(tw)], specs) for j in range(len(seeds))]
    imp = {}                      # layer importance: skill lost when a whole layer is silenced
    if ev.get('layer_knockouts', True):
        for L in ('sensory', 'inter1', 'inter2', 'command'):
            stk = lifetime(conn, dev, opts, over, specs, [(vals, {**bset, ('knockout', L): 1})], best, tw, 60)
            imp[L] = float(np.mean([x['fitness'] for x in st]) - np.mean([x['fitness'] for x in stk]))
    if ev.get('traits', True):
        start = [init[s] for s in seeds] if init else [tr.first_best[k] for k in range(len(seeds))]
        measure_traits(S, conn, dev, opts, over, specs, vals, bset, start, best, tw, tr, per_seed)
    bc = [brain_change(g, conn, opts, lay) for g in best]
    r = dict(combo=combo, metrics_per_seed=per_seed,
             metrics={k: float(np.nanmean([p[k] for p in per_seed])) for k in per_seed[0]},
             training_curve=np.mean([[h['fitness'] for h in hs] for hs in hist], 0).round(4).tolist(),
             brain_change={L: float(np.mean([b[L] for b in bc])) for L in bc[0]},
             layer_importance=imp, trait_curves=tr.curves(), seconds=round(time.time() - t0))
    print(f'   skill {r["metrics"]["fitness"]:.3f}  ({r["seconds"]} s)', flush=True)
    return r


def run_evolve(S, out, conn, dev):
    names, C = combos(S)
    return names, [eval_combo(S, combo, ci, out, conn, dev, f'{ci + 1}/{len(C)}') for ci, combo in enumerate(C)]


def run_behave(S, out, conn, dev):
    bh = S.get('behave', {})
    src = bh['brains']
    paths = sorted(Path(src).glob('**/best_genome.npy')) if Path(src).is_dir() else [Path(p) for p in src]
    paths = paths[:bh.get('max_brains', 16)]
    genomes = [np.load(p) for p in paths]
    names, C = combos(S)
    tw = list(range(TEST_WORLDS0, TEST_WORLDS0 + bh.get('worlds', 12)))
    groups = {}
    for ci, combo in enumerate(C):                      # combos that share the world settings run in one batch
        opts, over, specs, vals, bset = build(S, combo, conn)
        groups.setdefault(json.dumps(over, sort_keys=True), []).append((ci, combo, opts, over, specs, vals, bset))
    results = [None] * len(C)
    for gi, items in enumerate(groups.values()):
        opts, over, specs = items[0][2], items[0][3], items[0][4]
        print(f'batch {gi + 1}/{len(groups)}: {len(items)} combinations x {len(genomes)} brains x {len(tw)} worlds', flush=True)
        st = lifetime(conn, dev, opts, over, specs, [(it[5], it[6]) for it in items], genomes, tw, bh.get('clones', 60))
        n = len(genomes) * len(tw)
        for j, it in enumerate(items):
            block = st[j * n:(j + 1) * n]
            per = [summarize(block[b * len(tw):(b + 1) * len(tw)], specs) for b in range(len(genomes))]
            results[it[0]] = dict(combo=it[1], metrics_per_seed=per,
                                  metrics={k: float(np.mean([p[k] for p in per])) for k in per[0]})
    return names, results, [str(p) for p in paths]


def main(path, quick=False):
    from ..connectome import Connectome
    from ..worm2_gpu import pick_device
    from .report import report
    S = load(path, quick)
    S_BRAIN[0] = S.get('brain')
    out = Path('runs/bench') / S['name']
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / 'settings.json').write_text(json.dumps(S, indent=1))
    conn, dev = Connectome(), pick_device('cuda')
    t0 = time.time()
    mode = S.get('mode', 'evolve')
    print(f'experiment {S["name"]}: mode={mode}' + ('' if mode == 'campaign' else f', {len(combos(S)[1])} combinations'), flush=True)
    if mode == 'campaign':
        from .campaign import run_campaign
        run_campaign(S, out, conn, dev)
        return
    if mode == 'evolve':
        names, results = run_evolve(S, out, conn, dev); brains = None
    else:
        names, results, brains = run_behave(S, out, conn, dev)
    fits = fit_all(names, results, S['factor'])
    R = dict(name=S['name'], mode=mode, factors=S['factor'], results=results, surface=fits, brains=brains,
             seconds=round(time.time() - t0), description=S.get('description', ''))
    (out / 'results.json').write_text(json.dumps(R, indent=1))
    report(R, out)
    RES.mkdir(exist_ok=True)
    for f in out.glob('*'):
        if f.is_file() and f.suffix in ('.json', '.png', '.md'):
            shutil.copy(f, RES / f'bench_{S["name"]}_{f.name}')
    print(f'done in {R["seconds"]} s -> {out}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], '--quick' in sys.argv)
