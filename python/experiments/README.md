# Test bench experiments

Runs entirely on your PC's GPU. No cloud, no Claude needed.

**To run one:** drag a `.toml` file from this folder onto `python\run_experiment.bat` (or run
`run_experiment.bat experiments\NAME.toml`). When it finishes, read `runs\bench\NAME\summary.md` and the charts next
to it (`effects.png`, `surface.png`, `brain.png`). A copy also goes to `results\bench_NAME_*`.
Add `--quick` after the file name for a tiny test version (a few minutes).

**Don't close the black window while it runs.** It's safe to stop between experiments.

## Two kinds of experiment

| `mode` | question | what happens |
|---|---|---|
| `"evolve"` | environment -> brain | for every combination of settings: evolve brains, then test them; reports skill, behaviour, which brain layers changed and which layers matter |
| `"behave"` | brain -> behaviour | take already-evolved brains, turn dials, run one lifetime in identical worlds; reports what the worms do |

Every combination of the `[[factor]]` levels is run (a **factorial design**). Then a **quadratic** is fitted to every
result (a **response surface**):

    y = b0 + sum b_i x_i + sum b_ii x_i^2 + sum b_ij x_i x_j

`b_i` = straight effect of a dial, `b_ii` = the result peaks or dips inside the range (needs 3+ levels),
`b_ij` = two dials interact. The report says which are "clear" (bigger than twice their uncertainty) and where
the fitted best settings are.

Keep it to 2-4 factors with 2-3 levels each: 3 factors x 3 levels = 27 combinations already.

## Settings file

```toml
name = "my_test"
mode = "evolve"                 # or "behave"
description = "what I'm testing"

[base]                          # starting world: any setting in ecosim/config.py
predators = 6
food_regrow_per_tick = 0.2
touch_gain = 3.0
hunger = true                   # hunger peptide on/off
fitness = "end"                 # energy left at the end + survival

[world.features.toxin]          # formula-world features; built in: temperature, light, toxin, oxygen
a = 1.0                         # strength
b = -0.6                        # baseline (below 0 = only the peaks of the pattern are toxic)
scale = 150                     # patch size (world units; the world is 1920 x 1080)
period = 0                      # ticks to drift through one cycle (0 = never moves)
cost = 1.5                      # energy lost per tick at full strength (normal living cost is 0.6)
gain = 3.0                      # how strongly the sensing neurons feel it

[world.features.salt]           # a custom feature: say which neurons sense it
neurons = ["ASE"]
a = 1.0

[brain]
knockout = ["RIS"]              # always silenced (neuron ASHL, class ASH or a layer)
freeze = ["sensory"]            # evolve mode: synapses INTO these never change
[brain.gain]
command = 1.0                   # input multiplier per neuron/class/layer
[brain.modulators.serotonin]    # a named "mood": scales its targets' input
targets = ["command"]
effect = 0.6                    # at level 1 the targets get x0.6
level = 0.0                     # default level
[brain.timed_clamp]             # force neurons on/off for a window of ticks
targets = ["AVA"]
state = "on"
from_tick = 500
to_tick = 700

[evolve]                        # mode = "evolve"
seeds = 8                       # independent runs per combination
brains = 16                     # brains per run; each scored as 60 clones in full-size worlds
worlds_per_generation = 2
generations = 60
start = "random"                # or a folder of earlier brains (one *_sN folder with best_genome.npy per seed)
layer_knockouts = true          # also measure how much skill each layer carries

[behave]                        # mode = "behave"
brains = "runs/step19"          # folder searched for best_genome.npy (or a list of .npy files)
max_brains = 16
worlds = 12
clones = 60

[test]
worlds = 12                     # fixed unseen test worlds (seeds 4000+)

[[factor]]
name = "world.toxin.a"
levels = [0.0, 1.0, 2.0]
[[factor]]
name = "cfg.food_regrow_per_tick"
levels = [0.1, 0.2, 0.4]
```

## Dial names for `[[factor]]`

| dial | meaning |
|---|---|
| `cfg.<setting>` | any world setting in `ecosim/config.py`: `food_regrow_per_tick`, `predators`, `pred_speed`, `food_patches`, `obstacles`, ... |
| `world.<feature>.<a/b/scale/period/cost/gain>` | a formula-world feature listed under `[world.features]` |
| `brain.gain.<target>` | input multiplier for a neuron, class or layer |
| `brain.knockout.<target>` | 1 = silenced, 0 = normal |
| `brain.clamp.<target>` | 1 = forced on, -1 = forced off, 0 = normal |
| `brain.mod.<modulator>` | level of a modulator from `[brain.modulators]` |

**Layers** (approximate, from WormAtlas): `sensory`, `inter1` (AIA/AIB/AIY/AIZ: better or worse?),
`inter2` (RIA/RIB/RIM/RIS...: steering, speed, arousal), `command` (AVA/AVB/AVD/AVE/PVC: go or reverse),
`motor`, `pharynx`, `muscle`.

## Traits (every evolve run measures these)

Biology's **breeder's equation**: **R = h^2 x S**
- **S** (selection) = how much better the brains chosen to breed were than average, per generation
- **R** (response) = how much the population average actually changed per generation
- **h^2** (heritability) = R / S: how much of the selection got passed on (noise and mutation make it < 1)

| trait | measured as |
|---|---|
| skill | energy left/100 + survival |
| foraging | food eaten |
| survival | worms alive at the end |
| escape | minus predator bites |
| speed | average speed |
| rest_when_full | speed when hungry minus speed when full |
| clumping | minus distance to the nearest worm |
| avoid_<feature> | minus exposure to each formula-world feature (e.g. avoid_toxin) |
| **intelligence** | skill on 5 kinds of world it never trained in (scarcer / richer / moving food, faster predators, new poison), start vs end |
| **sense_<name>** | importance of each sense = skill lost when its neurons are silenced, start vs end (rising = evolution is using it) |

Each shows up in the report as `R_<trait>`, `S_<trait>`, `h2_<trait>`, `change_<trait>`, `intelligence_gain`,
`sense_<name>_gain`, and every one gets its own quadratic fit: a formula for which settings make that trait evolve
fastest. Optional `[[battery]]` tables replace the default intelligence worlds (see ecosim/bench/traits.py).

## Campaigns: screen -> zoom -> machine learning (`mode = "campaign"`)

For "which settings make trait X evolve fastest?" with the fewest runs. Factors take a range (`low`, `high`,
optional `integer = true`) instead of levels. Set `[campaign] target = "intelligence_gain"` (or any result name).

1. **Screen:** every factor at low/high in a fractional factorial (about N+1 runs for N factors, not 2^N). Ranks
   the factors; the unimportant ones get fixed at their better value.
2. **Zoom:** the top factors (`top = 3`) in a central composite design, quadratic fit, then shrink the box around
   the predicted best and repeat (`zoom_rounds`).
3. **Learn (machine learning):** a **Gaussian process** (a model that predicts the target *and how unsure it is*)
   fitted to every run so far picks the next settings by **expected improvement** (Bayesian optimisation), for
   `ml_runs` more runs.

Report: `summary.md` (factor ranking, each zoom's formula, the ML trace, best measured and model's best guess) and
`campaign.png`. Always confirm the winner with a bigger run before trusting it. Examples:
`campaign_intelligence.toml` (~6-7 h) and `campaign_smoke.toml` (minutes).

## Honest limits

- Brain-dial effects are facts about this simplified model, not proof about real worms.
- The formula world (temperature, light, toxin, oxygen, custom) is separate from the older Step 19 senses
  (`senses = true` in `[base]`); you can use both.
- Every extra factor multiplies the runs. Time per evolve combination is roughly
  seeds x brains x worlds_per_generation x generations / 1100 minutes on an RTX 3080
  (the toxin_vs_food example: 8 x 16 x 2 x 60 / 1100 = ~14 min per combination, ~2.3 h for all 9).
