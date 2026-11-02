"""Fully-GPU batched Step 3: brains AND world run on the graphics card.

batch3.py put only the brains on the GPU; every tick it still copied data back to the CPU for
eating, smell and movement, so the GPU sat idle most of the time. Here the whole tick loop is
PyTorch tensors on the GPU, with no copy back until the generation ends. Only evolution
(picking parents, mutating genomes) stays on the CPU, once per generation.

    python -m ecosim.batch3_gpu confirm            # Step 3d: seeds 1-32, both conditions (hunger vs no hunger, scarce food)
    python -m ecosim.batch3_gpu scarce             # Step 3b: seeds 1-4
    python -m ecosim.batch3_gpu run hunger_scarce 5 6 7 8 [--gens 60] [--cpu]

Results: runs/step3_gpu_full/<cond>_s<seed>/ (best_genome.npy, history.json), same format as step3.

Same rules as batch3.py (parallel eating, float32). Differences, all small:
- random numbers come from one PyTorch generator per batch, so a seed's result depends on which
  other seeds share its batch. Rerun with the same seed list to reproduce.
- the smell blur is the same Gaussian as scipy (sigma 4 cells, wraps at the edges), done as a GPU
  convolution; values match scipy to float32 rounding.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

from .config import Config
from .connectome import Connectome, SENSORS
from .sim import TAU
from .step3 import CONDITIONS, CFG_OVERRIDES, GENERATIONS
from . import worm2 as w
from .worm2 import Layout, N_OUT, WormBrains2, readout_names
from .worm2_gpu import pick_device
from .world import World

OUT = Path('runs/step3_gpu_full')


class Brains:
    """Same equations as worm2.WormBrains2, tensors in and out (no CPU copies)."""

    def __init__(self, conn, genomes, opts, dev):
        B, N = len(genomes), conn.N
        L = Layout(conn, opts)
        f = dict(dtype=torch.float32, device=dev)
        g = torch.as_tensor(genomes, **f)
        pre = torch.as_tensor(conn.pre, device=dev)
        post = torch.as_tensor(conn.post, device=dev)
        mult = 1.0 + torch.clamp(g[:, :L.E], -3, 3)
        vals = torch.as_tensor(conn.w_norm, **f) * mult * WormBrains2.chem_scale            # (B, E)
        W = torch.zeros(B, N * N, **f)
        W.index_add_(1, pre * N + post, vals)                                                  # duplicates add up, like np.add.at
        self.W = W.view(B, N, N)
        self.G = torch.as_tensor(conn.G * WormBrains2.gap_scale, **f)
        self.G_deg = torch.as_tensor(conn.G_deg * WormBrains2.gap_scale, **f)
        sg = torch.exp(torch.clamp(g[:, L.sens], -3, 3))
        self.g_on, self.g_off, self.g_lvl = sg[:, 0], sg[:, 1], sg[:, 2]
        self.D = g[:, L.dev].reshape(B, L.R, N_OUT) * 10.0
        self.Dl = g[:, L.lvl].reshape(B, L.R, N_OUT) * 3.0
        self.bias = g[:, L.bias]
        self.rec = g[:, L.rec] * opts.receptor_scale if opts.hunger else None
        self.v = torch.zeros(B, N, **f)
        self.rd = torch.as_tensor(conn.ids(readout_names(conn, opts)), device=dev)
        self.rbar = torch.zeros(B, len(self.rd), **f)
        self.s_on, self.s_off, self.s_lvl = (torch.as_tensor(conn.ids(SENSORS[k]), device=dev)
                                             for k in ('on', 'off', 'level'))
        c = WormBrains2
        self.k_dt, self.inh, self.adapt = c.dt / c.tau, c.inhibition, c.adapt

    def step(self, smell, d_smell, H):
        v = self.v
        r = torch.tanh(torch.clamp(v, min=0))
        I = torch.bmm(r.unsqueeze(1), self.W).squeeze(1)
        I += v @ self.G - self.G_deg * v
        I -= self.inh * r.mean(1, keepdim=True)
        I[:, self.s_on] += (self.g_on * torch.clamp(d_smell, min=0))[:, None]
        I[:, self.s_off] += (self.g_off * torch.clamp(-d_smell, min=0))[:, None]
        I[:, self.s_lvl] += (self.g_lvl * smell)[:, None]
        if self.rec is not None:
            I += H[:, None] * self.rec
        self.v = v + self.k_dt * (-v + I)
        r = torch.tanh(torch.clamp(self.v, min=0))
        x = r[:, self.rd]
        dev = x - self.rbar
        self.rbar += self.adapt * (x - self.rbar)
        o = torch.einsum('pr,pro->po', dev, self.D) + torch.einsum('pr,pro->po', x, self.Dl) + self.bias
        return torch.sigmoid(o[:, 1] - 2.0) * 0.3, torch.sigmoid(o[:, 0] + 1.0), torch.tanh(o[:, 2]) * 0.4


def gauss_kernel(sigma, dev):
    r = int(4.0 * sigma + 0.5)                       # scipy's default truncate=4
    x = torch.arange(-r, r + 1, dtype=torch.float32, device=dev)
    k = torch.exp(-0.5 * (x / sigma) ** 2)
    return k / k.sum(), r


def blur_wrap(grid, k, r):
    """Separable Gaussian blur with wrap-around edges. grid (K, gw, gh)."""
    x = grid.unsqueeze(1)                                                        # (K,1,gw,gh)
    x = Fn.conv2d(Fn.pad(x, (0, 0, r, r), mode='circular'), k.view(1, 1, -1, 1))
    x = Fn.conv2d(Fn.pad(x, (r, r, 0, 0), mode='circular'), k.view(1, 1, 1, -1))
    return x.squeeze(1)


def run_generation_gpu(cfg, genomes, seeds_rng, conn, opts, dev, gen_t):
    """genomes (K,P,G) numpy. seeds_rng: K numpy rngs (world layouts, start positions).
    gen_t: torch.Generator on dev (all per-tick randomness). Returns fitness (K,P) numpy, stats."""
    K, P, _ = genomes.shape
    f = dict(dtype=torch.float32, device=dev)
    T = cfg.ticks_per_generation
    # --- worlds: layout from World() on the CPU (same as step3 for the same rng), then to the GPU
    ws = [World(cfg, r) for r in seeds_rng]
    centers = torch.as_tensor(np.stack([x.patch_centers for x in ws]), **f)        # (K,C,2)
    food = torch.as_tensor(np.stack([x.food for x in ws]), **f)                      # (K,F,2)
    falive = torch.as_tensor(np.stack([x.food_alive for x in ws]), device=dev)       # (K,F)
    gw, gh, Fd, C = ws[0].gw, ws[0].gh, food.shape[1], centers.shape[1]
    pos = torch.as_tensor(np.stack([np.column_stack([r.uniform(0, cfg.width, P), r.uniform(0, cfg.height, P)])
                                    for r in seeds_rng]), **f)
    heading = torch.as_tensor(np.stack([r.uniform(0, TAU, P) for r in seeds_rng]), **f)
    kern, kr = gauss_kernel(cfg.smell_sigma_cells, dev)
    kidx = torch.arange(K, device=dev)
    wh = torch.tensor([cfg.width, cfg.height], **f)

    def smell_map():
        gx = torch.clamp((food[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((food[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        cnt = torch.zeros(K, gw * gh, **f)
        cnt.scatter_add_(1, gx * gh + gy, falive.float())
        s = blur_wrap(cnt.view(K, gw, gh), kern, kr)
        m = s.amax(dim=(1, 2), keepdim=True)
        return torch.where(m > 0, s / m.clamp(min=1e-12), s)

    def smell_at(smap, p):
        gx = torch.clamp((p[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((p[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        return smap.view(K, -1).gather(1, gx * gh + gy)

    size = torch.full((K, P), cfg.start_size, **f)
    energy = torch.full((K, P), cfg.start_energy, **f)
    H = torch.clamp(1 - energy / opts.gut_cap, 0, 1)
    alive = torch.ones(K, P, dtype=torch.bool, device=dev)
    eaten, lifetime, esum = (torch.zeros(K, P, **f) for _ in range(3))
    brains = Brains(conn, genomes.reshape(K * P, -1), opts, dev)
    smap = smell_map()
    prev = smell_at(smap, pos)
    r2 = cfg.eat_radius ** 2
    acc = 0.0
    BIG = K * Fd + 1

    for t in range(T):
        if t % cfg.smell_update_every == 0:
            smap = smell_map()
        smell = smell_at(smap, pos)
        d = torch.clamp((smell - prev) * 20.0, -1, 1)
        prev = smell
        p_tumble, speed_frac, turn = (x.view(K, P) for x in brains.step(smell.view(-1), d.view(-1), H.view(-1)))
        tumble = torch.rand(K, P, generator=gen_t, **f) < p_tumble
        newh = torch.rand(K, P, generator=gen_t, **f) * TAU
        heading = torch.where(tumble, newh, heading + torch.clamp(turn, -0.5, 0.5))
        speed = speed_frac * torch.clamp(cfg.speed_slope * size + cfg.speed_max, cfg.speed_min, cfg.speed_max)
        step = torch.stack([torch.cos(heading), torch.sin(heading)], -1) * speed[..., None]
        pos = torch.where(alive[..., None], torch.remainder(pos + step, wh), pos)
        energy = energy - torch.where(alive, cfg.base_cost + cfg.move_cost * speed, torch.zeros_like(speed))

        # --- eating: parallel rounds, random winner per contested food
        can = alive & (energy < opts.gut_cap - cfg.food_value)
        d2 = ((pos[:, :, None, :] - food[:, None, :, :]) ** 2).sum(-1)                     # (K,P,F)
        reach = (d2 <= r2) & falive[:, None, :] & can[:, :, None]
        ate = torch.zeros(K, P, dtype=torch.bool, device=dev)
        for _ in range(3):
            score = torch.rand(K, P, Fd, generator=gen_t, **f) * reach
            best, pick = score.max(2)                                                     # random reachable food
            has = best > 0
            prio = torch.rand(K, P, generator=gen_t, **f) * has                          # random priority, 0 = no pick
            key = torch.where(has, kidx[:, None] * Fd + pick, torch.full_like(pick, BIG - 1))
            top = torch.zeros(BIG, **f).scatter_reduce(0, key.view(-1), prio.view(-1), 'amax')
            win = has & (prio == top[key])
            ate |= win
            wf = torch.zeros(K, Fd, dtype=torch.bool, device=dev)
            wf.view(-1).scatter_(0, key[win], True)
            falive &= ~wf
            reach &= ~win[:, :, None] & ~wf[:, None, :]
        atef = ate.float()
        energy = energy + atef * cfg.food_value
        size = size + atef * cfg.size_per_food
        eaten += atef
        lifetime += alive.float()
        esum += torch.where(alive, torch.clamp(energy, min=0), torch.zeros_like(energy))
        H = torch.clamp(H + opts.h_rate * (torch.clamp(1 - energy / opts.gut_cap, 0, 1) - H) - opts.meal_drop * atef, 0, 1)
        alive &= energy > 0

        # --- regrow: n random dead foods per world respawn around a random patch centre
        acc += cfg.food_regrow_per_tick
        n = int(acc)
        if n:
            acc -= n
            sc = torch.rand(K, Fd, generator=gen_t, **f) * (~falive) - (falive).float()   # dead: [0,1), alive: -1
            v, idx = sc.topk(min(n, Fd), dim=1)
            ok = v >= 0
            cen = centers.gather(1, torch.randint(C, (K, idx.shape[1]), generator=gen_t, device=dev)[..., None].expand(-1, -1, 2))
            p = cen + torch.randn(K, idx.shape[1], 2, generator=gen_t, **f) * cfg.patch_spread
            p = torch.minimum(torch.clamp(p, min=0), wh - 1)
            kk = kidx[:, None].expand_as(idx)[ok]
            food[kk, idx[ok]] = p[ok]
            falive[kk, idx[ok]] = True
        if t % 100 == 99 and not bool(alive.any()):        # rare check: avoids a CPU sync every tick
            break

    fit = esum / T / cfg.food_value if opts.fitness == 'energy' else eaten + lifetime / T
    fit, eaten, esum, alive = (x.cpu().numpy() for x in (fit, eaten, esum, alive))
    stats = [dict(mean_food=float(eaten[k].mean()), mean_energy=float((esum[k] / T).mean()),
                  fitness=float(fit[k].mean()), survivors=int(alive[k].sum()), ticks=t + 1) for k in range(K)]
    return fit.astype(np.float64), stats


def evolve(cond, seeds, generations=GENERATIONS, out=OUT, device='cuda'):
    opts, conn = CONDITIONS[cond], Connectome()
    cfg = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen_t = torch.Generator(device=dev)
    gen_t.manual_seed(int(np.random.default_rng(list(seeds)).integers(2**62)))
    P = cfg.worm_population
    pop = np.stack([w.random_genomes(conn, P, r, opts) for r in rngs])
    n_elite = max(2, int(P * cfg.elite_fraction))
    hist, best = [[] for _ in seeds], [None] * len(seeds)
    print(f'{cond}: {len(seeds)} runs x {P} worms = {len(seeds) * P} brains, world + brains on {dev}', flush=True)
    t_all = time.perf_counter()
    for gen in range(generations):
        t0 = time.perf_counter()
        fit, stats = run_generation_gpu(cfg, pop, rngs, conn, opts, dev, gen_t)
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
        fm = np.array([s['fitness'] for s in stats])
        print(f'{cond} gen {gen:2d}  fitness mean {fm.mean():6.2f} (min {fm.min():6.2f}, max {fm.max():6.2f})  '
              f'{time.perf_counter() - t0:5.1f} s', flush=True)
    for k, s in enumerate(seeds):
        d = out / f'{cond}_s{s}'
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / 'best_genome.npy', best[k])
        (d / 'history.json').write_text(json.dumps(hist[k], indent=1))
    print(f'saved {out}  ({time.perf_counter() - t_all:.0f} s total)', flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    device = 'cpu' if '--cpu' in a else 'cuda'
    gens = int(a[a.index('--gens') + 1]) if '--gens' in a else None
    if a[0] == 'confirm':
        for c in ('hunger_scarce', 'nohunger_scarce'):
            evolve(c, list(range(1, 33)), gens or 60, device=device)
    elif a[0] == 'scarce':
        for c in ('hunger_scarce', 'nohunger_scarce'):
            evolve(c, [1, 2, 3, 4], gens or 60, device=device)
    elif a[0] == 'run':
        rest = [x for i, x in enumerate(a[2:], 2) if a[i - 1] != '--gens']
        evolve(a[1], [int(x) for x in rest if x.isdigit()], gens or GENERATIONS, device=device)
