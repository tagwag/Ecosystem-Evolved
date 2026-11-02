"""Batched Step 3: many runs (seeds) evolve side by side, sharing one GPU brain batch.

Why: on the GPU, one tick costs about the same for 60 worms or 3000 (see gpu_check).
So instead of 16 separate 60-worm runs, run all 16 at once as 960 worms.

Each run still has its own world, its own seed and its own population; runs never interact.
Only the brain math is pooled. The world (food, smell, eating) is vectorized NumPy over all runs.

    python -m ecosim.batch3 confirm            # Step 3c: hunger vs no hunger, scarce food, seeds 5-12
    python -m ecosim.batch3 scarce             # Step 3b: seeds 1-4
    python -m ecosim.batch3 run hunger_scarce 1 2 3 4 5 6 7 8 [--gens 60]
    add --cpu to run the brains on the CPU instead (slow, for checking)

Results: runs/step3_batch/<cond>_s<seed>/ (best_genome.npy, history.json), same format as step3.

Differences from step3.py (so results are comparable with each other, not bit-identical to step3):
- float32 GPU brain (as in worm2_gpu)
- eating is resolved in parallel: each hungry worm picks a random reachable food; if several pick
  the same food, a random one wins and the losers try again (up to 3 rounds). step3 instead
  walks worms one by one in random order. Both are fair; the outcomes differ slightly.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

from .config import Config
from .connectome import Connectome
from .sim import TAU, max_speed
from .step3 import CONDITIONS, CFG_OVERRIDES, GENERATIONS
from . import worm2 as w
from .worm2_gpu import WormBrainsTorch, pick_device
from .world import World

OUT = Path('runs/step3_batch')


class BatchWorld:
    """K independent worlds (same config), stored as stacked arrays."""

    def __init__(self, cfg: Config, rngs):
        self.cfg, self.rngs, K = cfg, rngs, len(rngs)
        ws = [World(cfg, r) for r in rngs]          # same layouts as step3 for the same seed
        self.centers = np.stack([x.patch_centers for x in ws])          # (K, C, 2)
        self.food = np.stack([x.food for x in ws])                      # (K, F, 2)
        self.alive = np.stack([x.food_alive for x in ws])               # (K, F)
        self.gw, self.gh = ws[0].gw, ws[0].gh
        self.acc = 0.0
        self.smell = np.zeros((K, self.gw, self.gh))
        self.update_smell()

    def update_smell(self):
        c = self.cfg
        for k in range(len(self.rngs)):
            f = self.food[k][self.alive[k]]
            g = np.zeros((self.gw, self.gh))
            gx = np.clip((f[:, 0] / c.smell_cell).astype(int), 0, self.gw - 1)
            gy = np.clip((f[:, 1] / c.smell_cell).astype(int), 0, self.gh - 1)
            np.add.at(g, (gx, gy), 1.0)
            g = gaussian_filter(g, c.smell_sigma_cells, mode='wrap')
            m = g.max()
            self.smell[k] = g / m if m > 0 else g

    def smell_at(self, pos):                          # pos (K, P, 2) -> (K, P)
        c = self.cfg
        gx = np.clip((pos[..., 0] / c.smell_cell).astype(int), 0, self.gw - 1)
        gy = np.clip((pos[..., 1] / c.smell_cell).astype(int), 0, self.gh - 1)
        return self.smell[np.arange(len(pos))[:, None], gx, gy]

    def eat(self, pos, can_eat, rng):
        """pos (K,P,2), can_eat (K,P) -> ate (K,P) bool. Parallel version of World.eat."""
        K, P = can_eat.shape
        r2 = self.cfg.eat_radius ** 2
        d2 = ((pos[:, :, None, :] - self.food[:, None, :, :]) ** 2).sum(-1)       # (K, P, F)
        reach = (d2 <= r2) & self.alive[:, None, :] & can_eat[:, :, None]
        ate = np.zeros((K, P), bool)
        F = self.food.shape[1]
        for _ in range(3):
            has = reach.any(2)
            if not has.any():
                break
            pick = np.argmax(reach * rng.random(reach.shape), axis=2)              # random reachable food
            kk, pp = np.nonzero(has)
            ff = pick[kk, pp]
            order = rng.permutation(len(kk))                                       # random winner per food
            key = (kk * F + ff)[order]
            _, first = np.unique(key, return_index=True)
            win = order[first]
            kw, pw, fw = kk[win], pp[win], ff[win]
            ate[kw, pw] = True
            self.alive[kw, fw] = False
            reach[kw, pw, :] = False
            reach[kw, :, fw] = False
        return ate

    def regrow(self):
        c = self.cfg
        self.acc += c.food_regrow_per_tick
        n = int(self.acc)
        if n == 0:
            return
        self.acc -= n
        for k, r in enumerate(self.rngs):
            dead = np.flatnonzero(~self.alive[k])
            if len(dead) == 0:
                continue
            idx = r.permutation(dead)[:n]
            cen = self.centers[k][r.integers(len(self.centers[k]), size=len(idx))]
            p = cen + r.normal(0, c.patch_spread, (len(idx), 2))
            self.food[k, idx] = np.clip(p, [0, 0], [c.width - 1, c.height - 1])
            self.alive[k, idx] = True


def run_generation_batch(cfg, genomes, rngs, conn, opts, device):
    """genomes (K, P, G). Returns fitness (K, P) and a list of K stat dicts."""
    K, P, _ = genomes.shape
    world = BatchWorld(cfg, rngs)
    move_rng = np.random.default_rng([int(r.integers(2**31)) for r in rngs])
    pos = np.stack([np.column_stack([r.uniform(0, cfg.width, P), r.uniform(0, cfg.height, P)]) for r in rngs])
    heading = np.stack([r.uniform(0, TAU, P) for r in rngs])
    size = np.full((K, P), cfg.start_size)
    energy = np.full((K, P), cfg.start_energy)
    H = np.clip(1 - energy / opts.gut_cap, 0, 1)
    alive = np.ones((K, P), bool)
    eaten, lifetime, esum = np.zeros((K, P)), np.zeros((K, P)), np.zeros((K, P))
    brains = WormBrainsTorch(conn, genomes.reshape(K * P, -1), opts, device)
    prev = world.smell_at(pos)
    T = cfg.ticks_per_generation
    for t in range(T):
        if t % cfg.smell_update_every == 0:
            world.update_smell()
        smell = world.smell_at(pos)
        d = np.clip((smell - prev) * 20.0, -1, 1)
        prev = smell
        p_tumble, speed_frac, turn = (x.reshape(K, P) for x in
                                      brains.step(smell.ravel(), d.ravel(), H.ravel()))
        tumble = move_rng.random((K, P)) < p_tumble
        heading = np.where(tumble, move_rng.uniform(0, TAU, (K, P)), heading + np.clip(turn, -0.5, 0.5))
        speed = speed_frac * max_speed(cfg, size)
        step = np.stack([np.cos(heading), np.sin(heading)], -1) * speed[..., None]
        pos = np.where(alive[..., None], (pos + step) % [cfg.width, cfg.height], pos)
        energy -= np.where(alive, cfg.base_cost + cfg.move_cost * speed, 0.0)
        ate = world.eat(pos, alive & (energy < opts.gut_cap - cfg.food_value), move_rng)
        energy += ate * cfg.food_value
        size += ate * cfg.size_per_food
        eaten += ate
        lifetime += alive
        esum += np.where(alive, np.maximum(energy, 0), 0.0)
        H = np.clip(H + opts.h_rate * (np.clip(1 - energy / opts.gut_cap, 0, 1) - H) - opts.meal_drop * ate, 0, 1)
        alive &= energy > 0
        world.regrow()
        if not alive.any():
            break
    fit = esum / T / cfg.food_value if opts.fitness == 'energy' else eaten + lifetime / T
    stats = [dict(mean_food=float(eaten[k].mean()), mean_energy=float((esum[k] / T).mean()),
                  fitness=float(fit[k].mean()), survivors=int(alive[k].sum()), ticks=t + 1) for k in range(K)]
    return fit, stats


def evolve_batch(cond, seeds, generations=GENERATIONS, out=OUT, device='cuda'):
    opts, conn = CONDITIONS[cond], Connectome()
    cfg = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    P = cfg.worm_population
    pop = np.stack([w.random_genomes(conn, P, r, opts) for r in rngs])
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist = [[] for _ in seeds]
    best = [None] * len(seeds)
    print(f'{cond}: {len(seeds)} runs x {P} worms = {len(seeds) * P} brains on {dev}', flush=True)
    for gen in range(generations):
        t0 = time.perf_counter()
        fit, stats = run_generation_batch(cfg, pop, rngs, conn, opts, dev)
        new = np.empty_like(pop)
        for k, r in enumerate(rngs):
            st = stats[k]; st['gen'] = gen; hist[k].append(st)
            order = np.argsort(fit[k])[::-1][:n_elite]
            best[k] = pop[k, order[0]].copy()
            elites = pop[k, order]
            kids = [elites[i] for i in range(n_elite)]
            while len(kids) < P:
                kids.append(w.mutate(elites[r.integers(n_elite)], conn, cfg, r, opts)[0])
            new[k] = np.array(kids)
        pop = new
        f = np.array([s['fitness'] for s in stats])
        print(f'{cond} gen {gen:2d}  fitness mean {f.mean():6.2f} (min {f.min():6.2f}, max {f.max():6.2f})  '
              f'{time.perf_counter() - t0:5.1f} s', flush=True)
    for k, s in enumerate(seeds):
        d = out / f'{cond}_s{s}'
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / 'best_genome.npy', best[k])
        (d / 'history.json').write_text(json.dumps(hist[k], indent=1))
    print('saved', out, flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    device = 'cpu' if '--cpu' in a else 'cuda'
    gens = int(a[a.index('--gens') + 1]) if '--gens' in a else None
    if a[0] == 'confirm':
        for c in ('hunger_scarce', 'nohunger_scarce'):
            evolve_batch(c, list(range(5, 13)), gens or 60, device=device)
    elif a[0] == 'scarce':
        for c in ('hunger_scarce', 'nohunger_scarce'):
            evolve_batch(c, [1, 2, 3, 4], gens or 60, device=device)
    elif a[0] == 'run':
        rest = [x for i, x in enumerate(a[2:], 2) if a[i - 1] != '--gens']
        seeds = [int(x) for x in rest if x.isdigit()]
        evolve_batch(a[1], seeds, gens or GENERATIONS, device=device)
