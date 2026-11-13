"""Factor engine: the equilibrium world (python/equilibrium) generalised so that EVERY factor in
python/factors/catalog.toml can be switched on, set to realistic 'auto' values, or set by hand from a config file.

How it fits together (details in README.md):
  config file (form)  ->  config.py checks it against the catalog, fills defaults  ->  World(...) here
  World holds R replicate worlds x the chosen arms (frozen / shadow / real), each with S worm slots.
  Each tick: every active factor updates its environment, adds sense inputs, and modifies per-worm costs, speed,
  death chance, fertility and mutation; then worms sense, think, move, eat, pay energy, die and split.

Genome (per worm) = toy-brain network with a FIXED input layout (5 base inputs + every possible sense channel; a
channel reads 0 while its factor is off) + a fixed list of TRAIT genes (resistances, mutation-rate gene, ...).
Fixed layouts mean founders and results are comparable across all configs.
"""
import json, math, time
from pathlib import Path

import numpy as np
import torch

from fields import Field

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")

BASE_INPUTS = ["smell", "dsmell", "taste", "dtaste", "eating"]
SENSES = ["temperature", "dtemperature", "oxygen", "co2", "salt", "ph", "light", "touch", "vibration",
          "efield", "mfield", "pheromone", "toxin", "pathogen", "predator"]
INPUTS = BASE_INPUTS + SENSES
H = 8                                                    # hidden neurons (toy-brain reference size)
TRAITS = {                                              # name: default value (founders start here)
    "mut_rate": 0.0,        # log10 multiplier on mutation size (0 = x1, 1 = x10). Evolves only if mutation_rate.evolvable
    "repair": 0.0,          # DNA-repair efficiency 0..1: fraction of radiation/mutagen damage repaired (costs energy)
    "resist_toxin": 0.0,    # 0..1 resistance to toxins
    "resist_pathogen": 0.0, # 0..1 resistance to bacterial pathogens / microsporidia / fungal parasites
    "resist_virus": 0.0,    # 0..1 resistance to the virus
    "heat_tol": 0.0,        # degrees C added to the temperature tolerance window
    "digest_b": 0.0,        # 0..1 ability to digest food type B (key innovation)
    "nictation": 0.0,       # 0..1 tendency to ride carriers
    "male": 0.0,            # 0..1 chance a child is male (mating_system factor)
    "maternal": 0.5,        # fraction of the parent's energy given to the child at a split
    "dauer": 0.0,           # 0..1 tendency to enter dauer (resting, no cost, no eating) when crowded / starving
    "escape": 0.0,          # 0..1 extra burst speed when touched (predators, traps)
}
TRAIT_NAMES = list(TRAITS)
REF_GENES = 130                                          # genome size of the reference toy brain (mutation scaling)


def layout():
    I = len(INPUTS)
    return [("Win", (H, I)), ("Wrec", (H, H)), ("b", (H,)), ("Wout", (2, H)), ("bout", (2,)), ("traits", (len(TRAITS),))]


def glen():
    return sum(int(np.prod(sh)) for _, sh in layout())


def unpack(G):
    out, i = {}, 0
    for n, sh in layout():
        k = int(np.prod(sh)); out[n] = G[..., i:i + k].reshape(G.shape[:-1] + sh); i += k
    return out


def from_toy(toy):
    """Convert toy-brain genomes (130 genes, 5 inputs) to the engine layout: extra sense columns = 0 (ignored until
    evolution uses them), traits = defaults."""
    toy = torch.as_tensor(toy, dtype=torch.float32)
    R = toy.shape[0]; out = torch.zeros(R, glen())
    i = 0; t = 0
    for n, sh in layout():
        k = int(np.prod(sh))
        if n == "Win":
            w = torch.zeros(R, H, len(INPUTS)); w[:, :, :5] = toy[:, :H * 5].reshape(R, H, 5); out[:, i:i + k] = w.reshape(R, -1); t = H * 5
        elif n == "traits":
            out[:, i:i + k] = torch.tensor([TRAITS[x] for x in TRAIT_NAMES])
        else:
            out[:, i:i + k] = toy[:, t:t + k]; t += k
        i += k
    return out


class World:
    def __init__(self, cfg, founders, factors):
        """cfg: the validated config (dict). founders: (R, glen()) genomes. factors: list of active Factor objects."""
        self.cfg = cfg; e = cfg["world"]
        self.R = R = int(cfg["run"]["replicates"]); self.arms = cfg["run"]["arms"]; A = len(self.arms)
        self.N = N = R * A; self.S = S = int(e["slots"]); self.size = float(e["size"])
        self.gen = torch.Generator(device=DEV); self.gen.manual_seed(int(cfg["run"]["seed"]))
        self.arm_name = [a for a in self.arms for _ in range(R)]
        self.arm = torch.tensor([self.arms.index(a) for a in self.arm_name], device=DEV)
        self.is_frozen = torch.tensor([a == "frozen" for a in self.arm_name], device=DEV)
        self.is_shadow = torch.tensor([a == "shadow" for a in self.arm_name], device=DEV)
        self.real_of = {}                                              # shadow world -> its real world (same replicate)
        if "shadow" in self.arms:
            assert "real" in self.arms, "a shadow arm needs a real arm to copy"
            for r in range(R):
                self.real_of[self.arms.index("shadow") * R + r] = self.arms.index("real") * R + r
        g = torch.Generator().manual_seed(int(cfg["run"]["seed"]))
        layout_ = 20 + (self.size - 40) * torch.rand(R, int(e["patches"]), 2, generator=g)
        self.patches = layout_.repeat(A, 1, 1).to(DEV)                 # same layout in every arm of a replicate
        P = self.patches.shape[1]
        self.food_max = torch.full((N, P), float(e["food_max"]), device=DEV)
        self.food = self.food_max.clone()
        self.food_type = torch.zeros(N, P, dtype=torch.long, device=DEV)   # 0 = normal food (food_quality may change it)
        self.food_value = torch.ones(N, P, device=DEV)                     # energy per unit eaten
        self.regrow = torch.full((N, P), float(e["regrow"]), device=DEV)
        n0 = int(S * float(e["start_fill"]))
        self.alive = torch.zeros(N, S, dtype=torch.bool, device=DEV); self.alive[:, :n0] = True
        F = founders.to(DEV).float()
        self.G = F.repeat(A, 1)[:, None, :].expand(N, S, F.shape[1]).clone()
        self.founder = F.repeat(A, 1)
        self.lineage = torch.arange(S, device=DEV)[None].expand(N, S).clone()
        self.energy = torch.full((N, S), float(e["e_start"]), device=DEV) * self.alive
        self.age = float(e["max_age"]) * torch.rand(N, S, generator=self.gen, device=DEV) * self.alive
        self.xy = self.size * torch.rand(N, S, 2, generator=self.gen, device=DEV)
        self.hd = 2 * math.pi * torch.rand(N, S, generator=self.gen, device=DEV)
        self.h = torch.zeros(N, S, H, device=DEV)
        self.prev = torch.zeros(N, S, 2, device=DEV)
        self.dauer = torch.zeros(N, S, dtype=torch.bool, device=DEV)  # resting stage (no cost, no eating, no moving)
        self.sense = {k: torch.zeros(N, S, device=DEV) for k in SENSES}
        self.t = 0
        self.stats = {k: torch.zeros(N, device=DEV) for k in ("births", "deaths", "eaten", "speed", "turn", "alive_ticks")}
        self.extra_deaths = {}                                         # cause -> (N,) count (from factors)
        self.p = unpack(self.G)
        self.factors = factors
        for f in factors:
            f.setup(self)

    # ------------------------------------------------------------------------------------------------ helpers
    def rand(self, *shape):
        return torch.rand(*shape, generator=self.gen, device=DEV)

    def randn(self, *shape):
        return torch.randn(*shape, generator=self.gen, device=DEV)

    def trait(self, name):
        return self.p["traits"][..., TRAIT_NAMES.index(name)]

    def trait01(self, name):
        return self.trait(name).clamp(0, 1)

    def pick(self, mask, n):
        """For each world choose n[w] random slots among mask[w] (bool mask out)."""
        if not bool((n > 0).any()):
            return torch.zeros_like(mask)
        key = self.rand(*mask.shape) + (~mask).float() * 10
        rank = key.argsort(1).argsort(1)
        return (rank < n[:, None]) & mask

    def kill(self, mask, cause):
        mask = mask & self.alive
        self.extra_deaths[cause] = self.extra_deaths.get(cause, torch.zeros(self.N, device=DEV)) + mask.sum(1)
        self._dead_now = self._dead_now | mask

    # ------------------------------------------------------------------------------------------------ one tick
    @torch.no_grad()
    def tick(self):
        e = self.cfg["world"]; N, S = self.N, self.S; self.t += 1; t = self.t
        self._dead_now = torch.zeros(N, S, dtype=torch.bool, device=DEV)
        a = (self.alive & ~self.dauer).float()                         # active worms
        for f in self.factors:
            f.update(self, t)
        # per-worm modifiers that factors adjust
        m = dict(cost=torch.zeros(N, S, device=DEV), speed=torch.ones(N, S, device=DEV),
                 death_p=torch.zeros(N, S, device=DEV), fertility=torch.ones(N, S, device=DEV),
                 mut=torch.ones(N, S, device=DEV), eat=torch.ones(N, S, device=DEV),
                 smell_food=torch.ones(N, 1, device=DEV), smell_add=torch.zeros(N, S, device=DEV))
        for k in self.sense:
            self.sense[k].zero_()
        for f in self.factors:
            f.modify(self, m)
        # base senses: food smell + taste (as in the toy brain)
        d2 = ((self.xy[:, :, None, :] - self.patches[:, None]) ** 2).sum(-1)
        frac = (self.food / self.food_max.clamp(min=1e-9))[:, None, :]
        sm = (frac * torch.exp(-d2 / (2 * float(e["sig_smell"]) ** 2))).sum(-1) * m["smell_food"] + m["smell_add"]
        ta = (frac * torch.exp(-d2 / (2 * float(e["sig_taste"]) ** 2))).sum(-1)
        cur = torch.stack([sm + 0.01 * self.randn(N, S), ta + 0.01 * self.randn(N, S)], -1)
        dcur = (cur - self.prev) * 10; self.prev = cur
        # eating (shared when crowded); food type B only digestible with the digest_b trait
        inside = (d2 < float(e["patch_r"]) ** 2).float() * a[:, :, None]
        want = inside * float(e["bite"]) * m["eat"][:, :, None]
        demand = want.sum(1)
        share = torch.where(demand > 0, (self.food / demand.clamp(min=1e-9)).clamp(max=1.0), torch.zeros_like(demand))
        got = want * share[:, None, :]
        self.food = self.food - got.sum(1)
        digest = torch.where(self.food_type[:, None, :] == 1, self.trait01("digest_b")[:, :, None], torch.ones_like(got))
        m["energy_in"] = (got * self.food_value[:, None, :] * digest).sum(-1)
        ate = got.sum(-1)
        self.food = self.food + self.regrow * (self.food_max - self.food)
        for f in self.factors:
            f.after_eat(self, got, m)                                  # may change m["energy_in"] (digestion, toxic food)
        energy_in = m["energy_in"]
        # brain
        x = torch.cat([torch.stack([cur[..., 0], dcur[..., 0], cur[..., 1], dcur[..., 1], (ate > 0).float()], -1),
                       torch.stack([self.sense[k] for k in SENSES], -1)], -1)
        p = self.p
        self.h = torch.tanh(torch.einsum("nshi,nsi->nsh", p["Win"], x) + torch.einsum("nshj,nsj->nsh", p["Wrec"], self.h)
                            + p["b"]) * a[..., None]
        o = torch.tanh(torch.einsum("nskh,nsh->nsk", p["Wout"], self.h) + p["bout"])
        turn = o[..., 0] * 0.6 + 0.1 * self.randn(N, S)
        self.hd = self.hd + turn * a
        sp = (0.3 + 0.7 * (o[..., 1] + 1) / 2) * m["speed"] * a
        self.xy = self.xy + sp[..., None] * torch.stack([torch.cos(self.hd), torch.sin(self.hd)], -1)
        for f in self.factors:
            f.after_move(self)
        lo, hi = self.xy < 0, self.xy > self.size
        self.xy = torch.where(lo, -self.xy, torch.where(hi, 2 * self.size - self.xy, self.xy)).clamp(0, self.size)
        self.hd = self.hd + math.pi * (lo | hi).any(-1).float()
        # energy: living + moving + factor costs + trait upkeep (resistances aren't free)
        upkeep = float(e["trait_cost"]) * sum(self.trait01(k) for k in
                                             ("repair", "resist_toxin", "resist_pathogen", "resist_virus", "digest_b", "escape"))
        upkeep = upkeep + float(e["trait_cost"]) * self.trait("heat_tol").clamp(min=0) / 5
        cost = (float(e["cost_base"]) + float(e["cost_move"]) * sp + m["cost"] + upkeep) * a
        cost = cost + float(e["dauer_cost"]) * self.dauer.float()
        self.energy = (self.energy + energy_in - cost) * self.alive
        st = self.stats
        st["eaten"] += ate.sum(1); st["speed"] += sp.sum(1); st["turn"] += (turn.abs() * a).sum(1); st["alive_ticks"] += a.sum(1)
        self.age = (self.age + 1) * self.alive
        # deaths
        shadow = self.is_shadow
        old = self.age >= float(e["max_age"])
        natural = ((self.energy <= 0) | old | (self.rand(N, S) < m["death_p"]) | self._dead_now) & self.alive & ~shadow[:, None]
        die = natural
        need = torch.zeros(N, device=DEV)
        for sw, rw in self.real_of.items():
            need[sw] = die[rw].sum()
        die = die | self.pick(self.alive & shadow[:, None], need)
        st["deaths"] += die.sum(1)
        self.alive = self.alive & ~die
        self.energy = self.energy * self.alive
        self.dauer = self.dauer & self.alive
        # births
        ready = (self.energy >= float(e["e_split"])) & self.alive & ~self.dauer & ~shadow[:, None]
        ready = ready & (self.rand(N, S) < m["fertility"].clamp(0, 1))
        nb = torch.zeros(N, device=DEV)
        for sw, rw in self.real_of.items():
            nb[sw] = ready[rw].sum()
        ready = ready | self.pick(self.alive & shadow[:, None], nb)
        self._birth(ready, m["mut"])

    def _birth(self, parent, mut_mult):
        free = ~self.alive
        prank = parent.cumsum(1) - 1
        free_slots = torch.sort((~free).float(), dim=1, stable=True).indices
        ok = parent & (prank < free.sum(1, keepdim=True))
        if not bool(ok.any()):
            return
        wi, pi = ok.nonzero(as_tuple=True)
        ci = free_slots[wi, prank[wi, pi]]
        g = self.G[wi, pi]
        e = self.cfg["world"]
        sigma = float(e["mut_sigma"]) * math.sqrt(REF_GENES / g.shape[1])           # fair scaling by genome size
        rate = 10 ** self.p["traits"][wi, pi, TRAIT_NAMES.index("mut_rate")].clamp(-3, 2)
        mult = (~self.is_frozen[wi]).float() * rate * mut_mult[wi, pi]
        g = g + (sigma * mult)[:, None] * self.randn(*g.shape)
        frac = self.p["traits"][wi, pi, TRAIT_NAMES.index("maternal")].clamp(0.05, 0.95)
        child_e = self.energy[wi, pi] * frac
        self.energy[wi, pi] = self.energy[wi, pi] - child_e
        self.G[wi, ci] = g
        self.energy[wi, ci] = child_e
        self.xy[wi, ci] = self.xy[wi, pi]
        self.hd[wi, ci] = 2 * math.pi * self.rand(len(wi))
        self.h[wi, ci] = 0; self.prev[wi, ci] = self.prev[wi, pi]
        self.age[wi, ci] = 0
        self.lineage[wi, ci] = self.lineage[wi, pi]
        self.dauer[wi, ci] = False
        self.alive[wi, ci] = True
        self.stats["births"] += torch.bincount(wi, minlength=self.N).float()
        self.p = unpack(self.G)
        for f in self.factors:
            f.on_birth(self, wi, pi, ci)

    # ------------------------------------------------------------------------------------------------ measuring
    @torch.no_grad()
    def measure(self):
        a = self.alive; n = a.sum(1).float(); nn = n.clamp(min=1); af = a.float()
        dist = ((self.G - self.founder[:, None]) ** 2).sum(-1).sqrt()
        mean_g = (self.G * af[..., None]).sum(1) / nn[:, None]
        div = (((self.G - mean_g[:, None]) ** 2).sum(-1) * af).sum(1) / nn
        lin = torch.zeros(self.N, self.S, device=DEV).scatter_add_(1, self.lineage, af)
        st = self.stats; at = st["alive_ticks"].clamp(min=1)
        row = dict(pop=n, births=st["births"].clone(), deaths=st["deaths"].clone(),
                   energy=(self.energy * af).sum(1) / nn, food=self.food.sum(1), gdist=(dist * af).sum(1) / nn,
                   diversity=div, lineages=(lin > 0).sum(1).float(), eat_rate=st["eaten"] / at,
                   speed=st["speed"] / at, turn=st["turn"] / at, age=(self.age * af).sum(1) / nn,
                   dauer=(self.dauer & a).sum(1).float())
        for k in TRAIT_NAMES:                                      # mean value of every trait gene
            row["trait_" + k] = (self.trait(k) * af).sum(1) / nn
        sense_w = self.p["Win"][..., 5:].abs().mean(2)            # (N, S, n_senses): how strongly each sense is wired
        for j, k in enumerate(SENSES):
            row["wire_" + k] = (sense_w[..., j] * af).sum(1) / nn
        for cause, c in self.extra_deaths.items():
            row["deaths_" + cause] = c.clone(); c.zero_()
        for f in self.factors:
            row.update(f.measure(self))
        for v in st.values():
            v.zero_()
        return {k: v.cpu().tolist() for k, v in row.items()}
