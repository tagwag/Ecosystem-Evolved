"""Equilibrium world: a stable, food-limited world where worms live, split and die on their own (no generations,
no scoring function). It is the ZERO POINT that later experiments are measured against.

Three arms run side by side, same world rules, same founders:
  frozen  - children are exact copies (no mutation)                        -> genetic change must stay exactly 0
  shadow  - mutation ON, but WHO reproduces / dies is random              -> change from chance alone (drift)
            (the "neutral shadow" of Bedau & Packard: each tick it copies the real arm's NUMBER of births and deaths
             in the same replicate world, but picks the parents and the victims at random, so a genome's quality
             cannot affect its success while the population size and turnover match the real arm exactly)
  real    - mutation ON, a worm splits when IT has enough energy, dies when IT runs out -> drift + selection
  Adaptation = real minus shadow.

Brain: the toy-brain recurrent net from python/toybrain (8 hidden neurons, smell + taste). Founders are the evolved
champion genomes from the toy-brain fair run (one lineage per replicate world), or random genomes if none are given.

Everything is batched on the GPU: R replicate worlds x 3 arms, each world has a fixed number of worm SLOTS; a slot is
alive or empty. Births fill empty slots.

Usage:  python eqworld.py [replicates] [ticks] [--founders PATH] [--slots N] [--quick] [--every N] [--tag NAME]
        --save-at 13000,20000      save full snapshots at those ticks (snapshots/eq<tag>_t<tick>.pt)
        --resume FILE [--pick r --copies k]   continue from a snapshot; with --pick only replicate r, as k copies
                                              (each copy gets its own random luck from that moment on)
See README.md in this folder for the full explanation.
Output: results/eq_<ticks>t_<seeds>s.json (time series per world + summary), progress in eq_log.txt
"""
import json, math, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "toybrain"))
from sim import shapes, glen  # noqa: E402  (same genome layout as the toy brain)

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BRAIN = dict(smell=1, H=8, plastic=0)
ARMS = ["frozen", "shadow", "real"]

# ---------------------------------------------------------------- world rules (all in one place, documented in README)
W = dict(
    # Sensing and patch geometry match the toy-brain arena exactly, so the founders' evolved brains read the world the
    # same way they were evolved in. The arena is 2x wider with 4x the patches = the same patch density.
    size=400.0,            # arena is size x size (toy arena: 100 x 100); big enough for ~400 worms so random
                           # birth/death noise is small (~5 %)
    patches=80,            # food patches, fixed positions per world (toy: 5 per 100x100 -> same density)
    patch_r=4.0,           # eating radius around a patch centre (toy PR)
    food_max=20.0,         # most food a patch holds (toy FMAX)
    regrow=0.01,           # regrowth per tick: food += regrow * (food_max - food)   (toy: 0.003 -> sets carrying capacity)
    bite=0.5,              # most food one worm eats per tick (toy)
    sig_smell=25.0, sig_taste=5.0,   # smell / taste ranges (toy SIG_SMELL, SIG_TASTE)
    e_start=10.0,          # founder energy, and a shadow-arm child's energy
    e_split=20.0,          # real/frozen: split when energy >= this (parent and child get half each)
    cost_base=0.02,        # energy burned per tick just living
    cost_move=0.02,        # extra energy per unit of speed (speed 0.3-1.0)
    max_age=6000,          # die of old age (same for every genome, so not selection)
    mut_sigma=0.1,         # per-gene mutation size (toy brain reference size: 130 genes)
)


def unpack(G):
    out, i = {}, 0
    for n, sh in shapes(BRAIN):
        k = int(np.prod(sh)); out[n] = G[..., i:i + k].reshape(G.shape[:-1] + sh); i += k
    return out


class EqWorld:
    """R*3 worlds (arm-major: worlds [0:R] frozen, [R:2R] shadow, [2R:3R] real), S slots each."""

    def __init__(self, founders, R, S, seed=0):
        self.R, self.S, self.N = R, S, 3 * R
        self.gen = torch.Generator(device=DEV); self.gen.manual_seed(seed)
        L = glen(BRAIN); N = self.N
        self.arm = torch.arange(N, device=DEV) // R                      # 0 frozen, 1 shadow, 2 real
        g = torch.Generator().manual_seed(seed)                          # world layouts: same for the 3 arms of a replicate
        layout = 20 + (W["size"] - 40) * torch.rand(R, W["patches"], 2, generator=g)
        self.patches = layout.repeat(3, 1, 1).to(DEV)                    # (N, P, 2)
        self.food = torch.full((N, W["patches"]), W["food_max"], device=DEV)
        n0 = S // 4                                                      # start a quarter full (160 of 640)
        self.alive = torch.zeros(N, S, dtype=torch.bool, device=DEV); self.alive[:, :n0] = True
        f = founders.to(DEV).float()                                     # (R, L): one founder genome per replicate
        self.G = f.repeat(3, 1)[:, None, :].expand(N, S, L).clone()      # every slot starts as the founder
        self.founder = f.repeat(3, 1)                                    # (N, L) for genetic distance
        self.lineage = torch.arange(S, device=DEV)[None].expand(N, S).clone()  # founder slot id = lineage label
        self.nmut = torch.zeros(N, S, device=DEV)      # mutation events on this worm's line of descent since the founder
        self.msize = torch.zeros(N, S, device=DEV)     # total size of those mutations (sum of mutation vector lengths)
        self.energy = torch.full((N, S), W["e_start"], device=DEV) * self.alive
        # founders get random ages so they don't all die of old age on the same tick
        self.age = W["max_age"] * torch.rand(N, S, generator=self.gen, device=DEV) * self.alive
        self.xy = W["size"] * torch.rand(N, S, 2, generator=self.gen, device=DEV)
        self.hd = 2 * math.pi * torch.rand(N, S, generator=self.gen, device=DEV)
        self.h = torch.zeros(N, S, BRAIN["H"], device=DEV)
        self.prev = torch.zeros(N, S, 2, device=DEV)
        self.births = torch.zeros(N, device=DEV); self.deaths = torch.zeros(N, device=DEV)
        self.eaten = torch.zeros(N, device=DEV); self.speed_sum = torch.zeros(N, device=DEV)
        self.turn_sum = torch.zeros(N, device=DEV); self.alive_ticks = torch.zeros(N, device=DEV)
        self.p = unpack(self.G)

    # ------------------------------------------------------------------ one tick for every worm in every world
    @torch.no_grad()
    def tick(self):
        N, S = self.N, self.S
        a = self.alive.float()
        d2 = ((self.xy[:, :, None, :] - self.patches[:, None]) ** 2).sum(-1)          # (N, S, P)
        frac = (self.food / W["food_max"])[:, None, :]
        sm = (frac * torch.exp(-d2 / (2 * W["sig_smell"] ** 2))).sum(-1)
        ta = (frac * torch.exp(-d2 / (2 * W["sig_taste"] ** 2))).sum(-1)
        nz = lambda: 0.01 * torch.randn(N, S, generator=self.gen, device=DEV)
        cur = torch.stack([sm + nz(), ta + nz()], -1)
        dcur = (cur - self.prev) * 10; self.prev = cur
        # eating: each worm inside a patch radius bites; a crowded patch is shared in proportion
        inside = (d2 < W["patch_r"] ** 2).float() * a[:, :, None]                       # (N, S, P)
        want = inside * W["bite"]
        demand = want.sum(1)                                                            # (N, P)
        share = torch.where(demand > 0, torch.clamp(self.food / demand.clamp(min=1e-9), max=1.0), torch.zeros_like(demand))
        got = want * share[:, None, :]                                                  # (N, S, P)
        self.food = self.food - got.sum(1)
        ate = got.sum(-1)                                                               # (N, S)
        self.food = self.food + W["regrow"] * (W["food_max"] - self.food)
        # brain
        x = torch.stack([cur[..., 0], dcur[..., 0], cur[..., 1], dcur[..., 1], (ate > 0).float()], -1)
        p = self.p
        self.h = torch.tanh(torch.einsum("nshi,nsi->nsh", p["Win"], x) + torch.einsum("nshj,nsj->nsh", p["Wrec"], self.h)
                            + p["b"]) * a[..., None]
        o = torch.tanh(torch.einsum("nskh,nsh->nsk", p["Wout"], self.h) + p["bout"])
        turn = o[..., 0] * 0.6 + 0.1 * torch.randn(N, S, generator=self.gen, device=DEV)
        self.hd = self.hd + turn
        sp = 0.3 + 0.7 * (o[..., 1] + 1) / 2
        self.xy = self.xy + (sp * a)[..., None] * torch.stack([torch.cos(self.hd), torch.sin(self.hd)], -1)
        lo, hi = self.xy < 0, self.xy > W["size"]
        self.xy = torch.where(lo, -self.xy, torch.where(hi, 2 * W["size"] - self.xy, self.xy))
        self.hd = self.hd + math.pi * (lo | hi).any(-1).float()
        cost = (W["cost_base"] + W["cost_move"] * sp) * a
        # bookkeeping for measurements
        self.eaten += ate.sum(1); self.speed_sum += (sp * a).sum(1); self.turn_sum += (turn.abs() * a).sum(1)
        self.alive_ticks += a.sum(1)
        self.age = (self.age + 1) * a
        # energy (shadow worms also track energy, but it never decides anything for them)
        shadow = self.arm == 1
        R = self.R
        self.energy = (self.energy + ate - cost) * a
        # ---- deaths: frozen + real die of starvation or old age; shadow copies the REAL arm's death COUNT of the same
        #      replicate this tick, with the victims picked at random (Bedau & Packard neutral shadow)
        old = self.age >= W["max_age"]
        die = ((self.energy <= 0) | old) & self.alive & ~shadow[:, None]
        n_real_deaths = die[2 * R:].sum(1).float()
        need = torch.zeros(self.N, device=DEV); need[R:2 * R] = n_real_deaths
        die = die | self._pick(self.alive & shadow[:, None], need)
        self.deaths += die.sum(1)
        self.alive = self.alive & ~die
        self.energy = self.energy * self.alive
        # ---- births: frozen + real split when their own energy is high; shadow copies the real arm's birth COUNT,
        #      parents picked at random among the living
        ready = (self.energy >= W["e_split"]) & self.alive & ~shadow[:, None]
        nb = torch.zeros(self.N, device=DEV); nb[R:2 * R] = ready[2 * R:].sum(1).float()
        ready = ready | self._pick(self.alive & shadow[:, None], nb)
        self._birth(ready, shadow)

    def _pick(self, mask, n):
        """For each world choose n[w] random slots among mask[w] (returns a bool mask)."""
        if not bool((n > 0).any()):
            return torch.zeros_like(mask)
        key = torch.rand(mask.shape, generator=self.gen, device=DEV) + (~mask).float() * 10   # non-candidates sort last
        rank = key.argsort(1).argsort(1)
        return (rank < n[:, None]) & mask

    def _birth(self, parent, shadow):
        free = ~self.alive
        prank = parent.cumsum(1) - 1                                   # 0,1,2.. among parents in each world
        free_slots = torch.sort((~free).float(), dim=1, stable=True).indices           # free slot indices first
        n_free = free.sum(1, keepdim=True)
        ok = parent & (prank < n_free)
        if not bool(ok.any()):
            return
        w_idx, p_idx = ok.nonzero(as_tuple=True)
        c_idx = free_slots[w_idx, prank[w_idx, p_idx]]
        # child = parent copy (+ mutation unless frozen); energy split in half (real/frozen); shadow children draw e_start
        g = self.G[w_idx, p_idx]
        mutate = (self.arm[w_idx] != 0).float()[:, None]
        d = mutate * W["mut_sigma"] * torch.randn(g.shape, generator=self.gen, device=DEV)
        g = g + d
        self.nmut[w_idx, c_idx] = self.nmut[w_idx, p_idx] + mutate[:, 0]
        self.msize[w_idx, c_idx] = self.msize[w_idx, p_idx] + d.norm(dim=-1)
        self.G[w_idx, c_idx] = g
        half = self.energy[w_idx, p_idx] / 2
        self.energy[w_idx, p_idx] = half
        self.energy[w_idx, c_idx] = half
        self.xy[w_idx, c_idx] = self.xy[w_idx, p_idx]
        self.hd[w_idx, c_idx] = 2 * math.pi * torch.rand(len(w_idx), generator=self.gen, device=DEV)
        self.h[w_idx, c_idx] = 0; self.prev[w_idx, c_idx] = self.prev[w_idx, p_idx]
        self.age[w_idx, c_idx] = 0
        self.lineage[w_idx, c_idx] = self.lineage[w_idx, p_idx]
        self.alive[w_idx, c_idx] = True
        self.births += torch.bincount(w_idx, minlength=self.N).float()
        self.p = unpack(self.G)

    # ------------------------------------------------------------------ measurements (one row per world)
    @torch.no_grad()
    def measure(self):
        a = self.alive; n = a.sum(1).float(); nn = n.clamp(min=1)
        af = a.float()[..., None]
        dist = ((self.G - self.founder[:, None]) ** 2).sum(-1).sqrt()                    # genetic distance to founder
        mean_g = (self.G * af).sum(1) / nn[:, None]
        div = (((self.G - mean_g[:, None]) ** 2).sum(-1) * a).sum(1) / nn               # genetic diversity (variance)
        lin = torch.zeros(self.N, self.S, device=DEV).scatter_add_(1, self.lineage, a.float())
        t = self.alive_ticks.clamp(min=1)
        dom = lin.argmax(1)                                                             # biggest surviving family
        in_dom = (self.lineage == dom[:, None]) & a
        nd = in_dom.sum(1).clamp(min=1)
        row = dict(pop=n, births=self.births.clone(), deaths=self.deaths.clone(),
                   mutations=(self.nmut * a).sum(1) / nn, mutation_size=(self.msize * a).sum(1) / nn,
                   top_family=dom.float(), top_family_share=in_dom.sum(1) / nn,
                   top_family_mutations=(self.nmut * in_dom).sum(1) / nd,
                   energy=(self.energy * a).sum(1) / nn, food=self.food.sum(1),
                   gdist=(dist * a).sum(1) / nn, diversity=div, lineages=(lin > 0).sum(1).float(),
                   eat_rate=self.eaten / t, speed=self.speed_sum / t, turn=self.turn_sum / t,
                   age=(self.age * a).sum(1) / nn)
        self.births.zero_(); self.deaths.zero_(); self.eaten.zero_(); self.speed_sum.zero_()
        self.turn_sum.zero_(); self.alive_ticks.zero_()
        return {k: v.cpu().tolist() for k, v in row.items()}


STATE_KEYS = ["patches", "food", "alive", "G", "founder", "lineage", "energy", "age", "xy", "hd", "h", "prev", "nmut", "msize"]


def save_snapshot(w, path, t):
    """Everything needed to continue the run exactly from tick t (plus the random generator state)."""
    torch.save(dict(t=t, R=w.R, S=w.S, W=W, state={k: getattr(w, k).cpu() for k in STATE_KEYS},
                    gen=w.gen.get_state()), path)


def resume_snapshot(path, pick=None, copies=1, seed=None):
    """Rebuild a world from a snapshot. pick=r keeps only replicate r (in all 3 arms) and makes `copies` copies of it;
    each copy then continues with its own random luck (new seed) - same world, same moment, different futures."""
    snap = torch.load(path, weights_only=False)
    R, S = snap["R"], snap["S"]
    w = EqWorld.__new__(EqWorld)
    st = {k: v.to(DEV) for k, v in snap["state"].items()}
    for k in ("nmut", "msize"):                                    # snapshots from before mutation tracking
        st.setdefault(k, torch.zeros_like(st["energy"]))
    if pick is not None:
        idx = torch.tensor([a * R + pick for a in range(3) for _ in range(copies)], device=DEV)
        st = {k: v[idx].clone() for k, v in st.items()}
        R = copies
    w.R, w.S, w.N = R, S, 3 * R
    w.gen = torch.Generator(device=DEV)
    if seed is None:
        w.gen.set_state(snap["gen"])
    else:
        w.gen.manual_seed(seed)
    w.arm = torch.arange(w.N, device=DEV) // R
    for k, v in st.items():
        setattr(w, k, v)
    for k in ("births", "deaths", "eaten", "speed_sum", "turn_sum", "alive_ticks"):
        setattr(w, k, torch.zeros(w.N, device=DEV))
    w.p = unpack(w.G)
    return w, snap["t"]


@torch.no_grad()
def frame(w, world=0, max_worms=640):
    """Live view / replay picture of one world (see python/remote/simctl.py)."""
    n = min(max(world, 0), w.N - 1); a = w.alive[n]
    worms = [[round(p[0], 1), round(p[1], 1), 0] for p in w.xy[n][a][:max_worms].cpu().tolist()]
    food = [[round(p[0], 1), round(p[1], 1), round(f / W["food_max"], 2)] for p, f in zip(w.patches[n].cpu().tolist(), w.food[n].cpu().tolist())]
    return dict(size=W["size"], worms=worms, food=food, extra={"arm": ARMS[int(w.arm[n])], "pop": int(a.sum())})


def load_founders(path, R):
    r = json.loads(Path(path).read_text())["normal"]["genomes"]
    g = torch.tensor(r, dtype=torch.float32)
    return g[torch.arange(R) % len(g)]


def main():
    args = [a for a in sys.argv[1:]]
    def opt(name, default):
        if name in args:
            i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    founders = opt("--founders", str(HERE.parent / "toybrain" / "results_gpu_300g_30s_fair.json"))
    S = int(opt("--slots", 640)); save_at = [int(x) for x in opt("--save-at", "").split(",") if x]
    resume = opt("--resume", None); pick = opt("--pick", None); copies = int(opt("--copies", 1))
    tag = opt("--tag", ""); every = int(opt("--every", 500))
    quick = "--quick" in args; args = [a for a in args if a != "--quick"]
    if quick:
        every = 50
    R = int(args[0]) if args else 30
    T = int(args[1]) if len(args) > 1 else 50000
    log = (HERE / "eq_log.txt").open("a")
    def say(m):
        line = f"{time.strftime('%H:%M:%S')} {m}"; print(line, flush=True); log.write(line + "\n"); log.flush()
    snapdir = HERE / "snapshots"; snapdir.mkdir(exist_ok=True)
    if resume:
        waited = 0
        while not Path(resume).exists() and waited < 7200:        # the job making it may still be running
            if waited % 300 == 0:
                say(f"waiting for snapshot {resume} ...")
            time.sleep(10); waited += 10
        w, t_start = resume_snapshot(resume, None if pick is None else int(pick), copies, seed=None if pick is None else 1000 + int(pick))
        R = w.R; src = f"snapshot {Path(resume).name} (tick {t_start}" + (f", replicate {pick} x {copies} copies)" if pick is not None else ")")
    else:
        if Path(founders).exists():
            F = load_founders(founders, R); src = founders
        else:
            F = 0.5 * torch.randn(R, glen(BRAIN), generator=torch.Generator().manual_seed(0)); src = "random"
        w = EqWorld(F, R, S, seed=1); t_start = 0
    say(f"equilibrium world on {DEV}: {R} replicates x 3 arms x {w.S} slots, ticks {t_start} -> {t_start + T}, from: {src}")
    series, t0 = [], time.time()
    sys.path.insert(0, str(HERE.parent / "remote"))
    from simctl import SimControl
    ctl = SimControl(f"eq{tag}", sync=(torch.cuda.synchronize if torch.cuda.is_available() else None))
    for t in range(t_start + 1, t_start + T + 1):
        w.tick()
        ctl.after_tick(t, lambda i, m: frame(w, i, m))
        if t in save_at:
            fn = snapdir / f"eq{tag}_t{t}.pt"; save_snapshot(w, fn, t); say(f"snapshot saved: {fn.name}")
        if t % every == 0:
            m = w.measure(); m["t"] = t; series.append(m)
            if t % (every * 20) == 0 or t == t_start + T:
                pop = np.array(m["pop"]).reshape(3, R).mean(1); gd = np.array(m["gdist"]).reshape(3, R).mean(1)
                say(f"t {t:7d}  pop frozen/shadow/real {pop[0]:5.1f} {pop[1]:5.1f} {pop[2]:5.1f}   "
                    f"genetic distance {gd[0]:.2f} {gd[1]:.2f} {gd[2]:.2f}   ({time.time() - t0:.0f} s)")
    if T >= 100000 or resume:
        save_snapshot(w, snapdir / f"eq{tag}_end_t{t_start + T}.pt", t_start + T)
    out = HERE / "results" / f"eq{tag}_{t_start + T}t_{R}s.json"; out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(world=W, slots=w.S, replicates=R, ticks=T, start_tick=t_start, every=every,
                                   founders=src, arms=ARMS, series=series)))
    say(f"saved {out.name}  EQ_DONE")


if __name__ == "__main__":
    main()
