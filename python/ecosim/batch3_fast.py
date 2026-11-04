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
        self.centers, self.food = z(K, self.C, 2), z(K, self.Fd, 2)
        self.falive = torch.zeros(K, self.Fd, dtype=torch.bool, device=dev)
        self.smap, self.prev = z(K, self.gw, self.gh), z(K, P)
        # Step 11 worm scent: field from worm positions, sensed like food smell
        self.pher_on = cfg.pheromone
        self.pmap, self.pprev = z(K, self.gw, self.gh), z(K, P)
        self.pkern, self.pkr = gauss_kernel(cfg.pher_sigma_cells, dev)
        self.pnorm = float(self.pkern[self.pkr] ** 2) * cfg.pher_full
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
        self.size.fill_(cfg.start_size); self.energy.fill_(cfg.start_energy)
        self.H.copy_(torch.clamp(1 - self.energy / self.gut_cap, 0, 1))
        self.alive.fill_(True)
        self.eaten.zero_(); self.lifetime.zero_(); self.esum.zero_(); self.bi.zero_()
        self.sat.zero_(); self.ti.zero_(); self.nn.zero_()
        self.touchF.zero_(); self.touchB.zero_(); self.bites.zero_(); self.pcool.zero_(); self.stomach.zero_()
        self.bump.zero_(); self.wall.zero_()
        if self.Q:
            self.ppos.copy_(torch.rand(K, self.Q, 2, generator=self.gen, **f) * self.wh)
            self.phead.copy_(torch.rand(K, self.Q, generator=self.gen, **f) * TAU)
        self.smap.copy_(self._smell_map())
        self.prev.copy_(self._smell_at(self.pos))
        if self.pher_on:
            self.pmap.copy_(self._pher_map(self.pos, self.alive))
            self.pprev.copy_(self._smell_at(self.pos, self.pmap))

    # ------------------------------------------------------------------ pieces
    def _solid_at(self, p, grid=None):
        """Obstacle lookup for points p (K, ..., 2) -> bool (K, ...)."""
        cfg = self.cfg
        gx = torch.clamp((p[..., 0] / cfg.obs_cell).long(), 0, self.ogw - 1)
        gy = torch.clamp((p[..., 1] / cfg.obs_cell).long(), 0, self.ogh - 1)
        idx = (gx * self.ogh + gy).reshape(self.K, -1)
        return (self.solid if grid is None else grid).gather(1, idx).view(p.shape[:-1])

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
        self.smap.copy_(self._smell_map())
        pprev = self.pprev
        if self.pher_on:
            self.pmap.copy_(self._pher_map(pos, alive))
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
            bs, (p_tumble, speed_frac, turn) = self.brain.step(bs, smell.view(-1), d.view(-1), H.view(-1), alarm, touch, pher,
                                                               bump.view(-1) if OBS else None)
            p_tumble, speed_frac, turn = p_tumble.view(K, P), speed_frac.view(K, P), turn.view(K, P)
            tumble = self._rand(K, P) < p_tumble
            heading = torch.where(tumble, self._rand(K, P) * TAU, heading + torch.clamp(turn, -0.5, 0.5))
            speed = speed_frac * torch.clamp(cfg.speed_slope * size + cfg.speed_max, cfg.speed_min, cfg.speed_max)
            step = torch.stack([torch.cos(heading), torch.sin(heading)], -1) * speed[..., None]
            npos = torch.remainder(pos + step, self.wh)
            if OBS:                                  # rock blocks the move; the worm feels the bump next tick
                blk = self._solid_at(npos) & ~self._solid_at(pos)     # (a worm stuck inside rock may leave)
                bump = (alive & blk).float()
                pos = torch.where((alive & ~blk)[..., None], npos, pos)
            else:
                pos = torch.where(alive[..., None], npos, pos)
            energy = energy - torch.where(alive, cfg.base_cost + cfg.move_cost * speed, zero)
            # nearest-neighbour distances (clumping measure) and neighbour counts (Step 14b herd predators)
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
                    fr = torch.tensor([0.15, 0.3, 0.45, 0.6, 0.75, 0.9], **self.f)
                    pts = torch.remainder(ppos[:, :, None, None, :] + delta[:, :, :, None, :] * fr[:, None], self.wh)
                    dsee = torch.where(self._solid_at(pts).any(-1), inf, dsee)
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
            # eating: parallel rounds, random winner per contested food (branch-free)
            can = alive & (energy < self.gut_cap - cfg.food_value)
            if DIG:                                  # gut must have room for a whole meal; satiety counts the gut too
                can = alive & (stomach <= cfg.stomach_cap - cfg.food_value) & (energy + stomach < self.gut_cap - cfg.food_value)
            d2 = ((pos[:, :, None, :] - food[:, None, :, :]) ** 2).sum(-1)
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
            atef = ate.float()
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
            nnd = torch.sqrt(torch.where(both, nd2, inf).min(2).values)
            okn = torch.isfinite(nnd)
            self.nn += torch.stack([torch.where(okn, nnd, zero).sum(1), okn.float().sum(1)], 1)
            if OBS:
                nw = self._solid_at(pos, self.nearw) & alive
                self.wall += torch.stack([nw.float().sum(1), alive.float().sum(1)], 1)
            full = (alive & (energy >= self.full_e)).float()
            hung = (alive & (energy < self.hungry_e)).float()
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
                          ('stomach', stomach), ('pprev', pprev), ('bump', bump)):
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
        for _ in range(n_blocks):
            if self.graph is not None:
                self.graph.replay()
            else:
                self._block()
        T, cfg = self.cfg.ticks_per_generation, self.cfg
        if self.fitness_mode == 'energy':          # average energy held (Step 3; can be gamed by idling, see 3e)
            fit = self.esum / T / cfg.food_value
        elif self.fitness_mode == 'end':           # energy left at the end (dead = 0) + time survived as tie-break
            fit = torch.where(self.alive, self.energy, torch.zeros_like(self.energy)) / cfg.food_value + self.lifetime / T
        else:                                      # 'food': food eaten + time survived (Steps 1-2, 4)
            fit = self.eaten + self.lifetime / T
        fit, eaten, esum, alive, sat, bites, nn, wall = (x.cpu().numpy() for x in (fit, self.eaten, self.esum, self.alive,
                                                                                  self.sat, self.bites, self.nn, self.wall))
        with np.errstate(invalid='ignore', divide='ignore'):
            sf_full, sf_hungry = sat[:, 0] / sat[:, 1], sat[:, 2] / sat[:, 3]
        stats = [dict(mean_food=float(eaten[k].mean()), mean_energy=float((esum[k] / T).mean()),
                      fitness=float(fit[k].mean()), survivors=int(alive[k].sum()), ticks=T,
                      speed_full=float(sf_full[k]), speed_hungry=float(sf_hungry[k]),
                      bites=float(bites[k].mean()),
                      nn_dist=float(nn[k, 0] / max(nn[k, 1], 1.0)),
                      near_wall=float(wall[k, 0] / max(wall[k, 1], 1.0)) if self.obs_on else float('nan'))
                 for k in range(self.K)]
        return fit.astype(np.float64), stats

    def recording(self):
        """The recorded worlds of the last generation as NumPy arrays (for the viewer)."""
        return {k: v.cpu().numpy() for k, v in self.recbuf.items()} if self.recbuf is not None else None


def evolve(cond, seeds, generations=GENERATIONS, out=OUT, device='cuda', graph=True, quiet=False, watch=0,
           eval_worlds=1, checkpoint_every=0, clonal=0, init=None):
    """watch: record the first `watch` seeds every generation for the live viewer (python -m ecosim.viewer).
    eval_worlds: score every brain on this many different worlds per generation and average (less luck in
                 selection; costs eval_worlds x the time). 1 = as before (identical results).
    checkpoint_every: also save each seed's best brain every N generations (ckpt_g<N>.npy), for re-testing.
    clonal: G > 0 = clonal-group scoring (Step 11): each brain is scored by G copies of itself sharing a world
            that is a G / population-sized copy of the normal one (area, food patches, regrowth scaled), so densities
            match the normal world. All groups of a seed get the
            SAME world each generation. Stops evolution from rewarding stealing food from your own kind
            (the tragedy of the commons found in Step 10), and matches the clone-based fair test.
    init: {seed: genome} = start each seed's population from that brain (it + mutants of it) instead of random
          brains (clonal mode only; Step 14a)."""
    opts, conn = CONDITIONS[cond], Connectome()
    cfg = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng(list(seeds)).integers(2**62)))
    P = cfg.worm_population
    if clonal:
        return _evolve_clonal(cond, seeds, generations, out, device, graph, quiet, checkpoint_every, clonal, init)
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


def _evolve_clonal(cond, seeds, generations, out, device, graph, quiet, checkpoint_every, G, init=None):
    opts, conn = CONDITIONS[cond], Connectome()
    base = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    P = base.worm_population
    # A smaller copy of the normal world: area, food patches and regrowth all scaled by G / P, so worm density,
    # food density, food per worm and patches per worm are the same as in the normal world (60 worms, 6 patches).
    f = G / P
    cfg = Config(seed=seeds[0], **dict(CFG_OVERRIDES.get(cond, {}), width=base.width * f ** 0.5,
                                       height=base.height * f ** 0.5, food_patches=max(1, round(base.food_patches * f)),
                                       food_regrow_per_tick=base.food_regrow_per_tick * f,
                                       predators=max(1, round(base.predators * f)) if base.predators else 0))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng(list(seeds) + [G]).integers(2**62)))
    K = len(seeds)
    sim = FastSim(cfg, opts, conn, K * P, G, dev, graph, gen)
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
        pop = np.stack([np.stack([init[s]] + [w.mutate(init[s], conn, base, r, opts)[0] for _ in range(P - 1)])
                        for s, r in zip(seeds, rngs)])
    n_elite = max(2, int(P * base.elite_fraction))
    hist, best = [[] for _ in seeds], [None] * K
    print(f'{cond}: {K} seeds x {P} brains, each scored as a group of {G} clones '
          f'({K * P} worlds of {cfg.width:.0f}x{cfg.height:.0f}, {K * P * G} worms on {dev}); '
          f'food per world {cfg.food_patches}x{cfg.food_per_patch}', flush=True)
    t_all = time.perf_counter()
    for g in range(generations):
        t0 = time.perf_counter()
        wseed = [int(r.integers(2**63)) for r in rngs]               # one world layout per seed per generation
        world_rngs = [np.random.default_rng(wseed[k]) for k in range(K) for _ in range(P)]
        genomes = pop.astype(np.float32).reshape(K * P, 1, -1).repeat(G, 1)
        fitw, statw = sim.run(genomes, world_rngs)
        fit = fitw.mean(1).reshape(K, P)                             # a brain's score = its group's mean
        t1 = time.perf_counter()
        new = np.empty_like(pop)
        for k, r in enumerate(rngs):
            sk = statw[k * P:(k + 1) * P]
            st = {key: float(np.nanmean([x[key] for x in sk])) for key in sk[0]}
            st['fitness'] = float(fit[k].mean()); st['best_fitness'] = float(fit[k].max()); st['gen'] = g
            hist[k].append(st)
            order = np.argsort(fit[k])[::-1][:n_elite]
            best[k] = pop[k, order[0]].copy()
            if checkpoint_every and (g + 1) % checkpoint_every == 0 and out is not None:
                d = out / f'{cond}_s{seeds[k]}'
                d.mkdir(parents=True, exist_ok=True)
                np.save(d / f'ckpt_g{g + 1}.npy', best[k])
            elites = pop[k, order]
            kids = [elites[i] for i in range(n_elite)]
            while len(kids) < P:
                parent = elites[r.integers(n_elite)]
                kids.append(g3.mutate(parent.astype(np.float64), conn, base, r, opts, names)[0] if grow
                            else w.mutate(parent, conn, base, r, opts)[0])
            new[k] = np.array(kids)
        pop = new
        if not quiet:
            fm = np.array([h[-1]['fitness'] for h in hist]); nn = np.nanmean([h[-1]['nn_dist'] for h in hist])
            print(f'{cond} gen {g:3d}  fitness mean {fm.mean():5.2f} (min {fm.min():5.2f}, max {fm.max():5.2f})  '
                  f'nearest-worm dist {nn:6.1f}  sim {t1 - t0:5.2f} s  evolve {time.perf_counter() - t1:4.2f} s', flush=True)
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
