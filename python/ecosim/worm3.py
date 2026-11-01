"""Step 4: brain growth (structural neuroevolution) on the worm connectome.

Each brain has the 300 real neurons + 95 muscles, plus K empty "slots" that new neurons can fill.
Growth mutations:
    duplicate   copy neuron i into a free slot: same inputs, same sensor input, and i's outputs and
                readout weights are split half/half between i and its copy -> at first the brain behaves
                almost the same (near-neutral), then the two copies can drift apart.
                Real nervous systems grew this way (gene duplication, then divergence).
    new_neuron  a blank neuron in a free slot with 3 weak inputs and 3 weak outputs (near-neutral)
    new_synapse a weak connection between two neurons that were not connected
Everything from Steps 2-3 stays: tweak / silence / restore / flip / knockout on the original synapses.

A slot's genes:
    act        1 = neuron exists
    src        index of the neuron it was copied from (-1 = blank new neuron)
    sin[k, j]  weight from neuron j into slot k
    sout[k, j] weight from slot k to neuron j
    sdec       its readout (decoder) weights: every grown neuron can affect behaviour
Added synapses between existing neurons: a list of (pre, post, weight).

growth=False gives the identical model with growth switched off (the control).
"""
from dataclasses import dataclass

import numpy as np

from .connectome import Connectome, READOUT, SENSORS, SILENT, FLIPPED, _is_neuron
from .sim import TAU, max_speed
from .world import World

N_OUT = 3


@dataclass
class Opts3:
    growth: bool = True
    slots: int = 50              # cap on grown neurons
    max_added: int = 150         # cap on added synapses
    p_duplicate: float = 0.06
    p_new_neuron: float = 0.03
    p_new_synapse: float = 0.25
    weak: float = 0.05           # starting weight of new connections
    gain_genes: float = 8.0      # expected decoder/gain genes mutated per child (0 = none, for tests)


class Layout3:
    def __init__(self, conn: Connectome, o: Opts3):
        self.N, self.K, self.M = conn.N, o.slots, o.max_added
        self.Nt = self.N + self.K
        self.E = conn.n_edges
        self.R = len([n for n in READOUT if n in conn.idx])
        i = self.E
        def take(n):
            nonlocal i
            s = slice(i, i + n); i += n; return s
        self.sens = take(3)
        self.dev = take(self.R * N_OUT)
        self.lvl = take(self.R * N_OUT)
        self.bias = take(N_OUT)
        self.act = take(self.K)
        self.src = take(self.K)
        self.sin = take(self.K * self.Nt)
        self.sout = take(self.K * self.Nt)
        self.sdev = take(self.K * N_OUT)
        self.slvl = take(self.K * N_OUT)
        self.add = take(self.M * 3)
        self.size = i


def random_genomes(conn, P, rng, o: Opts3):
    L = Layout3(conn, o)
    g = np.zeros((P, L.size))
    g[:, :L.E] = rng.normal(0, 0.15, (P, L.E))
    g[:, L.sens] = np.log(3) + rng.normal(0, 0.2, (P, 3))
    g[:, L.dev] = rng.normal(0, 0.3, (P, L.R * N_OUT))
    g[:, L.bias] = rng.normal(0, 0.3, (P, N_OUT))
    g[:, L.src] = -1
    return g


class GrowBrains:
    chem_scale, gap_scale, inhibition, tau, dt, adapt = 1.2, 0.05, 0.5, 3.0, 1.0, 0.05

    def __init__(self, conn: Connectome, genomes, o: Opts3):
        P, N = len(genomes), conn.N
        L = self.L = Layout3(conn, o)
        K, Nt = L.K, L.Nt
        mult = 1.0 + np.clip(genomes[:, :L.E], -3, 3)
        W = np.zeros((P, Nt, Nt), np.float32)
        np.add.at(W, (slice(None), conn.pre, conn.post), (conn.w_norm * mult * self.chem_scale).astype(np.float32))
        act = genomes[:, L.act] > 0.5                                       # P x K
        sin = genomes[:, L.sin].reshape(P, K, Nt) * act[:, :, None]
        sout = genomes[:, L.sout].reshape(P, K, Nt) * act[:, :, None]
        W[:, :, N:] += np.transpose(sin, (0, 2, 1)).astype(np.float32)     # j -> slot k
        W[:, N:, :] += sout.astype(np.float32)                              # slot k -> j
        add = genomes[:, L.add].reshape(P, L.M, 3)
        for p in range(P):
            used = add[p, :, 2] != 0
            if used.any():
                np.add.at(W[p], (add[p, used, 0].astype(int), add[p, used, 1].astype(int)), add[p, used, 2].astype(np.float32))
        self.W = W
        G = np.zeros((Nt, Nt), np.float32); G[:N, :N] = conn.G * self.gap_scale
        self.G, self.G_deg = G, G.sum(1)
        sg = genomes[:, L.sens]
        self.g_on, self.g_off, self.g_lvl = [np.exp(np.clip(sg[:, i], -3, 3)) for i in range(3)]
        self.D = (genomes[:, L.dev].reshape(P, L.R, N_OUT) * 10.0).astype(np.float32)
        self.Dl = (genomes[:, L.lvl].reshape(P, L.R, N_OUT) * 3.0).astype(np.float32)
        self.SD = (genomes[:, L.sdev].reshape(P, K, N_OUT) * 10.0 * act[:, :, None]).astype(np.float32)
        self.SDl = (genomes[:, L.slvl].reshape(P, K, N_OUT) * 3.0 * act[:, :, None]).astype(np.float32)
        self.d_bias = genomes[:, L.bias]
        self.n_active = N + act.sum(1)
        self.N, self.K = N, K
        self.v = np.zeros((P, Nt), np.float32)
        self.rd = conn.ids([n for n in READOUT if n in conn.idx])
        self.rbar = np.zeros((P, len(self.rd)), np.float32)
        self.sbar = np.zeros((P, K), np.float32)
        self.s_on, self.s_off, self.s_lvl = (conn.ids(SENSORS[k]) for k in ('on', 'off', 'level'))
        src = genomes[:, L.src].round().astype(int) * act - (~act)                 # -1 if inactive
        self.m_on = np.isin(src, self.s_on).astype(np.float32)                     # duplicates of sensors
        self.m_off = np.isin(src, self.s_off).astype(np.float32)                   # also sense
        self.m_lvl = np.isin(src, self.s_lvl).astype(np.float32)

    def step(self, smell, d_smell, H=None):
        v, N = self.v, self.N
        r = np.tanh(np.maximum(v, 0))
        I = np.einsum('pn,pnm->pm', r, self.W)
        I += v @ self.G - self.G_deg * v
        I -= self.inhibition * (r.sum(1) / self.n_active)[:, None]
        on, off, lvl = self.g_on * np.maximum(d_smell, 0), self.g_off * np.maximum(-d_smell, 0), self.g_lvl * smell
        I[:, self.s_on] += on[:, None]; I[:, self.s_off] += off[:, None]; I[:, self.s_lvl] += lvl[:, None]
        I[:, N:] += self.m_on * on[:, None] + self.m_off * off[:, None] + self.m_lvl * lvl[:, None]
        self.v = v + self.dt / self.tau * (-v + I)
        r = np.tanh(np.maximum(self.v, 0))
        x, xs = r[:, self.rd], r[:, N:]
        dev, devs = x - self.rbar, xs - self.sbar
        self.rbar += self.adapt * (x - self.rbar); self.sbar += self.adapt * (xs - self.sbar)
        o = (np.einsum('pr,pro->po', dev, self.D) + np.einsum('pr,pro->po', x, self.Dl)
             + np.einsum('pk,pko->po', devs, self.SD) + np.einsum('pk,pko->po', xs, self.SDl) + self.d_bias)
        speed_frac = 1.0 / (1.0 + np.exp(-(o[:, 0] + 1.0)))
        p_reverse = 1.0 / (1.0 + np.exp(-(o[:, 1] - 2.0))) * 0.3
        turn = np.tanh(o[:, 2]) * 0.4
        return p_reverse, speed_frac, turn


def run_generation(cfg, genomes, rng, conn, o: Opts3, controller='worm', trace=None):
    """Food fitness, as in Step 2. trace: optional dict of per-tick speed_frac, reversals, turn."""
    P = genomes.shape[0]
    world = World(cfg, rng)
    pos = np.column_stack([rng.uniform(0, cfg.width, P), rng.uniform(0, cfg.height, P)])
    heading = rng.uniform(0, TAU, P)
    size = np.full(P, cfg.start_size)
    energy = np.full(P, cfg.start_energy)
    alive = np.ones(P, bool)
    eaten, lifetime = np.zeros(P), np.zeros(P)
    brains = GrowBrains(conn, genomes, o) if controller == 'worm' else None
    prev_smell = world.smell_at(pos)
    if trace is not None:
        for k in ('speed_frac', 'reverse', 'turn', 'alive'):
            trace[k] = []
    for t in range(cfg.ticks_per_generation):
        if t % cfg.smell_update_every == 0:
            world.update_smell()
        smell = world.smell_at(pos)
        d_smell = np.clip((smell - prev_smell) * 20.0, -1, 1)
        prev_smell = smell
        if brains is not None:
            p_tumble, speed_frac, turn = brains.step(smell, d_smell)
        else:
            p_tumble, speed_frac, turn = np.full(P, 0.1), np.full(P, 0.7), np.zeros(P)
        tumble = rng.random(P) < p_tumble
        heading = np.where(tumble, rng.uniform(0, TAU, P), heading + np.clip(turn, -0.5, 0.5))
        speed = speed_frac * max_speed(cfg, size)
        step = np.column_stack([np.cos(heading), np.sin(heading)]) * speed[:, None]
        pos = np.where(alive[:, None], (pos + step) % [cfg.width, cfg.height], pos)
        energy -= np.where(alive, cfg.base_cost + cfg.move_cost * speed, 0.0)
        ate = world.eat(pos, alive)
        energy += ate * cfg.food_value
        size += ate * cfg.size_per_food
        eaten += ate
        lifetime += alive
        if trace is not None:
            trace['speed_frac'].append(np.where(alive, speed_frac, np.nan))
            trace['reverse'].append(np.where(alive, tumble, np.nan))
            trace['turn'].append(np.where(alive, np.abs(turn), np.nan))
            trace['alive'].append(alive.copy())
        alive &= energy > 0
        world.regrow()
        if not alive.any():
            break
    if trace is not None:
        for k in trace:
            trace[k] = np.array(trace[k])
    fitness = eaten + lifetime / cfg.ticks_per_generation
    return fitness, dict(mean_food=float(eaten.mean()), survivors=int(alive.sum()), ticks=t + 1)


# ---------------- mutation ----------------

def _incoming(child, conn, L, i):
    """Current weights into neuron i (vector over all Nt neurons)."""
    v = np.zeros(L.Nt)
    e = np.flatnonzero(conn.post == i)
    v[conn.pre[e]] += conn.w_norm[e] * (1 + np.clip(child[e], -3, 3)) * GrowBrains.chem_scale
    act = child[L.act] > 0.5
    v[L.N:] += child[L.sout].reshape(L.K, L.Nt)[:, i] * act
    if i >= L.N:
        v += child[L.sin].reshape(L.K, L.Nt)[i - L.N]
    return v


def _scale_outgoing(child, conn, L, i, f):
    """Multiply every outgoing weight of neuron i by f, returning the weights before scaling."""
    out = np.zeros(L.Nt)
    if i < L.N:
        e = np.flatnonzero(conn.pre == i)
        w = conn.w_norm[e] * (1 + np.clip(child[e], -3, 3)) * GrowBrains.chem_scale
        out[conn.post[e]] += w
        silent = np.abs(child[e] - SILENT) < 1e-6
        child[e] = np.where(silent, child[e], (1 + np.clip(child[e], -3, 3)) * f - 1)
        sin = child[L.sin].reshape(L.K, L.Nt)
        out[L.N:] += sin[:, i]
        sin[:, i] *= f
        child[L.sin] = sin.ravel()
    else:
        k = i - L.N
        sout = child[L.sout].reshape(L.K, L.Nt)
        out += sout[k]
        sout[k] *= f
        child[L.sout] = sout.ravel()
    return out


def _free_slot(child, L):
    free = np.flatnonzero(child[L.act] <= 0.5)
    return int(free[0]) if len(free) else None


def mutate(parent, conn, cfg, rng, o: Opts3, names):
    """Step 2 mutations + growth. names = list of all Nt names (for logging)."""
    L = Layout3(conn, o)
    child = parent.copy()
    ev = []
    E = L.E
    m = rng.random(E) < cfg.worm_mutation_rate
    if m.any():
        child[:E][m] += rng.normal(0, cfg.mutation_sigma, m.sum()); ev.append(('tweak', int(m.sum())))
    head = np.r_[np.arange(L.sens.start, L.bias.stop)]
    act = child[L.act] > 0.5
    if act.any():   # grown neurons' decoder weights are mutable too
        sd = np.arange(L.sdev.start, L.slvl.stop).reshape(2, L.K, N_OUT)[:, act].ravel()
        head = np.r_[head, sd]
    m = rng.random(len(head)) < min(0.1, o.gain_genes / len(head))
    if m.any():
        child[head[m]] += rng.normal(0, cfg.mutation_sigma, m.sum()); ev.append(('gain', int(m.sum())))
    # tweak existing connections of grown neurons (multiplicative, keeps zeros at zero)
    if act.any():
        for blk in (L.sin, L.sout):
            a = child[blk].reshape(L.K, L.Nt)
            nz = np.argwhere((a != 0) & act[:, None])
            if len(nz):
                pick = nz[rng.random(len(nz)) < cfg.worm_mutation_rate * 2]
                if len(pick):
                    a[pick[:, 0], pick[:, 1]] *= np.exp(rng.normal(0, cfg.mutation_sigma, len(pick)))
                    child[blk] = a.ravel()
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
    if not o.growth:
        return child, ev

    neurons = [i for i in range(L.N) if _is_neuron(conn.names[i])]
    # ---- duplicate a neuron ----
    if rng.random() < o.p_duplicate:
        k = _free_slot(child, L)
        if k is not None:
            live = neurons + [L.N + j for j in np.flatnonzero(child[L.act] > 0.5)]
            i = int(rng.choice(live))
            inc = _incoming(child, conn, L, i)
            out = _scale_outgoing(child, conn, L, i, 0.5)          # i keeps half of its outputs
            noise = lambda v: v * np.exp(rng.normal(0, 0.05, v.shape))
            sin = child[L.sin].reshape(L.K, L.Nt); sout = child[L.sout].reshape(L.K, L.Nt)
            sin[k] = noise(inc); sout[k] = noise(out * 0.5)        # copy gets the other half
            child[L.sin] = sin.ravel(); child[L.sout] = sout.ravel()
            # split readout weights the same way, if i is read out
            sdev = child[L.sdev].reshape(L.K, N_OUT); slvl = child[L.slvl].reshape(L.K, N_OUT)
            if i < L.N:
                ri = np.flatnonzero(np.array([conn.idx[n] for n in READOUT if n in conn.idx]) == i)
                if len(ri):
                    dev = child[L.dev].reshape(L.R, N_OUT); lvl = child[L.lvl].reshape(L.R, N_OUT)
                    dev[ri[0]] *= 0.5; lvl[ri[0]] *= 0.5
                    sdev[k] = dev[ri[0]]; slvl[k] = lvl[ri[0]]
                    child[L.dev] = dev.ravel(); child[L.lvl] = lvl.ravel()
                else:
                    sdev[k] = 0; slvl[k] = 0
            else:
                j = i - L.N
                sdev[j] *= 0.5; slvl[j] *= 0.5
                sdev[k] = sdev[j]; slvl[k] = slvl[j]
            child[L.sdev] = sdev.ravel(); child[L.slvl] = slvl.ravel()
            src = i if i < L.N else int(round(child[L.src][i - L.N]))
            child[L.act.start + k] = 1.0
            child[L.src.start + k] = src
            ev.append(('duplicate', names[src] if src >= 0 else 'new'))
    # ---- blank new neuron ----
    if rng.random() < o.p_new_neuron:
        k = _free_slot(child, L)
        if k is not None:
            sin = child[L.sin].reshape(L.K, L.Nt); sout = child[L.sout].reshape(L.K, L.Nt)
            sin[k] = 0; sout[k] = 0
            sin[k, rng.choice(neurons, 3, replace=False)] = o.weak
            sout[k, rng.choice(neurons, 3, replace=False)] = o.weak * rng.choice([-1, 1], 3)
            child[L.sin] = sin.ravel(); child[L.sout] = sout.ravel()
            child[L.sdev.start + k * N_OUT: L.sdev.start + (k + 1) * N_OUT] = rng.normal(0, 0.05, N_OUT)
            child[L.act.start + k] = 1.0
            child[L.src.start + k] = -1
            ev.append(('new_neuron', ''))
    # ---- new synapse ----
    if rng.random() < o.p_new_synapse:
        add = child[L.add].reshape(L.M, 3)
        free = np.flatnonzero(add[:, 2] == 0)
        if len(free):
            live = neurons + [L.N + j for j in np.flatnonzero(child[L.act] > 0.5)]
            a, b = rng.choice(live, 2, replace=False)
            add[free[0]] = (a, b, o.weak * rng.choice([-1, 1]))
            child[L.add] = add.ravel()
            ev.append(('new_synapse', f'{names[a]}->{names[b]}'))
    # added synapses can strengthen or weaken over time
    add = child[L.add].reshape(L.M, 3)
    used = np.flatnonzero(add[:, 2] != 0)
    if len(used):
        pick = used[rng.random(len(used)) < 0.1]
        add[pick, 2] *= np.exp(rng.normal(0, 0.3, len(pick)))
        child[L.add] = add.ravel()
    return child, ev


def all_names(conn, o: Opts3):
    return list(conn.names) + [f'NEW{k}' for k in range(o.slots)]


def n_grown(genome, conn, o: Opts3):
    L = Layout3(conn, o)
    return int((genome[L.act] > 0.5).sum()), int((genome[L.add].reshape(L.M, 3)[:, 2] != 0).sum())
