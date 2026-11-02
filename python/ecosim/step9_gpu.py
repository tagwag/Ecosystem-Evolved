"""Step 9: reserved breeding slots for puzzle solvers, started from the lucky Step 6b lineages. GPU.

Question: Step 6/6b found puzzles barely matter to evolution (puzzle food ~1 per worm vs ~12 normal food).
Does guaranteeing parents' slots to worms that solve puzzles (a reserved breeding slot) make puzzle
solving spread?

Setup (fixed before results):
    brain + world   Step 6 'puzzle_nomem' (curiosity learning brain, no memory pool, puzzle world,
                    scarce food), ported to the GPU in this file. Same equations as worm5/worm6.
    start           the three luckiest Step 6b lineages: puzzle_nomem seeds 12, 9, 5
                    (fair-test puzzle food 3.35, 2.68, 2.52 per worm; random walk 0.53).
                    Each run starts from that genome + 59 mutated copies.
                    Loaded from the lucky-lineage library: python/lineages/ (ecosim/lineages.py).
    arms            food_only  parents = top 12 of 60 by fitness (food + puzzle food + survival), as Step 6
                    slots      same, but up to 3 of the 12 parent places go to the worms with the most
                               puzzle solves, if they solved 2+ (2+ guards against one lucky solve)
    size            3 lineages x 10 replicates = 30 runs per arm, 60 generations. Replicate r uses the same
                    random seed in both arms, so the 30 pairs share starting population and first worlds.
    fair test       each run's final parent pool (12 genomes x 5 copies = 60 worms) on the 6 unseen Step 6
                    test worlds (seeds 6000-6005). Also the 3 original lucky genomes (60 copies) as baseline.
    rule            slots help if slots beat food_only on puzzle food per worm: paired sign-flip p < 0.05
                    over the 30 pairs (or wins in all 30). Cost check: total food (normal + puzzle).
    side question   (replay) do lucky lineages keep their edge? food_only puzzle food vs each lineage's
                    starting genome on the same test worlds. Descriptive only.

    python -m ecosim.step9_gpu run            (~15-30 min on an RTX 3080, estimate)
    python -m ecosim.step9_gpu analyze        -> results/step9_*
    python -m ecosim.step9_gpu test           tiny CPU/GPU smoke test + CPU-vs-GPU brain check

GPU results match CPU statistically, not number for number (float32, parallel eating, other random draws).
"""
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

from .batch3_gpu import gauss_kernel, blur_wrap
from .config import Config
from .connectome import Connectome, READOUT, SILENT
from .sim import TAU
from .worm2_gpu import pick_device
from . import worm5 as w5
from . import worm6 as w6

LINEAGES = {12: 3.35, 9: 2.68, 5: 2.52}            # Step 6b puzzle_nomem seed -> fair-test puzzle food
from . import lineages as LIN
REPS = list(range(1, 11))
GENS = 60
ARMS = ('food_only', 'slots')
N_SLOTS, MIN_SOLVES = 3, 2
OUT, RES = Path('runs/step9'), Path('results')
WORLDS = list(range(6000, 6006))                   # Step 6 test worlds
OPTS = w6.Opts6(memory=False, curriculum=False)
BLOCK = 10

TYPES = w6.SPOT_TYPES                              # linger, linger, revisit, revisit, seqA, seqB
PAYV = [w6.PAY.get(t, 0) for t in TYPES]


def cfg_puzzle(**kw):
    return dataclasses.replace(Config(**kw), food_regrow_per_tick=w6.SCARCE_REGROW)


# ---------------------------------------------------------------------------------------------- brain
class LearnBrainTorch:
    """worm5.LearnBrains at level 'curiosity' (Hebbian + dopamine RPE + curiosity), batched on the GPU.
    Synapses are per edge: weight = fixed part (genome) + plastic part Wp, summed into targets by a
    0/1 matrix multiply (same trick as batch3_fast)."""
    c = w5.LearnBrains

    def __init__(self, conn, B, dev):
        f = self.f = dict(dtype=torch.float32, device=dev)
        self.L = w5.Layout5(conn)
        E, N = conn.n_edges, conn.N
        self.pre = torch.as_tensor(conn.pre, device=dev)
        self.post = torch.as_tensor(conn.post, device=dev)
        M = torch.zeros(E, N, **f)
        M[torch.arange(E, device=dev), self.post] = 1.0
        self.M = M
        self.w_base = torch.as_tensor(conn.w_norm * self.c.chem_scale, **f)
        self.G = torch.as_tensor(conn.G * self.c.gap_scale, **f)
        self.G_deg = torch.as_tensor(conn.G_deg * self.c.gap_scale, **f)
        self.rd = torch.as_tensor(conn.ids([n for n in READOUT if n in conn.idx]), device=dev)
        ids = lambda names: torch.as_tensor(conn.ids(names), device=dev)
        self.iA = {k: ids(w5.ODOR_A[k]) for k in w5.ODOR_A}
        self.iB = {k: ids(w5.ODOR_B[k]) for k in w5.ODOR_B}
        self.B, self.E, self.N = B, E, N

    def load(self, genomes):
        """genomes: (B, G) numpy, Layout6 (only the Layout5 part is used: no memory pool)."""
        L, f = self.L, self.f
        g = torch.as_tensor(np.asarray(genomes)[:, :L.size], **f)
        B = len(g)
        self.vals = self.w_base * (1.0 + torch.clamp(g[:, :L.E], -3, 3))
        self.edge_ok = (torch.abs(g[:, :L.E] - SILENT) > 1e-6).float()
        sg = torch.exp(torch.clamp(g[:, L.sens], -3, 3))
        self.gA, self.gB = sg[:, :3], sg[:, 3:]
        self.D = g[:, L.dev].reshape(B, L.R, 3) * 10.0
        self.Dl = g[:, L.lvl].reshape(B, L.R, 3) * 3.0
        self.bias = g[:, L.bias]
        p = torch.clamp(g[:, L.plast], -6, 3)
        self.eta_h = 0.002 * torch.exp(p[:, 0])
        self.eta_r = 0.01 * torch.exp(p[:, 1])
        self.lam = torch.sigmoid(p[:, 2] + 3.0)
        self.cur = 0.2 * torch.exp(p[:, 3])
        z = lambda *s: torch.zeros(*s, **f)
        self.Wp, self.elig = z(B, self.E), z(B, self.E)
        self.v, self.nbar = z(B, self.N), z(B, self.N)
        self.rbar = z(B, len(self.rd))
        self.pred, self.Rbar = z(B, 2), z(B)

    def step(self, a, b, da, db):
        v = self.v
        r = torch.tanh(torch.clamp(v, min=0))
        I = (r[:, self.pre] * (self.vals + self.Wp)) @ self.M
        I = I + v @ self.G - self.G_deg * v
        I = I - self.c.inhibition * r.mean(1, keepdim=True)
        for k, xa, xb in (('level', a, b), ('up', torch.clamp(da, min=0), torch.clamp(db, min=0)),
                          ('down', torch.clamp(-da, min=0), torch.clamp(-db, min=0))):
            j = ('level', 'up', 'down').index(k)
            I[:, self.iA[k]] += (self.gA[:, j] * xa)[:, None]
            I[:, self.iB[k]] += (self.gB[:, j] * xb)[:, None]
        self.v = v + self.c.dt / self.c.tau * (-v + I)
        r = torch.tanh(torch.clamp(self.v, min=0))
        self._r = r
        x = r[:, self.rd]
        dev = x - self.rbar
        self.rbar = self.rbar + self.c.adapt * dev
        o = torch.einsum('pr,pro->po', dev, self.D) + torch.einsum('pr,pro->po', x, self.Dl) + self.bias
        return torch.sigmoid(o[:, 1] - 2.0) * 0.3, torch.sigmoid(o[:, 0] + 1.0), torch.tanh(o[:, 2]) * 0.4

    def learn(self, R, da, db):
        r = self._r
        self.nbar = self.nbar + 0.01 * (r - self.nbar)
        x = r - self.nbar
        co = x[:, self.pre] * x[:, self.post] * self.edge_ok
        dW = self.eta_h[:, None] * co
        self.elig = self.lam[:, None] * self.elig + co
        d = torch.stack([da, db], 1)
        R = R + self.cur * torch.abs(d - self.pred).sum(1)
        self.pred = self.pred + 0.05 * (d - self.pred)
        rpe = R - self.Rbar
        self.Rbar = self.Rbar + 0.01 * (R - self.Rbar)
        dW = dW + (self.eta_r * rpe)[:, None] * self.elig
        self.Wp = torch.clamp(self.Wp + dW, -w5.WP_CAP, w5.WP_CAP)


# ---------------------------------------------------------------------------------------------- world
class PuzzleSimGPU:
    """K puzzle worlds x P worms each (worm6.run_generation, phase='puzzle'), all on one device."""

    def __init__(self, cfg, conn, K, P, dev, gen):
        self.cfg, self.conn, self.K, self.P, self.dev, self.gen = cfg, conn, K, P, dev, gen
        f = self.f = dict(dtype=torch.float32, device=dev)
        self.brain = LearnBrainTorch(conn, K * P, dev)
        w0 = w6.PuzzleWorld(cfg, np.random.default_rng(0))
        self.gw, self.gh, self.Fd, self.C = w0.gw, w0.gh, len(w0.food), len(w0.patch_centers)
        T = cfg.ticks_per_generation
        acc, n = 0.0, []
        for _ in range(T):
            acc += cfg.food_regrow_per_tick
            k = int(acc); acc -= k; n.append(k)
        self.n_sched, self.nmax = n, max(1, max(n))
        self.kern, self.kr = gauss_kernel(cfg.smell_sigma_cells, dev)
        self.kidx = torch.arange(K, device=dev)
        self.wh = torch.tensor([cfg.width, cfg.height], **f)
        self.ar_nmax = torch.arange(self.nmax, device=dev)
        tt = lambda name: torch.tensor([t == name for t in TYPES], device=dev)
        self.is_l, self.is_r, self.is_a, self.is_b = tt('linger'), tt('revisit'), tt('seqA'), tt('seqB')
        self.pay = torch.tensor(PAYV, **f)

    def _rand(self, *s):
        return torch.rand(*s, generator=self.gen, **self.f)

    def _smell_map(self, food, falive):
        cfg, K, gw, gh = self.cfg, self.K, self.gw, self.gh
        gx = torch.clamp((food[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((food[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        cnt = torch.zeros(K, gw * gh, **self.f)
        cnt.scatter_add_(1, gx * gh + gy, falive.float())
        s = blur_wrap(cnt.view(K, gw, gh), self.kern, self.kr)
        m = s.amax(dim=(1, 2), keepdim=True)
        return torch.where(m > 0, s / m.clamp(min=1e-12), s)

    def _at(self, grid, p):
        cfg, gw, gh = self.cfg, self.gw, self.gh
        gx = torch.clamp((p[..., 0] / cfg.smell_cell).long(), 0, gw - 1)
        gy = torch.clamp((p[..., 1] / cfg.smell_cell).long(), 0, gh - 1)
        return grid.reshape(self.K, -1).gather(1, gx * gh + gy)

    @torch.no_grad()
    def run(self, genomes, rngs):
        """genomes (K, P, G) numpy; rngs: K numpy rngs (world layout + start positions, as worm6).
        Returns fitness (K,P), solves (K,P), stats list."""
        cfg, K, P, Fd, dev, f = self.cfg, self.K, self.P, self.Fd, self.dev, self.f
        T = cfg.ticks_per_generation
        br = self.brain
        br.load(genomes.reshape(K * P, -1))
        ws = [w6.PuzzleWorld(cfg, r, puzzles=True) for r in rngs]
        centers = torch.as_tensor(np.stack([x.patch_centers for x in ws]), **f)
        food = torch.as_tensor(np.stack([x.food for x in ws]), **f)
        falive = torch.as_tensor(np.stack([x.food_alive for x in ws]), device=dev)
        spots = torch.as_tensor(np.stack([x.spots for x in ws]), **f)                  # K,6,2
        psmell = torch.as_tensor(np.stack([x.psmell for x in ws]), **f)               # K,gw,gh
        pos = torch.as_tensor(np.stack([np.column_stack([r.uniform(0, cfg.width, P), r.uniform(0, cfg.height, P)])
                                        for r in rngs]), **f)
        heading = torch.as_tensor(np.stack([r.uniform(0, TAU, P) for r in rngs]), **f)
        z = lambda *s: torch.zeros(*s, **f)
        size, energy = torch.full((K, P), cfg.start_size, **f), torch.full((K, P), cfg.start_energy, **f)
        alive = torch.ones(K, P, dtype=torch.bool, device=dev)
        eaten, lifetime, pfood, solves = z(K, P), z(K, P), z(K, P), z(K, P)
        by = z(K, P, len(TYPES))
        S = len(TYPES)
        inside = torch.zeros(K, P, S, dtype=torch.bool, device=dev)
        in_time, left_at, cool = z(K, P, S), torch.full((K, P, S), -1e9, **f), torch.full((K, P, S), -1e9, **f)
        seqA_at = torch.full((K, P), -1e9, **f)
        smap = self._smell_map(food, falive)
        pa, pb = self._at(smap, pos), self._at(psmell, pos)
        r2, BIG = cfg.eat_radius ** 2, K * Fd + 1
        zero = torch.zeros((), **f)
        for t in range(T):
            if t % cfg.smell_update_every == 0:
                smap = self._smell_map(food, falive)
            a, b = self._at(smap, pos), self._at(psmell, pos)
            da, db = torch.clamp((a - pa) * 20, -1, 1), torch.clamp((b - pb) * 20, -1, 1)
            pa, pb = a, b
            p_tumble, speed_frac, turn = (x.view(K, P) for x in br.step(a.view(-1), b.view(-1), da.view(-1), db.view(-1)))
            tumble = self._rand(K, P) < p_tumble
            heading = torch.where(tumble, self._rand(K, P) * TAU, heading + torch.clamp(turn, -0.5, 0.5))
            speed = speed_frac * torch.clamp(cfg.speed_slope * size + cfg.speed_max, cfg.speed_min, cfg.speed_max)
            step = torch.stack([torch.cos(heading), torch.sin(heading)], -1) * speed[..., None]
            pos = torch.where(alive[..., None], torch.remainder(pos + step, self.wh), pos)
            energy = energy - torch.where(alive, cfg.base_cost + cfg.move_cost * speed, zero)
            # eating (as batch3_fast): parallel rounds, random winner per contested food
            d2 = ((pos[:, :, None, :] - food[:, None, :, :]) ** 2).sum(-1)
            reach = (d2 <= r2) & falive[:, None, :] & alive[:, :, None]
            ate = torch.zeros(K, P, dtype=torch.bool, device=dev)
            for _ in range(3):
                best, pick = (self._rand(K, P, Fd) * reach).max(2)
                has = best > 0
                prio = self._rand(K, P) * has
                key = torch.where(has, self.kidx[:, None] * Fd + pick, torch.full_like(pick, BIG - 1))
                top = torch.zeros(BIG, **f).scatter_reduce(0, key.view(-1), prio.view(-1), 'amax')
                win = has & (prio == top[key])
                ate = ate | win
                taken = torch.zeros(BIG, **f).scatter_reduce(0, key.view(-1), win.view(-1).float(), 'amax')
                wf = taken[:K * Fd].view(K, Fd) > 0
                falive = falive & ~wf
                reach = reach & ~win[:, :, None] & ~wf[:, None, :]
            atef = ate.float()
            # puzzles (worm6.run_generation, phase 'puzzle')
            dist = torch.linalg.norm(pos[:, :, None, :] - spots[:, None, :, :], dim=-1)   # K,P,S
            now_in = (dist < w6.SPOT_R) & alive[..., None]
            entered = now_in & ~inside
            in_time = torch.where(now_in, in_time + 1, zero)
            left_at = torch.where(inside & ~now_in, torch.full_like(left_at, t), left_at)
            ready = (t - cool) > w6.COOLDOWN
            gap = t - left_at
            hit = ((in_time == w6.LINGER_T) & self.is_l) | \
                  (entered & (gap >= w6.REVISIT_MIN) & (gap <= w6.REVISIT_MAX) & self.is_r)
            seqA_at = torch.where((entered & self.is_a).any(-1), torch.full_like(seqA_at, t), seqA_at)
            hit = hit | (entered & ((t - seqA_at) <= w6.SEQ_T)[..., None] & self.is_b)
            hit = hit & ready
            hf = hit.float()
            cool = torch.where(hit, torch.full_like(cool, t), cool)
            pay = (hf * self.pay).sum(-1)
            by = by + hf * self.pay
            pfood = pfood + pay
            nh = hf.sum(-1)
            solves = solves + nh
            inside = now_in
            energy = energy + atef * cfg.food_value + pay * cfg.food_value
            size = size + atef * cfg.size_per_food
            eaten = eaten + atef
            lifetime = lifetime + alive.float()
            br.learn(((atef + nh) * alive).view(-1), da.view(-1), db.view(-1))
            alive = alive & (energy > 0)
            # regrowth (as batch3_fast)
            sc = self._rand(K, Fd) * (~falive) - falive.float()
            val, idx = sc.topk(self.nmax, dim=1)
            ok = (val >= 0) & (self.ar_nmax[None, :] < self.n_sched[t])
            ci = (self._rand(K, self.nmax) * self.C).long().clamp(max=self.C - 1)
            cen = centers.gather(1, ci[..., None].expand(-1, -1, 2))
            p = cen + torch.randn(K, self.nmax, 2, generator=self.gen, **f) * cfg.patch_spread
            p = torch.minimum(torch.clamp(p, min=0), self.wh - 1)
            old = food.gather(1, idx[..., None].expand(-1, -1, 2))
            food = food.scatter(1, idx[..., None].expand(-1, -1, 2), torch.where(ok[..., None], p, old))
            falive = falive.scatter(1, idx, falive.gather(1, idx) | ok)
        fit = eaten + pfood + lifetime / T
        fit, solves, eaten, pfood, by, alive = (x.cpu().numpy() for x in (fit, solves, eaten, pfood, by, alive))
        stats = []
        for k in range(K):
            st = dict(mean_food=float(eaten[k].mean()), mean_puzzle=float(pfood[k].mean()),
                      mean_total=float((eaten[k] + pfood[k]).mean()), survivors=int(alive[k].sum()),
                      solvers2=int((solves[k] >= MIN_SOLVES).sum()))
            for j, typ in enumerate(TYPES):
                if PAYV[j]:
                    st[f'puzzle_{typ}'] = st.get(f'puzzle_{typ}', 0.0) + float(by[k, :, j].mean())
            stats.append(st)
        return fit.astype(np.float64), solves, stats


# ---------------------------------------------------------------------------------------------- evolution
def pick_parents(fit, solves, arm, n_elite):
    order = list(np.argsort(fit)[::-1])
    if arm == 'food_only':
        return np.array(order[:n_elite]), 0
    cand = [i for i in np.lexsort((fit, solves))[::-1] if solves[i] >= MIN_SOLVES][:N_SLOTS]
    rest = [i for i in order if i not in cand][:n_elite - len(cand)]
    return np.array(cand + rest), len(cand)


def lucky_genome(seed):
    return LIN.load(f'6b-puzzle_nomem-s{seed}')          # lucky-lineage library (python/lineages/)


def runs():
    return [(L, r) for L in LINEAGES for r in REPS]


def evolve(arm, generations=GENS, device='cuda', run_list=None, out=OUT, ticks=None):
    run_list = run_list or runs()
    done = out / f'{arm}_done.json'
    if done.exists():
        print(arm, 'already done, skipping', flush=True)
        return
    conn = Connectome()
    cfg = cfg_puzzle(**({'ticks_per_generation': ticks} if ticks else {}))
    dev = pick_device(device)
    P = cfg.worm_population
    n_elite = max(2, int(P * cfg.elite_fraction))
    rngs = [np.random.default_rng(1000 * L + r) for L, r in run_list]      # same in both arms
    gen = torch.Generator(device=dev)
    gen.manual_seed(int(np.random.default_rng([L * 100 + r for L, r in run_list]).integers(2**62)))
    pop = []
    for (L, r), rng in zip(run_list, rngs):
        g0 = lucky_genome(L)
        pop.append([g0] + [w6.mutate(g0, conn, cfg, rng, OPTS) for _ in range(P - 1)])
    pop = np.array(pop)
    sim = PuzzleSimGPU(cfg, conn, len(run_list), P, dev, gen)
    hist = [[] for _ in run_list]
    print(f'{arm}: {len(run_list)} runs x {P} worms on {dev}', flush=True)
    for g in range(generations):
        t0 = time.perf_counter()
        fit, solves, stats = sim.run(pop, rngs)
        t1 = time.perf_counter()
        new = np.empty_like(pop)
        for k, rng in enumerate(rngs):
            par, n_res = pick_parents(fit[k], solves[k], arm, n_elite)
            stats[k].update(gen=g, reserved_used=n_res)
            hist[k].append(stats[k])
            elites = pop[k, par]
            kids = [elites[i] for i in range(n_elite)]
            while len(kids) < P:
                kids.append(w6.mutate(elites[rng.integers(n_elite)], conn, cfg, rng, OPTS))
            new[k] = np.array(kids)
            if g == generations - 1:
                d = out / f'{arm}_L{run_list[k][0]}_r{run_list[k][1]}'
                d.mkdir(parents=True, exist_ok=True)
                np.save(d / 'parents.npy', elites)
                (d / 'history.json').write_text(json.dumps(hist[k], indent=1))
        pop = new
        pm = np.mean([s['mean_puzzle'] for s in stats]); fm = np.mean([s['mean_food'] for s in stats])
        print(f'{arm} gen {g:2d}  food {fm:5.2f}  puzzle {pm:5.2f}  solvers(2+) '
              f'{np.mean([s["solvers2"] for s in stats]):4.1f}  sim {t1 - t0:5.1f} s  evolve {time.perf_counter() - t1:4.1f} s',
              flush=True)
    done.write_text(json.dumps(dict(generations=generations, runs=run_list)))


def fair_test(groups, conn, dev, ticks=None):
    """groups: list of (name, genomes (n, G)). Each group fills 60 worms (genomes repeated), tested on
    the 6 test worlds. Returns {name: mean stats over worlds}."""
    cfg = cfg_puzzle(**({'ticks_per_generation': ticks} if ticks else {}))
    P, out = cfg.worm_population, {}
    for i in range(0, len(groups), 10):
        chunk = groups[i:i + 10]
        pairs = [(name, g, wd) for name, g in chunk for wd in WORLDS]
        G = np.stack([np.resize(g, (P, g.shape[1])) for _, g, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(777)
        sim = PuzzleSimGPU(cfg, conn, len(pairs), P, dev, gen)
        _, _, st = sim.run(G, [np.random.default_rng(wd) for _, _, wd in pairs])
        for name, _ in chunk:
            rows = [st[j] for j, p in enumerate(pairs) if p[0] == name]
            out[name] = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
        del sim
        if dev.type == 'cuda':
            torch.cuda.empty_cache()
    return out


def paired(a, b):
    diff = np.asarray(a) - np.asarray(b)
    flips = np.random.default_rng(0).choice([-1, 1], (20000, len(diff)))
    p = float((np.abs((flips * diff).mean(1)) >= abs(diff.mean()) - 1e-12).mean())
    return dict(mean_a=float(np.mean(a)), mean_b=float(np.mean(b)), mean_diff=float(diff.mean()),
                wins=int((diff > 0).sum()), n=len(diff), p_value=p)


def analyze(device='cuda', out=OUT, run_list=None, ticks=None, tag='step9'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    run_list = run_list or runs()
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device(device), Connectome()
    groups = [(f'{a}_L{L}_r{r}', np.load(out / f'{a}_L{L}_r{r}' / 'parents.npy')) for a in ARMS for L, r in run_list]
    groups += [(f'start_L{L}', lucky_genome(L)[None]) for L in sorted({L for L, _ in run_list})]
    fair = fair_test(groups, conn, dev, ticks)
    key = lambda a, m: [fair[f'{a}_L{L}_r{r}'][m] for L, r in run_list]
    tests = {'slots vs food_only: puzzle food (PRIMARY)': paired(key('slots', 'mean_puzzle'), key('food_only', 'mean_puzzle')),
             'slots vs food_only: total food': paired(key('slots', 'mean_total'), key('food_only', 'mean_total')),
             'slots vs food_only: sequence': paired(key('slots', 'puzzle_seqB'), key('food_only', 'puzzle_seqB'))}
    replay = {}
    for L in sorted({L for L, _ in run_list}):
        for a in ARMS:
            v = [fair[f'{a}_L{L}_r{r}']['mean_puzzle'] for LL, r in run_list if LL == L]
            replay[f'L{L} {a}'] = dict(start=fair[f'start_L{L}']['mean_puzzle'], step6b_cpu=LINEAGES[L],
                                       end_mean=float(np.mean(v)), end_min=float(np.min(v)), end_max=float(np.max(v)))
    res = dict(tests=tests, replay=replay, fair=fair)
    (RES / f'{tag}_results.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(dict(tests=tests, replay=replay), indent=1), flush=True)
    # chart: left = puzzle food per run (paired lines), right = puzzle food over generations
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    cols = {12: '#2a78d6', 9: '#d6762a', 5: '#3a9e5c'}
    for L, r in run_list:
        y = [fair[f'food_only_L{L}_r{r}']['mean_puzzle'], fair[f'slots_L{L}_r{r}']['mean_puzzle']]
        a1.plot([0, 1], y, color=cols.get(L, '#888'), alpha=0.5, marker='o', ms=3)
    for L in sorted({L for L, _ in run_list}):
        a1.plot([-0.15], [fair[f'start_L{L}']['mean_puzzle']], marker='*', ms=12, color=cols.get(L, '#888'),
                label=f'lineage s{L} (star = starting genome)')
    a1.set_xticks([-0.15, 0, 1], ['start', 'food only', 'reserved slots'])
    t = tests['slots vs food_only: puzzle food (PRIMARY)']
    a1.set_title(f'Puzzle food, unseen worlds (p = {t["p_value"]:.3f}, slots win {t["wins"]}/{t["n"]})')
    a1.set_ylabel('puzzle food per worm'); a1.grid(alpha=0.3); a1.legend(fontsize=8)
    for a, c in (('food_only', '#999999'), ('slots', '#2a78d6')):
        H = np.array([[g['mean_puzzle'] for g in json.loads((out / f'{a}_L{L}_r{r}' / 'history.json').read_text())]
                      for L, r in run_list])
        a2.plot(H.mean(0), color=c, lw=2, label=a)
        a2.fill_between(range(H.shape[1]), np.percentile(H, 25, 0), np.percentile(H, 75, 0), color=c, alpha=0.15)
    a2.set_xlabel('generation'); a2.set_ylabel('puzzle food per worm (evolving population)')
    a2.set_title(f'During evolution (mean of {len(run_list)} runs, band = middle half)'); a2.legend(); a2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RES / f'{tag}_slots.png', dpi=130); plt.close(fig)


# ---------------------------------------------------------------------------------------------- checks
def brain_check(n_ticks=50):
    """Same inputs into worm5.LearnBrains (NumPy) and LearnBrainTorch: outputs should agree to ~1e-4."""
    conn = Connectome()
    g = np.stack([lucky_genome(L) for L in LINEAGES])
    cpu = w5.LearnBrains(conn, g[:, :w5.Layout5(conn).size], w5.Opts5('curiosity'))
    gpu = LearnBrainTorch(conn, len(g), torch.device('cpu'))
    gpu.load(g)
    rng = np.random.default_rng(0)
    worst = 0.0
    for t in range(n_ticks):
        a, b = rng.random(len(g)), rng.random(len(g))
        da, db = rng.uniform(-1, 1, len(g)), rng.uniform(-1, 1, len(g))
        R = (rng.random(len(g)) < 0.1).astype(float)
        o1 = cpu.step(a, b, da, db)
        T = lambda x: torch.as_tensor(x, dtype=torch.float32)
        o2 = gpu.step(T(a), T(b), T(da), T(db))
        cpu.learn(R, da, db, t)
        gpu.learn(T(R), T(da), T(db))
        worst = max(worst, max(float(np.abs(x - y.numpy()).max()) for x, y in zip(o1, o2)))
    wp = float(np.abs(cpu.Wp - gpu.Wp.numpy()).max())
    print(f'brain check: max output difference {worst:.2e}, max plastic weight difference {wp:.2e}')
    return worst, wp


def smoke():
    worst, wp = brain_check()
    assert worst < 1e-3 and wp < 1e-3, 'GPU brain does not match the CPU brain'
    tmp = Path('runs/step9_test')
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    rl = [(12, 1), (9, 1)]
    for a in ARMS:
        evolve(a, generations=2, run_list=rl, out=tmp, ticks=200)
    analyze(out=tmp, run_list=rl, ticks=200, tag='step9_test')
    print('SMOKE TEST OK')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'run':
        for a in ARMS:
            evolve(a)
    elif cmd == 'analyze':
        analyze()
    elif cmd == 'test':
        smoke()
