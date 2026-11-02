"""Step 6: exploration -> puzzle curriculum, and an evolvable memory pool.

Brain: the Step 5 'curiosity' brain (Hebbian + dopamine three-factor learning + curiosity reward) with
odor A = food smell and odor B = puzzle-spot smell, PLUS an optional memory pool:
    up to M_MAX extra neurons, each with a self-loop and recurrent links, reading the 28 readout neurons
    and the 8 odor sensor neurons, and feeding the motor decoder. Self-loops let activity persist = memory.
    Each slot has an 'active' gene; mutation turns slots on (p=0.10) or off (p=0.05). Starts with 4 on.

World:
    explore phase  normal food + a bonus of EXPLORE_BONUS energy (and a dopamine hit) for every new
                   64x64 cell a worm visits for the first time in its life
    puzzle phase   normal food made scarce (regrowth 0.2) + 6 puzzle spots with their own smell:
                     linger  x2  stay within 50 units for 25 ticks in a row        -> 3 food
                     revisit x2  return to it 100-600 ticks after last leaving it -> 3 food
                     seq A/B     visit A, then reach B within 500 ticks            -> 6 food (paid at B)
                   per worm, per spot cooldown 150 ticks. Puzzle food = energy straight to that worm,
                   counted as food and as a dopamine reward.
"""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter

from .connectome import Connectome, READOUT, SILENT, FLIPPED
from .sim import TAU, max_speed
from .world import World
from . import worm5 as w5

N_OUT = 3
M_MAX = 40
M_START = 4
SPOT_TYPES = ['linger', 'linger', 'revisit', 'revisit', 'seqA', 'seqB']
PAY = {'linger': 3, 'revisit': 3, 'seqB': 6}
SPOT_R, LINGER_T, REVISIT_MIN, REVISIT_MAX, SEQ_T, COOLDOWN = 50.0, 25, 100, 600, 500, 150
CELL, EXPLORE_BONUS = 64.0, 15.0
SCARCE_REGROW = 0.2


@dataclass
class Opts6:
    memory: bool = True
    curriculum: bool = True
    explore_gens: int = 20


class PuzzleWorld(World):
    def __init__(self, cfg, rng, puzzles=True):
        super().__init__(cfg, rng)
        self.puzzles = puzzles
        self.spots = np.column_stack([rng.uniform(150, cfg.width - 150, len(SPOT_TYPES)),
                                      rng.uniform(150, cfg.height - 150, len(SPOT_TYPES))])
        grid = np.zeros((self.gw, self.gh))
        if puzzles:
            gx = np.clip((self.spots[:, 0] / cfg.smell_cell).astype(int), 0, self.gw - 1)
            gy = np.clip((self.spots[:, 1] / cfg.smell_cell).astype(int), 0, self.gh - 1)
            grid[gx, gy] = 1.0
            s = gaussian_filter(grid, cfg.smell_sigma_cells * 1.5, mode='wrap')
            grid = s / s.max()
        self.psmell = grid

    def puzzle_at(self, pos):
        gx = np.clip((pos[:, 0] / self.cfg.smell_cell).astype(int), 0, self.gw - 1)
        gy = np.clip((pos[:, 1] / self.cfg.smell_cell).astype(int), 0, self.gh - 1)
        return self.psmell[gx, gy]


class Layout6:
    def __init__(self, conn):
        self.base = w5.Layout5(conn)
        self.I = self.base.R + sum(len(v) for v in w5.ODOR_A.values()) + sum(len(v) for v in w5.ODOR_B.values())  # readout + odor sensor neurons
        i = self.base.size
        def take(n):
            nonlocal i
            s = slice(i, i + n); i += n; return s
        self.m_act = take(M_MAX)
        self.m_in = take(M_MAX * self.I)
        self.m_rec = take(M_MAX * M_MAX)
        self.m_self = take(M_MAX)
        self.m_dec = take(M_MAX * N_OUT)
        self.size = i


def random_genomes(conn, P, rng, o: Opts6):
    L = Layout6(conn)
    g = np.zeros((P, L.size))
    g[:, :L.base.size] = w5.random_genomes(conn, P, rng)
    g[:, L.m_act.start:L.m_act.start + M_START] = 1.0 if o.memory else 0.0
    g[:, L.m_in] = rng.normal(0, 0.3, (P, M_MAX * L.I))
    g[:, L.m_rec] = rng.normal(0, 0.1, (P, M_MAX * M_MAX))
    g[:, L.m_self] = rng.normal(1.0, 0.3, (P, M_MAX))           # self-loop ~0.73 after sigmoid-ish map
    g[:, L.m_dec] = rng.normal(0, 0.1, (P, M_MAX * N_OUT))
    return g


class MemBrains(w5.LearnBrains):
    def __init__(self, conn, genomes, o: Opts6):
        L = self.L6 = Layout6(conn)
        super().__init__(conn, genomes[:, :L.base.size], w5.Opts5('curiosity'))
        P = len(genomes)
        self.mem = o.memory
        act = (genomes[:, L.m_act] > 0.5) & o.memory
        self.m_on = act.astype(np.float32)
        self.Win = (genomes[:, L.m_in].reshape(P, M_MAX, L.I) * self.m_on[:, :, None]).astype(np.float32)
        self.Wrec = (genomes[:, L.m_rec].reshape(P, M_MAX, M_MAX) * self.m_on[:, :, None] * self.m_on[:, None, :]).astype(np.float32)
        self.a_self = (np.tanh(genomes[:, L.m_self]) * self.m_on).astype(np.float32)        # -1..1 self-loop
        self.Dm = (genomes[:, L.m_dec].reshape(P, M_MAX, N_OUT) * 3.0 * self.m_on[:, :, None]).astype(np.float32)
        self.m = np.zeros((P, M_MAX), np.float32)
        self.sens_ids = np.concatenate([self.ids[k][j] for k in ('level', 'up', 'down') for j in (0, 1)])
        self.n_mem = act.sum(1)

    def step(self, a, b, da, db):
        p_rev, spd, turn = super().step(a, b, da, db)
        if not self.mem:
            return p_rev, spd, turn
        r = self._r
        x = np.concatenate([r[:, self.rd], r[:, self.sens_ids]], 1)
        self.m = np.tanh(self.a_self * self.m + np.einsum('pi,pmi->pm', x, self.Win)
                         + np.einsum('pk,pmk->pm', self.m, self.Wrec)).astype(np.float32) * self.m_on
        dm = np.einsum('pm,pmo->po', self.m, self.Dm)
        # re-squash with the memory contribution added on the same pre-activation scale
        spd = 1 / (1 + np.exp(-(np.log(spd / (1 - spd + 1e-9) + 1e-9) + dm[:, 0])))
        pr = np.clip(p_rev / 0.3, 1e-6, 1 - 1e-6)
        p_rev = 1 / (1 + np.exp(-(np.log(pr / (1 - pr)) + dm[:, 1]))) * 0.3
        turn = np.tanh(np.arctanh(np.clip(turn / 0.4, -0.999, 0.999)) + dm[:, 2]) * 0.4
        return p_rev, spd, turn


def run_generation(cfg, genomes, rng, conn, o: Opts6, phase='puzzle', controller='worm', detail=False):
    """phase: 'explore' or 'puzzle'. Fitness = food (puzzle food included; explore bonus counted as food/10)."""
    from dataclasses import replace
    if phase == 'puzzle':
        cfg = replace(cfg, food_regrow_per_tick=SCARCE_REGROW)
    P = genomes.shape[0]
    world = PuzzleWorld(cfg, rng, puzzles=(phase == 'puzzle'))
    pos = np.column_stack([rng.uniform(0, cfg.width, P), rng.uniform(0, cfg.height, P)])
    heading = rng.uniform(0, TAU, P)
    size = np.full(P, cfg.start_size)
    energy = np.full(P, cfg.start_energy)
    alive = np.ones(P, bool)
    eaten, lifetime, pfood = np.zeros(P), np.zeros(P), np.zeros(P)
    by_type = {k: np.zeros(P) for k in PAY}
    brains = MemBrains(conn, genomes, o) if controller == 'worm' else None
    T = cfg.ticks_per_generation
    K = len(SPOT_TYPES)
    inside = np.zeros((P, K), bool); in_time = np.zeros((P, K)); left_at = np.full((P, K), -1e9)
    cool = np.full((P, K), -1e9); seqA_at = np.full(P, -1e9)
    gw, gh = int(np.ceil(cfg.width / CELL)), int(np.ceil(cfg.height / CELL))
    visited = np.zeros((P, gw * gh), bool)
    new_cells = np.zeros(P)
    pa, pb = world.smell_at(pos), world.puzzle_at(pos)
    for t in range(T):
        if t % cfg.smell_update_every == 0:
            world.update_smell()
        a, b = world.smell_at(pos), world.puzzle_at(pos)
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
        reward = ate.astype(float)
        bonus = np.zeros(P)
        if phase == 'explore':
            cell = (pos[:, 0] // CELL).astype(int) * gh + (pos[:, 1] // CELL).astype(int)
            new = alive & ~visited[np.arange(P), cell]
            visited[np.arange(P), cell] |= alive
            new_cells += new
            bonus += new * EXPLORE_BONUS
            reward += new * 0.1
        else:
            d = np.linalg.norm(pos[:, None, :] - world.spots[None], axis=2)      # P x K
            now_in = (d < SPOT_R) & alive[:, None]
            entered = now_in & ~inside
            in_time = np.where(now_in, in_time + 1, 0)
            left_at = np.where(inside & ~now_in, t, left_at)
            ready = (t - cool) > COOLDOWN
            for k, typ in enumerate(SPOT_TYPES):
                if typ == 'linger':
                    hit = (in_time[:, k] == LINGER_T) & ready[:, k]
                elif typ == 'revisit':
                    gap = t - left_at[:, k]
                    hit = entered[:, k] & (gap >= REVISIT_MIN) & (gap <= REVISIT_MAX) & ready[:, k]
                elif typ == 'seqA':
                    seqA_at = np.where(entered[:, k], t, seqA_at)
                    hit = np.zeros(P, bool)
                else:   # seqB
                    hit = entered[:, k] & ((t - seqA_at) <= SEQ_T) & ready[:, k]
                if hit.any():
                    cool[hit, k] = t
                    by_type[typ] += hit * PAY[typ]
                    pfood += hit * PAY[typ]
                    bonus += hit * PAY[typ] * cfg.food_value
                    reward += hit
            inside = now_in
        energy += ate * cfg.food_value + bonus
        size += ate * cfg.size_per_food
        eaten += ate
        lifetime += alive
        if brains is not None:
            brains.learn(reward * alive, da, db, t)
        alive &= energy > 0
        world.regrow()
        if not alive.any():
            break
    total = eaten + pfood + (new_cells * EXPLORE_BONUS / cfg.food_value if phase == 'explore' else 0)
    fitness = total + lifetime / T
    st = dict(mean_food=float(eaten.mean()), mean_puzzle=float(pfood.mean()), mean_total=float(total.mean()),
              new_cells=float(new_cells.mean()), survivors=int(alive.sum()),
              mem_size=float(brains.n_mem.mean()) if brains is not None else 0.0)
    if detail:
        st.update({f'puzzle_{k}': float(v.mean()) for k, v in by_type.items()})
    return fitness, st


def mutate(parent, conn, cfg, rng, o: Opts6):
    L = Layout6(conn)
    child = parent.copy()
    child[:L.base.size] = w5.mutate(parent[:L.base.size], conn, cfg, rng, w5.Opts5('curiosity'))
    if o.memory:
        act = child[L.m_act] > 0.5
        if rng.random() < 0.10 and (~act).any():
            child[L.m_act.start + int(rng.choice(np.flatnonzero(~act)))] = 1.0
        if rng.random() < 0.05 and act.sum() > 0:
            child[L.m_act.start + int(rng.choice(np.flatnonzero(act)))] = 0.0
        act = child[L.m_act] > 0.5
        if act.any():
            for blk, n_per in ((L.m_in, L.I), (L.m_rec, M_MAX), (L.m_self, 1), (L.m_dec, N_OUT)):
                genes = child[blk].reshape(M_MAX, n_per) if n_per > 1 else child[blk].reshape(M_MAX, 1)
                mask = (rng.random(genes.shape) < 6 / max(1, act.sum() * n_per)) & act[:, None]
                genes[mask] += rng.normal(0, cfg.mutation_sigma, mask.sum())
                child[blk] = genes.ravel()
    return child
