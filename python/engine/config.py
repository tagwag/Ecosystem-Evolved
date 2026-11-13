"""Config files ('experiment forms') -> checked settings -> factor objects.

A config is a TOML file with [run], [world] and one [factors.<name>] section per factor (sections may be left out:
missing factors are 'off'). Every factor in python/factors/catalog.toml has an entry in REGISTRY below; the
check fails if the catalog and the registry ever disagree, so nothing can be silently skipped.

Each factor section:  mode = "off" | "auto" | "custom"
   off     the factor does not exist in the world (neutral; this is the equilibrium baseline)
   auto    'autopilot': realistic settings taken from the research (AUTO below; explained in FACTOR_GUIDE.md)
   custom  start from DEFAULT below, then apply any keys given in the section (nested dicts are merged)
Any unknown key in a section is an error (typos must not silently do nothing).
"""
import copy
import tomllib
from pathlib import Path

import factors_bio as B
import factors_env as E

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "factors" / "catalog.toml"

RUN_DEFAULTS = dict(name="unnamed", replicates=30, ticks=50000, arms=["frozen", "shadow", "real"], seed=1,
                    founders="toybrain_fair", every=500)
WORLD_DEFAULTS = dict(size=400.0, patches=80, patch_r=4.0, food_max=20.0, regrow=0.01, bite=0.5, sig_smell=25.0,
                      sig_taste=5.0, e_start=10.0, e_split=20.0, cost_base=0.02, cost_move=0.02, max_age=6000,
                      mut_sigma=0.1, slots=640, start_fill=0.25, trait_cost=0.005, dauer_cost=0.002)


def band(lo, hi, below=None, above=None):
    return dict(ok_low=lo, ok_high=hi, below=below or {}, above=above or {})


F = lambda space="uniform", **k: dict(space=space, **k)   # field shorthand

# name: (class, DEFAULT params for 'custom', AUTO params for 'auto')
REGISTRY = {
    # ---------------------------------------------------------------- physical
    "temperature": (lambda p: E.Temperature("temperature", p),
                    dict(field=F(level=20.0), q10=2.0,
                         effects=band(16, 24, below=dict(speed=-0.04, fert=0.05),
                                      above=dict(cost=0.002, death=0.0003, fert=0.4))),
                    dict(field=F("gradient", low=15.0, high=25.0, time="cycle", period=20000, amplitude=0.05))),
    "oxygen": (lambda p: E.FieldFactor("oxygen", p),
               dict(field=F(level=8.0), sense="oxygen", sense_center=8.0, sense_scale=0.1,
                    effects=band(5, 12, below=dict(speed=-0.15, death=0.0002), above=dict(cost=0.0005, mut=0.01))),
               dict(field=F("patches", low=21.0, high=4.0, spot_r=30.0))),
    "carbon_dioxide": (lambda p: E.FieldFactor("carbon_dioxide", p),
                       dict(field=F(level=0.0), sense="co2", sense_scale=0.5, effects=band(0, 1, above=dict(cost=0.002))),
                       dict(field=F("patches", low=0.0, high=3.0, spot_r=20.0))),
    "humidity": (lambda p: E.FieldFactor("humidity", p),
                 dict(field=F(level=1.0), resist="dauer", effects=band(0.6, 1.0, below=dict(death=0.02, cost=0.01))),
                 dict(field=F(level=1.0, time="shock", shock_start=15000, shock_len=2000, shock_level=0.3,
                              shock_every=20000))),
    "osmolarity": (lambda p: E.FieldFactor("osmolarity", p),
                   dict(field=F(level=50.0), sense="salt", sense_center=50.0, sense_scale=0.01,
                        effects=band(0, 150, above=dict(cost=0.00005, death=0.000005, speed=-0.001))),
                   dict(field=F("spots", low=50.0, high=300.0, n_spots=4, spot_r=50.0))),
    "ph": (lambda p: E.FieldFactor("ph", p),
           dict(field=F(level=6.5), sense="ph", sense_center=6.5, sense_scale=0.5,
                effects=band(5, 8, below=dict(cost=0.002, death=0.0003), above=dict(cost=0.002, death=0.0003))),
           dict(field=F("gradient", low=4.5, high=8.5))),
    "substrate": (lambda p: E.Substrate("substrate", p),
                  dict(field=F(level=1.0), cost_per_unit=0.01, pillars=0, pillar_r=15.0),
                  dict(field=F("spots", low=1.0, high=2.5, n_spots=6, spot_r=40.0), pillars=15)),
    "light": (lambda p: E.FieldFactor("light", p),
              dict(field=F(level=0.0), sense="light", sense_scale=1.0,
                   effects=band(-1, 0.3, above=dict(cost=0.002, mut=0.2))),
              dict(field=F(level=0.4, time="cycle", period=2000, amplitude=1.0))),
    "mechanical": (lambda p: E.FieldFactor("mechanical", p),
                   dict(field=F(level=0.0), sense="vibration", sense_scale=1.0, effects={}),
                   dict(field=F(level=0.0, time="shock", shock_start=500, shock_len=20, shock_level=1.0, shock_every=1000))),
    "electric_field": (lambda p: E.DirectionalField("electric_field", p),
                       dict(field=F(level=0.0), angle=0.0, sense="efield", sense_scale=0.3),
                       dict(field=F(level=3.0), angle=0.0)),
    "magnetic_field": (lambda p: E.DirectionalField("magnetic_field", p),
                       dict(field=F(level=0.0), angle=90.0, sense="mfield", sense_scale=1.0),
                       dict(field=F(level=0.5), angle=90.0)),
    "gravity": (lambda p: E.FieldFactor("gravity", p),
                dict(field=F(level=1.0), effects=band(0.8, 1.2, below=dict(speed=-0.2, cost=0.005), above=dict(cost=0.003))),
                dict(field=F(level=1.0))),
    "radiofrequency": (lambda p: E.FieldFactor("radiofrequency", p),
                       dict(field=F(level=0.0), effects=band(-1, 0, above=dict(cost=0.001, fert=0.05))),
                       dict(field=F(level=0.0))),
    # ---------------------------------------------------------------- radiation (mutation sources)
    "radiation": (lambda p: E.Radiation(p),
                  dict(sources={}, field=F(level=1.0), mut_per_gy=2.0, fert_per_gy=0.05, death_per_gy=0.00002),
                  dict(sources={"gamma": 0.002, "radon": 0.0005, "uv_b": 0.01}, field=F(level=1.0))),
    "chemical_mutagens": (lambda p: E.ChemicalMutagen("chemical_mutagens", p),
                          dict(field=F(level=0.0), mut_per_unit=1.0, cost_per_unit=0.0005),
                          dict(field=F("spots", low=0.0, high=1.0, n_spots=2, spot_r=40.0))),
    # ---------------------------------------------------------------- food
    "food_amount": (lambda p: B.FoodAmount(p),
                    dict(food_max_mult=1.0, regrow_mult=1.0, value_mult=1.0, famine_every=0, famine_len=0, famine_mult=0.1),
                    dict(famine_every=20000, famine_len=3000, famine_mult=0.2)),
    "food_layout": (lambda p: B.FoodLayout(p), dict(mode="fixed", drift=0.05, relocate_every=10000),
                    dict(mode="seasonal", relocate_every=20000)),
    "food_quality": (lambda p: B.FoodQuality(p),
                     dict(frac_b=0.0, value_b=2.0, frac_toxic=0.0, toxic_cost=2.0, quality_mult=1.0),
                     dict(frac_b=0.2, value_b=2.0, frac_toxic=0.05)),
    "digestion": (lambda p: B.Digestion(p), dict(gut_cap=3.0, rate=0.1), dict(gut_cap=3.0, rate=0.1)),
    "microbiome": (lambda p: B.Microbiome(p),
                   dict(frac_protective=0.3, frac_harmful=0.0, gain=0.01, loss=0.0005, protection=0.5, harm_cost=0.01,
                        vertical=0.5),
                   dict(frac_protective=0.3, frac_harmful=0.1)),
    # ---------------------------------------------------------------- enemies and neighbours
    "pathogen_bacteria": (lambda p: B.PathogenBacteria(p),
                          dict(mode="fixed", frac_patches=0.3, infect=0.02, cost=0.02, death=0.0002, fert_loss=0.3,
                               recover=0.0005, vertical=0.0, lag=5000),
                          dict(mode="coevolving", frac_patches=0.2)),
    "virus": (lambda p: B.Virus(p),
              dict(start_frac=0.05, radius=5.0, transmit=0.01, cost=0.005, death=0.00002, fert_loss=0.1,
                   recover=0.001, vertical=0.0, hgt=0.0, hgt_frac=0.05),
              dict(start_frac=0.05, hgt=0.01)),
    "microsporidia": (lambda p: B.Microsporidia(p),
                      dict(field=F("spots", low=0.0, high=0.002, n_spots=3, spot_r=40.0), cost=0.005, death=0.00005,
                           fert_loss=0.5, recover=0.0, vertical=0.3),
                      dict()),
    "fungal_parasites": (lambda p: B.FungalParasites(p),
                         dict(field=F("spots", low=0.0, high=0.001, n_spots=2, spot_r=30.0), cost=0.01, death=0.002,
                              fert_loss=0.5, recover=0.0, vertical=0.0),
                         dict()),
    "predatory_fungi": (lambda p: B.PredatoryFungi(p), dict(n_traps=10, trap_r=6.0, catch=0.05, lure=0.0),
                        dict(n_traps=20, lure=0.3)),
    "predators": (lambda p: B.Predators(p),
                  dict(mode="chaser", count=3, speed=0.8, sense_r=60.0, bite_r=3.0, damage=5.0, cooldown=60,
                       touch_r=8.0, switch_food=0.5),
                  dict(mode="pristionchus", count=8, speed=0.6, switch_food=0.5)),
    "competitors": (lambda p: B.Competitors(p), dict(count=50, bite=0.5, temp_slope=0.05), dict(count=60)),
    "carriers": (lambda p: B.Carriers(p), dict(every=2000, radius=20.0, board=0.5, distance=150.0), dict()),
    # ---------------------------------------------------------------- population / genetics
    "population_density": (lambda p: B.PopulationDensity(p),
                           dict(per_cell_full=10.0, crowd=1.0, hungry=2.0, dauer_rate=0.01, exit_rate=0.01), dict()),
    "boom_bust": (lambda p: B.BoomBust(p), dict(patch_death=0.0002), dict(patch_death=0.0002)),
    "population_size": (lambda p: B.PopulationSize(p), dict(bottleneck_at=[], bottleneck_every=0, survive=0.1),
                        dict(bottleneck_every=25000, survive=0.1)),
    "mating_system": (lambda p: B.MatingSystem(p), dict(mode="androdioecy", radius=10.0, male_scale=1.0),
                      dict(mode="androdioecy")),
    "migration": (lambda p: B.Migration(p), dict(islands=4, rate=0.0001), dict(islands=4, rate=0.0001)),
    "mutation_rate": (lambda p: B.MutationRate(p), dict(base_mult=1.0, evolvable=False, repair_cost=0.0),
                      dict(evolvable=True, repair_cost=0.002)),
    "inheritance_extra": (lambda p: B.InheritanceExtra(p),
                          dict(avoid_generations=4, maternal_evolvable=True, maternal_fixed=0.5), dict()),
    # ---------------------------------------------------------------- chemicals
    "toxins": (lambda p: E.Toxins(p),
               dict(sources={}, field=F("spots", low=0.0, high=1.0, n_spots=3, spot_r=40.0)),
               dict(sources={"cadmium": 0.5, "hydrogen_sulfide": 0.3, "microplastics": 0.5})),
    # ---------------------------------------------------------------- meta
    "variability": (lambda p: B.Variability(p), dict(mode="regular", every=5000, step=0.2), dict(mode="irregular")),
}


def deep_merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in extra.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def check_catalog():
    cat = tomllib.loads(CATALOG.read_text())
    missing = set(cat) - set(REGISTRY); extra = set(REGISTRY) - set(cat)
    if missing or extra:
        raise RuntimeError(f"catalog and engine disagree: not in engine {sorted(missing)}, not in catalog {sorted(extra)}")
    return cat


def factor_params(name, section):
    """Return the params the factor will run with, or None if off."""
    section = dict(section or {})
    mode = section.pop("mode", "off")
    if mode not in ("off", "auto", "custom"):
        raise ValueError(f"[factors.{name}] mode must be off, auto or custom (got {mode!r})")
    _, default, auto = REGISTRY[name]
    if mode == "off":
        if section:
            raise ValueError(f"[factors.{name}] is off but has settings {sorted(section)}; set mode = \"custom\" to use them")
        return None
    if mode == "auto":
        if section:
            raise ValueError(f"[factors.{name}] auto mode takes no settings (got {sorted(section)}); use custom")
        return deep_merge(default, auto)
    unknown = set(section) - set(default)
    if unknown:
        raise ValueError(f"[factors.{name}] unknown settings {sorted(unknown)}; allowed: {sorted(default)}")
    return deep_merge(default, section)


def load(path):
    """Read + check a config form. Returns (cfg dict with run/world/factors filled in, list of factor objects)."""
    check_catalog()
    raw = tomllib.loads(Path(path).read_text())
    bad = set(raw) - {"run", "world", "factors"}
    if bad:
        raise ValueError(f"unknown top-level sections {sorted(bad)}")
    run = dict(RUN_DEFAULTS); run.update(raw.get("run", {}))
    if set(raw.get("run", {})) - set(RUN_DEFAULTS):
        raise ValueError(f"unknown [run] keys {sorted(set(raw['run']) - set(RUN_DEFAULTS))}")
    world = dict(WORLD_DEFAULTS)
    if set(raw.get("world", {})) - set(WORLD_DEFAULTS):
        raise ValueError(f"unknown [world] keys {sorted(set(raw['world']) - set(WORLD_DEFAULTS))}")
    world.update(raw.get("world", {}))
    fsec = raw.get("factors", {})
    unknown = set(fsec) - set(REGISTRY)
    if unknown:
        raise ValueError(f"unknown factors {sorted(unknown)} (see python/factors/catalog.toml)")
    active, used = [], {}
    for name in REGISTRY:
        prm = factor_params(name, fsec.get(name))
        used[name] = {"mode": (fsec.get(name) or {}).get("mode", "off"), "params": prm}
        if prm is not None:
            active.append(REGISTRY[name][0](prm))
    return dict(run=run, world=world, factors=used), active
