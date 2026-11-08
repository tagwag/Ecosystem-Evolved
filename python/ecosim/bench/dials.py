"""Dials: everything a tester can set, addressed by a path string.

    cfg.<field>                 any world setting in config.Config (food_regrow_per_tick, predators, pred_speed, ...)
    world.<feature>.<field>     formula-world feature: a, b, scale, period, cost, gain  (see bench/formula.py)
    brain.gain.<target>         input multiplier for a neuron (ASHL), class (ASH) or layer (command)
    brain.knockout.<target>     1 = silenced, 0 = normal
    brain.clamp.<target>        1 = forced on, -1 = forced off, 0 = normal (whole lifetime)
    brain.mod.<modulator>       level of a modulator defined in [brain.modulators.<name>] (multiplies its targets' gain)
"""
import numpy as np

from .layers import resolve


def split(path):
    parts = path.split('.')
    if parts[0] == 'cfg' and len(parts) == 2:
        return 'cfg', parts[1], None
    if parts[0] == 'world' and len(parts) == 3:
        return 'world', parts[1], parts[2]
    if parts[0] == 'brain' and len(parts) == 3 and parts[1] in ('gain', 'knockout', 'clamp', 'mod'):
        return 'brain', parts[1], parts[2]
    raise ValueError(f'bad dial path {path!r} (see ecosim/bench/dials.py)')


def brain_rows(conn, brain_cfg, settings):
    """One brain setting -> (gain, keep, set) arrays (N,). brain_cfg = fixed [brain] table, settings = factor values
    {('gain'|'knockout'|'clamp'|'mod', target): value} for this combination."""
    N = conn.N
    gain, keep, st = np.ones(N), np.ones(N), np.zeros(N)
    fixed = dict(brain_cfg or {})
    items = []
    for t, v in (fixed.get('gain') or {}).items():
        items.append(('gain', t, v))
    for t in fixed.get('knockout') or []:
        items.append(('knockout', t, 1))
    mods = fixed.get('modulators') or {}
    for name, m in mods.items():
        items.append(('mod', name, m.get('level', 1.0)))
    for (kind, t), v in settings.items():
        items = [x for x in items if not (x[0] == kind and x[1] == t)] + [(kind, t, v)]
    for kind, t, v in items:
        if kind == 'gain':
            gain[resolve(conn, t)] *= v
        elif kind == 'mod':
            if t not in mods:
                raise ValueError(f'modulator {t!r} is not defined in [brain.modulators]')
            m = mods[t]
            gain[resolve(conn, m['targets'])] *= max(0.0, 1 + (m.get('effect', 1.0) - 1) * v)   # effect at level 1
        elif kind == 'knockout' and v:
            ids = resolve(conn, t); keep[ids] = 0; st[ids] = 0
        elif kind == 'clamp' and v:
            ids = resolve(conn, t); keep[ids] = 0; st[ids] = 2.0 if v > 0 else -1.0
    return gain, keep, st


def timed_clamp(conn, brain_cfg):
    """[brain.timed_clamp] targets / state ('on'|'off') / from_tick / to_tick -> (keep_w, set_w, window) or None."""
    tc = (brain_cfg or {}).get('timed_clamp')
    if not tc:
        return None
    keep, st = np.ones(conn.N), np.zeros(conn.N)
    ids = resolve(conn, tc['targets'])
    keep[ids] = 0; st[ids] = 2.0 if tc.get('state', 'on') == 'on' else -1.0
    return keep, st, (int(tc['from_tick']), int(tc['to_tick']))


def freeze_mask(conn, opts, targets):
    """Genome mask: synapse genes INTO the target neurons (and their hunger receptors) never mutate."""
    from ..worm2 import Layout
    L = Layout(conn, opts)
    m = np.zeros(L.size, bool)
    if targets:
        ids = np.array(resolve(conn, targets))
        m[:L.E] = np.isin(conn.post, ids)
        if opts.hunger:
            r = np.zeros(conn.N, bool); r[ids] = True
            m[L.rec] = r
    return m
