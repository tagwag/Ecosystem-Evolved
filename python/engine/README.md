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

## 9. Evolution toolkit: checkpoints, resume, branching, family trees (added 2026-11-13)

**Safe interrupt and resume.** Every `run.checkpoint_every` ticks (default 10,000) the complete state is saved to
`results/<name>_ckpt/t<tick>.pt`: every worm, genome, id and counter, every factor's internal state (infections,
predator positions, gut contents, fields...), the random generator and the measurements so far. If a run is stopped
(window closed, power cut, watcher CANCEL), running the same form again **resumes from the latest checkpoint**
automatically and continues exactly as if it had never stopped (tested: identical final numbers). `--fresh` starts over.

**Return to / branch from any saved moment.**
`python run.py configs/<form>.toml --from-tick 20000 --as my_branch --seed 7`
starts a new run called `my_branch` from tick 20,000 of `<form>`'s run. Without `--seed` it repeats the original
exactly; with a seed it is the same world at the same moment with new luck: a **Lenski-style replay** ("would
evolution go the same way again?"). The branch also copies the family-tree log up to that moment.
Watcher: `{"experiment": "form_branch", "args": {"form": "...", "tick": 20000, "as": "my_branch", "seed": 7}}`.

**Family-tree recording** (`run.record_tree = true`, default). Every worm gets an id (founders 0..slots-1, then
counting up in each world). Every birth is logged (tick, world, parent id, child id, mutation size) and every death
(tick, world, id) in `results/<name>_tree/part*.npz`. Every worm also carries `nmut` (mutation events on its line of
descent since its founder) and `msize` (their total size). Measured every sample: `mutations`, `mutation_size`,
`top_family`, `top_family_share`, `top_family_mutations`.

**Genealogy tools** (`genealogy.py`; worlds numbered arm by arm: frozen 0..R-1, shadow R..2R-1, real 2R..3R-1):
| command | answers |
|---|---|
| `python genealogy.py <run> summary --world W` | how many generations deep, births/deaths per 1000 ticks, mutation size per birth, founder families extinct |
| `... living --world W` | which founder families are alive at the end, their share and generation depth |
| `... trace --world W --uid U` | worm U's full line of descent: every ancestor, birth tick, mutation size, death tick |
| `... mrca --world W` | the most recent common ancestor of everyone alive at the end, and when the population coalesced |
| `... fixation --world W --level 0.95` | when (if ever) one founder family took over |
| `... muller --world W` | Muller plot (PNG): share of each founder family over time |
| `... family --world W --uid U` | one family's size over time + a drawing of its tree (PNG) |
| `... report --world W` | all of the above in one text file + PNGs (`results/<run>_w<W>_genealogy.txt`) |
Watcher: `{"experiment": "genealogy_report", "args": {"run": "baseline", "world": 60}}` (CPU only, seconds).

## 10. New world settings: noise, mutation style, recombination, immigration (added 2026-11-13)
All are in the `[world]` section of a form, footnotes [W19]-[W26] in FACTOR_GUIDE.md. **The defaults reproduce the old
behaviour exactly** (same random numbers), so older forms and results stay comparable.

| setting | default | allowed | what it does |
|---|---|---|---|
| `sense_noise` | 0.01 | 0-1 | noise on smell and taste readings each tick |
| `motor_noise` | 0.1 | 0-2 | random wobble on every turn |
| `mutation_mode` | "all" | "all", "sparse" | all genes change a little, or ~`mutation_genes` genes change by bigger steps (same expected total) |
| `mutation_genes` | 10 | 1-1000 | genes changed per child in sparse mode |
| `recombination_rate` | 0.0 | 0-1 | chance per birth of a 50/50 gene mix with the nearest worm within `recombination_radius` |
| `recombination_radius` | 10.0 | 0-400 | how near that worm must be |
| `immigration_rate` | 0.0 | 0-100 | newcomers per 1000 ticks per world; each starts a new family (parent id -1) |
| `immigrant_source` | "founders" | "founders", "random" | newcomers carry the founder genome, or a random unevolved one |

Rules that keep the controls honest:
- The **frozen arm never gets recombination or immigrants**, so its zero-change check (genetic distance 0) still holds.
- Shadow and real arms get immigrants at the same rate but independently, so their populations can differ by a few worms.
- Out-of-range or unknown values are refused with a message naming the allowed values (also in `--preflight`).
- New measurements: `immigrants` and `recombinations` (counts per sample, per world) appear in results when used.
Test: `configs/test_new_world.toml --quick` (all switched on) passes the zero point. Code: engine.py `_immigrate`,
the recombination block in `_birth`, the noise lines in `tick`.

## 11. Allowed-word lists and `factor_mode` (added 2026-11-13)
- Every text setting with a fixed set of words is listed in config.py: `FIELD_CHOICES` (field.space, field.time),
  `FACTOR_MODE_CHOICES` (a factor's own mode), `SOURCE_CHOICES` (radiation / toxin sources), `WORLD_CHOICES`.
  `check_choices()` refuses anything else with the allowed list. Before this, a typo was silently ignored by the factor
  code (e.g. `space = "gradiant"` quietly behaved like a flat field). If you add a word to the factor code, add it here.
- In a form, a factor's own mode is written `factor_mode = "pristionchus"` because `mode` is off / auto / custom.
  The template (configs/TEMPLATE.toml) shows it that way.
