"""C. elegans hermaphrodite connectome as an evolvable controller.

Data: python/data/celegans_herm_edgelist.csv = Cook et al. 2019 (Nature 571:63) whole-animal
connectome, as packaged by OpenWorm c302 (MIT License).

Model: a graded (non-spiking) rate network -- most C. elegans neurons use graded potentials.
    dv/dt = (-v + chemical input + gap-junction current + sensory input) / tau
    r     = tanh(max(v, 0))                                   (activity, 0..1)
Chemical synapse strength = log(1 + synapse count); GABAergic neurons inhibit.

Sensors (well-studied chemotaxis neurons):
    ASEL  ON  cell: excited when concentration rises
    ASER  OFF cell: excited when concentration falls
    AWCL/R OFF cells: excited when odor falls
    AWAL/R: excited by odor presence
Motor readout (an evolvable "decoder", like the trained decoder in the FlyGM fly-brain paper):
    reads 28 known locomotion neurons (AVA/AVB/AVD/AVE/PVC command interneurons, AIB/AIY/AIZ/
    RIA/RIM chemotaxis interneurons, SMD/RMD head motor neurons), each measured as its change
    from its own recent average, and turns them into:
    forward speed, reversal ("pirouette": back up, pick a new heading), and steering.

Missing data: the wiring lists WHICH neurons connect, not whether most synapses excite or
inhibit (only GABA neurons are marked). To keep the all-excitatory graph from running away:
    - each neuron's chemical input is normalized by its total incoming synapse count
    - a global inhibition term (stand-in for the unlabeled inhibitory synapses)
and evolution is allowed to set each synapse's sign and strength.

Genome:
    one gene m per chemical synapse: weight = base * (1 + m)
        m = 0  original strength,  m = -1  silenced,  m = -2  sign flipped
    + a few global gains (sensor gains, readout gains)
"""
import csv
import re
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / 'data' / 'celegans_herm_edgelist.csv'

# McIntire et al. 1993: GABAergic neurons
GABA = {'RMED', 'RMEV', 'RMEL', 'RMER', 'AVL', 'DVB', 'RIS'} | \
       {f'DD{i}' for i in range(1, 7)} | {f'VD{i}' for i in range(1, 14)}

SENSORS = {'on': ['ASEL'], 'off': ['ASER', 'AWCL', 'AWCR'], 'level': ['AWAL', 'AWAR']}
FWD, BWD = ['AVBL', 'AVBR'], ['AVAL', 'AVAR']
HEAD_D = [f'dBWM{s}{i}' for s in 'LR' for i in range(1, 7)]
HEAD_V = [f'vBWM{s}{i}' for s in 'LR' for i in range(1, 7)]
# Known locomotion / chemotaxis neurons that the motor decoder reads
READOUT = [n + s for n in ['AVA', 'AVB', 'AVD', 'AVE', 'PVC', 'AIB', 'AIY', 'AIZ', 'RIA', 'RIM']
           for s in 'LR'] + ['SMDDL', 'SMDDR', 'SMDVL', 'SMDVR', 'RMDDL', 'RMDDR', 'RMDVL', 'RMDVR']
N_OUT = 3                                   # speed, reversal, turn
N_GAINS = 3 + len(READOUT) * N_OUT + N_OUT  # sensor gains + decoder weights + decoder biases


def _is_neuron(s):
    return re.fullmatch(r'[A-Z][A-Z0-9]{1,5}', s) is not None


def _is_muscle(s):
    return re.fullmatch(r'[dv]BWM[LR]\d+', s) is not None


class Connectome:
    def __init__(self, path=DATA):
        rows = list(csv.DictReader(open(path)))
        for r in rows:
            r['Source'], r['Target'] = r['Source'].strip(), r['Target'].strip()
        keep = lambda s: _is_neuron(s) or _is_muscle(s)
        names = sorted({s for r in rows for s in (r['Source'], r['Target']) if keep(s)})
        self.names = names
        self.idx = {n: i for i, n in enumerate(names)}
        N = len(names)
        chem = [(self.idx[r['Source']], self.idx[r['Target']], float(r['Weight']))
                for r in rows if r['Type'] == 'chemical' and keep(r['Source']) and keep(r['Target'])]
        gap = [(self.idx[r['Source']], self.idx[r['Target']], float(r['Weight']))
               for r in rows if r['Type'] == 'electrical' and keep(r['Source']) and keep(r['Target'])]
        self.pre = np.array([c[0] for c in chem]); self.post = np.array([c[1] for c in chem])
        sign = np.array([-1.0 if names[p] in GABA else 1.0 for p in self.pre])
        self.w_chem = sign * np.log1p([c[2] for c in chem])
        G = np.zeros((N, N))
        for a, b, w in gap:
            G[a, b] = G[b, a] = max(G[a, b], np.log1p(w))
        self.G = G
        self.G_deg = G.sum(1)
        self.N = N
        self.n_edges = len(chem)
        in_abs = np.zeros(N); np.add.at(in_abs, self.post, np.abs(self.w_chem))
        in_abs[in_abs == 0] = 1.0
        self.w_norm = self.w_chem / in_abs[self.post]      # normalized by total input

    def ids(self, names):
        return np.array([self.idx[n] for n in names if n in self.idx])


def genome_size(conn: Connectome):
    return conn.n_edges + N_GAINS


def random_genomes(conn, P, rng, sigma=0.15):
    g = np.zeros((P, genome_size(conn)))
    g[:, :conn.n_edges] = rng.normal(0, sigma, (P, conn.n_edges))     # small wiring variation
    g[:, conn.n_edges:] = rng.normal(0, 0.3, (P, N_GAINS))
    g[:, conn.n_edges:conn.n_edges + 3] = np.log(3) + rng.normal(0, 0.2, (P, 3))   # sensor gains
    return g


class WormBrains:
    """P connectome brains simulated together (dense batched matrices, float32)."""
    chem_scale, gap_scale, inhibition, tau, dt = 1.2, 0.05, 0.5, 3.0, 1.0
    adapt = 0.05      # how fast each readout neuron's 'recent average' follows it

    def __init__(self, conn: Connectome, genomes):
        P, N = len(genomes), conn.N
        self.conn = conn
        mult = 1.0 + np.clip(genomes[:, :conn.n_edges], -3, 3)
        W = np.zeros((P, N, N), np.float32)
        np.add.at(W, (slice(None), conn.pre, conn.post), (conn.w_norm * mult * self.chem_scale).astype(np.float32))
        self.W = W
        self.G = (conn.G * self.gap_scale).astype(np.float32)
        self.G_deg = (conn.G_deg * self.gap_scale).astype(np.float32)
        gains = genomes[:, conn.n_edges:]
        self.g_on, self.g_off, self.g_lvl = [np.exp(np.clip(gains[:, i], -3, 3)) for i in range(3)]
        R = len(READOUT)
        self.D = gains[:, 3:3 + R * N_OUT].reshape(P, R, N_OUT) * 10.0
        self.d_bias = gains[:, 3 + R * N_OUT:3 + R * N_OUT + N_OUT]
        self.v = np.zeros((P, N), np.float32)
        self.rd = conn.ids(READOUT)
        self.rbar = None
        c = conn
        self.s_on, self.s_off, self.s_lvl = c.ids(SENSORS['on']), c.ids(SENSORS['off']), c.ids(SENSORS['level'])
        self.fwd, self.bwd = c.ids(FWD), c.ids(BWD)
        self.hd, self.hv = c.ids(HEAD_D), c.ids(HEAD_V)

    def step(self, smell, d_smell, energy_frac):
        v = self.v
        r = np.tanh(np.maximum(v, 0))
        I = np.einsum('pn,pnm->pm', r, self.W)
        I += v @ self.G - self.G_deg * v
        I -= self.inhibition * r.mean(1, keepdims=True)          # global inhibition
        I[:, self.s_on] += (self.g_on * np.maximum(d_smell, 0))[:, None]
        I[:, self.s_off] += (self.g_off * np.maximum(-d_smell, 0))[:, None]
        I[:, self.s_lvl] += (self.g_lvl * smell)[:, None]
        self.v = v + self.dt / self.tau * (-v + I)
        r = np.tanh(np.maximum(self.v, 0))
        x = r[:, self.rd]
        if self.rbar is None:
            self.rbar = x.copy()
        dev = x - self.rbar
        self.rbar += self.adapt * (x - self.rbar)
        o = np.einsum('pr,pro->po', dev, self.D) + self.d_bias
        speed_frac = 1.0 / (1.0 + np.exp(-(o[:, 0] + 1.0)))
        p_reverse = 1.0 / (1.0 + np.exp(-(o[:, 1] - 2.0))) * 0.3
        turn = np.tanh(o[:, 2]) * 0.4
        return p_reverse, speed_frac, turn


SILENT = -1.0   # weight x0 = synapse removed
FLIPPED = -2.0  # weight x(-1) = excitatory <-> inhibitory


def mutate_worm(parent, conn, cfg, rng):
    """Returns (child, events). events = list of (type, detail) so selection can be studied."""
    child = parent.copy()
    events = []
    E = conn.n_edges
    mask = rng.random(E) < cfg.worm_mutation_rate
    if mask.any():
        child[:E][mask] += rng.normal(0, cfg.mutation_sigma, mask.sum())
        events.append(('tweak', int(mask.sum())))
    gmask = rng.random(N_GAINS) < 0.1
    if gmask.any():
        child[E:E + N_GAINS][gmask] += rng.normal(0, cfg.mutation_sigma, gmask.sum())
        events.append(('gain', int(gmask.sum())))
    if rng.random() < cfg.p_silence:
        e = int(rng.integers(E)); child[e] = SILENT
        events.append(('silence', f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'))
    if rng.random() < cfg.p_restore:
        silent = np.flatnonzero(np.abs(child[:E] - SILENT) < 0.05)
        if len(silent):
            e = int(rng.choice(silent)); child[e] = 0.0
            events.append(('restore', f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'))
    if rng.random() < cfg.p_flip:
        e = int(rng.integers(E)); child[e] = FLIPPED
        events.append(('flip', f'{conn.names[conn.pre[e]]}->{conn.names[conn.post[e]]}'))
    if rng.random() < cfg.p_knockout:
        n = int(rng.integers(conn.N))
        out = np.flatnonzero(conn.pre == n)
        if len(out):
            child[out] = SILENT
            events.append(('knockout', conn.names[n]))
    return child, events
