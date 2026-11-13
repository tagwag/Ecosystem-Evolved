"""Biological, food and population factors (catalog categories: food, biological, population, genetic, meta).

Each class documents its model in its docstring; the numbers and the research behind them are in FACTOR_GUIDE.md.
All of them are SIMPLIFIED models of the effect described in the literature, not biochemistry.
"""
import math

import torch

from factors_env import Factor
from fields import Field


def _near(w, pts, r):
    """(N, S, K) bool: worm within r of each point; pts (N, K, 2)."""
    return ((w.xy[:, :, None, :] - pts[:, None]) ** 2).sum(-1) < r * r


def _mean(w, x):
    a = w.alive.float(); return (x * a).sum(1) / a.sum(1).clamp(min=1)


# ===================================================================================================== FOOD
class FoodAmount(Factor):
    """Scales how much food there is. food_max_mult x patch size, regrow_mult x regrowth (sets carrying capacity),
    value_mult x energy per unit. Optional feast/famine: famine_every ticks, famine_len ticks with regrowth x famine_mult."""
    name = "food_amount"

    def setup(self, w):
        p = self.params
        w.food_max *= p.get("food_max_mult", 1.0); w.food = w.food_max.clone()
        w.regrow *= p.get("regrow_mult", 1.0); self.base_regrow = w.regrow.clone()
        w.food_value *= p.get("value_mult", 1.0)

    def update(self, w, t):
        p = self.params; ev = int(p.get("famine_every", 0))
        if ev > 0:
            famine = (t % ev) >= ev - int(p.get("famine_len", 0))          # famine at the END of each cycle
            w.regrow = self.base_regrow * (p.get("famine_mult", 0.1) if famine else 1.0)


class FoodLayout(Factor):
    """Where food is. mode: 'fixed' (default patches) | 'moving' (patches drift at `drift` units/tick) |
    'seasonal' (every `relocate_every` ticks all patches jump to new spots) | 'uniform' (patches re-spread evenly)."""
    name = "food_layout"

    def setup(self, w):
        p = self.params
        if p.get("mode") == "uniform":
            k = w.patches.shape[1]; side = math.ceil(math.sqrt(k))
            g = (torch.arange(side, device=w.gen.device) + 0.5) * w.size / side
            X, Y = torch.meshgrid(g, g, indexing="xy")
            pts = torch.stack([X.flatten(), Y.flatten()], -1)[:k]
            w.patches = pts[None].expand(w.N, -1, -1).clone()
        self.vel = torch.randn(w.N, w.patches.shape[1], 2, generator=w.gen, device=w.gen.device)

    def update(self, w, t):
        p = self.params
        if p.get("mode") == "moving":
            w.patches = (w.patches + float(p.get("drift", 0.05)) * self.vel) % w.size
        elif p.get("mode") == "seasonal" and t % int(p.get("relocate_every", 10000)) == 0:
            w.patches = 20 + (w.size - 40) * torch.rand(w.patches.shape, generator=w.gen, device=w.gen.device)


class FoodQuality(Factor):
    """Food types. frac_b of patches hold food type B (worth value_b x energy) that a worm can only digest in
    proportion to its digest_b trait (a KEY INNOVATION it must evolve, like Lenski's citrate). frac_toxic of patches
    are toxic (eating there costs toxic_cost per unit). quality_mult scales the energy of all normal food."""
    name = "food_quality"

    def setup(self, w):
        p = self.params; P = w.patches.shape[1]
        r = torch.rand(w.R, P, generator=torch.Generator().manual_seed(7)).repeat(len(w.arms), 1).to(w.gen.device)
        fb, ft = p.get("frac_b", 0.0), p.get("frac_toxic", 0.0)
        w.food_type = torch.where(r < fb, 1, 0)
        self.toxic = (r >= fb) & (r < fb + ft)
        w.food_value = torch.where(w.food_type == 1, torch.full_like(w.food_value, p.get("value_b", 2.0)),
                                   w.food_value * p.get("quality_mult", 1.0))

    def after_eat(self, w, got, m):
        if bool(self.toxic.any()):
            bad = (got * self.toxic[:, None, :]).sum(-1)
            m["energy_in"] = m["energy_in"] - self.params.get("toxic_cost", 2.0) * bad * (1 - w.trait01("resist_toxin"))

    def measure(self, w):
        return {"trait_digest_b_mean": _mean(w, w.trait01("digest_b"))}


class Digestion(Factor):
    """Food goes into a gut (capacity `gut_cap`) and is absorbed at `rate` per tick, `moving_mult` x slower at full
    speed (real worms digest better when still). A full gut stops eating."""
    name = "digestion"

    def setup(self, w):
        self.gut = torch.zeros(w.N, w.S, device=w.gen.device)

    def modify(self, w, m):
        full = self.gut >= float(self.params.get("gut_cap", 3.0))
        m["eat"] *= (~full).float()

    def after_eat(self, w, got, m):
        p = self.params
        self.gut = (self.gut + m["energy_in"]) * w.alive
        rate = float(p.get("rate", 0.05))
        absorb = torch.minimum(self.gut, torch.full_like(self.gut, rate))
        self.gut = self.gut - absorb
        m["energy_in"] = absorb

    def on_birth(self, w, wi, pi, ci):
        self.gut[wi, ci] = 0


class Microbiome(Factor):
    """Each worm carries a protective-microbe level 0..1 picked up at `frac_protective` of food patches (rate `gain`
    per tick while eating there) and slowly lost (`loss`). Protection lowers pathogen infection by `protection` x level.
    Harmful microbes at `frac_harmful` of patches cost `harm_cost` per tick while carried. Antibiotics (toxins factor)
    wipe both. Children inherit `vertical` x the parent's level."""
    name = "microbiome"

    def setup(self, w):
        P = w.patches.shape[1]; g = torch.Generator().manual_seed(11)
        r = torch.rand(w.R, P, generator=g).repeat(len(w.arms), 1).to(w.gen.device)
        fp, fh = self.params.get("frac_protective", 0.3), self.params.get("frac_harmful", 0.0)
        self.prot_patch = (r < fp).float(); self.harm_patch = ((r >= fp) & (r < fp + fh)).float()
        self.level = torch.zeros(w.N, w.S, device=w.gen.device); self.harm = torch.zeros_like(self.level)
        w.protection = self.level

    def after_eat(self, w, got, m):
        p = self.params; eating = (got > 0).float()
        self.level = (self.level + p.get("gain", 0.01) * (eating * self.prot_patch[:, None]).sum(-1)).clamp(0, 1)
        self.harm = (self.harm + p.get("gain", 0.01) * (eating * self.harm_patch[:, None]).sum(-1)).clamp(0, 1)
        self.level *= 1 - p.get("loss", 0.0005); self.harm *= 1 - p.get("loss", 0.0005)
        tox = next((f for f in w.factors if f.name == "toxins"), None)
        if tox is not None and torch.is_tensor(getattr(tox, "antibiotic", None)):
            clear = (tox.antibiotic > 0.1).float(); self.level *= 1 - clear; self.harm *= 1 - clear
        m["energy_in"] = m["energy_in"] - p.get("harm_cost", 0.01) * self.harm
        w.protection = self.level * p.get("protection", 0.5)

    def on_birth(self, w, wi, pi, ci):
        v = self.params.get("vertical", 0.5)
        self.level[wi, ci] = self.level[wi, pi] * v; self.harm[wi, ci] = self.harm[wi, pi] * v

    def measure(self, w):
        return {"microbiome_protective": _mean(w, self.level), "microbiome_harmful": _mean(w, self.harm)}


# ===================================================================================================== ENEMIES
class Infection(Factor):
    """Shared machinery for things a worm can CATCH: per-worm infected flag, cost and death chance while infected,
    recovery chance, fertility loss, optional vertical (parent -> child) transmission. Resistance trait and the
    microbiome lower the chance of catching it. Subclasses decide WHERE it is caught."""
    resist_trait = "resist_pathogen"

    def setup(self, w):
        self.inf = torch.zeros(w.N, w.S, dtype=torch.bool, device=w.gen.device)
        self.caught = torch.zeros(w.N, device=w.gen.device)

    def catch(self, w, chance):
        prot = getattr(w, "protection", torch.zeros_like(chance))
        avoid = getattr(w, "inherited_avoid", None)
        c = chance * (1 - w.trait01(self.resist_trait)) * (1 - prot)
        if avoid is not None:
            c = c * (1 - 0.5 * (avoid > 0).float())
        new = (w.rand(*c.shape) < c) & w.alive & ~self.inf
        self.inf |= new; self.caught += new.sum(1)
        return new

    def modify(self, w, m):
        p = self.params; i = self.inf.float()
        m["cost"] += p.get("cost", 0.02) * i
        m["death_p"] += p.get("death", 0.0002) * i
        m["fertility"] *= 1 - p.get("fert_loss", 0.3) * i
        self.inf &= w.rand(w.N, w.S) >= p.get("recover", 0.0005)
        self.inf &= w.alive

    def on_birth(self, w, wi, pi, ci):
        v = float(self.params.get("vertical", 0.0))
        self.inf[wi, ci] = self.inf[wi, pi] & (w.rand(len(wi)) < v)

    def measure(self, w):
        out = {f"{self.name}_infected": _mean(w, self.inf.float()), f"{self.name}_new": self.caught.clone()}
        self.caught.zero_(); return out


class PathogenBacteria(Infection):
    """Bacterial pathogen living on `frac_patches` of food patches; eating there gives `infect` chance per tick.
    Infected worms smell of it nearby (pathogen sense = level of infected food in range) so avoidance can evolve.
    mode 'fixed' or 'coevolving' (Red Queen): the pathogen's counter-adaptation tracks the population's mean
    resistance with lag `lag` ticks, so resistance only helps while it is ahead."""
    name = "pathogen_bacteria"

    def setup(self, w):
        super().setup(w)
        P = w.patches.shape[1]; r = torch.rand(w.R, P, generator=torch.Generator().manual_seed(13))
        self.bad = (r < self.params.get("frac_patches", 0.3)).repeat(len(w.arms), 1).to(w.gen.device).float()
        self.adapt = torch.zeros(w.N, device=w.gen.device)

    def after_eat(self, w, got, m):
        p = self.params
        exposure = ((got > 0).float() * self.bad[:, None]).sum(-1).clamp(max=1)
        chance = p.get("infect", 0.02) * exposure
        if p.get("mode") == "coevolving":
            res = _mean(w, w.trait01(self.resist_trait))
            self.adapt += (res - self.adapt) / float(p.get("lag", 5000))
            chance = chance * (1 + 2 * self.adapt[:, None]).clamp(max=3)          # pathogen catches up
        self.catch(w, chance)
        d2 = ((w.xy[:, :, None, :] - w.patches[:, None]) ** 2).sum(-1)
        w.sense["pathogen"] += (self.bad[:, None] * torch.exp(-d2 / (2 * 15.0 ** 2))).sum(-1)


class Microsporidia(Infection):
    """Nematocida-like gut parasite: spores in an environmental field (level = infection chance per tick there) and
    parent -> child transmission (`vertical`). Mostly costs fertility."""
    name = "microsporidia"

    def setup(self, w):
        super().setup(w)
        self.field = Field(self.params.get("field", {"space": "spots", "low": 0.0, "high": 0.002}), w.N, w.size, 64,
                           w.gen.device, w.gen, patches=w.patches)

    def update(self, w, t):
        self.field.update(t)
        self.catch(w, self.field.at(w.xy))


class FungalParasites(Microsporidia):
    """Drechmeria/Harposporium-like spores: same machinery as microsporidia, but they kill (high `death`)."""
    name = "fungal_parasites"


class Virus(Infection):
    """Orsay-like virus spread worm-to-worm within `radius` (chance `transmit` per infected neighbour per tick).
    Also a source of HORIZONTAL GENE TRANSFER: with chance `hgt` per transmission, a random block of `hgt_frac` of the
    donor's genome is copied into the new host. resist_virus trait lowers infection."""
    name = "virus"
    resist_trait = "resist_virus"

    def setup(self, w):
        super().setup(w)
        seed = w.rand(w.N, w.S) < self.params.get("start_frac", 0.05)
        self.inf |= seed & w.alive
        self.hgt_events = torch.zeros(w.N, device=w.gen.device)

    def update(self, w, t):
        p = self.params; r = float(p.get("radius", 5.0))
        if t % 5:                                                     # every 5 ticks (cheaper); chance x5
            return
        xs = w.xy
        d2 = ((xs[:, :, None, :] - xs[:, None, :, :]) ** 2).sum(-1)  # (N, S, S)
        near = (d2 < r * r) & self.inf[:, None, :] & w.alive[:, :, None]
        k = near.sum(-1).float()
        before = self.inf.clone()
        new = self.catch(w, 1 - (1 - 5 * p.get("transmit", 0.01)) ** k)
        if p.get("hgt", 0.0) > 0 and bool(new.any()):
            wi, ci = new.nonzero(as_tuple=True)
            donor = torch.argmax((near[wi, ci].float() + w.rand(len(wi), w.S) * 0.01), -1)
            do = w.rand(len(wi)) < p["hgt"]
            wi, ci, donor = wi[do], ci[do], donor[do]
            if len(wi):
                L = w.G.shape[-1]; blk = max(1, int(L * p.get("hgt_frac", 0.05)))
                start = (w.rand(len(wi)) * (L - blk)).long()
                idx = start[:, None] + torch.arange(blk, device=w.gen.device)[None]
                w.G[wi[:, None], ci[:, None], idx] = w.G[wi[:, None], donor[:, None], idx]
                w.p = __import__("engine").unpack(w.G)
                self.hgt_events += torch.bincount(wi, minlength=w.N).float()

    def measure(self, w):
        out = super().measure(w); out["virus_hgt_events"] = self.hgt_events.clone(); self.hgt_events.zero_(); return out


class PredatoryFungi(Factor):
    """Arthrobotrys-like traps at `n_traps` fixed spots (radius `trap_r`). A worm inside is caught with chance
    `catch` per tick unless it escapes (escape trait: chance x (1 - escape)); caught = killed. `lure` adds a
    food-like smell around traps (real traps release food-mimicking odours)."""
    name = "predatory_fungi"

    def setup(self, w):
        k = int(self.params.get("n_traps", 10))
        self.traps = 20 + (w.size - 40) * torch.rand(w.N, k, 2, generator=w.gen, device=w.gen.device)

    def modify(self, w, m):
        p = self.params; r = float(p.get("trap_r", 6.0))
        d2 = ((w.xy[:, :, None, :] - self.traps[:, None]) ** 2).sum(-1)
        inside = (d2 < r * r).any(-1)
        w.sense["touch"] += inside.float()
        m["smell_add"] += p.get("lure", 0.0) * torch.exp(-d2 / (2 * 25.0 ** 2)).sum(-1)
        caught = inside & (w.rand(w.N, w.S) < p.get("catch", 0.05) * (1 - w.trait01("escape")))
        w.kill(caught, "fungus_trap")


class Predators(Factor):
    """Moving predators (`count` per world, speed `speed`) chase the nearest worm within `sense_r`; contact
    (within `bite_r`) takes `damage` energy, then the predator rests `cooldown` ticks. Worms feel a predator within
    `touch_r` (touch + predator senses) and the escape trait adds burst speed. mode 'pristionchus': predators are
    worm-like (slower, also eat bacteria) and only turn predatory (mouth-form switch) when food on the map is below
    `switch_food` of the maximum; they can also be eaten-food competitors."""
    name = "predators"

    def setup(self, w):
        k = int(self.params.get("count", 3)); dev = w.gen.device
        self.pos = w.size * torch.rand(w.N, k, 2, generator=w.gen, device=dev)
        self.cool = torch.zeros(w.N, k, device=dev); self.bites = torch.zeros(w.N, device=dev)
        self.predatory = torch.ones(w.N, k, dtype=torch.bool, device=dev)

    def update(self, w, t):
        p = self.params
        if p.get("mode") == "pristionchus":
            food_frac = w.food.sum(1) / w.food_max.sum(1).clamp(min=1e-9)
            self.predatory = (food_frac < p.get("switch_food", 0.5))[:, None].expand_as(self.cool)
        d = w.xy[:, None, :, :] - self.pos[:, :, None, :]                    # (N, k, S, 2)
        dist = d.norm(dim=-1) + (~w.alive[:, None]).float() * 1e9
        j = dist.argmin(-1)                                                 # nearest worm per predator
        nd = dist.gather(-1, j[..., None])[..., 0]
        tgt = torch.gather(d, 2, j[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]
        chase = (nd < p.get("sense_r", 60.0)) & (self.cool <= 0) & self.predatory
        step = torch.where(chase[..., None], tgt / nd.clamp(min=1e-6)[..., None],
                           torch.randn(self.pos.shape, generator=w.gen, device=w.gen.device) * 0.5)
        self.pos = (self.pos + float(p.get("speed", 0.8)) * step).clamp(0, w.size)
        bite = chase & (nd < p.get("bite_r", 3.0))
        if bool(bite.any()):
            ni, ki = bite.nonzero(as_tuple=True); si = j[ni, ki]
            w.energy[ni, si] -= float(p.get("damage", 5.0)) * (1 - 0.5 * w.trait01("escape")[ni, si])
            self.cool[ni, ki] = float(p.get("cooldown", 60))
            self.bites += torch.bincount(ni, minlength=w.N).float()
        self.cool -= 1

    def modify(self, w, m):
        d2 = ((w.xy[:, :, None, :] - self.pos[:, None]) ** 2).sum(-1)
        near = (d2 < self.params.get("touch_r", 8.0) ** 2).any(-1).float()
        w.sense["touch"] += near; w.sense["predator"] += torch.exp(-d2 / (2 * 20.0 ** 2)).sum(-1)
        m["speed"] *= 1 + near * w.trait01("escape")

    def measure(self, w):
        out = {"predator_bites": self.bites.clone()}; self.bites.zero_(); return out


class Competitors(Factor):
    """Another species eating the same food (C. briggsae-like): `count` simple agents that drift to the nearest
    patch and eat `bite` x efficiency, where efficiency rises with temperature (briggsae wins when warm):
    eff = 1 + temp_slope x (T - 20) using the temperature factor's field if active."""
    name = "competitors"

    def setup(self, w):
        k = int(self.params.get("count", 50))
        self.pos = w.size * torch.rand(w.N, k, 2, generator=w.gen, device=w.gen.device)

    def update(self, w, t):
        p = self.params
        d = w.patches[:, None] - self.pos[:, :, None]                     # (N, k, P, 2)
        dist = d.norm(dim=-1) + (w.food[:, None] < 0.5).float() * 1e6
        j = dist.argmin(-1); nd = dist.gather(-1, j[..., None])[..., 0]
        tgt = torch.gather(d, 2, j[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]
        self.pos = (self.pos + 0.6 * tgt / nd.clamp(min=1e-6)[..., None]).clamp(0, w.size)
        temp = next((f for f in w.factors if f.name == "temperature"), None)
        T = temp.field.at(self.pos) if temp is not None else torch.full(self.pos.shape[:2], 20.0, device=w.gen.device)
        eff = (1 + p.get("temp_slope", 0.05) * (T - 20)).clamp(min=0)
        at = (nd < float(w.cfg["world"]["patch_r"])).float() * eff * p.get("bite", 0.5)
        eat = torch.zeros_like(w.food).scatter_add_(1, j, at)
        w.food = (w.food - eat).clamp(min=0)


class Carriers(Factor):
    """Snails/isopods that pass by every `every` ticks along a straight path; worms within `radius` of a carrier
    climb on with chance `nictation` trait x `board` per tick and are dropped `distance` away. Dispersal helps escape
    crowded or empty areas."""
    name = "carriers"

    def setup(self, w):
        self.rides = torch.zeros(w.N, device=w.gen.device)

    def update(self, w, t):
        p = self.params
        if t % int(p.get("every", 2000)):
            return
        c = 20 + (w.size - 40) * torch.rand(w.N, 1, 2, generator=w.gen, device=w.gen.device)
        near = _near(w, c, float(p.get("radius", 20.0)))[..., 0]
        board = near & w.alive & (w.rand(w.N, w.S) < p.get("board", 0.5) * w.trait01("nictation"))
        if bool(board.any()):
            ang = 2 * math.pi * w.rand(w.N, 1)
            jump = float(p.get("distance", 150.0)) * torch.cat([torch.cos(ang), torch.sin(ang)], -1)
            w.xy = torch.where(board[..., None], (w.xy + jump[:, None]) % w.size, w.xy)
            self.rides += board.sum(1)

    def measure(self, w):
        out = {"carrier_rides": self.rides.clone()}; self.rides.zero_(); return out


# ===================================================================================================== POPULATION
class PopulationDensity(Factor):
    """Ascaroside-like crowding pheromone: every worm adds scent to a coarse grid; the pheromone sense reads it.
    Worms enter DAUER (no cost, no eating, no moving) with chance dauer-trait x `dauer_rate` when the local scent is
    above `crowd` or their energy is below `hungry`, and leave dauer with chance `exit_rate` when scent is low."""
    name = "population_density"

    def setup(self, w):
        self.cells = 32

    def modify(self, w, m):
        p = self.params; c = self.cells
        i = (w.xy / w.size * c).long().clamp(0, c - 1); flat = i[..., 1] * c + i[..., 0]
        grid = torch.zeros(w.N, c * c, device=w.gen.device).scatter_add_(1, flat, w.alive.float())
        scent = grid.gather(1, flat) / float(p.get("per_cell_full", 10.0))
        w.sense["pheromone"] += scent
        crowd = (scent > p.get("crowd", 1.0)) | (w.energy < p.get("hungry", 2.0))
        enter = crowd & w.alive & ~w.dauer & (w.rand(w.N, w.S) < p.get("dauer_rate", 0.01) * w.trait01("dauer"))
        leave = w.dauer & ~crowd & (w.rand(w.N, w.S) < p.get("exit_rate", 0.01))
        w.dauer = (w.dauer | enter) & ~leave


class BoomBust(Factor):
    """Food patches don't last: each patch dies with chance `patch_death` per tick (food_max -> 0) and a new one
    appears at a random spot (rotting fruit appears and is used up)."""
    name = "boom_bust"

    def update(self, w, t):
        dead = torch.rand(w.food.shape, generator=w.gen, device=w.gen.device) < self.params.get("patch_death", 0.0002)
        if bool(dead.any()):
            new = 20 + (w.size - 40) * torch.rand(w.patches.shape, generator=w.gen, device=w.gen.device)
            w.patches = torch.where(dead[..., None], new, w.patches)
            w.food = torch.where(dead, torch.zeros_like(w.food), w.food)


class PopulationSize(Factor):
    """Bottlenecks: at each tick listed in `bottleneck_at` (or every `bottleneck_every` ticks), only `survive`
    fraction of worms survive (chosen at random). Carrying capacity itself is set by food (food_amount)."""
    name = "population_size"

    def update(self, w, t):
        p = self.params; ev = int(p.get("bottleneck_every", 0))
        if t in set(p.get("bottleneck_at", [])) or (ev > 0 and t % ev == 0):
            kill = w.alive & (w.rand(w.N, w.S) > p.get("survive", 0.1))
            w.kill(kill, "bottleneck")


class MatingSystem(Factor):
    """Hermaphrodites + males. A child is male with chance = parent's 'male' trait (x `male_scale`). Males can't
    reproduce alone; a hermaphrodite that splits with a male within `radius` OUTCROSSES: the child's genome takes
    each gene from the male with chance 0.5. mode 'selfing' disables males (trait ignored)."""
    name = "mating_system"

    def setup(self, w):
        self.male = torch.zeros(w.N, w.S, dtype=torch.bool, device=w.gen.device)
        self.outx = torch.zeros(w.N, device=w.gen.device)

    def modify(self, w, m):
        m["fertility"] *= (~self.male).float()

    def on_birth(self, w, wi, pi, ci):
        p = self.params
        if p.get("mode") == "selfing":
            self.male[wi, ci] = False; return
        r = float(p.get("radius", 10.0))
        males = self.male & w.alive
        d2 = ((w.xy[wi] - w.xy[wi, pi][:, None, :]) ** 2).sum(-1) + (~males[wi]).float() * 1e9   # (births, S)
        dmin, mj = d2.min(-1)
        cross = dmin < r * r
        if bool(cross.any()):
            a, b = wi[cross], ci[cross]; mm = mj[cross]
            mask = w.rand(len(a), w.G.shape[-1]) < 0.5
            w.G[a, b] = torch.where(mask, w.G[a, mm], w.G[a, b])
            w.p = __import__("engine").unpack(w.G)
            self.outx += torch.bincount(a, minlength=w.N).float()
        self.male[wi, ci] = w.rand(len(wi)) < w.trait01("male")[wi, pi] * p.get("male_scale", 1.0)

    def measure(self, w):
        out = {"male_frac": _mean(w, self.male.float()), "outcrossings": self.outx.clone()}; self.outx.zero_(); return out


class Migration(Factor):
    """Splits each world into `islands` vertical strips separated by walls; worms can't cross, except that each
    tick a worm moves to a random other island with chance `rate`."""
    name = "migration"

    def after_move(self, w):
        k = int(self.params.get("islands", 4)); width = w.size / k
        isl = (self._prev_x / width).floor().clamp(0, k - 1) if hasattr(self, "_prev_x") else (w.xy[..., 0] / width).floor()
        lo, hi = isl * width + 1e-3, (isl + 1) * width - 1e-3
        x = w.xy[..., 0].clamp(lo, hi)
        mig = w.alive & (w.rand(w.N, w.S) < self.params.get("rate", 0.0001))
        new_isl = (isl + 1 + (w.rand(w.N, w.S) * (k - 1)).floor()) % k
        x = torch.where(mig, new_isl * width + w.rand(w.N, w.S) * width, x)
        w.xy = torch.stack([x, w.xy[..., 1]], -1)
        self._prev_x = x


class MutationRate(Factor):
    """Base mutation size multiplier `base_mult`. If `evolvable`, the mut_rate trait gene (log10 multiplier) is
    inherited and mutates like any gene, so evolution can tune its own mutation rate; otherwise it is reset to 0 at
    every birth. `repair_cost` = extra energy per tick per unit of the repair trait (DNA repair is not free)."""
    name = "mutation_rate"

    def modify(self, w, m):
        m["mut"] *= self.params.get("base_mult", 1.0)
        m["cost"] += self.params.get("repair_cost", 0.0) * w.trait01("repair")

    def on_birth(self, w, wi, pi, ci):
        if not self.params.get("evolvable", False):
            from engine import TRAIT_NAMES
            w.p["traits"][wi, ci, TRAIT_NAMES.index("mut_rate")] = 0.0

    def measure(self, w):
        return {"mut_rate_mean_log10": _mean(w, w.trait("mut_rate"))}


class InheritanceExtra(Factor):
    """Non-genetic inheritance. (1) Learned pathogen avoidance passed down for `avoid_generations` generations
    (small-RNA inheritance in real worms): a worm infected by a pathogen marks its children, who catch pathogens
    50 % less. (2) Maternal provisioning is the 'maternal' trait (always active in the engine); `maternal_evolvable`
    false resets it to `maternal_fixed` at every birth."""
    name = "inheritance_extra"

    def setup(self, w):
        w.inherited_avoid = torch.zeros(w.N, w.S, device=w.gen.device)

    def on_birth(self, w, wi, pi, ci):
        p = self.params
        infected = torch.zeros(len(wi), dtype=torch.bool, device=w.gen.device)
        for f in w.factors:
            if hasattr(f, "inf") and f.name in ("pathogen_bacteria", "microsporidia", "fungal_parasites"):
                infected |= f.inf[wi, pi]
        w.inherited_avoid[wi, ci] = torch.where(infected, torch.full_like(infected, int(p.get("avoid_generations", 4)), dtype=torch.float),
                                                (w.inherited_avoid[wi, pi] - 1).clamp(min=0))
        if not p.get("maternal_evolvable", True):
            from engine import TRAIT_NAMES
            w.p["traits"][wi, ci, TRAIT_NAMES.index("maternal")] = p.get("maternal_fixed", 0.5)


class Variability(Factor):
    """Makes the world change over time on its own: every `every` ticks (regular) or at random times with the
    same average (irregular), ONE randomly chosen active field factor gets its level shifted by `step` x its range.
    Use it to test 'predictable vs unpredictable worlds'."""
    name = "variability"

    def update(self, w, t):
        p = self.params; ev = int(p.get("every", 5000))
        hit = (t % ev == 0) if p.get("mode", "regular") == "regular" else bool(torch.rand(1, generator=torch.Generator().manual_seed(t)) < 1 / ev)
        if not hit:
            return
        fs = [f for f in w.factors if hasattr(f, "field") and f is not self]
        if not fs:
            return
        f = fs[t % len(fs)]
        rng = (f.field.base.max() - f.field.base.min()).clamp(min=1.0)
        f.field.base = f.field.base + float(p.get("step", 0.2)) * rng * (1 if (t // ev) % 2 else -1)


# ===================================================================================================== INTERNAL
class StarvationSignal(Factor):
    """Near-starvation 'pain' signal (ASH-nociceptor-like). When a worm's energy is below `threshold`, the
    nociception sense reads (threshold - energy) / threshold x `gain` (0 when fed, up to `gain` at zero energy), so
    evolution can wire an alarm into behaviour. `hunger_override` (0..1): real hungry worms ignore aversive cues to
    reach food (Ghosh et al. 2016); while the signal is on, the toxin, pathogen and predator senses are scaled down by
    hunger_override x signal (0 = no override)."""
    name = "starvation_signal"

    def modify(self, w, m):
        p = self.params; thr = float(p.get("threshold", 3.0))
        sig = ((thr - w.energy) / thr).clamp(0, 1) * w.alive
        w.sense["nociception"] += sig * float(p.get("gain", 1.0))
        ov = float(p.get("hunger_override", 0.0))
        if ov > 0:
            self._scale = (1 - ov * sig)
        self._last = sig

    def after_eat(self, w, got, m):
        if hasattr(self, "_scale"):                     # aversive senses were filled during modify(); damp them now
            for k in ("toxin", "pathogen", "predator"):
                w.sense[k] *= self._scale

    def measure(self, w):
        return {"starvation_signal_mean": _mean(w, self._last)} if hasattr(self, "_last") else {}
