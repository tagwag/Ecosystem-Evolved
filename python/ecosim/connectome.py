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
Motor readout:
    forward speed  <- AVB (forward command) minus AVA (backward command)
    reversal/turn  <- AVA over AVB  (a "pirouette": reverse then pick a new heading)
    steering       <- dorsal minus ventral head muscles (the worm crawls on its side,
                      so dorsal/ventral bending = left/right on the plate)

Genome:
    one log-multiplier per chemical synapse  (evolution can strengthen/weaken/silence wiring)
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

N_GAINS = 6   # on-gain, off-gain, level-gain, speed-gain, reversal-bias, steer-gain


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

    def ids(self, names):
        return np.array([self.idx[n] for n in names if n in self.idx])


def genome_size(conn: Connectome):
    return conn.n_edges + N_GAINS


def random_genomes(conn, P, rng, sigma=0.3):
    g = np.zeros((P, genome_size(conn)))
    g[:, :conn.n_edges] = rng.normal(0, sigma, (P, conn.n_edges))     # small wiring variation
    g[:, conn.n_edges:] = rng.normal(0, 0.3, (P, N_GAINS))
    return g


class WormBrains:
    """P connectome brains simulated together (dense batched matrices, float32)."""
    chem_scale, gap_scale, tau, dt = 0.15, 0.05, 3.0, 1.0

    def __init__(self, conn: Connectome, genomes):
        P, N = len(genomes), conn.N
        self.conn = conn
        mult = np.exp(np.clip(genomes[:, :conn.n_edges], -6, 3))
        W = np.zeros((P, N, N), np.float32)
        np.add.at(W, (slice(None), conn.pre, conn.post), (conn.w_chem * mult * self.chem_scale).astype(np.float32))
        self.W = W
        self.G = (conn.G * self.gap_scale).astype(np.float32)
        self.G_deg = (conn.G_deg * self.gap_scale).astype(np.float32)
        gains = genomes[:, conn.n_edges:]
        self.g_on, self.g_off, self.g_lvl = [np.exp(gains[:, i]) * 2.0 for i in range(3)]
        self.g_speed = np.exp(gains[:, 3]) * 3.0
        self.rev_bias = gains[:, 4] - 1.0
        self.g_steer = gains[:, 5] * 2.0
        self.v = np.zeros((P, N), np.float32)
        c = conn
        self.s_on, self.s_off, self.s_lvl = c.ids(SENSORS['on']), c.ids(SENSORS['off']), c.ids(SENSORS['level'])
        self.fwd, self.bwd = c.ids(FWD), c.ids(BWD)
        self.hd, self.hv = c.ids(HEAD_D), c.ids(HEAD_V)

    def step(self, smell, d_smell, energy_frac):
        v = self.v
        r = np.tanh(np.maximum(v, 0))
        I = np.einsum('pn,pnm->pm', r, self.W)
        I += v @ self.G - self.G_deg * v
        I[:, self.s_on] += (self.g_on * np.maximum(d_smell, 0))[:, None]
        I[:, self.s_off] += (self.g_off * np.maximum(-d_smell, 0))[:, None]
        I[:, self.s_lvl] += (self.g_lvl * smell)[:, None]
        self.v = v + self.dt / self.tau * (-v + I)
        r = np.tanh(np.maximum(self.v, 0))
        fwd, bwd = r[:, self.fwd].mean(1), r[:, self.bwd].mean(1)
        speed_frac = 1.0 / (1.0 + np.exp(-self.g_speed * (fwd - bwd)))
        p_reverse = 1.0 / (1.0 + np.exp(-(8.0 * (bwd - fwd) + self.rev_bias))) * 0.2
        turn = self.g_steer * (r[:, self.hd].mean(1) - r[:, self.hv].mean(1))
        return p_reverse, speed_frac, turn
