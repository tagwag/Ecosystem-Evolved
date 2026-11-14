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
                    founders="toybrain_fair", every=500, checkpoint_every=10000, record_tree=True)
WORLD_DEFAULTS = dict(size=400.0, patches=80, patch_r=4.0, food_max=20.0, regrow=0.01, bite=0.5, sig_smell=25.0,
                      sig_taste=5.0, e_start=10.0, e_split=20.0, cost_base=0.02, cost_move=0.02, max_age=6000,
                      mut_sigma=0.1, slots=640, start_fill=0.25, trait_cost=0.005, dauer_cost=0.002,
                      # added 2026-11-13 (defaults = the old built-in behaviour, so old forms give the same results)
                      sense_noise=0.01, motor_noise=0.1, mutation_mode="all", mutation_genes=10,
                      recombination_rate=0.0, recombination_radius=10.0, immigration_rate=0.0,
                      immigrant_source="founders")
# Allowed values / safe ranges for the [world] settings above that are not plain positive numbers.
WORLD_CHOICES = dict(mutation_mode=("all", "sparse"), immigrant_source=("founders", "random"))
WORLD_RANGES = dict(sense_noise=(0.0, 1.0), motor_noise=(0.0, 2.0), mutation_genes=(1, 1000),
                    recombination_rate=(0.0, 1.0), recombination_radius=(0.0, 400.0), immigration_rate=(0.0, 100.0))


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
    # ---------------------------------------------------------------- internal signals
    "starvation_signal": (lambda p: B.StarvationSignal(p), dict(threshold=3.0, gain=1.0, hunger_override=0.0),
                          dict(threshold=3.0, gain=1.0, hunger_override=0.5)),
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


# ------------------------------------------------------------------ fixed lists of allowed values (GUI dropdowns)
# Every text setting that only accepts certain words is listed here, so the form checker can refuse a typo with the
# list of allowed words, and the GUI can show a dropdown. Keep in sync with the factor code (fields.py, factors_*.py).
FIELD_CHOICES = dict(space=("uniform", "gradient", "spots", "hotspot", "patches"),
                     time=("constant", "cycle", "random", "shock"))
FACTOR_MODE_CHOICES = dict(food_layout=("fixed", "moving", "seasonal", "uniform"),
                           pathogen_bacteria=("fixed", "coevolving"),
                           predators=("chaser", "pristionchus"),
                           mating_system=("androdioecy", "selfing"),
                           variability=("regular", "irregular"))
SOURCE_CHOICES = dict(radiation=tuple(E.RAD_WEIGHT), toxins=tuple(E.TOXIN_EFFECTS))


def check_choices(name, prm):
    """Refuse words that the factor code would not understand (it would otherwise silently ignore them)."""
    if name in FACTOR_MODE_CHOICES and prm.get("mode") not in FACTOR_MODE_CHOICES[name]:
        raise ValueError(f"[factors.{name}] factor_mode = {prm.get('mode')!r} is not allowed; choose one of "
                         f"{list(FACTOR_MODE_CHOICES[name])}")
    fld = prm.get("field")
    if isinstance(fld, dict):
        for k, opts in FIELD_CHOICES.items():
            if k in fld and fld[k] not in opts:
                raise ValueError(f"[factors.{name}] field.{k} = {fld[k]!r} is not allowed; choose one of {list(opts)}")
    if name in SOURCE_CHOICES:
        bad = set(prm.get("sources") or {}) - set(SOURCE_CHOICES[name])
        if bad:
            raise ValueError(f"[factors.{name}] unknown sources {sorted(bad)}; allowed: {list(SOURCE_CHOICES[name])}")


def factor_params(name, section):
    """Return the params the factor will run with, or None if off.
    NOTE on the word 'mode': in a form, `mode` is always off / auto / custom. Some factors also have their OWN mode
    (predators: chaser / pristionchus, food_layout: fixed / moving / ...). In a form that one is written
    `factor_mode = "pristionchus"`; it is passed to the factor as its `mode`."""
    section = dict(section or {})
    mode = section.pop("mode", "off")
    if "factor_mode" in section:
        section["mode"] = section.pop("factor_mode")
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
        prm = deep_merge(default, auto); check_choices(name, prm); return prm
    unknown = set(section) - set(default)
    if unknown:
        allowed = sorted("factor_mode" if k == "mode" else k for k in default)
        raise ValueError(f"[factors.{name}] unknown settings {sorted(unknown)}; allowed: {allowed}")
    prm = deep_merge(default, section); check_choices(name, prm); return prm


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
    for k, opts in WORLD_CHOICES.items():                 # named choices: clear error listing the allowed values
        if world[k] not in opts:
            raise ValueError(f"[world] {k} = {world[k]!r} is not allowed; choose one of {list(opts)}")
    for k, (lo, hi) in WORLD_RANGES.items():              # numbers with a safe range
        if not isinstance(world[k], (int, float)) or not lo <= world[k] <= hi:
            raise ValueError(f"[world] {k} = {world[k]!r} must be a number from {lo} to {hi}")
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


# ------------------------------------------------------------------------------------------------ safety estimate
GPU_BUDGET_MB = 7500        # most GPU memory one engine run may plan to use (RTX 3080 has 10 GB; leave room for Windows)
RAM_BUDGET_MB = 8000        # most system memory for the results kept in memory


def estimate(cfg):
    """Rough memory need of a run (MB) and hard-limit errors, BEFORE anything is allocated.
    Main GPU arrays per tick: worm x food-patch distances (N x S x P), genomes (N x S x genes, x3 copies while
    mutating), brain state, and N x S x S for the virus factor (worm-to-worm distances). x2.5 for temporaries."""
    from engine import glen, H
    run, w = cfg["run"], cfg["world"]
    N = int(run["replicates"]) * len(run["arms"]); S = int(w["slots"]); P = int(w["patches"])
    genes = glen(); b = 4
    gpu = N * S * P * b * 6 + N * S * genes * b * 3 + N * S * (H + 40) * b
    if cfg["factors"].get("virus", {}).get("params") is not None:
        gpu += N * S * S * b * 3
    gpu_mb = gpu * 2.5 / 2 ** 20 + 600                              # + CUDA/PyTorch overhead
    n_samples = int(run["ticks"]) // max(1, int(run["every"]))
    ram_mb = n_samples * N * 80 * 8 / 2 ** 20 + 1500
    errs = []
    if gpu_mb > GPU_BUDGET_MB:
        errs.append(f"needs ~{gpu_mb:,.0f} MB of GPU memory (limit {GPU_BUDGET_MB:,} MB): "
                    f"{N} worlds x {S} slots x {P} patches is too big. Lower replicates, world.slots or world.patches.")
    if ram_mb > RAM_BUDGET_MB:
        errs.append(f"keeps ~{ram_mb:,.0f} MB of measurements in memory (limit {RAM_BUDGET_MB:,} MB): raise run.every or lower ticks.")
    if int(w["slots"]) < 1 or int(run["replicates"]) < 1 or int(run["ticks"]) < 1:
        errs.append("replicates, ticks and world.slots must be >= 1")
    if int(run["ticks"]) > 20_000_000:
        errs.append(f"ticks = {int(run['ticks']):,} is over the 20,000,000 safety cap (days of GPU time)")
    return dict(gpu_mb=round(gpu_mb), ram_mb=round(ram_mb), errors=errs)
