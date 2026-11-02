"""Step 5: lifetime learning ladder on the worm connectome.

World: TWO odors. One comes from food patches, the other from decoy patches (no food).
Which odor means food is flipped at random in every world, so evolution cannot hard-wire
"follow odor A": only a worm that learns during its life can tell which odor pays.

Sensors (a modeling choice, not exact biology):
    odor A: level -> AWAL/AWAR,  rising -> ASEL,  falling -> ASER
    odor B: level -> AWCL/AWCR,  rising -> AWBL,  falling -> AWBR

Brain = the Step 3 worm brain (Cook 2019 wiring, 28-neuron decoder reading change + level) plus a
PLASTIC weight on every chemical synapse, Wp (starts at 0 every life, so nothing learned is inherited).

Ladder (each level adds one thing; all strengths are genes, so evolution can switch them off):
    fixed      Wp stays 0 (Steps 2-4 brain)
    hebb       lifetime learning: Wp += eta_h * pre * post                    (Hebbian)
    dopamine   + reward: eligibility trace e = lam*e + pre*post; Wp += eta_r * R * e,
               R = 1 on each meal                                             (three-factor learning)
    curiosity  + intrinsic reward: R += c * surprise, surprise = how much the odor change
               differs from its recent average                                (intrinsic motivation)
    sleep      + every 300 ticks: Wp *= (1 - s), traces cleared               (synaptic downscaling)
               Instant, no lost foraging time, so it tests only the "reset".
Branch off the ladder (user's idea):
    sprint_rest  dopamine level + shaped rewards (no curiosity, no sleep):
               sprint: each meal pays an extra  k_s * exp(-ticks since last meal / 150)   -> short dashes to food pay more
               rest:   while resting (speed command < 0.3) for over 20 ticks in a row, each tick pays  k_r * 0.02
               Dopamine only steers lifetime learning; evolution still selects on food eaten, so if a reward
               is harmful, evolution can shrink its gene.
|Wp| is capped at 0.5 per synapse.
"""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter

from .connectome import Connectome, READOUT, SILENT, FLIPPED
from .sim import TAU, max_speed
from .world import World

N_OUT = 3
LEVELS = ['fixed', 'hebb', 'dopamine', 'curiosity', 'sleep']
CONDITIONS = LEVELS + ['sprint_rest']
ODOR_A = {'level': ['AWAL', 'AWAR'], 'up': ['ASEL'], 'down': ['ASER']}
ODOR_B = {'level': ['AWCL', 'AWCR'], 'up': ['AWBL'], 'down': ['AWBR']}
N_PLAST = 7            # eta_h, eta_r, lam, curiosity, sleep, sprint, rest
SLEEP_EVERY = 300
WP_CAP = 0.5


@dataclass
class Opts5:
    level: str = 'dopamine'

    def has(self, what):
        if self.level == 'sprint_rest':
            return what in ('hebb', 'dopamine', 'sprint_rest')
        if what == 'sprint_rest':
            return False
        return LEVELS.index(self.level) >= LEVELS.index(what)

    def genes_used(self):
        """Indices of the plasticity genes this condition uses (others never mutate)."""
        return {'fixed': [], 'hebb': [0], 'dopamine': [0, 1, 2], 'curiosity': [0, 1, 2, 3],
                'sleep': [0, 1, 2, 3, 4], 'sprint_rest': [0, 1, 2, 5, 6]}[self.level]


class TwoOdorWorld(World):
    """Food smell as before + a static decoy smell. food_is_a: which odor channel carries food."""
    def __init__(self, cfg, rng):
        super().__init__(cfg, rng)
        self.decoy_centers = np.column_stack([rng.uniform(100, cfg.width - 100, cfg.food_patches),
                                              rng.uniform(100, cfg.height - 100, cfg.food_patches)])
        pts = np.concatenate([c + rng.normal(0, cfg.patch_spread, (cfg.food_per_patch, 2)) for c in self.decoy_centers])
        grid = np.zeros((self.gw, self.gh))
        gx = np.clip((pts[:, 0] / cfg.smell_cell).astype(int), 0, self.gw - 1)
        gy = np.clip((pts[:, 1] / cfg.smell_cell).astype(int), 0, self.gh - 1)
        np.add.at(grid, (gx, gy), 1.0)
        d = gaussian_filter(grid, cfg.smell_sigma_cells, mode='wrap')
        self.decoy = d / d.max()
        self.food_is_a = bool(rng.random() < 0.5)

    def decoy_at(self, pos):
        gx = np.clip((pos[:, 0] / self.cfg.smell_cell).astype(int), 0, self.gw - 1)
        gy = np.clip((pos[:, 1] / self.cfg.smell_cell).astype(int), 0, self.gh - 1)
        return self.decoy[gx, gy]


class Layout5:
    def __init__(self, conn):
        self.E, self.R = conn.n_edges, len([n for n in READOUT if n in conn.idx])
        i = self.E
        def take(n):
            nonlocal i
            s = slice(i, i + n); i += n; return s
        self.sens = take(6)
        self.dev = take(self.R * N_OUT)
        self.lvl = take(self.R * N_OUT)
        self.bias = take(N_OUT)
        self.plast = take(N_PLAST)
        self.size = i


def random_genomes(conn, P, rng):
    L = Layout5(conn)
    g = np.zeros((P, L.size))
    g[:, :L.E] = rng.normal(0, 0.15, (P, L.E))
    g[:, L.sens] = np.log(3) + rng.normal(0, 0.2, (P, 6))
    g[:, L.dev] = rng.normal(0, 0.3, (P, L.R * N_OUT))
    g[:, L.bias] = rng.normal(0, 0.3, (P, N_OUT))
    g[:, L.plast] = rng.normal(0, 0.2, (P, N_PLAST))
    return g


def plastic_params(genomes, L):
    p = np.clip(genomes[:, L.plast], -6, 3)
    return dict(eta_h=0.002 * np.exp(p[:, 0]), eta_r=0.01 * np.exp(p[:, 1]),
                lam=1 / (1 + np.exp(-(p[:, 2] + 3.0))),          # ~0.95 at gene 0
                curiosity=0.2 * np.exp(p[:, 3]), sleep=1 / (1 + np.exp(-p[:, 4])),
                sprint=np.exp(p[:, 5]), rest=np.exp(p[:, 6]))


class LearnBrains:
    chem_scale, gap_scale, inhibition, tau, dt, adapt = 1.2, 0.05, 0.5, 3.0, 1.0, 0.05

    def __init__(self, conn: Connectome, genomes, o: Opts5):
        P, N = len(genomes), conn.N
        L = self.L = Layout5(conn)
        self.o, self.P, self.N = o, P, N
        mult = 1.0 + np.clip(genomes[:, :L.E], -3, 3)
        W = np.zeros((P, N, N), np.float32)
        np.add.at(W, (slice(None), conn.pre, conn.post), (conn.w_norm * mult * self.chem_scale).astype(np.float32))
        self.W = W
        self.G = (conn.G * self.gap_scale).astype(np.float32)
        self.G_deg = (conn.G_deg * self.gap_scale).astype(np.float32)
        sg = np.exp(np.clip(genomes[:, L.sens], -3, 3))
        self.gA, self.gB = sg[:, :3], sg[:, 3:]                       # level, up, down
        self.D = (genomes[:, L.dev].reshape(P, L.R, N_OUT) * 10.0).astype(np.float32)
        self.Dl = (genomes[:, L.lvl].reshape(P, L.R, N_OUT) * 3.0).astype(np.float32)
        self.d_bias = genomes[:, L.bias]
        self.pp = plastic_params(genomes, L)
        self.pre, self.post = conn.pre, conn.post
        alive_edge = np.abs(genomes[:, :L.E] - SILENT) > 1e-6         # silenced synapses can't learn
        self.edge_ok = alive_edge.astype(np.float32)
        self.flat = (np.arange(P)[:, None] * N + conn.post[None, :]).ravel()
        self.Wp = np.zeros((P, L.E), np.float32)
        self.elig = np.zeros((P, L.E), np.float32)
        self.v = np.zeros((P, N), np.float32)
        self.rd = conn.ids([n for n in READOUT if n in conn.idx])
        self.rbar = np.zeros((P, len(self.rd)), np.float32)
        self.ids = {k: (conn.ids(ODOR_A[k]), conn.ids(ODOR_B[k])) for k in ODOR_A}
        self.pred = np.zeros((P, 2), np.float32)                      # running average of odor changes
        self.since_meal = np.zeros(P)                                  # sprint timer
        self.rest_streak = np.zeros(P)
        self.nbar = np.zeros((P, N), np.float32)                      # running mean rate per neuron (covariance rule)
        self.Rbar = np.zeros(P)                                        # expected reward (prediction error)

    def step(self, a, b, da, db):
        v, P, N = self.v, self.P, self.N
        r = np.tanh(np.maximum(v, 0))
        I = np.einsum('pn,pnm->pm', r, self.W)
        if self.o.has('hebb'):
            I += np.bincount(self.flat, (r[:, self.pre] * self.Wp).ravel(), minlength=P * N).reshape(P, N)
        I += v @ self.G - self.G_deg * v
        I -= self.inhibition * r.mean(1, keepdims=True)
        for (ia, ib), (xa, xb), k in ((self.ids['level'], (a, b), 0),
                                      (self.ids['up'], (np.maximum(da, 0), np.maximum(db, 0)), 1),
                                      (self.ids['down'], (np.maximum(-da, 0), np.maximum(-db, 0)), 2)):
            I[:, ia] += (self.gA[:, k] * xa)[:, None]
            I[:, ib] += (self.gB[:, k] * xb)[:, None]
        self.v = v + self.dt / self.tau * (-v + I)
        r = np.tanh(np.maximum(self.v, 0))
        self._r = r
        x = r[:, self.rd]
        dev = x - self.rbar
        self.rbar += self.adapt * (x - self.rbar)
        o = np.einsum('pr,pro->po', dev, self.D) + np.einsum('pr,pro->po', x, self.Dl) + self.d_bias
        speed_frac = 1.0 / (1.0 + np.exp(-(o[:, 0] + 1.0)))
        p_reverse = 1.0 / (1.0 + np.exp(-(o[:, 1] - 2.0))) * 0.3
        turn = np.tanh(o[:, 2]) * 0.4
        return p_reverse, speed_frac, turn

    def learn(self, ate, da, db, t, speed_frac=None):
        """Update plastic weights after a tick. Returns the reward signal (for logging)."""
        o, pp = self.o, self.pp
        if not o.has('hebb'):
            return np.zeros(self.P)
        r = self._r
        # Covariance rule (fixed 2026-11-01): activity relative to each neuron's own running average,
        # so synapses can weaken (LTD) as well as strengthen. The old rule used raw rates (always >= 0)
        # and could only strengthen: weights ratcheted to the cap and brains saturated.
        self.nbar += 0.01 * (r - self.nbar)
        x = r - self.nbar
        co = x[:, self.pre] * x[:, self.post] * self.edge_ok
        dW = pp['eta_h'][:, None] * co
        R = np.zeros(self.P)
        if o.has('dopamine'):
            self.elig = pp['lam'][:, None].astype(np.float32) * self.elig + co
            R = ate.astype(float)
            if o.has('curiosity'):
                d = np.column_stack([da, db])
                surprise = np.abs(d - self.pred).sum(1)
                self.pred += 0.05 * (d - self.pred)
                R = R + pp['curiosity'] * surprise
            if o.has('sprint_rest'):
                R = R + ate * pp['sprint'] * np.exp(-self.since_meal / 150.0)
                self.since_meal = np.where(ate, 0, self.since_meal + 1)
                resting = speed_frac < 0.3
                self.rest_streak = np.where(resting, self.rest_streak + 1, 0)
                R = R + (self.rest_streak > 20) * pp['rest'] * 0.02
            # Reward prediction error (fixed 2026-11-01): reward minus expected reward, can be negative.
            rpe = R - self.Rbar
            self.Rbar += 0.01 * (R - self.Rbar)
            dW = dW + (pp['eta_r'] * rpe)[:, None] * self.elig
        self.Wp = np.clip(self.Wp + dW, -WP_CAP, WP_CAP).astype(np.float32)
        if o.has('sleep') and t > 0 and t % SLEEP_EVERY == 0:
            self.Wp *= (1 - pp['sleep'])[:, None].astype(np.float32)
            self.elig[:] = 0
        return R


def run_generation(cfg, genomes, rng, conn, o: Opts5, controller='worm', food_is_a=None, halves=False):
    """Food fitness. food_is_a forces the odor meaning (None = random). halves=True also returns food
    eaten in the first and second half of life (learning check)."""
    P = genomes.shape[0]
    world = TwoOdorWorld(cfg, rng)
    if food_is_a is not None:
        world.food_is_a = food_is_a
    pos = np.column_stack([rng.uniform(0, cfg.width, P), rng.uniform(0, cfg.height, P)])
    heading = rng.uniform(0, TAU, P)
    size = np.full(P, cfg.start_size)
    energy = np.full(P, cfg.start_energy)
    alive = np.ones(P, bool)
    eaten, lifetime = np.zeros(P), np.zeros(P)
    first, second = np.zeros(P), np.zeros(P)
    brains = LearnBrains(conn, genomes, o) if controller == 'worm' else None
    T = cfg.ticks_per_generation

    def odors(p):
        f, dcy = world.smell_at(p), world.decoy_at(p)
        return (f, dcy) if world.food_is_a else (dcy, f)
    pa, pb = odors(pos)
    for t in range(T):
        if t % cfg.smell_update_every == 0:
            world.update_smell()
        a, b = odors(pos)
        da, db = np.clip((a - pa) * 20, -1, 1), np.clip((b - pb) * 20, -1, 1)
        pa, pb = a, b
        if brains is not None:
            p_tumble, speed_frac, turn = brains.step(a, b, da, db)
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
        (first if t < T // 2 else second)[:] += ate
        lifetime += alive
        if brains is not None:
            brains.learn(ate & alive, da, db, t, speed_frac)
        alive &= energy > 0
        world.regrow()
        if not alive.any():
            break
    fitness = eaten + lifetime / T
    st = dict(mean_food=float(eaten.mean()), survivors=int(alive.sum()), food_is_a=world.food_is_a)
    if halves:
        st.update(first=float(first.mean()), second=float(second.mean()))
    return fitness, st


def mutate(parent, conn, cfg, rng, o: Opts5):
    L = Layout5(conn)
    child = parent.copy()
    E = L.E
    m = rng.random(E) < cfg.worm_mutation_rate
    child[:E][m] += rng.normal(0, cfg.mutation_sigma, m.sum())
    head = np.arange(L.sens.start, L.bias.stop)
    m = rng.random(len(head)) < min(0.1, 8 / len(head))
    child[head[m]] += rng.normal(0, cfg.mutation_sigma, m.sum())
    # plasticity genes: only the ones this condition uses
    used = o.genes_used()
    if used:
        idx = L.plast.start + np.array(used)
        m = rng.random(len(idx)) < 0.3
        child[idx[m]] += rng.normal(0, 0.3, m.sum())
    if rng.random() < cfg.p_silence:
        child[int(rng.integers(E))] = SILENT
    if rng.random() < cfg.p_restore:
        s = np.flatnonzero(np.abs(child[:E] - SILENT) < 0.05)
        if len(s):
            child[int(rng.choice(s))] = 0.0
    if rng.random() < cfg.p_flip:
        child[int(rng.integers(E))] = FLIPPED
    if rng.random() < cfg.p_knockout:
        out = np.flatnonzero(conn.pre == int(rng.integers(conn.N)))
        if len(out):
            child[out] = SILENT
    return child
