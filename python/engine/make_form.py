"""Generate the experiment FORM (configs/TEMPLATE.toml) and the reference GUIDE it points to (FACTOR_GUIDE.md) from
the factor catalog + the engine's registry, so the form, the guide and the code can never disagree.

Run after changing any factor:   python make_form.py
Every line of the form carries a footnote like [F12]; FACTOR_GUIDE.md has a section with the same tag explaining
what the setting is, how the engine models it, the autopilot values, the evidence and the sources.
"""
import inspect
import tomllib
from pathlib import Path

import config as C

HERE = Path(__file__).resolve().parent
CAT = tomllib.loads(C.CATALOG.read_text())
SRC = (C.CATALOG.parent / "sources.md").read_text()

RUN_DOCS = {
    "name": "Name of the experiment; results are saved as results/<name>.json/.png/_stats.txt.",
    "replicates": "How many independent worlds per arm (each with its own food layout and founder). More = more reliable "
                  "statistics. 30 is a good default; >= 16 is needed for paired tests to be able to reach p < 0.05 after "
                  "correcting for several comparisons.",
    "ticks": "How long the run lasts. One tick = one step of every worm. ~6,000 ticks is one worm lifetime (max_age); "
             "50,000 ticks is roughly 10-20 worm generations at equilibrium.",
    "arms": "Which versions of the world to run side by side. frozen = no mutation (checks the code; must show zero "
            "genetic change), shadow = random survival (chance alone), real = natural selection. "
            "Adaptation = real minus shadow. 'shadow' needs 'real'.",
    "seed": "Random seed. The same seed + the same form = the same run (on the same machine).",
    "founders": "Which brains start the worlds: toybrain_fair (evolved champions of the toy-brain fair run, one per "
                "replicate), toybrain (original run), random (unevolved; they usually starve), or a path to a results file.",
    "every": "Measure every N ticks.",
}
WORLD_DOCS = {
    "size": "Arena width and height (units). 400 x 400 holds ~380 worms with the default food.",
    "patches": "Number of food patches (fixed spots unless food_layout moves them).",
    "patch_r": "A worm eats when within this distance of a patch centre.",
    "food_max": "Most food a patch can hold.",
    "regrow": "Each tick a patch regrows this fraction of what's missing. Sets the carrying capacity.",
    "bite": "Most food one worm eats per tick; worms crowding a patch share it.",
    "sig_smell": "How far food smell reaches (long range, AWA/AWC-like).",
    "sig_taste": "How far taste reaches (short range, ASE-like).",
    "e_start": "Energy of founders.",
    "e_split": "A worm splits in two when its energy reaches this.",
    "cost_base": "Energy burned per tick just living (scaled by temperature if that factor is on).",
    "cost_move": "Extra energy per tick per unit of speed.",
    "max_age": "Death of old age (the same for every genome, so it is not selection).",
    "mut_sigma": "Mutation size per gene for a child, before scaling by genome size and mutation factors.",
    "slots": "Most worms a world can hold (memory). Keep above the carrying capacity.",
    "start_fill": "Fraction of slots filled with founders at the start.",
    "trait_cost": "Energy per tick per unit of each resistance/ability trait (abilities aren't free).",
    "dauer_cost": "Energy per tick while in the dauer resting stage.",
}
LEVEL = {"EVO": "easy", "EFFECT": "easy", "CONTESTED": "researcher", "UNTESTED": "researcher"}


def toml_val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {toml_val(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(toml_val(x) for x in v) + "]"
    return repr(v)


def source_lines(nums):
    lines = {int(l.split(".", 1)[0]): l.split(".", 1)[1].strip() for l in SRC.splitlines() if l[:1].isdigit()}
    return [f"[{n}] {lines.get(n, '(see sources.md)')}" for n in nums]


def main():
    form = ["# ============================================================================================",
            "# EXPERIMENT FORM. Fill it in like a form, then run:  python run.py configs/<your-copy>.toml",
            "# Every setting has a footnote tag like [F7]; look it up in FACTOR_GUIDE.md (same folder) for what it",
            "# means, how it is modelled, the research behind it and the sources.",
            "# Factors: mode = \"off\" (not in the world) | \"auto\" (realistic autopilot) | \"custom\" (your values).",
            "# To ISOLATE one trait/factor: set that one to custom, leave the rest off (or auto for a natural background).",
            "# ============================================================================================", "", "[run]"]
    guide = ["# Factor guide: footnotes for the experiment form", "",
             "Every `[tag]` in `configs/TEMPLATE.toml` (and in the GUI) points to a section here. Generated by "
             "`make_form.py` from the factor catalog and the engine code; edit those, then regenerate.", "",
             "**Modes:** `off` = the factor doesn't exist in the world (the equilibrium baseline). `auto` = autopilot, "
             "realistic values chosen from the research (listed per factor below). `custom` = start from the defaults "
             "listed below and change what you set.", "",
             "**Evidence tags:** EVO = shown to drive evolution; EFFECT = changes fitness or behaviour; CONTESTED = "
             "disputed; UNTESTED = no C. elegans study found. CONTESTED/UNTESTED factors appear only in the GUI's "
             "Researcher mode.", "",
             "**Every factor is a simplified model** of the effect the studies describe (energy cost, speed, death "
             "chance, fertility, mutation, senses), not biochemistry. Model units are explained per factor.", "",
             "## Run settings", ""]
    for i, (k, v) in enumerate(C.RUN_DEFAULTS.items(), 1):
        form.append(f"{k} = {toml_val(v)}".ljust(46) + f"# [R{i}]")
        guide += [f"### [R{i}] run.{k}", f"Default: `{toml_val(v)}`. {RUN_DOCS.get(k, '')}", ""]
    form += ["", "[world]   # the equilibrium world; change only if you know why (Researcher mode in the GUI)"]
    guide += ["## World settings (the equilibrium baseline)", ""]
    for i, (k, v) in enumerate(C.WORLD_DEFAULTS.items(), 1):
        form.append(f"# {k} = {toml_val(v)}".ljust(46) + f"# [W{i}]")
        guide += [f"### [W{i}] world.{k}", f"Default: `{toml_val(v)}`. {WORLD_DOCS.get(k, '')}", ""]
    guide += ["## Factors", ""]
    by_cat = {}
    for name in C.REGISTRY:
        by_cat.setdefault(CAT[name]["category"], []).append(name)
    fi = 0
    for cat, names in by_cat.items():
        form += ["", f"# ------------------------------------------------------------------ {cat.upper()}"]
        guide += [f"### Category: {cat}", ""]
        for name in names:
            fi += 1; tag = f"F{fi}"; c = CAT[name]; cls, default, auto = C.REGISTRY[name]
            obj = cls(C.deep_merge(default, auto))
            doc = inspect.getdoc(type(obj)) or ""
            form += [f"[factors.{name}]".ljust(46) + f"# [{tag}] {c['evidence']}, {c['status']}",
                     'mode = "off"'.ljust(46) + "# off | auto | custom"]
            for k, v in default.items():
                form.append(f"# {k} = {toml_val(v)}")
            guide += [f"#### [{tag}] {name}  ({c['evidence']}; GUI level: {LEVEL[c['evidence']]})", "",
                      f"**Real-world forms:** {', '.join(c['forms'])}.", ""]
            if c.get("notes"):
                guide += [f"**What the research says:** {c['notes']}", ""]
            if c.get("real_range"):
                guide += [f"**Real range:** {c['real_range']}", ""]
            if doc:
                guide += ["**How the engine models it:**", "", "```", doc, "```", ""]
            guide += [f"**Custom defaults:** `{toml_val(default)}`", "",
                      f"**Autopilot (auto) changes:** `{toml_val(auto) if auto else '(same as defaults)'}`", ""]
            if c.get("sources"):
                guide += ["**Sources:**", ""] + [f"- {s}" for s in source_lines(c["sources"])] + [""]
    (HERE / "configs").mkdir(exist_ok=True)
    (HERE / "configs" / "TEMPLATE.toml").write_text("\n".join(form) + "\n")
    (HERE / "FACTOR_GUIDE.md").write_text("\n".join(guide) + "\n")
    print(f"wrote configs/TEMPLATE.toml and FACTOR_GUIDE.md ({fi} factors)")


if __name__ == "__main__":
    main()
