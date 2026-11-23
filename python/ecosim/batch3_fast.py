"""Fastest Step 3: batch3_gpu.py + CUDA graphs + sparse synapse math.

Same model and rules as batch3_gpu.py. Speedups:
1. CUDA graph: 10 ticks are recorded once and replayed as one GPU command. This removes the
   ~4 ms per tick of Python and kernel-launch overhead that limited batch3_gpu.
2. Synapses as a sparse product: input = (firing of each synapse's source x weight) summed into
   its target, done as one matrix multiply with a fixed 0/1 map. No 395x395 weight matrix per
   worm, so far less memory traffic (and room for many more worms).
3. All buffers are allocated once per run and refilled each generation, so the graph is
   recorded once and reused for every generation.
4. Branch-free tick: no CPU checks inside the loop (dead worms simply stop changing).

    python -m ecosim.batch3_fast confirm               # Step 3d: hunger vs no hunger, seeds 1-32
    python -m ecosim.batch3_fast run hunger_scarce 1 2 3 4 [--gens 60] [--cpu] [--nograph]
    python -m ecosim.batch3_fast bench                 # speed test: 8, 32, 128 seeds
    add --out <folder> to save somewhere other than runs/step3_fast
    add --watch N to record the first N seeds every generation for the live viewer:
    python -m ecosim.viewer                            # in a second window

Results: runs/step3_fast/<cond>_s<seed>/ (best_genome.npy, history.json), same format as step3.
GPU randomness comes from one generator per run seeded from the seed list, so (as in batch3_gpu)
a seed reproduces only with the same seed list. Within that, runs on the GPU are repeatable.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

_THROTTLE_FILE = Path(__file__).resolve().parent.parent / 'gpu_throttle.txt'


def gpu_idle_fraction():
    """Quiet mode. python/gpu_throttle.txt holds the fraction of time the GPU rests (0 = full speed, 0.5 = rest half
    the time, max 0.9). Read once per generation, so it can be changed while a run is going. Missing file = 0.
    It only adds sleeps between tick blocks: the numbers computed are identical."""
    try:
        return min(0.9, max(0.0, float(_THROTTLE_FILE.read_text().split()[0])))
    except Exception:
        return 0.0


from .batch3_gpu import gauss_kernel, blur_wrap
from .config import Config
from .connectome import Connectome, SENSORS
from .sim import TAU
from .step3 import CONDITIONS, CFG_OVERRIDES, GENERATIONS
from . import worm2 as w
from .worm2 import Layout, N_OUT, WormBrains2, readout_names
from .worm2_gpu import pick_device
from .gpu_brains import make_brain
from .world import World

OUT = Path('runs/step3_fast')
BLOCK = 10           # ticks per graph replay; must equal cfg.smell_update_every


def make_sense_fields(cfg, rng, gw, gh):
    """Step 19 static fields on the smell grid: temperature [0,1] (0.5 = comfortable), light [0,1], toxic [0,1]."""
    c = cfg.smell_cell
    X, Y = np.meshgrid((np.arange(gw) + 0.5) * c, (np.arange(gh) + 0.5) * c, indexing='ij')
    n = lambda d: max(1, int(round(d * cfg.width * cfg.height / 1e6)))

    def bump(sig):
        dx = (X - rng.uniform(0, cfg.width) + cfg.width / 2) % cfg.width - cfg.width / 2
        dy = (Y - rng.uniform(0, cfg.height) + cfg.height / 2) % cfg.height - cfg.height / 2
        return np.exp(-(dx ** 2 + dy ** 2) / (2 * sig ** 2))
    T = sum(rng.choice([-1.0, 1.0]) * bump(rng.uniform(150, 350)) for _ in range(n(cfg.temp_bumps) + 1))
    T = 0.5 + 0.5 * T / max(np.abs(T).max(), 1e-9)                       # hottest/coldest spot = 1 / 0
    L = np.clip(sum(bump(rng.uniform(60, 140)) * 1.3 for _ in range(n(cfg.light_zones))), 0, 1)
    X_ = np.clip(sum(bump(rng.uniform(30, 70)) * 1.5 for _ in range(n(cfg.toxic_zones))), 0, 1)
    return np.stack([T, L, X_]).astype(np.float32)


def make_phase_schedule(rng, n_blocks, dmin, dmax):
    """Step 22: 0/1 per block, alternating phases of random length dmin..dmax blocks, random first phase."""
    out, on, i = np.zeros(n_blocks, np.float32), bool(rng.integers(2)), 0
    while i < n_blocks:
        d = int(rng.integers(dmin, dmax + 1))
        out[i:i + d] = 1.0 if on else 0.0
        on, i = not on, i + d
    return out


def simplex2d(x, y, seed=0):
    """2-D simplex noise (Perlin / Gustavson), vectorised with NumPy. x, y: arrays of the same shape -> values in
    about -1..1. Same family of noise as the OpenSimplexNoise class the original Java game used for its cave walls
    (not number-for-number the same map: different permutation table)."""
    perm = np.random.default_rng(seed).permutation(256); perm = np.concatenate([perm, perm])
    g = np.array([[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]], float)
    F2, G2 = 0.5 * (np.sqrt(3.0) - 1.0), (3.0 - np.sqrt(3.0)) / 6.0
    s = (x + y) * F2
    i, j = np.floor(x + s).astype(int), np.floor(y + s).astype(int)
    t = (i + j) * G2
    x0, y0 = x - (i - t), y - (j - t)
    i1 = (x0 > y0).astype(int); j1 = 1 - i1
    x1, y1 = x0 - i1 + G2, y0 - j1 + G2
    x2, y2 = x0 - 1.0 + 2.0 * G2, y0 - 1.0 + 2.0 * G2
    ii, jj = i & 255, j & 255

    def corner(xc, yc, di, dj):
        gi = perm[ii + di + perm[jj + dj]] % 8
        tt = np.maximum(0.5 - xc * xc - yc * yc, 0.0)
        return tt ** 4 * (g[gi, 0] * xc + g[gi, 1] * yc)
    return 70.0 * (corner(x0, y0, 0, 0) + corner(x1, y1, i1, j1) + corner(x2, y2, 1, 1))


def make_gravity_pattern(cfg, gw, gh):
    """Step 21: the fixed gravity pattern on the smell grid, values -1..+1 with mean 0 (+ = heavier than 1 g).
    Made like the cave walls of the original Java game (Obstacle.java: wall where simplex noise, sampled at a
    feature size, is high), with three changes for this world:
      1. the world wraps around, so the noise is cross-faded with shifted copies of itself to tile without a seam;
      2. FEATHERED EDGES: instead of the hard wall / no-wall cut, a smooth ramp (smoothstep) of half-width
         grav_feather around the wall level grav_wall, so heavy regions fade into light ones like blended paint;
      3. the result is shifted to mean 0 and scaled so the largest value is 1 in size: walls end up near +1
         (heavy), open ground slightly negative (light).
    Layout fixed by cfg.grav_seed: every world and every run gets the SAME pattern; only its strength differs."""
    c, W, H, fs = cfg.smell_cell, cfg.width, cfg.height, cfg.grav_feature
    X, Y = np.meshgrid((np.arange(gw) + 0.5) * c, (np.arange(gh) + 0.5) * c, indexing='ij')
    n = lambda x, y: simplex2d(x / fs, y / fs, cfg.grav_seed)
    wx, wy = X / W, Y / H                                   # cross-fade weights for seamless wrap-around
    N = (n(X, Y) * (1 - wx) * (1 - wy) + n(X - W, Y) * wx * (1 - wy)
         + n(X - W, Y - H) * wx * wy + n(X, Y - H) * (1 - wx) * wy)
    N = N / max(np.abs(N).max(), 1e-9)                      # -1..1
    if cfg.grav_feather > 0:
        u = np.clip((N - (cfg.grav_wall - cfg.grav_feather)) / (2 * cfg.grav_feather), 0.0, 1.0)
        S = u * u * (3 - 2 * u)                             # smoothstep: 0 = open ground, 1 = inside a wall
    else:
        S = (N >= cfg.grav_wall).astype(float)              # the original hard cave-wall edge
    G = S - S.mean()
    return (G / max(np.abs(G).max(), 1e-9)).astype(np.float32)


def gravity_noise(cfg, gw, gh, seed):
    """Step 29: the raw seamless noise field behind make_gravity_pattern (values -1..1), for any noise seed."""
    c, W, H, fs = cfg.smell_cell, cfg.width, cfg.height, cfg.grav_feature
    X, Y = np.meshgrid((np.arange(gw) + 0.5) * c, (np.arange(gh) + 0.5) * c, indexing='ij')
    n = lambda x, y: simplex2d(x / fs, y / fs, seed)
    wx, wy = X / W, Y / H
    N = (n(X, Y) * (1 - wx) * (1 - wy) + n(X - W, Y) * wx * (1 - wy)
         + n(X - W, Y - H) * wx * wy + n(X, Y - H) * (1 - wx) * wy)
    return N / max(np.abs(N).max(), 1e-9)


def gravity_shape(cfg, N):
    """Step 29: noise field -> gravity pattern, exactly as make_gravity_pattern does it (feathered cave walls,
    mean 0, largest value 1 in size)."""
    if cfg.grav_feather > 0:
        u = np.clip((N - (cfg.grav_wall - cfg.grav_feather)) / (2 * cfg.grav_feather), 0.0, 1.0)
        S = u * u * (3 - 2 * u)
    else:
        S = (N >= cfg.grav_wall).astype(float)
    G = S - S.mean()
    return (G / max(np.abs(G).max(), 1e-9)).astype(np.float32)


def circle_centres(cfg, food_centres):
    """Step 23: where the field circles go in one world.
    'food'  -> exactly on the food patch centres.
    'decoy' -> the same number of circles, each placed as far as possible from every food patch (best of 200 random
               tries, distance measured on the wrap-around world). The random tries use a generator seeded from the
               food layout itself, so the world's own random stream (food, worm starts) is untouched: a decoy world
               has the SAME food as the matching 'food' world."""
    fc = np.asarray(food_centres, float)
    if cfg.circle_place == 'food':
        return fc
    if cfg.circle_place != 'decoy':
        raise ValueError(f"circle_place must be 'food' or 'decoy', not {cfg.circle_place!r}")
    rng = np.random.default_rng(int(abs(fc).sum() * 1000) % 2**32 + 23)
    W, H = cfg.width, cfg.height
    out = []
    for _ in range(len(fc)):
        cand = np.column_stack([rng.uniform(0, W, 200), rng.uniform(0, H, 200)])
        dx = np.abs(cand[:, None, 0] - fc[None, :, 0]); dx = np.minimum(dx, W - dx)
        dy = np.abs(cand[:, None, 1] - fc[None, :, 1]); dy = np.minimum(dy, H - dy)
        out.append(cand[np.argmax(np.sqrt(dx ** 2 + dy ** 2).min(1))])
    return np.array(out)


def make_circle_field(cfg, centres, gw, gh):
    """Step 23: the feathered-circle field on the smell grid, values 0..1 (gw x gh).
    1 within circle_r of a centre, smoothstep fade to 0 at circle_r + circle_feather, 0 beyond. Distances wrap
    around the world edges (the world is a torus). Overlapping circles: the larger value wins."""
    c = cfg.smell_cell
    X, Y = np.meshgrid((np.arange(gw) + 0.5) * c, (np.arange(gh) + 0.5) * c, indexing='ij')
    F = np.zeros((gw, gh))
    for cx, cy in centres:
        dx = np.abs(X - cx); dx = np.minimum(dx, cfg.width - dx)
        dy = np.abs(Y - cy); dy = np.minimum(dy, cfg.height - dy)
        u = np.clip((np.sqrt(dx ** 2 + dy ** 2) - cfg.circle_r) / max(cfg.circle_feather, 1e-9), 0.0, 1.0)
        F = np.maximum(F, 1 - u * u * (3 - 2 * u))           # 1 inside, smooth fade, 0 outside
    return F.astype(np.float32)


def make_obstacles(cfg, rng):
    """Step 18: random pillars, walls and caves rasterised on an obs_cell grid. Returns bool (gw, gh), True = solid."""
    c = cfg.obs_cell
    gw, gh = int(np.ceil(cfg.width / c)), int(np.ceil(cfg.height / c))
    X, Y = np.meshgrid((np.arange(gw) + 0.5) * c, (np.arange(gh) + 0.5) * c, indexing='ij')
    solid = np.zeros((gw, gh), bool)
    n = lambda d: max(1, int(round(d * cfg.width * cfg.height / 1e6)))

    def dxy(cx, cy):                          # wrapped offsets (the world is a torus)
        dx = (X - cx + cfg.width / 2) % cfg.width - cfg.width / 2
        dy = (Y - cy + cfg.height / 2) % cfg.height - cfg.height / 2
        return dx, dy
    for _ in range(n(cfg.obs_pillars)):
        dx, dy = dxy(rng.uniform(0, cfg.width), rng.uniform(0, cfg.height))
        solid |= dx ** 2 + dy ** 2 < rng.uniform(25, 50) ** 2
    for _ in range(n(cfg.obs_walls)):
        dx, dy = dxy(rng.uniform(0, cfg.width), rng.uniform(0, cfg.height))
        a, L = rng.uniform(0, np.pi), rng.uniform(150, 300)
        along, across = dx * np.cos(a) + dy * np.sin(a), -dx * np.sin(a) + dy * np.cos(a)
        solid |= (np.abs(along) < L / 2) & (np.abs(across) < 6)
    for _ in range(n(cfg.obs_caves)):
        dx, dy = dxy(rng.uniform(0, cfg.width), rng.uniform(0, cfg.height))
        R, open_at = rng.uniform(60, 90), rng.uniform(-np.pi, np.pi)
        ang = np.angle(np.exp(1j * (np.arctan2(dy, dx) - open_at)))      # angle from the opening's centre
        solid |= (np.abs(np.hypot(dx, dy) - R) < 6) & (np.abs(ang) > np.radians(40))
    return solid
FULL, HUNGRY = 0.8, 0.4   # fractions of the gut cap, as in step3_analyze


class FastSim:
    def __init__(self, cfg, opts, conn, K, P, dev, use_graph, gen, record=()):
        """record: indices of worlds (0..K-1) to record every tick for the viewer (ecosim/viewer.py)."""
        assert cfg.smell_update_every == BLOCK and cfg.ticks_per_generation % BLOCK == 0
        assert cfg.season_every % BLOCK == 0
        self.cfg, self.opts, self.conn, self.K, self.P, self.dev, self.gen = cfg, opts, conn, K, P, dev, gen
        self.use_graph = use_graph and dev.type == 'cuda'
        self.graph = None
        f = self.f = dict(dtype=torch.float32, device=dev)
        z = lambda *s: torch.zeros(*s, **f)
        # --- the brain model (Worm2Brain or GrowBrain, see gpu_brains.py)
        self.brain = make_brain(conn, opts, cfg, K * P, dev)
        # world rules that depend on the condition (Step 4 conditions have no gut limit / peptide)
        self.gut_cap = getattr(opts, 'gut_cap', float('inf'))
        self.h_rate, self.meal_drop = getattr(opts, 'h_rate', 0.0), getattr(opts, 'meal_drop', 0.0)
        self.fitness_mode = getattr(opts, 'fitness', 'food')
        self.ash_on = getattr(opts, 'ash_alarm', 0.0) > 0
        self.ash_level = getattr(opts, 'ash_start', 0.2) * min(self.gut_cap, 1e9)
        self.Q = cfg.predators
        # --- world buffers
        w0 = World(cfg, np.random.default_rng(0))
        self.gw, self.gh, self.Fd, self.C = w0.gw, w0.gh, len(w0.food), len(w0.patch_centers)
        if getattr(cfg, 'corridor', False):    # Step 28: one food per corridor, nothing else (much less work per tick)
            self.Fd = P * max(1, getattr(cfg, 'corridor_food', 1))
        self.centers, self.food = z(K, self.C, 2), z(K, self.Fd, 2)
        self.falive = torch.zeros(K, self.Fd, dtype=torch.bool, device=dev)
        self.smap, self.prev = z(K, self.gw, self.gh), z(K, P)
        # Step 11 worm scent: field from worm positions, sensed like food smell
        self.pher_on = cfg.pheromone
        self.pmap, self.pprev = z(K, self.gw, self.gh), z(K, P)
        self.pkern, self.pkr = gauss_kernel(cfg.pher_sigma_cells, dev)
        self.pnorm = float(self.pkern[self.pkr] ** 2) * cfg.pher_full
        self.ppeak = float(self.pkern[self.pkr] ** 2)       # one predator's scent peak (Step 19)
        self.nn = z(K, 2)                      # sum of nearest-neighbour distances, count (clumping measure)
        self.pos, self.heading = z(K, P, 2), z(K, P)
        self.size, self.energy, self.H = z(K, P), z(K, P), z(K, P)
        self.alive = torch.zeros(K, P, dtype=torch.bool, device=dev)
        self.eaten, self.lifetime, self.esum = z(K, P), z(K, P), z(K, P)
        Q = max(cfg.predators, 1)
        self.ppos, self.phead, self.pcool = z(K, Q, 2), z(K, Q), z(K, Q)
        self.touchF, self.touchB, self.bites = z(K, P), z(K, P), z(K, P)
        self.stomach = z(K, P)                 # Step 8c digestion: food eaten but not yet usable energy
        # Step 18 obstacles: solid grid, 'near a wall' grid (solid dilated by 2 cells), last tick's bumps
        self.obs_on = cfg.obstacles
        self.ogw, self.ogh = int(math.ceil(cfg.width / cfg.obs_cell)), int(math.ceil(cfg.height / cfg.obs_cell))
        og = (K, self.ogw * self.ogh) if self.obs_on else (K, 1)
        self.solid = torch.zeros(og, dtype=torch.bool, device=dev)
        self.nearw = torch.zeros(og, dtype=torch.bool, device=dev)
        self.bump = z(K, P)
        self.wall = z(K, 2)                    # sum of living worms near a wall, count of living worms
        # Step 18b diagnostics (worm-ticks / events, all worms incl. ones that later die): near-rock ticks, open
        # ticks, bites near rock, bites in the open, deaths near rock, deaths in the open, hidden ticks (in a
        # predator's range but every sight line blocked), exposed ticks (seen by >=1 predator), bump ticks, alive ticks
        self.odiag = z(K, 10)
        # Step 19 senses: static fields (temperature, light, toxic) and per-block maps (predator scent, CO2)
        self.sense_on = cfg.senses
        ng = self.gw * self.gh if self.sense_on else 1
        self.sfield, self.dmap, self.onfood = z(K, 3, ng), z(K, 2, ng), z(K, P)
        self.sense_cost = z(K, 4)              # energy lost to temperature, light, toxic, CO2 (per worm, summed)
        # Step 21 gravity pattern (see config.py): fixed pattern, per-world strength grav_s (K,1), default 0 = no
        # gravity differences. Set strengths before the first run: sim.grav_s.copy_(...)  (shape (K, 1)).
        self.grav_on = getattr(cfg, 'gravity', False)
        gp = make_gravity_pattern(cfg, self.gw, self.gh).reshape(1, -1) if self.grav_on else np.zeros((1, 1), np.float32)
        self.gpat = torch.as_tensor(gp, **f).repeat(K, 1)                 # (K, cells)
        self.grav_s = z(K, 1)
        self.gexp = z(K, 3)                    # sums over living worm-ticks: dg, pattern value, count
        gm = torch.zeros(conn.N, **f)
        if self.grav_on:
            gm[torch.as_tensor(conn.ids(['PVDL', 'PVDR']), device=dev)] = cfg.grav_gain
        self.gmap = gm
        # Step 23 food circles + magnetism (see config.py). circ_on: gravity pattern and/or magnetic field are rebuilt
        # from each world's food layout in load(). Magnetic field (K, cells) 0..1, strength mag_s (K,1), sensed by AFD.
        self.circ_on = getattr(cfg, 'field_circles', False)
        self.mag_on = getattr(cfg, 'magnetism', False)
        self.mpat = z(K, self.gw * self.gh) if self.mag_on else z(K, 1)
        self.mag_s = z(K, 1)
        self.mexp = z(K, 2)                    # sums over living worm-ticks: field value under the worm, count
        mm = torch.zeros(conn.N, **f)
        if self.mag_on:
            mm[torch.as_tensor(conn.ids(['AFDL', 'AFDR']), device=dev)] = cfg.mag_gain
        self.mmap = mm
        # Step 25 beacon (see config.py): cue into chosen neurons + hidden reward zone, one circle per world
        self.bea_on = getattr(cfg, 'beacon', False)
        bm = torch.zeros(conn.N, **f)
        bn = [n.strip() for n in getattr(cfg, 'beacon_neurons', '').split(',') if n.strip()]
        if self.bea_on and bn:
            bm[torch.as_tensor(conn.ids(bn), device=dev)] = cfg.beacon_gain
        self.bmap = bm
        self.bc, self.bv = z(K, 2), z(K, 2)              # beacon centre and drift per tick
        self.b_cue, self.b_rew = torch.ones(K, 1, **f), torch.ones(K, 1, **f)   # per world: cue on/off, reward on/off
        self.bexp = z(K, 4)                    # sums over living worm-ticks: field value, distance, count; arrival tick
        self.b_place = None                    # optional (K, 2) array: fixed beacon centres for the next load()
        # Step 27 fleeing food (see config.py)
        self.flee_on = getattr(cfg, 'food_flee_speed', 0.0) > 0
        self.fled = torch.zeros(K, self.Fd, dtype=torch.bool, device=dev)   # has this food item fled yet?
        self.fstart, self.frun, self.frest = z(K, self.Fd), z(K, self.Fd), z(K, self.Fd)
        nmov = int(round(getattr(cfg, 'food_flee_fraction', 1.0) * self.Fd))
        self.fmover = (torch.arange(self.Fd, device=dev) < nmov)[None, :].expand(K, self.Fd).contiguous()   # Step 27b
        self.fdrift = getattr(cfg, 'food_flee_mode', 'flee') == 'drift'
        self.fhead = z(K, self.Fd)                                       # drifting food: current heading
        self.flx = z(K, 6)                     # sums: caught fleeing food, group catches, all food taken, slow eats,
                                               #       chase ticks of caught fleeing food, food-ticks spent running
        # Step 28 corridor test (see config.py)
        self.corr_on = getattr(cfg, 'corridor', False)
        self.goal, self.carr = z(K, P, 2), z(K, P)          # each worm's food position; arrival tick (world age)
        self.wage = z(K)                                    # ticks since this world was (re)started
        self.cylo, self.cyhi = z(K, P), z(K, P)             # corridor band (y limits) of each worm
        self.beh = z(K, 4)                     # sums over living worm-ticks: tumbles (reversals), |turn|, near food, count
        # Step 22 red light / green light (see config.py): per-world phase schedule and the signal the peptide carries
        self.red_on = getattr(cfg, 'redlight', False)
        nb = cfg.ticks_per_generation // BLOCK
        self.red_sched, self.sig_sched = z(K, nb), z(K, nb)
        self.rexp = z(K, 4)                    # sums over living worm-ticks: speed on red, red count, speed on green, green count
        self.form = None                       # test-bench formula world (ecosim/bench), set by set_formula()
        self.wcost = z(K, 1)                   # Step 20: extra energy per tick per world (copy-fidelity cost); 0 = as before
        self.los_fr = torch.tensor([0.15, 0.3, 0.45, 0.6, 0.75, 0.9], **f)   # sight-line sample points (made here:
                                                                            # no CPU->GPU copies inside a CUDA graph)
        # --- food regrowth schedule (same running-total rule as World.regrow), per block
        T = cfg.ticks_per_generation
        acc, n = 0.0, []
        for _ in range(T):
            acc += cfg.food_regrow_per_tick
            k = int(acc); acc -= k; n.append(k)
        self.nmax = max(1, max(n))
        self.n_sched = torch.as_tensor(np.array(n).reshape(T // BLOCK, BLOCK), device=dev)
        self.bi = torch.zeros((), dtype=torch.long, device=dev)
        self.kern, self.kr = gauss_kernel(cfg.smell_sigma_cells, dev)
        self.kidx = torch.arange(K, device=dev)
        self.wh = torch.tensor([cfg.width, cfg.height], **f)
        self.ar_nmax = torch.arange(self.nmax, device=dev)
        # --- satiety check (as in step3_analyze): brain's speed command when full vs hungry, per world
        self.full_e, self.hungry_e = FULL * self.gut_cap, HUNGRY * self.gut_cap
        self.sat = z(K, 4)                     # sum speed_frac full, count full, sum hungry, count hungry
        self.spd = z(K, 2)                     # sum speed_frac over living worms, count (mean speed, trait tracking)
        # --- recording for the viewer: positions, energy, food of the chosen worlds, every tick
        self.rec_idx = torch.as_tensor(list(record), dtype=torch.long, device=dev)
        R, T = len(record), cfg.ticks_per_generation
        h = dict(dtype=torch.float16, device=dev)
        self.ti = torch.zeros((), dtype=torch.long, device=dev)
        if R:
            self.recbuf = dict(pos=torch.zeros(T, R, P, 2, **h), energy=torch.zeros(T, R, P, **h),
                            alive=torch.zeros(T, R, P, dtype=torch.bool, device=dev),
                            heading=torch.zeros(T, R, P, **h),
                            food=torch.zeros(T, R, self.Fd, 2, **h),
                            falive=torch.zeros(T, R, self.Fd, dtype=torch.bool, device=dev),
                            pred=torch.zeros(T, R, Q, 2, **h))
        else:
            self.recbuf = None

    # ------------------------------------------------------------------ setup each generation
    def load(self, genomes, rngs):
        cfg, opts, f, K, P = self.cfg, self.opts, self.f, self.K, self.P
        self.brain.load(genomes.reshape(K * P, -1))
        ws = [World(cfg, r) for r in rngs]                      # same layouts as step3 for the same rng
        if self.obs_on:
            sol = np.stack([make_obstacles(cfg, np.random.default_rng(r.integers(2**62))) for r in rngs])
            near = sol.copy()
            for sx in (-2, -1, 0, 1, 2):
                for sy in (-2, -1, 0, 1, 2):
                    near |= np.roll(np.roll(sol, sx, 1), sy, 2)
            self.solid.copy_(torch.as_tensor(sol.reshape(K, -1), device=self.dev))
            self.nearw.copy_(torch.as_tensor(near.reshape(K, -1), device=self.dev))
            cell = lambda p: (np.clip((p[..., 0] / cfg.obs_cell).astype(int), 0, self.ogw - 1),
                              np.clip((p[..., 1] / cfg.obs_cell).astype(int), 0, self.ogh - 1))
            for k, x in enumerate(ws):                          # no food inside rock
                gx, gy = cell(x.food)
                x.food_alive = x.food_alive & ~sol[k][gx, gy]
        self.centers.copy_(torch.as_tensor(np.stack([x.patch_centers for x in ws]), **f))
        if not self.corr_on:                   # (corridor mode places its own food below)
            self.food.copy_(torch.as_tensor(np.stack([x.food for x in ws]), **f))
            self.falive.copy_(torch.as_tensor(np.stack([x.food_alive for x in ws]), device=self.dev))
        pos0 = np.stack([np.column_stack([r.uniform(0, cfg.width, P), r.uniform(0, cfg.height, P)]) for r in rngs])
        if self.obs_on:                                         # worms don't start inside rock
            for k, r in enumerate(rngs):
                for _ in range(50):
                    gx, gy = cell(pos0[k])
                    bad = sol[k][gx, gy]
                    if not bad.any():
                        break
                    pos0[k][bad] = np.column_stack([r.uniform(0, cfg.width, bad.sum()), r.uniform(0, cfg.height, bad.sum())])
        self.pos.copy_(torch.as_tensor(pos0, **f))
        self.heading.copy_(torch.as_tensor(np.stack([r.uniform(0, TAU, P) for r in rngs]), **f))
        if self.corr_on:                       # Step 28: worm i alone in corridor i, one food at the far end
            sp = cfg.height / P
            assert cfg.corridor_width < sp and 100 + cfg.corridor_len + 20 < cfg.width, 'corridors do not fit'
            cy = (np.arange(P) + 0.5) * sp
            x1 = 100.0 + cfg.corridor_len
            fd = np.zeros((self.Fd, 2)); fa = np.ones(self.Fd, bool)
            nf = self.Fd // P                    # food items per corridor (1 = one piece; more = a small patch)
            fr = np.random.default_rng(28)       # same patch layout in every world
            fd[:, 0] = np.repeat(np.full(P, x1), nf)
            fd[:, 1] = np.repeat(cy, nf)
            if nf > 1:
                hw0 = cfg.corridor_width / 2 - 2
                fd[:, 0] = np.clip(fd[:, 0] - np.abs(fr.normal(0, cfg.corridor_spread, self.Fd)), x1 - 3 * cfg.corridor_spread, x1)
                fd[:, 1] = fd[:, 1] + np.clip(fr.normal(0, cfg.corridor_spread, self.Fd), -hw0, hw0)
            self.food.copy_(torch.as_tensor(np.broadcast_to(fd, (K, self.Fd, 2)).copy(), **f))
            self.falive.copy_(torch.as_tensor(np.broadcast_to(fa, (K, self.Fd)).copy(), device=self.dev))
            self.pos.copy_(torch.as_tensor(np.broadcast_to(np.column_stack([np.full(P, 100.0), cy]), (K, P, 2)).copy(), **f))
            gx = x1 - (3 * cfg.corridor_spread if nf > 1 else 0.0)   # a patch counts as reached at its front edge
            self.goal.copy_(torch.as_tensor(np.broadcast_to(np.column_stack([np.full(P, gx), cy]), (K, P, 2)).copy(), **f))
            hw = cfg.corridor_width / 2
            self.cylo.copy_(torch.as_tensor(np.broadcast_to(cy - hw, (K, P)).copy(), **f))
            self.cyhi.copy_(torch.as_tensor(np.broadcast_to(cy + hw, (K, P)).copy(), **f))
            self.carr.fill_(float(cfg.ticks_per_generation))
            self.wage.zero_()
        self.size.fill_(cfg.start_size); self.energy.fill_(cfg.start_energy)
        self.H.copy_(torch.clamp(1 - self.energy / self.gut_cap, 0, 1))
        self.alive.fill_(True)
        self.eaten.zero_(); self.lifetime.zero_(); self.esum.zero_(); self.bi.zero_()
        self.sat.zero_(); self.ti.zero_(); self.nn.zero_(); self.spd.zero_()
        self.touchF.zero_(); self.touchB.zero_(); self.bites.zero_(); self.pcool.zero_(); self.stomach.zero_()
        self.bump.zero_(); self.wall.zero_(); self.odiag.zero_(); self.onfood.zero_(); self.sense_cost.zero_()
        self.gexp.zero_(); self.rexp.zero_(); self.mexp.zero_(); self.beh.zero_()
        self.fled.zero_(); self.fstart.zero_(); self.frun.zero_(); self.frest.zero_(); self.flx.zero_()
        if self.flee_on and self.fdrift:
            self.fhead.copy_(torch.rand(K, self.Fd, generator=self.gen, **f) * TAU)
        if self.circ_on:                       # Step 23: one feathered circle per food patch (or decoy), this world
            fld = np.stack([make_circle_field(cfg, circle_centres(cfg, x.patch_centers), self.gw, self.gh).reshape(-1)
                            for x in ws])
            if self.grav_on:
                self.gpat.copy_(torch.as_tensor(cfg.circle_sign * fld, **f))
            if self.mag_on:
                self.mpat.copy_(torch.as_tensor(fld, **f))
        if self.red_on:                        # new random phases every generation, per world (drawn last: the
            nb = cfg.ticks_per_generation // BLOCK   # world layouts above use the same random numbers as without it)
            rr = [np.random.default_rng(r.integers(2**62)) for r in rngs]
            red = np.stack([make_phase_schedule(x, nb, cfg.red_min, cfg.red_max) for x in rr])
            sig = red if cfg.red_signal == 'true' else np.stack([make_phase_schedule(x, nb, cfg.red_min, cfg.red_max) for x in rr])
            self.red_sched.copy_(torch.as_tensor(red, **f)); self.sig_sched.copy_(torch.as_tensor(sig, **f))
        if self.bea_on:                        # Step 25: one beacon per world (random numbers drawn after all others)
            rb = [np.random.default_rng(r.integers(2**62)) for r in rngs]
            c = np.stack([[x.uniform(0, cfg.width), x.uniform(0, cfg.height)] for x in rb])
            a = np.array([x.uniform(0, TAU) for x in rb])
            if self.b_place is not None:
                c = np.asarray(self.b_place, dtype=np.float64).reshape(K, 2)
            self.bc.copy_(torch.as_tensor(c, **f))
            self.bv.copy_(torch.as_tensor(np.column_stack([np.cos(a), np.sin(a)]) * cfg.beacon_speed, **f))
            self.bexp.zero_(); self.bexp[:, 3] = float(cfg.ticks_per_generation)
        if self.form is not None:
            self._load_formula(rngs)
        if self.sense_on:
            self.sfield.copy_(torch.as_tensor(np.stack([make_sense_fields(cfg, np.random.default_rng(r.integers(2**62)),
                                                                          self.gw, self.gh) for r in rngs]),
                                              **f).view(K, 3, -1))
        if self.Q:
            self.ppos.copy_(torch.rand(K, self.Q, 2, generator=self.gen, **f) * self.wh)
            self.phead.copy_(torch.rand(K, self.Q, generator=self.gen, **f) * TAU)
        self.smap.copy_(self._smell_map())
        self.prev.copy_(self._smell_at(self.pos))
        if self.pher_on:
            self.pmap.copy_(self._pher_map(self.pos, self.alive))
            self.pprev.copy_(self._smell_at(self.pos, self.pmap))
        if self.sense_on:
            self.dmap.copy_(self._sense_maps(self.pos, self.alive, self.ppos))

    def set_formula(self, specs, per_world):
        """Test bench: add formula-world features. specs = list of feature specs (bench.formula.feature_specs);
        per_world = {field: array (K, F)} for a, b, scale, period, cost, gain (world dials may differ per world).
        Call before the first run (CUDA graph capture)."""
        from .bench.layers import resolve
        K, F, N, f = self.K, len(specs), self.conn.N, self.f
        from .bench.formula import N_WAVES
        SM = torch.zeros(K, F, N, **f)
        for i, sp in enumerate(specs):
            ids = resolve(self.conn, sp['neurons'])
            SM[:, i, ids] = torch.as_tensor(per_world['gain'][:, i], **f)[:, None]
        z = lambda *sh: torch.zeros(*sh, **f)
        self.form = dict(specs=specs, pw={k: np.asarray(v, float) for k, v in per_world.items()},
                         SM=SM, signed=torch.as_tensor([sp['signed'] for sp in specs], device=self.dev),
                         a=z(K, F), b=z(K, F), cost=z(K, F), n=z(K, F, N_WAVES), m=z(K, F, N_WAVES),
                         phi=z(K, F, N_WAVES), c=z(K, F, N_WAVES), om=z(K, F, N_WAVES),
                         exp=z(K, F), paid=z(K, F))

    def _load_formula(self, rngs):
        from .bench.formula import draw_waves
        fm, cfg = self.form, self.cfg
        pw, F = fm['pw'], len(fm['specs'])
        W = {k: [] for k in ('n', 'm', 'phi', 'c', 'om')}
        for k, r in enumerate(rngs):
            fr = np.random.default_rng(r.integers(2**62))
            rows = [draw_waves(fr, cfg.width, cfg.height, pw['scale'][k, i], pw['period'][k, i]) for i in range(F)]
            for j, key in enumerate(('n', 'm', 'phi', 'c', 'om')):
                W[key].append(np.stack([row[j] for row in rows]))
        for key in W:
            fm[key].copy_(torch.as_tensor(np.stack(W[key]), **self.f))
        for key in ('a', 'b', 'cost'):
            fm[key].copy_(torch.as_tensor(pw[key], **self.f))
        fm['exp'].zero_(); fm['paid'].zero_()

    def _formula_at(self, pos):
        """Feature values (K, P, F) at worm positions, this tick."""
        fm, cfg = self.form, self.cfg
        t = self.ti.float()
        x = pos[..., 0, None, None] / cfg.width; y = pos[..., 1, None, None] / cfg.height       # (K,P,1,1)
        arg = 2 * math.pi * (fm['n'][:, None] * x + fm['m'][:, None] * y) + fm['om'][:, None] * t + fm['phi'][:, None]
        v = fm['b'][:, None] + fm['a'][:, None] * (fm['c'][:, None] * torch.cos(arg)).sum(-1)
        return torch.where(fm['signed'], torch.clamp(v, -1, 1), torch.clamp(v, 0, 1))

    # ------------------------------------------------------------------ pieces
    def _solid_at(self, p, grid=None):
        """Obstacle lookup for points p (K, ..., 2) -> bool (K, ...)."""
        cfg = self.cfg
        gx = torch.clamp((p[..., 0] / cfg.obs_cell).long(), 0, self.ogw - 1)
        gy = torch.clamp((p[..., 1] / cfg.obs_cell).long(), 0, self.ogh - 1)
        idx = (gx * self.ogh + gy).reshape(self.K, -1)
        return (self.solid if grid is None else grid).gather(1, idx).view(p.shape[:-1])

    def _sense_maps(self, pos, alive, ppos):
        """Step 19: predator scent (1 = right next to a predator, capped) and CO2 (crowds + food), (K, 2, cells)."""
        cfg, K, gw, gh = self.cfg, self.K, self.gw, self.gh
        cnt = lambda p, w: torch.zeros(K, gw * gh, **self.f).scatter_add_(
            1, torch.clamp((p[..., 0] / cfg.smell_cell).long(), 0, gw - 1) * gh
            + torch.clamp((p[..., 1] / cfg.smell_cell).long(), 0, gh - 1), w)
        if self.Q:
            pk = blur_wrap(cnt(ppos, torch.ones(K, self.Q, **self.f)).view(K, gw, gh), self.pkern, self.pkr)
            pred = torch.clamp(pk / self.ppeak, 0, 1).view(K, -1)
        else:
            pred = torch.zeros(K, gw * gh, **self.f)
        crowd = blur_wrap(cnt(pos, alive.float()).view(K, gw, gh), self.pkern, self.pkr) / self.pnorm
        co2 = torch.clamp(0.7 * crowd + 0.3 * self.smap, 0, 1).view(K, -1)
        return torch.stack([pred, co2], 1)

    def _rand(self, *s):
        return torch.rand(*s, generator=self.gen, **self.f)

    def _smell_map(self):
        cfg, K, gw, gh = self.cfg, self.K, self.gw, self.gh
        gx = torch.clamp((self.food[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((self.food[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        cnt = torch.zeros(K, gw * gh, **self.f)
        cnt.scatter_add_(1, gx * gh + gy, self.falive.float())
        s = blur_wrap(cnt.view(K, gw, gh), self.kern, self.kr)
        m = s.amax(dim=(1, 2), keepdim=True)
        return torch.where(m > 0, s / m.clamp(min=1e-12), s)

    def _smell_at(self, p, field=None):
        cfg, gw, gh = self.cfg, self.gw, self.gh
        gx = torch.clamp((p[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((p[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        return (self.smap if field is None else field).view(self.K, -1).gather(1, gx * gh + gy)

    def _pher_map(self, pos, alive):
        """Worm scent: blurred density of living worms, 1 = pher_full worms in one spot (capped at 1)."""
        cfg, K, gw, gh = self.cfg, self.K, self.gw, self.gh
        gx = torch.clamp((pos[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((pos[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        cnt = torch.zeros(K, gw * gh, **self.f)
        cnt.scatter_add_(1, gx * gh + gy, alive.float())
        return torch.clamp(blur_wrap(cnt.view(K, gw, gh), self.pkern, self.pkr) / self.pnorm, 0, 1)

    # ------------------------------------------------------------------ one block of ticks
    def _block(self):
        cfg, opts, K, P, Fd, dev = self.cfg, self.opts, self.K, self.P, self.Fd, self.dev
        bs = {k: getattr(self.brain, k) for k in self.brain.state_names}
        pos, heading = self.pos, self.heading
        size, energy, H, alive = self.size, self.energy, self.H, self.alive
        eaten, lifetime, esum, food, falive, prev = self.eaten, self.lifetime, self.esum, self.food, self.falive, self.prev
        ppos, phead, pcool, touchF, touchB, bites = self.ppos, self.phead, self.pcool, self.touchF, self.touchB, self.bites
        bump, OBS = self.bump, self.obs_on
        stomach, DIG = self.stomach, cfg.digestion
        Q, half = self.Q, self.wh / 2
        inf = torch.full((), float('inf'), **self.f)
        if not self.corr_on:                     # corridor mode: food never moves, the smell map from load() stays
            self.smap.copy_(self._smell_map())
        pprev = self.pprev
        if self.pher_on:
            self.pmap.copy_(self._pher_map(pos, alive))
        SENSE, onfood = self.sense_on, self.onfood
        FORM = self.form is not None
        GRAV = self.grav_on
        MAG = self.mag_on
        RED = self.red_on
        BEA, FLEE, CORR = self.bea_on, self.flee_on, self.corr_on
        fled, fstart, frun, frest = self.fled, self.fstart, self.frun, self.frest
        TIRE = FLEE and cfg.food_tire_run > 0
        R2f, TT = cfg.food_flee_radius ** 2, float(cfg.ticks_per_generation)
        if RED:                                  # this block's phase (K,1) and the peptide command, graph-safe lookup
            red = self.red_sched.index_select(1, self.bi.view(1))
            Hcmd = self.sig_sched.index_select(1, self.bi.view(1)).expand(K, P)
        if SENSE:
            self.dmap.copy_(self._sense_maps(self.pos, self.alive, self.ppos))
        nrow = self.n_sched.index_select(0, self.bi.view(1)).squeeze(0)    # graph-safe (no CPU sync)
        r2, BIG = cfg.eat_radius ** 2, K * Fd + 1
        zero = torch.zeros((), **self.f)
        HERD = cfg.pred_loner > 0 or cfg.pred_confuse > 0
        if cfg.season_every > 0:                 # Step 16 seasons: patches move every season_every ticks
            mv = ((self.bi * BLOCK) % cfg.season_every == 0) & (self.bi > 0)
            self.centers.copy_(torch.where(mv, self._rand(K, self.C, 2) * self.wh, self.centers))
        for j in range(BLOCK):
            smell = self._smell_at(pos)
            d = torch.clamp((smell - prev) * 20.0, -1, 1)
            prev = smell
            alarm = None
            if self.ash_on:                     # 0 above ash_start of the gut, rising to 1 at zero energy
                alarm = (torch.clamp((self.ash_level - energy) / self.ash_level, 0, 1) * alive).view(-1)
            touch = (touchF.view(-1), touchB.view(-1)) if (Q and cfg.touch_gain > 0) else None
            pher = None
            if self.pher_on:
                pl = self._smell_at(pos, self.pmap)
                pher = (pl.view(-1), torch.clamp((pl - pprev) * 20.0, -1, 1).view(-1))
                pprev = pl
            extra = None
            if SENSE:                                # Step 19: sample every sense at the worm's position
                gi = (torch.clamp((pos[..., 0] / cfg.smell_cell).long(), 0, self.gw - 1) * self.gh
                      + torch.clamp((pos[..., 1] / cfg.smell_cell).long(), 0, self.gh - 1))          # (K,P)
                sf = self.sfield.gather(2, gi[:, None, :].expand(-1, 3, -1))                      # (K,3,P)
                dm = self.dmap.gather(2, gi[:, None, :].expand(-1, 2, -1))                        # (K,2,P)
                tmp, lit, tox, prd, co2 = 2 * sf[:, 0] - 1, sf[:, 1], sf[:, 2], dm[:, 0], dm[:, 1]
                extra = torch.stack([tmp, lit, tox, prd, co2, 1 - smell, onfood], -1).view(K * P, -1)
            inject = None
            if FORM:                                 # test bench: formula features -> chosen sensory neurons
                fv = self._formula_at(pos)                                                         # (K,P,F)
                inject = torch.einsum('kpf,kfn->kpn', fv, self.form['SM']).reshape(K * P, -1)
            if GRAV:                                 # Step 21: local gravity offset at each worm, sensed by PVD
                gix = (torch.clamp((pos[..., 0] / cfg.smell_cell).long(), 0, self.gw - 1) * self.gh
                       + torch.clamp((pos[..., 1] / cfg.smell_cell).long(), 0, self.gh - 1))         # (K,P)
                gpv = self.gpat.gather(1, gix)                                                   # pattern, -1..+1
                dg = self.grav_s * gpv                                                           # gravity - 1 g
                ginj = dg.reshape(K * P, 1) * self.gmap[None, :]
                inject = ginj if inject is None else inject + ginj
            if MAG:                                  # Step 23: magnetic field at each worm, sensed by AFD (pure cue)
                mix = (torch.clamp((pos[..., 0] / cfg.smell_cell).long(), 0, self.gw - 1) * self.gh
                       + torch.clamp((pos[..., 1] / cfg.smell_cell).long(), 0, self.gh - 1))
                mfv = self.mpat.gather(1, mix)                                                   # field, 0..1
                minj = (self.mag_s * mfv).reshape(K * P, 1) * self.mmap[None, :]
                inject = minj if inject is None else inject + minj
                maf = alive.float()
                self.mexp += torch.stack([(mfv * maf).sum(1), maf.sum(1)], 1)
            if BEA:                                  # Step 25: beacon field at each worm (smooth circle, wraps)
                bdl = torch.remainder(pos - self.bc[:, None, :] + half, self.wh) - half
                bdist = torch.sqrt((bdl ** 2).sum(-1))                                          # (K,P)
                btt = torch.clamp((bdist - cfg.beacon_r) / cfg.beacon_feather, 0, 1)
                bfv = 1 - btt * btt * (3 - 2 * btt)                                             # 1 inside .. 0
                binj = (self.b_cue * bfv).reshape(K * P, 1) * self.bmap[None, :]
                inject = binj if inject is None else inject + binj
            Hin = Hcmd if RED else H                 # Step 22: the peptide carries the outside command, not hunger
            bs, (p_tumble, speed_frac, turn) = self.brain.step(bs, smell.view(-1), d.view(-1), Hin.reshape(-1), alarm, touch, pher,
                                                               bump.view(-1) if OBS else None, extra,
                                                               inject=inject, tick=self.ti)
            p_tumble, speed_frac, turn = p_tumble.view(K, P), speed_frac.view(K, P), turn.view(K, P)
            tumble = self._rand(K, P) < p_tumble
            heading = torch.where(tumble, self._rand(K, P) * TAU, heading + torch.clamp(turn, -0.5, 0.5))
            speed = speed_frac * torch.clamp(cfg.speed_slope * size + cfg.speed_max, cfg.speed_min, cfg.speed_max)
            if GRAV:                                 # heavier ground is slower, lighter ground faster
                speed = speed * torch.clamp(1 - cfg.grav_slow * dg, 0.25, 1.75)
            step = torch.stack([torch.cos(heading), torch.sin(heading)], -1) * speed[..., None]
            npos = torch.remainder(pos + step, self.wh)
            if CORR:                                 # Step 28: sliding walls (clamp to the corridor band and ends)
                cx = torch.clamp((pos + step)[..., 0], 90.0, 110.0 + cfg.corridor_len)
                cyy = torch.minimum(torch.maximum((pos + step)[..., 1], self.cylo), self.cyhi)
                npos = torch.stack([cx, cyy], -1)
            if OBS:                                  # rock blocks the move; the worm feels the bump next tick
                blk = self._solid_at(npos) & ~self._solid_at(pos)     # (a worm stuck inside rock may leave)
                bump = (alive & blk).float()
                pos = torch.where((alive & ~blk)[..., None], npos, pos)
            else:
                pos = torch.where(alive[..., None], npos, pos)
            energy = energy - torch.where(alive, cfg.base_cost + self.wcost + cfg.move_cost * speed, zero)
            if RED:                                  # moving on red costs energy; standing still is free
                af = alive.float()
                energy = energy - cfg.red_cost * red * speed_frac * af
                self.rexp += torch.stack([(speed_frac * af * red).sum(1), (af * red).sum(1),
                                          (speed_frac * af * (1 - red)).sum(1), (af * (1 - red)).sum(1)], 1)
            if GRAV:                                 # heavier ground costs more energy, lighter ground less
                af = alive.float()
                energy = energy - cfg.grav_cost * dg * af
                self.gexp += torch.stack([(dg * af).sum(1), (gpv * af).sum(1), af.sum(1)], 1)
            if BEA:                                  # Step 25: hidden reward inside the beacon; bookkeeping; drift
                baf = alive.float()
                room = torch.clamp(self.gut_cap - energy, min=0)
                energy = energy + torch.minimum(cfg.beacon_reward * self.b_rew * bfv * baf, room)
                bfrac = ((bdist < cfg.beacon_r).float() * baf).sum(1) / baf.sum(1).clamp(min=1)
                barr = torch.where((bfrac >= 0.5) & (self.bexp[:, 3] >= TT), self.ti.float(), self.bexp[:, 3])
                self.bexp[:, :3] += torch.stack([(bfv * baf).sum(1), (bdist * baf).sum(1), baf.sum(1)], 1)
                self.bexp[:, 3].copy_(barr)
                self.bc.copy_(torch.remainder(self.bc + self.bv, self.wh))
            if FORM:                                 # test bench feature costs (signed features: |value|)
                fa = fv.abs() * alive[..., None].float()
                fpaid = fa * self.form['cost'][:, None, :]
                energy = energy - fpaid.sum(-1)
                self.form['exp'] += fa.sum(1); self.form['paid'] += fpaid.sum(1)
            if SENSE:                                # Step 19 world costs: discomfort, UV, poison, stale air
                cs = torch.stack([cfg.temp_cost * tmp.abs(), cfg.light_cost * lit, cfg.toxic_cost * tox,
                                  cfg.co2_cost * torch.clamp(2 * co2 - 1, min=0)], 1) * alive[:, None].float()  # (K,4,P)
                energy = energy - cs.sum(1)
                self.sense_cost += cs.sum(2)
            # nearest-neighbour distances (clumping measure) and neighbour counts (Step 14b herd predators)
            if not CORR:                             # (corridor mode: worms are walled apart, skip this work)
                dd = torch.remainder(pos[:, :, None] - pos[:, None, :] + half, self.wh) - half
                nd2 = (dd ** 2).sum(-1)
                both = alive[:, :, None] & alive[:, None, :] & ~torch.eye(P, dtype=torch.bool, device=dev)[None]
            if Q:   # predators: chase nearest living prey in range, bite on contact, pause after a bite
                if HERD:
                    nbr = (both & (nd2 < cfg.herd_radius ** 2)).float().sum(2)                    # (K,P)
                delta = torch.remainder(pos[:, None] - ppos[:, :, None] + half, self.wh) - half     # (K,Q,P,2), wraps
                dist2 = torch.where(alive[:, None, :], (delta ** 2).sum(-1), inf)
                if cfg.pred_sense_still >= 0:    # Step 8b: moving prey are noticed from farther away
                    rng_p = cfg.pred_sense_still + (cfg.pred_sense - cfg.pred_sense_still) * torch.clamp(speed / cfg.speed_max, 0, 1)
                    seen = dist2 < (rng_p ** 2)[:, None, :]                                         # (K,Q,P)
                    dsee = torch.where(seen, dist2, inf)
                else:
                    dsee = torch.where(dist2 < cfg.pred_sense ** 2, dist2, inf)
                if OBS:                          # no seeing through rock: sample 6 points along each sight line
                    fr = self.los_fr
                    pts = torch.remainder(ppos[:, :, None, None, :] + delta[:, :, :, None, :] * fr[:, None], self.wh)
                    los_blk = self._solid_at(pts).any(-1)
                    dsee = torch.where(los_blk, inf, dsee)
                    inr = dist2 < cfg.pred_sense ** 2
                    seen_any = (inr & ~los_blk).any(1)
                    hid_now = ((inr & los_blk).any(1) & ~seen_any & alive).float()
                    exp_now = (seen_any & alive).float()
                if HERD and cfg.pred_loner > 0:  # crowded prey look farther away -> loners are chased first
                    dsee = dsee * ((1 + cfg.pred_loner * nbr) ** 2)[:, None, :]
                nd, ni = dsee.min(2)                                                             # nearest noticed prey
                bd, bi_ = dist2.min(2)                                                           # nearest prey at all
                ready = pcool <= 0
                tv = delta.gather(2, ni[..., None, None].expand(-1, -1, 1, 2)).squeeze(2)
                hunt = ready & torch.isfinite(nd)
                phead = torch.where(hunt, torch.atan2(tv[..., 1], tv[..., 0]),
                                    phead + (self._rand(K, Q) - 0.5) * 0.6)
                bite = ready & (bd < cfg.pred_bite ** 2)                                         # contact bites anyone
                land = bite
                if HERD and cfg.pred_confuse > 0:  # confusion effect: bites on prey in a crowd often miss
                    pn = nbr.gather(1, bi_)                                                          # (K,Q)
                    land = bite & (self._rand(K, Q) * (1 + cfg.pred_confuse * pn) < 1)
                dmg = torch.zeros(K, P, **self.f).scatter_add(1, bi_, land.float() * cfg.pred_damage)
                energy = energy - dmg * alive
                bites = bites + (dmg > 0).float()
                if OBS:
                    bit_now = ((dmg > 0) & alive).float()
                pcool = torch.where(bite, torch.full_like(pcool, float(cfg.pred_cooldown)), torch.clamp(pcool - 1, min=0))
                pspd = torch.where(pcool > 0, zero, torch.full_like(pcool, cfg.pred_speed))
                npp = torch.remainder(ppos + torch.stack([torch.cos(phead), torch.sin(phead)], -1) * pspd[..., None], self.wh)
                if OBS:                          # predators can't pass rock either: stop and turn somewhere new
                    pb = self._solid_at(npp) & ~self._solid_at(ppos)
                    ppos = torch.where(pb[..., None], ppos, npp)
                    phead = torch.where(pb, phead + (self._rand(K, Q) + 0.5) * math.pi, phead)
                else:
                    ppos = npp
                # touch felt by prey next tick: closest predator, front or back of the body
                md, mq = dist2.min(1)                                                            # (K,P)
                dist = torch.sqrt(torch.clamp(md, max=1e12))
                tch = torch.clamp(1 - dist / cfg.touch_radius, 0, 1) * alive
                to_pred = -delta.gather(1, mq[:, None, :, None].expand(-1, 1, -1, 2)).squeeze(1)  # prey -> predator
                ahead = (torch.cos(heading) * to_pred[..., 0] + torch.sin(heading) * to_pred[..., 1]) > 0
                touchF, touchB = tch * ahead, tch * ~ahead
            if FLEE:                                 # Step 27: food runs from the nearest worm within its flee radius
                dfw = torch.remainder(food[:, None] - pos[:, :, None] + half, self.wh) - half    # (K,P,Fd,2) worm->food
                fd2 = torch.where(alive[:, :, None], (dfw ** 2).sum(-1), inf)                  # (K,P,Fd)
                md2, mw = fd2.min(1)                                                            # nearest worm per food
                near_n = (fd2 < R2f).float().sum(1)                                             # worms within radius
                frun_now = falive & (md2 < R2f) & self.fmover
                if self.fdrift:                      # Step 27b drift: movers always wander, blind to worms
                    frun_now = falive & self.fmover
                if TIRE:
                    frun_now = frun_now & (frest <= 0)
                away = dfw.gather(1, mw[:, None, :, None].expand(-1, 1, -1, 2)).squeeze(1)    # (K,Fd,2)
                fang = torch.atan2(away[..., 1], away[..., 0]) + (self._rand(K, Fd) * 2 - 1) * cfg.food_flee_wobble
                if self.fdrift:
                    self.fhead.copy_(self.fhead + (self._rand(K, Fd) * 2 - 1) * cfg.food_flee_wobble)
                    fang = self.fhead
                fmv = torch.stack([torch.cos(fang), torch.sin(fang)], -1) * cfg.food_flee_speed
                food = torch.where(frun_now[..., None], torch.remainder(food + fmv, self.wh), food)
                fstart = torch.where(frun_now & ~fled, self.ti.float().expand(K, Fd), fstart)
                fled = fled | frun_now
                if TIRE:
                    frun = torch.where(frun_now, frun + 1, torch.zeros_like(frun))
                    tired = frun >= cfg.food_tire_run
                    frest = torch.where(tired, torch.full_like(frest, float(cfg.food_tire_rest)), torch.clamp(frest - 1, min=0))
                    frun = torch.where(tired, torch.zeros_like(frun), frun)
                took = torch.zeros(K, Fd, dtype=torch.bool, device=dev)
            # eating: parallel rounds, random winner per contested food (branch-free)
            can = alive & (energy < self.gut_cap - cfg.food_value)
            if DIG:                                  # gut must have room for a whole meal; satiety counts the gut too
                can = alive & (stomach <= cfg.stomach_cap - cfg.food_value) & (energy + stomach < self.gut_cap - cfg.food_value)
            d2 = ((pos[:, :, None, :] - food[:, None, :, :]) ** 2).sum(-1)
            if SENSE:                                # on a food lawn: any food within 20 units (felt next tick)
                onfood = (((d2 < 400.0) & falive[:, None, :]).any(2) & alive).float()
            nearf = (((d2 < 400.0) & falive[:, None, :]).any(2) & alive).float()     # within 20 units of food
            if CORR:                                 # Step 28: first arrival at the worm's own food
                got = alive & (((pos - self.goal) ** 2).sum(-1) < cfg.corridor_reach ** 2)
                self.carr.copy_(torch.where(got & (self.carr >= TT), self.wage[:, None].expand(-1, P), self.carr))
                self.wage += 1                       # world age (worlds can be restarted one by one: step28 streaming)
            reach = (d2 <= r2) & falive[:, None, :] & can[:, :, None]
            ate = torch.zeros(K, P, dtype=torch.bool, device=dev)
            for _ in range(3):
                best, pick = (self._rand(K, P, Fd) * reach).max(2)
                has = best > 0
                prio = self._rand(K, P) * has
                key = torch.where(has, self.kidx[:, None] * Fd + pick, torch.full_like(pick, BIG - 1))
                top = torch.zeros(BIG, **self.f).scatter_reduce(0, key.view(-1), prio.view(-1), 'amax')
                win = has & (prio == top[key])
                ate = ate | win
                taken = torch.zeros(BIG, **self.f).scatter_reduce(0, key.view(-1), win.view(-1).float(), 'amax')
                wf = taken[:K * Fd].view(K, Fd) > 0
                falive = falive & ~wf
                reach = reach & ~win[:, :, None] & ~wf[:, None, :]
                if FLEE:
                    took = took | wf
            atef = ate.float()
            if FLEE:                                 # Step 27 bookkeeping: who caught what, how
                cf = took & fled
                self.flx += torch.stack([cf.float().sum(1), (cf & (near_n >= 2)).float().sum(1), took.float().sum(1),
                                         (ate & (speed_frac < 0.2)).float().sum(1),
                                         torch.where(cf, self.ti.float() - fstart, zero).sum(1),
                                         frun_now.float().sum(1)], 1)
            if DIG:                                  # food -> gut; gut -> energy, fastest when still
                stomach = stomach + atef * cfg.food_value
                frac = torch.clamp(speed / cfg.speed_max, 0, 1)
                dig = torch.minimum(stomach, cfg.dig_rate * (1 - (1 - cfg.dig_moving) * frac)) * alive
                stomach = stomach - dig
                energy = energy + dig
            else:
                energy = energy + atef * cfg.food_value
            size = size + atef * cfg.size_per_food
            eaten = eaten + atef
            lifetime = lifetime + alive.float()
            esum = esum + torch.where(alive, torch.clamp(energy, min=0), zero)
            fullness = (energy + stomach) if DIG else energy
            H = torch.clamp(H + self.h_rate * (torch.clamp(1 - fullness / self.gut_cap, 0, 1) - H) - self.meal_drop * atef, 0, 1)
            # clumping: distance from each living worm to its nearest living neighbour (wraps at edges)
            if not CORR:
                nnd = torch.sqrt(torch.where(both, nd2, inf).min(2).values)
                okn = torch.isfinite(nnd)
                self.nn += torch.stack([torch.where(okn, nnd, zero).sum(1), okn.float().sum(1)], 1)
            if OBS:
                nearpos = self._solid_at(pos, self.nearw)
                nw = nearpos & alive
                self.wall += torch.stack([nw.float().sum(1), alive.float().sum(1)], 1)
                if Q:
                    af, nwf, npf = alive.float(), nw.float(), nearpos.float()
                    died = (alive & (energy <= 0)).float()
                    self.odiag += torch.stack([nwf.sum(1), (af - nwf).sum(1), (bit_now * nwf).sum(1),
                                               (bit_now * (af - nwf)).sum(1), (died * npf).sum(1),
                                               (died * (1 - npf)).sum(1), hid_now.sum(1), exp_now.sum(1),
                                               (bump * af).sum(1), af.sum(1)], 1)
            full = (alive & (energy >= self.full_e)).float()
            hung = (alive & (energy < self.hungry_e)).float()
            self.spd += torch.stack([(speed_frac * alive).sum(1), alive.float().sum(1)], 1)
            self.beh += torch.stack([(tumble & alive).float().sum(1), (turn.abs() * alive).sum(1), nearf.sum(1),
                                     alive.float().sum(1)], 1)
            self.sat += torch.stack([(speed_frac * full).sum(1), full.sum(1),
                                     (speed_frac * hung).sum(1), hung.sum(1)], 1)
            if self.recbuf is not None:
                ri, t1 = self.rec_idx, self.ti.view(1)
                for name, x in (('pos', pos), ('energy', energy), ('alive', alive), ('heading', heading), ('pred', ppos)):
                    self.recbuf[name].index_copy_(0, t1, x.index_select(0, ri)[None].to(self.recbuf[name].dtype))
            alive = alive & (energy > 0)
            # regrowth: up to nmax dead foods per world, as many as this tick's schedule says
            sc = self._rand(K, Fd) * (~falive) - falive.float()
            val, idx = sc.topk(self.nmax, dim=1)
            ok = (val >= 0) & (self.ar_nmax[None, :] < nrow[j])
            ci = (self._rand(K, self.nmax) * self.C).long().clamp(max=self.C - 1)
            cen = self.centers.gather(1, ci[..., None].expand(-1, -1, 2))
            p = cen + torch.randn(K, self.nmax, 2, generator=self.gen, **self.f) * cfg.patch_spread
            p = torch.minimum(torch.clamp(p, min=0), self.wh - 1)
            if OBS:                                  # food that would grow inside rock doesn't
                ok = ok & ~self._solid_at(p)
            old = food.gather(1, idx[..., None].expand(-1, -1, 2))
            food = food.scatter(1, idx[..., None].expand(-1, -1, 2), torch.where(ok[..., None], p, old))
            falive = falive.scatter(1, idx, falive.gather(1, idx) | ok)
            if FLEE:                                 # regrown food starts calm
                fled = fled.scatter(1, idx, fled.gather(1, idx) & ~ok)
                if TIRE:
                    frun = frun.scatter(1, idx, torch.where(ok, zero, frun.gather(1, idx)))
                    frest = frest.scatter(1, idx, torch.where(ok, zero, frest.gather(1, idx)))
            if self.recbuf is not None:
                t1 = self.ti.view(1)
                self.recbuf['food'].index_copy_(0, t1, food.index_select(0, self.rec_idx)[None].half())
                self.recbuf['falive'].index_copy_(0, t1, falive.index_select(0, self.rec_idx)[None])
            self.ti.add_(1)
        # write back into the fixed buffers (needed for graph replay)
        for name in self.brain.state_names:
            getattr(self.brain, name).copy_(bs[name])
        for name, val in (('pos', pos), ('heading', heading), ('size', size),
                          ('energy', energy), ('H', H), ('alive', alive), ('eaten', eaten), ('lifetime', lifetime),
                          ('esum', esum), ('food', food), ('falive', falive), ('prev', prev), ('ppos', ppos),
                          ('phead', phead), ('pcool', pcool), ('touchF', touchF), ('touchB', touchB), ('bites', bites),
                          ('stomach', stomach), ('pprev', pprev), ('bump', bump), ('onfood', onfood)):
            getattr(self, name).copy_(val)
        if self.flee_on:
            for name, val in (('fled', fled), ('fstart', fstart), ('frun', frun), ('frest', frest)):
                getattr(self, name).copy_(val)
        self.bi.add_(1)

    # ------------------------------------------------------------------ run one generation
    def run(self, genomes, rngs):
        n_blocks = self.cfg.ticks_per_generation // BLOCK
        if self.use_graph and self.graph is None:
            self.load(genomes, rngs)
            s = torch.cuda.Stream()
            s.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(s):                   # warm-up, required before recording
                for _ in range(3):
                    self._block()
            torch.cuda.current_stream().wait_stream(s)
            self.graph = torch.cuda.CUDAGraph()
            if self.gen is not None:
                self.graph.register_generator_state(self.gen)
            with torch.cuda.graph(self.graph):
                self._block()
        self.load(genomes, rngs)
        idle, t_b = gpu_idle_fraction(), time.perf_counter()
        for i in range(n_blocks):
            if self.graph is not None:
                self.graph.replay()
            else:
                self._block()
            if idle and i % 5 == 4:                  # quiet mode: rest the GPU between short bursts (results unchanged)
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                busy = time.perf_counter() - t_b
                time.sleep(busy * idle / (1 - idle))
                t_b = time.perf_counter()
        T, cfg = self.cfg.ticks_per_generation, self.cfg
        if self.fitness_mode == 'energy':          # average energy held (Step 3; can be gamed by idling, see 3e)
            fit = self.esum / T / cfg.food_value
        elif self.fitness_mode == 'eaten':         # Step 27b: food eaten only (no survival tie-break: idling earns 0)
            fit = self.eaten.clone()
        elif self.fitness_mode == 'end':           # energy left at the end (dead = 0) + time survived as tie-break
            fit = torch.where(self.alive, self.energy, torch.zeros_like(self.energy)) / cfg.food_value + self.lifetime / T
        else:                                      # 'food': food eaten + time survived (Steps 1-2, 4)
            fit = self.eaten + self.lifetime / T
        fit, eaten, esum, alive, sat, bites, nn, wall, odiag = (x.cpu().numpy() for x in (
            fit, self.eaten, self.esum, self.alive, self.sat, self.bites, self.nn, self.wall, self.odiag))
        scost = self.sense_cost.cpu().numpy()
        gexp = self.gexp.cpu().numpy()
        rexp = self.rexp.cpu().numpy()
        mexp = self.mexp.cpu().numpy()
        spd = self.spd.cpu().numpy()
        beh, bexp, flx = self.beh.cpu().numpy(), self.bexp.cpu().numpy(), self.flx.cpu().numpy()
        carr = self.carr.cpu().numpy()
        fexp = self.form['exp'].cpu().numpy() if self.form is not None else None
        fpaid = self.form['paid'].cpu().numpy() if self.form is not None else None
        with np.errstate(invalid='ignore', divide='ignore'):
            sf_full, sf_hungry = sat[:, 0] / sat[:, 1], sat[:, 2] / sat[:, 3]
        stats = [dict(mean_food=float(eaten[k].mean()), mean_energy=float((esum[k] / T).mean()),
                      fitness=float(fit[k].mean()), survivors=int(alive[k].sum()), ticks=T,
                      speed_full=float(sf_full[k]), speed_hungry=float(sf_hungry[k]),
                      mean_speed=float(spd[k, 0] / max(spd[k, 1], 1.0)),
                      # 2026-11-16 behaviour measures (all runs): reversals (tumbles) per worm-tick, mean |turn| per
                      # tick, share of time within 20 units of food
                      reversal_rate=float(beh[k, 0] / max(beh[k, 3], 1.0)),
                      turn_rate=float(beh[k, 1] / max(beh[k, 3], 1.0)),
                      near_food=float(beh[k, 2] / max(beh[k, 3], 1.0)),
                      # Step 25 beacon: mean field value under living worms (time in the circle), mean distance to the
                      # centre, tick when half the living worms were first inside the circle (= ticks if never)
                      beacon_occ=float(bexp[k, 0] / max(bexp[k, 2], 1.0)) if self.bea_on else float('nan'),
                      beacon_dist=float(bexp[k, 1] / max(bexp[k, 2], 1.0)) if self.bea_on else float('nan'),
                      beacon_arrival=float(bexp[k, 3]) if self.bea_on else float('nan'),
                      # Step 27 fleeing food: catches of food that had fled, how many with another worm within the
                      # flee radius (group), all food taken, eats by a worm under 20 % speed (ambush), summed chase
                      # ticks of caught fleeing food, food-ticks spent running
                      flee=flx[k].tolist() if self.flee_on else None,
                      # Step 28: arrival tick of each worm at its corridor's food (ticks_per_generation = never)
                      corr_arrival=carr[k].tolist() if self.corr_on else None,
                      bites=float(bites[k].mean()),
                      nn_dist=float(nn[k, 0] / max(nn[k, 1], 1.0)),
                      near_wall=float(wall[k, 0] / max(wall[k, 1], 1.0)) if self.obs_on else float('nan'),
                      odiag=odiag[k].tolist() if self.obs_on else None,
                      sense_cost=(scost[k] / self.P).tolist() if self.sense_on else None,
                      # Step 21: where the worms spend their time. grav_pattern = mean pattern value under living
                      # worms (-1 lightest .. +1 heaviest; negative = they stay on light ground); grav_offset = the
                      # same in g units (x the world's strength)
                      # Step 22: mean speed command (0..1) during red and during green phases
                      speed_red=float(rexp[k, 0] / max(rexp[k, 1], 1.0)) if self.red_on else float('nan'),
                      speed_green=float(rexp[k, 2] / max(rexp[k, 3], 1.0)) if self.red_on else float('nan'),
                      grav_offset=float(gexp[k, 0] / max(gexp[k, 2], 1.0)) if self.grav_on else float('nan'),
                      grav_pattern=float(gexp[k, 1] / max(gexp[k, 2], 1.0)) if self.grav_on else float('nan'),
                      # Step 23: mean magnetic-field value (0..1) under living worms = time spent inside the circles
                      mag_field=float(mexp[k, 0] / max(mexp[k, 1], 1.0)) if self.mag_on else float('nan'),
                      feature_exposure=(fexp[k] / (self.P * T)).tolist() if fexp is not None else None,
                      feature_cost=(fpaid[k] / self.P).tolist() if fexp is not None else None)
                 for k in range(self.K)]
        return fit.astype(np.float64), stats

    def recording(self):
        """The recorded worlds of the last generation as NumPy arrays (for the viewer)."""
        return {k: v.cpu().numpy() for k, v in self.recbuf.items()} if self.recbuf is not None else None


def evolve(cond, seeds, generations=GENERATIONS, out=OUT, device='cuda', graph=True, quiet=False, watch=0,
           eval_worlds=1, checkpoint_every=0, clonal=0, init=None, brains=0, setup=None, freeze=None, on_gen=None,
           deadline=None, peakstop=None):
    """watch: record the first `watch` seeds every generation for the live viewer (python -m ecosim.viewer).
    eval_worlds: score every brain on this many different worlds per generation and average (less luck in
                 selection; costs eval_worlds x the time). 1 = as before (identical results).
    checkpoint_every: also save each seed's best brain every N generations (ckpt_g<N>.npy), for re-testing.
    clonal: G > 0 = clonal-group scoring (Step 11): each brain is scored by G copies of itself sharing a world
            that is a G / population-sized copy of the normal one (area, food patches, regrowth scaled), so densities
            match the normal world. All groups of a seed get the
            SAME world each generation. Stops evolution from rewarding stealing food from your own kind
            (the tragedy of the commons found in Step 10), and matches the clone-based fair test.
          clonal=60 (= worm_population) gives full-size worlds, exactly like the fair test (Step 19).
    brains: brains per seed in clonal mode (default worm_population). eval_worlds: clonal mode scores every brain
          on this many different worlds per generation and averages (Step 19).
    init: {seed: genome} = start each seed's population from that brain (it + mutants of it) instead of random
          brains (clonal mode only; Step 14a).
    deadline: (clonal mode only) a time.time() value, or a function returning True when it is time to stop. Checked
          before every generation; on stop the best brains + history so far are saved as usual (Step 20).
    peakstop: (clonal mode only) an ecosim.peakstop.PeakStop = the owner's PEAK-STOP rule for breeding runs
          (2026-11-23): at each checkpoint, a seed whose skill has passed its peak is interbred and continues, and
          ends after the allowed restarts; the run stops early when all seeds ended. Saves peak_genome.npy."""
    opts, conn = CONDITIONS[cond], Connectome()
    cfg = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng(list(seeds)).integers(2**62)))
    P = cfg.worm_population
    if clonal:
        return _evolve_clonal(cond, seeds, generations, out, device, graph, quiet, checkpoint_every, clonal, init,
                              brains, eval_worlds, setup, freeze, on_gen, deadline, peakstop=peakstop)
    W = eval_worlds
    # extra worlds get their own random streams, so W = 1 uses exactly the old stream (same results as before)
    wrngs = [[rngs[k]] + [np.random.default_rng([s, 7919, i]) for i in range(1, W)] for k, s in enumerate(seeds)]
    sim = FastSim(cfg, opts, conn, len(seeds) * W, P, dev, graph, gen, record=range(min(watch, len(seeds))))
    live = LIVE / cond if watch else None
    if live:
        live.mkdir(parents=True, exist_ok=True)
    pop = np.stack([w.random_genomes(conn, P, r, opts) for r in rngs])
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist, best = [[] for _ in seeds], [None] * len(seeds)
    mode = 'CUDA graph' if sim.use_graph else 'no graph'
    print(f'{cond}: {len(seeds)} runs x {P} worms = {len(seeds) * P} brains on {dev} ({mode})', flush=True)
    t_all, times = time.perf_counter(), []
    for g in range(generations):
        t0 = time.perf_counter()
        if W == 1:
            fit, stats = sim.run(pop, rngs)
        else:                                            # same brains on W worlds; average the scores
            fitw, statw = sim.run(np.repeat(pop, W, axis=0), [r for k in range(len(seeds)) for r in wrngs[k]])
            fit = fitw.reshape(len(seeds), W, -1).mean(1)
            stats = [{key: float(np.mean([statw[k * W + i][key] for i in range(W)])) for key in statw[0]}
                     for k in range(len(seeds))]
        t1 = time.perf_counter()
        new = np.empty_like(pop)
        for k, r in enumerate(rngs):
            st = stats[k]; st['gen'] = g; hist[k].append(st)
            order = np.argsort(fit[k])[::-1][:n_elite]
            best[k] = pop[k, order[0]].copy()
            if checkpoint_every and (g + 1) % checkpoint_every == 0 and out is not None:
                d = out / f'{cond}_s{seeds[k]}'
                d.mkdir(parents=True, exist_ok=True)
                np.save(d / f'ckpt_g{g + 1}.npy', best[k])
            elites = pop[k, order]
            kids = [elites[i] for i in range(n_elite)]
            while len(kids) < P:
                kids.append(w.mutate(elites[r.integers(n_elite)], conn, cfg, r, opts)[0])
            new[k] = np.array(kids)
        pop = new
        if live:
            write_live(live, sim, fit, stats, hist, seeds[:watch], g, cond, cfg)
        t2 = time.perf_counter()
        times.append((t1 - t0, t2 - t1))
        if not quiet:
            fm = np.array([s['fitness'] for s in stats])
            print(f'{cond} gen {g:2d}  fitness mean {fm.mean():6.2f} (min {fm.min():6.2f}, max {fm.max():6.2f})  '
                  f'sim {t1 - t0:5.2f} s  evolve {t2 - t1:4.2f} s', flush=True)
    if out is not None:
        for k, s in enumerate(seeds):
            d = out / f'{cond}_s{s}'
            d.mkdir(parents=True, exist_ok=True)
            np.save(d / 'best_genome.npy', best[k])
            (d / 'history.json').write_text(json.dumps(hist[k], indent=1))
        print(f'saved {out}  ({time.perf_counter() - t_all:.0f} s total)', flush=True)
    return hist, times


def _evolve_clonal(cond, seeds, generations, out, device, graph, quiet, checkpoint_every, G, init=None, brains=0, W=1,
                   setup=None, freeze=None, on_gen=None, deadline=None, peakstop=None):
    """setup(sim, cfg): test-bench hook called once after the simulator is built (formula world, brain dials).
    freeze: bool gene mask; those genes never mutate (test bench).
    on_gen(g, k, fit (P,), per-brain stats list (P), elite indices, population (P, genes)): called every generation
    (test bench trait tracking: selection differential S and response R)."""
    opts, conn = CONDITIONS[cond], Connectome()
    base = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    PW = base.worm_population
    P = brains or PW                                     # brains per seed
    # A smaller copy of the normal world: area, food patches and regrowth all scaled by G / P, so worm density,
    # food density, food per worm and patches per worm are the same as in the normal world (60 worms, 6 patches).
    f = G / PW
    cfg = Config(seed=seeds[0], **dict(CFG_OVERRIDES.get(cond, {}), width=base.width * f ** 0.5,
                                       height=base.height * f ** 0.5, food_patches=max(1, round(base.food_patches * f)),
                                       food_regrow_per_tick=base.food_regrow_per_tick * f,
                                       predators=max(1, round(base.predators * f)) if base.predators else 0))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng(list(seeds) + [G]).integers(2**62)))
    K = len(seeds)
    sim = FastSim(cfg, opts, conn, K * P * W, G, dev, graph, gen)
    if setup is not None:
        setup(sim, cfg)
    from .worm3 import Opts3
    grow = isinstance(opts, Opts3)                       # Step 4 growing brains use worm3's genome + mutations
    if grow:
        from . import worm3 as g3
        names = g3.all_names(conn, opts)
        pop = np.stack([g3.random_genomes(conn, P, r, opts) for r in rngs]).astype(np.float32)
    else:
        pop = np.stack([w.random_genomes(conn, P, r, opts) for r in rngs])
    if init is not None:                                 # start from given brains: the brain itself + P-1 mutants
        assert not grow
        pop = np.stack([init[s] if np.ndim(init[s]) == 2 else              # a whole population (teacher) ...
                        np.stack([init[s]] + [w.mutate(init[s], conn, base, r, opts)[0] for _ in range(P - 1)])
                        for s, r in zip(seeds, rngs)])                    # ... or one brain + mutants of it
    n_elite = max(2, int(P * base.elite_fraction))
    hist, best = [[] for _ in seeds], [None] * K
    print(f'{cond}: {K} seeds x {P} brains, each scored as a group of {G} clones '
          f'on {W} world(s) each ({K * P * W} worlds of {cfg.width:.0f}x{cfg.height:.0f}, {K * P * W * G} worms on {dev}); '
          f'food per world {cfg.food_patches}x{cfg.food_per_patch}', flush=True)
    t_all = time.perf_counter()
    for g in range(generations):
        # Step 20: stop cleanly (keeping everything so far) at a clock time (deadline = time.time() value) or when
        # deadline is a function that returns True (e.g. 'the job that started me was cancelled').
        if deadline is not None and (deadline() if callable(deadline) else time.time() >= deadline):
            print(f'{cond}: STOP (deadline or cancel) before generation {g}; saving what we have', flush=True)
            break
        t0 = time.perf_counter()
        wseed = [[int(r.integers(2**63)) for _ in range(W)] for r in rngs]   # W world layouts per seed per generation
        world_rngs = [np.random.default_rng(wseed[k][v]) for k in range(K) for _ in range(P) for v in range(W)]
        genomes = pop.astype(np.float32).reshape(K * P, 1, 1, -1).repeat(W, 1).repeat(G, 2).reshape(K * P * W, G, -1)
        fitw, statw = sim.run(genomes, world_rngs)
        fit = fitw.mean(1).reshape(K, P, W).mean(2)                  # a brain's score = its groups' mean
        t1 = time.perf_counter()
        new = np.empty_like(pop)
        for k, r in enumerate(rngs):
            sk = statw[k * P * W:(k + 1) * P * W]
            st = {key: float(np.nanmean([x[key] for x in sk])) for key in sk[0] if not isinstance(sk[0][key], (list, type(None)))}
            st['fitness'] = float(fit[k].mean()); st['best_fitness'] = float(fit[k].max()); st['gen'] = g
            hist[k].append(st)
            order = np.argsort(fit[k])[::-1][:n_elite]
            if on_gen is not None:
                per = [{key: float(np.nanmean([x[key] for x in sk[b * W:(b + 1) * W]])) for key in sk[0]
                        if isinstance(sk[0][key], (int, float)) and not isinstance(sk[0][key], bool)} for b in range(P)]
                if sk[0].get('feature_exposure') is not None:
                    for b in range(P):
                        per[b]['feature_exposure'] = np.mean([x['feature_exposure'] for x in sk[b * W:(b + 1) * W]], 0).tolist()
                on_gen(g, k, fit[k], per, order, pop[k])
            best[k] = pop[k, order[0]].copy()
            if checkpoint_every and (g + 1) % checkpoint_every == 0 and out is not None:
                d = out / f'{cond}_s{seeds[k]}'
                d.mkdir(parents=True, exist_ok=True)
                np.save(d / f'ckpt_g{g + 1}.npy', best[k])
            elites = pop[k, order]
            kids = [elites[i] for i in range(n_elite)]
            while len(kids) < P:
                parent = elites[r.integers(n_elite)]
                kid = (g3.mutate(parent.astype(np.float64), conn, base, r, opts, names)[0] if grow
                       else w.mutate(parent, conn, base, r, opts)[0])
                if freeze is not None:
                    kid = np.where(freeze, parent, kid)
                kids.append(kid)
            new[k] = np.array(kids)
        pop = new
        if peakstop is not None and (g + 1) % peakstop.every == 0:            # owner's peak-stop rule (peakstop.py)
            pop = peakstop.step(g + 1, best, pop, rngs, n_elite)
        if not quiet:
            fm = np.array([h[-1]['fitness'] for h in hist]); nn = np.nanmean([h[-1]['nn_dist'] for h in hist])
            print(f'{cond} gen {g:3d}  fitness mean {fm.mean():5.2f} (min {fm.min():5.2f}, max {fm.max():5.2f})  '
                  f'nearest-worm dist {nn:6.1f}  sim {t1 - t0:5.2f} s  evolve {time.perf_counter() - t1:4.2f} s', flush=True)
        if peakstop is not None and peakstop.all_done():
            print(f'{cond}: PEAK-STOP - every seed has passed its last peak; run ends early after generation {g + 1}', flush=True)
            break
    if peakstop is not None and out is not None:
        peakstop.finish(out, cond, seeds, best)
    if out is not None:
        for k, s in enumerate(seeds):
            d = out / f'{cond}_s{s}'
            d.mkdir(parents=True, exist_ok=True)
            np.save(d / 'best_genome.npy', best[k])
            (d / 'history.json').write_text(json.dumps(hist[k], indent=1))
        print(f'saved {out}  ({time.perf_counter() - t_all:.0f} s total)', flush=True)
    return hist, None


LIVE = Path('runs/live')


def write_live(folder, sim, fit, stats, hist, seeds, gen, cond, cfg):
    """One file per generation for the viewer; written to a temp name, then renamed (never half-read)."""
    rec = sim.recording()
    R = len(seeds)
    data = dict(gen=gen, cond=cond, seeds=np.array(seeds), width=cfg.width, height=cfg.height, predators=cfg.predators,
                gut_cap=min(sim.gut_cap, 3000.0), fitness=fit[:R].astype(np.float32),
                history=np.array([[h['fitness'] for h in hist[k]] for k in range(len(hist))], np.float32),
                **rec)
    tmp = folder / 'latest_tmp.npz'
    np.savez(tmp, **data)
    tmp.replace(folder / 'latest.npz')


def bench(device='cuda'):
    print('Speed test: hunger_scarce, 3 generations each (first one includes setup / graph recording)')
    for K in (8, 32, 128):
        for graph in (False, True):
            _, t = evolve('hunger_scarce', list(range(1, K + 1)), 3, out=None, device=device, graph=graph, quiet=True)
            sim = np.mean([a for a, b in t[1:]]); evo = np.mean([b for a, b in t[1:]])
            print(f'  {K:4d} seeds  graph={str(graph):5s}  sim {sim:6.2f} s  evolve {evo:5.2f} s  '
                  f'-> {(sim + evo) / K:6.3f} s per seed per generation', flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    device = 'cpu' if '--cpu' in a else 'cuda'
    graph = '--nograph' not in a
    gens = int(a[a.index('--gens') + 1]) if '--gens' in a else None
    watch = int(a[a.index('--watch') + 1]) if '--watch' in a else 0
    out = Path(a[a.index('--out') + 1]) if '--out' in a else OUT
    if a[0] == 'confirm':
        for c in ('hunger_scarce', 'nohunger_scarce'):
            evolve(c, list(range(1, 33)), gens or 60, device=device, graph=graph, watch=watch)
    elif a[0] == 'scarce':
        for c in ('hunger_scarce', 'nohunger_scarce'):
            evolve(c, [1, 2, 3, 4], gens or 60, device=device, graph=graph, watch=watch)
    elif a[0] == 'bench':
        bench(device)
    elif a[0] == 'run':
        rest = [x for i, x in enumerate(a[2:], 2) if a[i - 1] not in ('--gens', '--watch', '--out')]
        evolve(a[1], [int(x) for x in rest if x.isdigit()], gens or GENERATIONS, out=out, device=device, graph=graph,
               watch=watch)
