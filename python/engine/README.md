# Factor engine — handbook

**What it is:** the simulation that runs *experiment forms*. It is the equilibrium world (`python/equilibrium`)
extended so that **every one of the 37 factors** in the factor catalog (`python/factors/catalog.toml`) can be
switched on in a config file, either with realistic **autopilot** values or with your own values.

**Why:** to isolate one trait or factor at a time against a calm, measured baseline, and to make every experiment a
fill-in-the-blanks form instead of new code.

**Who should read this:** anyone writing experiment forms, adding factors, or debugging the engine.

---

## 1. Quick start

1. Copy `configs/TEMPLATE.toml` to `configs/my_experiment.toml`.
2. Set `name` under `[run]`. Under the factor you want to study, change `mode = "off"` to `"auto"` (realistic) or
   `"custom"` (then uncomment and change the settings below it).
3. Check it fast on any computer (seconds, CPU): `python run.py configs/my_experiment.toml --quick`
4. Run it for real on the 3080 through the watcher, by job file in `python/remote/queue/`:
   `{"experiment": "form", "args": {"form": "my_experiment"}}`
   (or by hand: `..\.venv\Scripts\python.exe run.py configs/my_experiment.toml`)
5. Results: `results/<name>.json` (all data), `results/<name>.png` (chart), `results/<name>_stats.txt` (numbers and
   statistical tests).

Every setting in the form carries a footnote tag (`[R2]`, `[W5]`, `[F14]` …). Look it up in **`FACTOR_GUIDE.md`**:
what it means, how the engine models it, its autopilot values, the evidence level and the sources.

## 2. The three modes of a factor
| mode | what happens | use it for |
|---|---|---|
| `off` | the factor doesn't exist in the world | the equilibrium baseline; everything you're *not* studying |
| `auto` | autopilot: realistic settings from the research (listed in the guide) | a natural background, or a first look at a factor |
| `custom` | defaults from the guide + whatever you set | the factor you are isolating / dose-response experiments |

To **isolate** a trait: put the factor that should drive it on `custom` (or `auto`), keep everything else `off`, and
compare with the baseline run (`configs/baseline.toml`, all off). Change one thing per experiment.

## 3. How a run works
- **Worlds:** `replicates` independent worlds per **arm**. Arms: `frozen` (no mutation; must show zero genetic
  change), `shadow` (copies the real arm's births and deaths but picks who at random = chance alone), `real`
  (natural selection). **Adaptation = real minus shadow.** See `python/equilibrium/README.md` for why.
- **Each tick**, for every worm: active factors update the environment → factors adjust that worm's energy cost,
  speed, death chance, fertility, mutation size and senses → the worm senses, its brain decides turn and speed, it
  moves, eats, pays energy → it may die (starvation, old age, factor effects) → if its energy is high enough it
  splits in two (child = mutated copy).
- **Brain:** the toy-brain network (8 hidden neurons). Inputs: 5 base senses (smell, smell change, taste, taste change,
  eating) **plus 15 extra sense channels** (temperature, oxygen, CO2, salt, pH, light, touch, vibration, electric
  field, magnetic field, pheromone, toxin, pathogen, predator…). A channel reads 0 while its factor is off. The
  layout is fixed, so founders and results are comparable across every form.
- **Trait genes** (not neurons): mutation-rate gene, DNA repair, toxin/pathogen/virus resistance, heat tolerance,
  ability to digest food type B, nictation (riding carriers), male tendency, maternal provisioning, dauer tendency,
  escape. They evolve like any gene; abilities cost energy (`trait_cost`), so they only spread if they pay.
- **Founders:** evolved champions from the toy-brain fair run (one per replicate) converted to this layout.

## 4. What is measured (every `every` ticks, every world)
Population, births, deaths (and deaths by cause), energy, food, genetic distance from founder, genetic diversity,
founder lineages alive, eating rate, speed, turning, age, worms in dauer, the mean of **every trait gene**
(`trait_*`), how strongly **every sense** is wired into the brain (`wire_*`; an unused sense drifts, a useful one
grows), plus each active factor's own measures (infection rates, bites, dose, …).

The stats file applies the baseline rules (equilibrium, zero point) when a frozen arm exists, lists every measure at
the end of the run per arm, and tests real vs shadow (sign-flip permutation test, paired by replicate).

## 5. Files
| file | what |
|---|---|
| `engine.py` | the world: worms, brains, eating, energy, deaths, births, measurements, genome layout, trait list |
| `fields.py` | environmental fields (space pattern × time pattern) used by most physical/chemical factors |
| `factors_env.py` | physical, radiation and chemical factors |
| `factors_bio.py` | food, living-enemy, population and genetic factors |
| `config.py` | the **registry** (every factor: class, custom defaults, autopilot) + loading and checking forms |
| `run.py` | runs a form; `--quick` for a seconds-long check |
| `analyze.py` | chart + stats for a result file |
| `make_form.py` | regenerates `configs/TEMPLATE.toml` and `FACTOR_GUIDE.md` from the catalog + registry |
| `test_factors.py` | smoke test: every factor alone on autopilot (run after any change) |
| `configs/` | `TEMPLATE.toml` (blank form), `baseline.toml`, `example_*.toml` |
| `FACTOR_GUIDE.md` | footnotes: explanation, model, autopilot values, evidence and sources for every setting |

## 6. Safety rails
- A form with an unknown section, factor, or setting is **rejected** with a message saying what's wrong. Typos never
  silently do nothing.
- `off` with settings, or `auto` with settings, is rejected (ambiguous).
- The catalog and the registry are compared on every load; if a factor is in one but not the other, nothing runs.

## 7. Adding or changing a factor
1. Add/edit its entry in `python/factors/catalog.toml` (forms, evidence, sources).
2. Write or edit its class in `factors_env.py` / `factors_bio.py` (docstring = how it is modelled; it appears in the guide).
3. Add/edit its line in `REGISTRY` in `config.py`: class, custom defaults, autopilot values.
4. `python test_factors.py 1500 <name>` then `python make_form.py`.

## 8. Known limits (read before drawing conclusions)
- Every factor is a **simplified** model of the direction and rough size of the effect described in the research,
  not of the biochemistry. Magnitudes are model units; the guide says where numbers come from and which are guesses.
- CONTESTED / UNTESTED factors (magnetic field, radiofrequency) are modelled as abstract senses or as heat, and
  flagged; the GUI only shows them in Researcher mode.
- The brain is the small toy brain, not the 300-neuron connectome (swap-in is possible later).
- Switching on everything at once (`auto` everywhere) makes the world unlivable within a few thousand ticks. That is
  expected: every hazard is active at once.
- Short `--quick` runs show whether a form works, not what evolves. Evolution needs the full run.
