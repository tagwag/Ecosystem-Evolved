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
from .world import World

OUT = Path('runs/step3_fast')
BLOCK = 10           # ticks per graph replay; must equal cfg.smell_update_every
FULL, HUNGRY = 0.8, 0.4   # fractions of the gut cap, as in step3_analyze


class FastSim:
    def __init__(self, cfg, opts, conn, K, P, dev, use_graph, gen, record=()):
        """record: indices of worlds (0..K-1) to record every tick for the viewer (ecosim/viewer.py)."""
        assert cfg.smell_update_every == BLOCK and cfg.ticks_per_generation % BLOCK == 0
        self.cfg, self.opts, self.conn, self.K, self.P, self.dev, self.gen = cfg, opts, conn, K, P, dev, gen
        self.use_graph = use_graph and dev.type == 'cuda'
        self.graph = None
        f = self.f = dict(dtype=torch.float32, device=dev)
        B, N, E = K * P, conn.N, conn.n_edges
        L = self.L = Layout(conn, opts)
        # --- fixed connectome pieces
        self.pre = torch.as_tensor(conn.pre, device=dev)
        M = torch.zeros(E, N, **f)
        M[torch.arange(E, device=dev), torch.as_tensor(conn.post, device=dev)] = 1.0
        self.M = M                                                       # synapse -> target map
        self.w_base = torch.as_tensor(conn.w_norm * WormBrains2.chem_scale, **f)
        self.G = torch.as_tensor(conn.G * WormBrains2.gap_scale, **f)
        self.G_deg = torch.as_tensor(conn.G_deg * WormBrains2.gap_scale, **f)
        self.rd = torch.as_tensor(conn.ids(readout_names(conn, opts)), device=dev)
        self.s_on, self.s_off, self.s_lvl = (torch.as_tensor(conn.ids(SENSORS[k]), device=dev)
                                             for k in ('on', 'off', 'level'))
        c = WormBrains2
        self.k_dt, self.inh, self.adapt = c.dt / c.tau, c.inhibition, c.adapt
        # --- per-brain buffers (refilled each generation)
        z = lambda *s: torch.zeros(*s, **f)
        self.vals, self.g3 = z(B, E), z(B, 3)
        self.D, self.Dl, self.bias = z(B, L.R, N_OUT), z(B, L.R, N_OUT), z(B, N_OUT)
        self.rec = z(B, N) if opts.hunger else None
        self.v, self.rbar = z(B, N), z(B, L.R)
        # --- world buffers
        w0 = World(cfg, np.random.default_rng(0))
        self.gw, self.gh, self.Fd, self.C = w0.gw, w0.gh, len(w0.food), len(w0.patch_centers)
        self.centers, self.food = z(K, self.C, 2), z(K, self.Fd, 2)
        self.falive = torch.zeros(K, self.Fd, dtype=torch.bool, device=dev)
        self.smap, self.prev = z(K, self.gw, self.gh), z(K, P)
        self.pos, self.heading = z(K, P, 2), z(K, P)
        self.size, self.energy, self.H = z(K, P), z(K, P), z(K, P)
        self.alive = torch.zeros(K, P, dtype=torch.bool, device=dev)
        self.eaten, self.lifetime, self.esum = z(K, P), z(K, P), z(K, P)
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
        self.full_e, self.hungry_e = FULL * opts.gut_cap, HUNGRY * opts.gut_cap
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
                            falive=torch.zeros(T, R, self.Fd, dtype=torch.bool, device=dev))
        else:
            self.recbuf = None

    # ------------------------------------------------------------------ setup each generation
    def load(self, genomes, rngs):
        cfg, opts, L, f, K, P = self.cfg, self.opts, self.L, self.f, self.K, self.P
        g = torch.as_tensor(genomes.reshape(K * P, -1), **f)
        self.vals.copy_(self.w_base * (1.0 + torch.clamp(g[:, :L.E], -3, 3)))
        self.g3.copy_(torch.exp(torch.clamp(g[:, L.sens], -3, 3)))
        self.D.copy_(g[:, L.dev].reshape(-1, L.R, N_OUT) * 10.0)
        self.Dl.copy_(g[:, L.lvl].reshape(-1, L.R, N_OUT) * 3.0)
        self.bias.copy_(g[:, L.bias])
        if self.rec is not None:
            self.rec.copy_(g[:, L.rec] * opts.receptor_scale)
        self.v.zero_(); self.rbar.zero_()
        ws = [World(cfg, r) for r in rngs]                      # same layouts as step3 for the same rng
        self.centers.copy_(torch.as_tensor(np.stack([x.patch_centers for x in ws]), **f))
        self.food.copy_(torch.as_tensor(np.stack([x.food for x in ws]), **f))
        self.falive.copy_(torch.as_tensor(np.stack([x.food_alive for x in ws]), device=self.dev))
        self.pos.copy_(torch.as_tensor(np.stack([np.column_stack([r.uniform(0, cfg.width, P), r.uniform(0, cfg.height, P)])
                                                 for r in rngs]), **f))
        self.heading.copy_(torch.as_tensor(np.stack([r.uniform(0, TAU, P) for r in rngs]), **f))
        self.size.fill_(cfg.start_size); self.energy.fill_(cfg.start_energy)
        self.H.copy_(torch.clamp(1 - self.energy / opts.gut_cap, 0, 1))
        self.alive.fill_(True)
        self.eaten.zero_(); self.lifetime.zero_(); self.esum.zero_(); self.bi.zero_()
        self.sat.zero_(); self.ti.zero_()
        self.smap.copy_(self._smell_map())
        self.prev.copy_(self._smell_at(self.pos))

    # ------------------------------------------------------------------ pieces
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

    def _smell_at(self, p):
        cfg, gw, gh = self.cfg, self.gw, self.gh
        gx = torch.clamp((p[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((p[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        return self.smap.view(self.K, -1).gather(1, gx * gh + gy)

    def _brain(self, v, rbar, smell, d, H):
        r = torch.tanh(torch.clamp(v, min=0))
        I = (r[:, self.pre] * self.vals) @ self.M                   # chemical synapses (sparse as a matmul)
        I = I + v @ self.G - self.G_deg * v                          # gap junctions
        I = I - self.inh * r.mean(1, keepdim=True)
        I[:, self.s_on] += (self.g3[:, 0] * torch.clamp(d, min=0))[:, None]
        I[:, self.s_off] += (self.g3[:, 1] * torch.clamp(-d, min=0))[:, None]
        I[:, self.s_lvl] += (self.g3[:, 2] * smell)[:, None]
        if self.rec is not None:
            I = I + H[:, None] * self.rec
        v = v + self.k_dt * (-v + I)
        r = torch.tanh(torch.clamp(v, min=0))
        x = r[:, self.rd]
        dev = x - rbar
        rbar = rbar + self.adapt * dev
        o = torch.einsum('pr,pro->po', dev, self.D) + torch.einsum('pr,pro->po', x, self.Dl) + self.bias
        return v, rbar, torch.sigmoid(o[:, 1] - 2.0) * 0.3, torch.sigmoid(o[:, 0] + 1.0), torch.tanh(o[:, 2]) * 0.4

    # ------------------------------------------------------------------ one block of ticks
    def _block(self):
        cfg, opts, K, P, Fd, dev = self.cfg, self.opts, self.K, self.P, self.Fd, self.dev
        v, rbar, pos, heading = self.v, self.rbar, self.pos, self.heading
        size, energy, H, alive = self.size, self.energy, self.H, self.alive
        eaten, lifetime, esum, food, falive, prev = self.eaten, self.lifetime, self.esum, self.food, self.falive, self.prev
        self.smap.copy_(self._smell_map())
        nrow = self.n_sched.index_select(0, self.bi.view(1)).squeeze(0)    # graph-safe (no CPU sync)
        r2, BIG = cfg.eat_radius ** 2, K * Fd + 1
        zero = torch.zeros((), **self.f)
        for j in range(BLOCK):
            smell = self._smell_at(pos)
            d = torch.clamp((smell - prev) * 20.0, -1, 1)
            prev = smell
            v, rbar, p_tumble, speed_frac, turn = self._brain(v, rbar, smell.view(-1), d.view(-1), H.view(-1))
            p_tumble, speed_frac, turn = p_tumble.view(K, P), speed_frac.view(K, P), turn.view(K, P)
            tumble = self._rand(K, P) < p_tumble
            heading = torch.where(tumble, self._rand(K, P) * TAU, heading + torch.clamp(turn, -0.5, 0.5))
            speed = speed_frac * torch.clamp(cfg.speed_slope * size + cfg.speed_max, cfg.speed_min, cfg.speed_max)
            step = torch.stack([torch.cos(heading), torch.sin(heading)], -1) * speed[..., None]
            pos = torch.where(alive[..., None], torch.remainder(pos + step, self.wh), pos)
            energy = energy - torch.where(alive, cfg.base_cost + cfg.move_cost * speed, zero)
            # eating: parallel rounds, random winner per contested food (branch-free)
            can = alive & (energy < opts.gut_cap - cfg.food_value)
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
            energy = energy + atef * cfg.food_value
            size = size + atef * cfg.size_per_food
            eaten = eaten + atef
            lifetime = lifetime + alive.float()
            esum = esum + torch.where(alive, torch.clamp(energy, min=0), zero)
            H = torch.clamp(H + opts.h_rate * (torch.clamp(1 - energy / opts.gut_cap, 0, 1) - H) - opts.meal_drop * atef, 0, 1)
            full = (alive & (energy >= self.full_e)).float()
            hung = (alive & (energy < self.hungry_e)).float()
            self.sat += torch.stack([(speed_frac * full).sum(1), full.sum(1),
                                     (speed_frac * hung).sum(1), hung.sum(1)], 1)
            if self.recbuf is not None:
                ri, t1 = self.rec_idx, self.ti.view(1)
                for name, x in (('pos', pos), ('energy', energy), ('alive', alive), ('heading', heading)):
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
            old = food.gather(1, idx[..., None].expand(-1, -1, 2))
            food = food.scatter(1, idx[..., None].expand(-1, -1, 2), torch.where(ok[..., None], p, old))
            falive = falive.scatter(1, idx, falive.gather(1, idx) | ok)
            if self.recbuf is not None:
                t1 = self.ti.view(1)
                self.recbuf['food'].index_copy_(0, t1, food.index_select(0, self.rec_idx)[None].half())
                self.recbuf['falive'].index_copy_(0, t1, falive.index_select(0, self.rec_idx)[None])
            self.ti.add_(1)
        # write back into the fixed buffers (needed for graph replay)
        for name, val in (('v', v), ('rbar', rbar), ('pos', pos), ('heading', heading), ('size', size),
                          ('energy', energy), ('H', H), ('alive', alive), ('eaten', eaten), ('lifetime', lifetime),
                          ('esum', esum), ('food', food), ('falive', falive), ('prev', prev)):
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
        fit = self.esum / T / cfg.food_value if self.opts.fitness == 'energy' else self.eaten + self.lifetime / T
        fit, eaten, esum, alive, sat = (x.cpu().numpy() for x in (fit, self.eaten, self.esum, self.alive, self.sat))
        with np.errstate(invalid='ignore', divide='ignore'):
            sf_full, sf_hungry = sat[:, 0] / sat[:, 1], sat[:, 2] / sat[:, 3]
        stats = [dict(mean_food=float(eaten[k].mean()), mean_energy=float((esum[k] / T).mean()),
                      fitness=float(fit[k].mean()), survivors=int(alive[k].sum()), ticks=T,
                      speed_full=float(sf_full[k]), speed_hungry=float(sf_hungry[k])) for k in range(self.K)]
        return fit.astype(np.float64), stats

    def recording(self):
        """The recorded worlds of the last generation as NumPy arrays (for the viewer)."""
        return {k: v.cpu().numpy() for k, v in self.recbuf.items()} if self.recbuf is not None else None


def evolve(cond, seeds, generations=GENERATIONS, out=OUT, device='cuda', graph=True, quiet=False, watch=0):
    """watch: record the first `watch` seeds every generation for the live viewer (python -m ecosim.viewer)."""
    opts, conn = CONDITIONS[cond], Connectome()
    cfg = Config(seed=seeds[0], **CFG_OVERRIDES.get(cond, {}))
    dev = pick_device(device)
    rngs = [np.random.default_rng(s) for s in seeds]
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng(list(seeds)).integers(2**62)))
    P = cfg.worm_population
    sim = FastSim(cfg, opts, conn, len(seeds), P, dev, graph, gen, record=range(min(watch, len(seeds))))
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
        fit, stats = sim.run(pop, rngs)
        t1 = time.perf_counter()
        new = np.empty_like(pop)
        for k, r in enumerate(rngs):
            st = stats[k]; st['gen'] = g; hist[k].append(st)
            order = np.argsort(fit[k])[::-1][:n_elite]
            best[k] = pop[k, order[0]].copy()
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


LIVE = Path('runs/live')


def write_live(folder, sim, fit, stats, hist, seeds, gen, cond, cfg):
    """One file per generation for the viewer; written to a temp name, then renamed (never half-read)."""
    rec = sim.recording()
    R = len(seeds)
    data = dict(gen=gen, cond=cond, seeds=np.array(seeds), width=cfg.width, height=cfg.height,
                gut_cap=sim.opts.gut_cap, fitness=fit[:R].astype(np.float32),
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
