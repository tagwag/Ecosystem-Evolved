"""Physical and chemical factors (catalog categories: physical, radiation, chemical).

Most of them are a FieldFactor: an environmental field (fields.py) plus EFFECT RULES that say what the level does to
a worm. Effects use an 'OK band' [ok_low, ok_high]: inside it nothing happens; outside it, effects grow with the
distance d from the band:
    below / above : {cost: energy per tick per unit d, death: chance per tick per unit d,
                     fert: fertility lost per unit d (1 = fully fertile, 0 = sterile),
                     speed: speed change per unit d (-0.1 = 10 % slower per unit), mut: mutation x(1 + mut*d)}
`sense` names the brain input channel the level feeds (scaled by `sense_scale` after subtracting `sense_center`).
`resist` names a trait gene that shrinks all harmful effects (effect x (1 - trait)).
Units and the reasoning behind every number: FACTOR_GUIDE.md (footnotes in the config form point there).
"""
import math

import torch

from fields import Field


class Factor:
    """Base class: every hook does nothing unless a factor overrides it."""
    name = "factor"

    def __init__(self, params):
        self.params = params

    def setup(self, w): ...
    def update(self, w, t): ...
    def modify(self, w, m): ...
    def after_eat(self, w, got, m): ...
    def after_move(self, w): ...
    def on_birth(self, w, wi, pi, ci): ...

    def measure(self, w):
        return {}


def apply_band(level, rules, m, resist=None, w=None):
    """Turn a per-worm level into effects on the modifier dict m (see module docstring)."""
    lo, hi = rules.get("ok_low", -math.inf), rules.get("ok_high", math.inf)
    shrink = 1.0 if resist is None else (1 - w.trait01(resist))
    for side, d in (("below", (lo - level).clamp(min=0)), ("above", (level - hi).clamp(min=0))):
        r = rules.get(side) or {}
        if not r:
            continue
        if r.get("cost"):
            m["cost"] += r["cost"] * d * shrink
        if r.get("death"):
            m["death_p"] += r["death"] * d * shrink
        if r.get("fert"):
            m["fertility"] *= (1 - r["fert"] * d * shrink).clamp(min=0)
        if r.get("speed"):
            m["speed"] *= (1 + r["speed"] * d * shrink).clamp(min=0)
        if r.get("mut"):
            m["mut"] *= 1 + r["mut"] * d * shrink


class FieldFactor(Factor):
    def __init__(self, name, params):
        super().__init__(params); self.name = name

    def setup(self, w):
        self.field = Field(self.params["field"], w.N, w.size, int(self.params.get("cells", 64)), w.gen.device, w.gen,
                           patches=w.patches)

    def update(self, w, t):
        self.field.update(t)

    def level(self, w):
        return self.field.at(w.xy)

    def modify(self, w, m):
        v = self.level(w)
        apply_band(v, self.params.get("effects", {}), m, self.params.get("resist"), w)
        ch = self.params.get("sense")
        if ch:
            w.sense[ch] += (v - self.params.get("sense_center", 0.0)) * self.params.get("sense_scale", 1.0)
        self._last = v

    def measure(self, w):
        a = w.alive.float(); n = a.sum(1).clamp(min=1)
        return {f"{self.name}_level": (self._last * a).sum(1) / n} if hasattr(self, "_last") else {}


class Temperature(FieldFactor):
    """Field in degrees C. Metabolism follows Q10 (cost_base x q10^((T-20)/10)); fertility collapses above ~25-26 C;
    the heat_tol trait shifts the upper limit. Senses: temperature (AFD-like) and its change over time."""

    def modify(self, w, m):
        p = self.params
        T = self.level(w) - w.trait("heat_tol").clamp(min=0) * (self.level(w) > p["effects"]["ok_high"]).float()
        q = p.get("q10", 2.0)
        m["cost"] += float(w.cfg["world"]["cost_base"]) * (q ** ((T - 20) / 10) - 1)
        apply_band(T, p["effects"], m)
        v = self.level(w)
        prev = getattr(self, "_prev", v)
        w.sense["temperature"] += (v - 20) * 0.1
        w.sense["dtemperature"] += (v - prev) * 5
        self._prev = v; self._last = v


class DirectionalField(FieldFactor):
    """Electric or magnetic field with a direction (`angle`, degrees) and strength (field level). The worm senses
    strength x cos(heading - angle): i.e. whether it is moving along the field. No energy effects (none are known)."""

    def modify(self, w, m):
        v = self.level(w)
        ang = math.radians(self.params.get("angle", 0.0))
        w.sense[self.params["sense"]] += v * torch.cos(w.hd - ang) * self.params.get("sense_scale", 1.0)
        self._last = v


# Radiation weighting factors (how much damage per Gy compared with gamma), after ICRP 103 (approximate); UV forms
# are in 'gamma-equivalent' model units because UV damage is surface-only and measured differently.
RAD_WEIGHT = {"uv_a": 0.02, "uv_b": 0.3, "uv_c": 1.0, "xray": 1.0, "gamma": 1.0, "beta": 1.0, "alpha": 20.0,
              "neutron": 10.0, "proton": 2.0, "heavy_ion": 20.0, "radon": 20.0}


class Radiation(Factor):
    """Radiation as a MUTATION SOURCE (its main biological effect) plus fertility loss and death at high dose.
    params.sources = {form: dose_rate} in Gy per 1000 ticks; params.field = where it is (uniform/hotspot/...; the
    field's level is a 0..1 multiplier). Effective dose = sum(weight x rate). Effects per unit effective dose:
    mutation x(1 + mut_per_gy x dose x (1 - repair)), fertility - fert_per_gy x dose, death chance death_per_gy x dose.
    The 'repair' trait (DNA repair, costs energy) removes that fraction of the damage."""
    name = "radiation"

    def setup(self, w):
        self.field = Field(self.params.get("field", {"space": "uniform", "level": 1.0}), w.N, w.size, 64,
                           w.gen.device, w.gen, patches=w.patches)
        self.eff = sum(RAD_WEIGHT[k] * float(v) for k, v in self.params.get("sources", {}).items())

    def update(self, w, t):
        self.field.update(t)

    def modify(self, w, m):
        p = self.params
        dose = self.eff * self.field.at(w.xy) * (1 - w.trait01("repair"))
        m["mut"] *= 1 + p.get("mut_per_gy", 2.0) * dose
        m["fertility"] *= (1 - p.get("fert_per_gy", 0.05) * dose).clamp(min=0)
        m["death_p"] += p.get("death_per_gy", 0.00002) * dose
        self._last = dose

    def measure(self, w):
        a = w.alive.float(); n = a.sum(1).clamp(min=1)
        return {"radiation_dose": (self._last * a).sum(1) / n}


class ChemicalMutagen(FieldFactor):
    """Mutagen field (e.g. EMS); level in model units. Raises mutation size; repair trait protects."""

    def modify(self, w, m):
        v = self.level(w) * (1 - w.trait01("repair"))
        m["mut"] *= 1 + self.params.get("mut_per_unit", 1.0) * v
        m["cost"] += self.params.get("cost_per_unit", 0.0005) * v
        self._last = v


# What each toxin does per unit of level (model units 0..~3). Sources for the direction of each effect: guide.
TOXIN_EFFECTS = {
    "levamisole":   dict(speed=-0.4, cost=0.002),               # paralyses: slower movement (fewer matings too)
    "ivermectin":   dict(speed=-0.3, death=0.0004),
    "benzimidazole": dict(fert=0.3, death=0.0002),
    "cadmium":      dict(cost=0.004, fert=0.2),
    "copper":       dict(cost=0.003, death=0.0002),
    "lead":         dict(cost=0.002, fert=0.1),
    "hydrogen_sulfide": dict(death=0.0008),
    "ethanol":      dict(speed=-0.2, cost=0.001),
    "microplastics": dict(eat=-0.15, cost=0.001),               # gut damage: absorbs less food
    "oxidants":     dict(mut=0.5, cost=0.002),
    "antibiotics":  dict(cost=0.0005),                          # also clears the microbiome (microbiome factor)
}


class Toxins(Factor):
    """params.sources = {toxin: level}; params.field = where (multiplier 0..1). resist_toxin trait shrinks effects.
    Sense: 'toxin' channel = total toxin level (worms can learn/evolve avoidance)."""
    name = "toxins"

    def setup(self, w):
        self.field = Field(self.params.get("field", {"space": "spots", "low": 0.0, "high": 1.0}), w.N, w.size, 64,
                           w.gen.device, w.gen, patches=w.patches)

    def update(self, w, t):
        self.field.update(t)

    def modify(self, w, m):
        f = self.field.at(w.xy); shrink = 1 - w.trait01("resist_toxin"); total = 0
        for k, lvl in self.params.get("sources", {}).items():
            e = TOXIN_EFFECTS[k]; d = float(lvl) * f; total = total + d; d = d * shrink
            if "speed" in e: m["speed"] *= (1 + e["speed"] * d).clamp(min=0)
            if "cost" in e: m["cost"] += e["cost"] * d
            if "death" in e: m["death_p"] += e["death"] * d
            if "fert" in e: m["fertility"] *= (1 - e["fert"] * d).clamp(min=0)
            if "eat" in e: m["eat"] *= (1 + e["eat"] * d).clamp(min=0)
            if "mut" in e: m["mut"] *= 1 + e["mut"] * d
        w.sense["toxin"] += total if torch.is_tensor(total) else 0
        self.antibiotic = float(self.params.get("sources", {}).get("antibiotics", 0)) * f
        self._last = total if torch.is_tensor(total) else torch.zeros_like(f)

    def measure(self, w):
        a = w.alive.float(); n = a.sum(1).clamp(min=1)
        return {"toxin_level": (self._last * a).sum(1) / n}


class Substrate(FieldFactor):
    """Ground type as a field of 'difficulty' (1 = agar surface). Speed is divided by it (3D soil, liquid = harder),
    and moving costs more. Optional pillars (obstacles) push worms out: params.pillars = count, pillar_r = radius."""

    def setup(self, w):
        super().setup(w)
        k = int(self.params.get("pillars", 0))
        self.pillars = w.size * (0.1 + 0.8 * torch.rand(w.N, max(k, 1), 2, generator=w.gen, device=w.gen.device))
        self.k = k

    def modify(self, w, m):
        v = self.level(w).clamp(min=0.1)
        m["speed"] /= v
        m["cost"] += self.params.get("cost_per_unit", 0.01) * (v - 1).clamp(min=0)
        self._last = v

    def after_move(self, w):
        if self.k == 0:
            return
        r = float(self.params.get("pillar_r", 15.0))
        d = w.xy[:, :, None, :] - self.pillars[:, None]                       # (N, S, k, 2)
        dist = d.norm(dim=-1).clamp(min=1e-6)
        inside = dist < r
        if bool(inside.any()):
            push = (d / dist[..., None]) * (r - dist).clamp(min=0)[..., None]
            w.xy = w.xy + (push * inside[..., None]).sum(2)
            w.sense["touch"] += inside.any(-1).float()
