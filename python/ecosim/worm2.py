"""Step 3: worm brain with a hunger neuropeptide, a gut limit, and an optional open readout.

Kept separate from connectome.py so the Step 2 results stay reproducible.

New pieces
----------
Hunger peptide H (0..1, one per worm), a stand-in for real C. elegans feeding-state signals
(insulin / TGF-beta / serotonin). It is NOT a synapse: it is broadcast to every neuron at once
("volume transmission"):
    H drifts slowly toward (1 - energy / gut_cap)  -> rises as energy falls
    each meal drops H at once by meal_drop          -> a fast satiety signal
    input to neuron n  +=  H * receptor[n]          -> receptor[n] is an evolvable gene, starts at 0,
                                                       so the starting brain ignores H
Gut limit: a worm with energy >= gut_cap - food_value cannot eat (it is full). Without this,
eating is always worth it and resting can never pay off.

Decoder: reads each readout neuron two ways:
    change from its recent average (as in Step 2)  -> fast reactions, e.g. odor drops
    raw level                                        -> slow states, e.g. hunger
The raw-level reading is needed because the change-only decoder would erase any slow signal.

Readout set:
    'known' = the 28 locomotion/chemotaxis neurons used in Step 2
    'all'   = every neuron (no biology given; tests whether evolution finds AVA/AVB/AVD itself)

Fitness:
    'food'   = food eaten (+ survival tie-break), as in Steps 1-2
    'energy' = average energy held over the generation (0 while dead), in units of food
               -> rewards staying fed, not eating the most
"""
from dataclasses import dataclass

import numpy as np

from .connectome import (Connectome, READOUT, SENSORS, SILENT, FLIPPED, _is_neuron)
from .sim import TAU, max_speed
from .world import World

N_OUT = 3


@dataclass
class Opts:
    hunger: bool = True
    readout: str = 'known'        # 'known' | 'all'
    fitness: str = 'energy'       # 'energy' | 'food'
    gut_cap: float = 1500.0
    h_rate: float = 0.01          # how fast H follows the energy level (per tick)
    meal_drop: float = 0.25       # instant H drop per meal
    receptor_scale: float = 2.0


def readout_names(conn: Connectome, opts: Opts):
    if opts.readout == 'all':
        return [n for n in conn.names if _is_neuron(n)]
    return [n for n in READOUT if n in conn.idx]


class Layout:
    """Where each part lives in the flat genome."""
    def __init__(self, conn: Connectome, opts: Opts):
        self.E = conn.n_edges
        self.R = len(readout_names(conn, opts))
        i = self.E
        self.sens = slice(i, i + 3); i += 3
        self.dev = slice(i, i + self.R * N_OUT); i += self.R * N_OUT
        self.lvl = slice(i, i + self.R * N_OUT); i += self.R * N_OUT
        self.bias = slice(i, i + N_OUT); i += N_OUT
        self.rec = slice(i, i + (conn.N if opts.hunger else 0)); i += conn.N if opts.hunger else 0
        self.size = i


def random_genomes(conn, P, rng, opts: Opts):
    L = Layout(conn, opts)
    g = np.zeros((P, L.size))
    g[:, :L.E] = rng.normal(0, 0.15, (P, L.E))
    g[:, L.sens] = np.log(3) + rng.normal(0, 0.2, (P, 3))
    s = 0.3 * np.sqrt(28 / L.R)       # same total decoder strength whatever the readout size
    g[:, L.dev] = rng.normal(0, s, (P, L.R * N_OUT))
    g[:, L.bias] = rng.normal(0, 0.3, (P, N_OUT))
    # level decoder and receptors start at 0: the starting brain is the Step 2 brain
    return g


class WormBrains2:
    chem_scale, gap_scale, inhibition, tau, dt, adapt = 1.2, 0.05, 0.5, 3.0, 1.0, 0.05

    def __init__(self, conn: Connectome, genomes, opts: Opts):
        P, N = len(genomes), conn.N
        L = self.L = Layout(conn, opts)
        self.opts = opts
        mult = 1.0 + np.clip(genomes[:, :L.E], -3, 3)
        W = np.zeros((P, N, N), np.float32)
        np.add.at(W, (slice(None), conn.pre, conn.post), (conn.w_norm * mult * self.chem_scale).astype(np.float32))
        self.W = W
        self.G = (conn.G * self.gap_scale).astype(np.float32)
        self.G_deg = (conn.G_deg * self.gap_scale).astype(np.float32)
        sg = genomes[:, L.sens]
        self.g_on, self.g_off, self.g_lvl = [np.exp(np.clip(sg[:, i], -3, 3)) for i in range(3)]
        self.D = (genomes[:, L.dev].reshape(P, L.R, N_OUT) * 10.0).astype(np.float32)
        self.Dl = (genomes[:, L.lvl].reshape(P, L.R, N_OUT) * 3.0).astype(np.float32)
        self.d_bias = genomes[:, L.bias]
        self.rec = (genomes[:, L.rec] * opts.receptor_scale).astype(np.float32) if opts.hunger else None
        self.v = np.zeros((P, N), np.float32)
        self.rd = conn.ids(readout_names(conn, opts))
        self.rbar = np.zeros((P, len(self.rd)), np.float32)
        self.s_on, self.s_off, self.s_lvl = (conn.ids(SENSORS[k]) for k in ('on', 'off', 'level'))

    def step(self, smell, d_smell, H):
        v = self.v
        r = np.tanh(np.maximum(v, 0))
        I = np.einsum('pn,pnm->pm', r, self.W)
        I += v @ self.G - self.G_deg * v
        I -= self.inhibition * r.mean(1, keepdims=True)
        I[:, self.s_on] += (self.g_on * np.maximum(d_smell, 0))[:, None]
        I[:, self.s_off] += (self.g_off * np.maximum(-d_smell, 0))[:, None]
        I[:, self.s_lvl] += (self.g_lvl * smell)[:, None]
        if self.rec is not None:
            I += H[:, None].astype(np.float32) * self.rec          # the peptide: broadcast to all
        self.v = v + self.dt / self.tau * (-v + I)
        r = np.tanh(np.maximum(self.v, 0))
        x = r[:, self.rd]
        dev = x - self.rbar
        self.rbar += self.adapt * (x - self.rbar)
        o = np.einsum('pr,pro->po', dev, self.D) + np.einsum('pr,pro->po', x, self.Dl) + self.d_bias
        speed_frac = 1.0 / (1.0 + np.exp(-(o[:, 0] + 1.0)))
        p_reverse = 1.0 / (1.0 + np.exp(-(o[:, 1] - 2.0))) * 0.3
        turn = np.tanh(o[:, 2]) * 0.4
        return p_reverse, speed_frac, turn


def run_generation(cfg, genomes, rng, conn, opts: Opts, controller='worm', trace=None, hook=None):
    """controller: 'worm' or 'random' (random walk baseline).
    trace: optional dict; filled with per-tick arrays (speed, speed_frac, energy, H, alive).
           speed_frac is the brain's own speed command, before the body-size limit.
    hook: optional function(brains) called every tick (for readout analysis)."""
    P = genomes.shape[0]
    world = World(cfg, rng)
    pos = np.column_stack([rng.uniform(0, cfg.width, P), rng.uniform(0, cfg.height, P)])
    heading = rng.uniform(0, TAU, P)
    size = np.full(P, cfg.start_size)
    energy = np.full(P, cfg.start_energy)
    H = np.clip(1 - energy / opts.gut_cap, 0, 1)
    alive = np.ones(P, bool)
    eaten, lifetime, energy_sum = np.zeros(P), np.zeros(P), np.zeros(P)
    brains = WormBrains2(conn, genomes, opts) if controller == 'worm' else None
    prev_smell = world.smell_at(pos)
    if trace is not None:
        for k in ('speed', 'speed_frac', 'energy', 'H', 'alive'):
            trace[k] = []

    for t in range(cfg.ticks_per_generation):
        if t % cfg.smell_update_every == 0:
            world.update_smell()
        smell = world.smell_at(pos)
        d_smell = np.clip((smell - prev_smell) * 20.0, -1, 1)
        prev_smell = smell
        if brains is not None:
            p_tumble, speed_frac, turn = brains.step(smell, d_smell, H)
            if hook is not None:
                hook(brains)
        else:
            p_tumble, speed_frac, turn = np.full(P, 0.1), np.full(P, 0.7), 0.0
        tumble = rng.random(P) < p_tumble
        heading = np.where(tumble, rng.uniform(0, TAU, P), heading + np.clip(turn, -0.5, 0.5))
        speed = speed_frac * max_speed(cfg, size)
        step = np.column_stack([np.cos(heading), np.sin(heading)]) * speed[:, None]
        pos = np.where(alive[:, None], (pos + step) % [cfg.width, cfg.height], pos)

        energy -= np.where(alive, cfg.base_cost + cfg.move_cost * speed, 0.0)
        hungry_enough = energy < opts.gut_cap - cfg.food_value     # gut limit
        ate = world.eat(pos, alive & hungry_enough)
        energy += ate * cfg.food_value
        size += ate * cfg.size_per_food
        eaten += ate
        lifetime += alive
        energy_sum += np.where(alive, np.maximum(energy, 0), 0.0)
        target = np.clip(1 - energy / opts.gut_cap, 0, 1)
        H = np.clip(H + opts.h_rate * (target - H) - opts.meal_drop * ate, 0, 1)
        if trace is not None:
            trace['speed'].append(np.where(alive, speed, np.nan))
            trace['speed_frac'].append(np.where(alive, speed_frac, np.nan))
            trace['energy'].append(energy.copy()); trace['H'].append(H.copy()); trace['alive'].append(alive.copy())
        alive &= energy > 0
        world.regrow()
        if not alive.any():
            break

    T = cfg.ticks_per_generation
    if opts.fitness == 'energy':
        fitness = energy_sum / T / cfg.food_value
    else:
        fitness = eaten + lifetime / T
    if trace is not None:
        for k in trace:
            trace[k] = np.array(trace[k])
    return fitness, dict(mean_food=float(eaten.mean()), mean_energy=float((energy_sum / T).mean()),
                         fitness=float(fitness.mean()), survivors=int(alive.sum()), ticks=t + 1)


def mutate(parent, conn, cfg, rng, opts: Opts):
    """Step 2 structural mutations + mutation of decoder and hunger receptors."""
    L = Layout(conn, opts)
    child = parent.copy()
    ev = []
    E = L.E
    m = rng.random(E) < cfg.worm_mutation_rate
    if m.any():
        child[:E][m] += rng.normal(0, cfg.mutation_sigma, m.sum()); ev.append(('tweak', int(m.sum())))
    # decoder + sensor gains: about 8 genes per child, whatever the readout size
    head = np.r_[np.arange(L.sens.start, L.sens.stop), np.arange(L.dev.start, L.bias.stop)]
    m = rng.random(len(head)) < min(0.1, 8 / len(head))
    if m.any():
        child[head[m]] += rng.normal(0, cfg.mutation_sigma, m.sum()); ev.append(('gain', int(m.sum())))
    if opts.hunger:
        rec = np.arange(L.rec.start, L.rec.stop)
        m = rng.random(len(rec)) < 8 / len(rec)
        if m.any():
            child[rec[m]] += rng.normal(0, 0.3, m.sum()); ev.append(('receptor', int(m.sum())))
    if rng.random() < cfg.p_silence:
        child[int(rng.integers(E))] = SILENT; ev.append(('silence', ''))
    if rng.random() < cfg.p_restore:
        s = np.flatnonzero(np.abs(child[:E] - SILENT) < 0.05)
        if len(s):
            child[int(rng.choice(s))] = 0.0; ev.append(('restore', ''))
    if rng.random() < cfg.p_flip:
        child[int(rng.integers(E))] = FLIPPED; ev.append(('flip', ''))
    if rng.random() < cfg.p_knockout:
        out = np.flatnonzero(conn.pre == int(rng.integers(conn.N)))
        if len(out):
            child[out] = SILENT; ev.append(('knockout', ''))
    return child, ev
