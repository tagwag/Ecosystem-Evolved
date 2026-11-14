"""All tunable numbers live here (no magic numbers buried in the code)."""
from dataclasses import dataclass


@dataclass
class Config:
    # ---- world ----
    width: float = 1920.0
    height: float = 1080.0
    seed: int = 1

    # ---- food (patchy, like the original foodFall) ----
    food_patches: int = 6           # number of food clusters
    food_per_patch: int = 60
    patch_spread: float = 60.0      # std-dev of a patch, in world units
    food_value: float = 100.0       # energy per food (Constants.foodValue)
    season_every: int = 0           # Step 16: food patches jump to new random spots every N ticks (0 = never);
                                    # old food stays, new food grows at the new spots. GPU code only.
    food_regrow_per_tick: float = 0.6  # foods respawned per tick (fractional ok)
    eat_radius: float = 8.0

    # ---- smell field (what the cell can sense: concentration only, no direction) ----
    smell_cell: float = 16.0        # grid resolution of the smell map
    smell_sigma_cells: float = 4.0  # how far smell diffuses (in grid cells)
    smell_update_every: int = 10    # ticks between smell-map refreshes

    # ---- body (rules carried over from Cell.java) ----
    start_size: float = 20.0
    size_per_food: float = 10.0     # Cell.grow(): size += 10
    start_energy: float = 600.0
    base_cost: float = 0.6          # energy burned per tick just existing
    move_cost: float = 0.25         # extra energy per unit of speed
    # speed = -5/8000 * size + 5   (Cell.size2speed for normal cells), never below 1
    speed_slope: float = -5.0 / 8000.0
    speed_max: float = 5.0
    speed_min: float = 1.0

    # ---- brain ----
    hidden: int = 4

    # ---- evolution ----
    population: int = 120
    ticks_per_generation: int = 1500
    generations: int = 60
    elite_fraction: float = 0.2     # top survivors that become parents (leaderboard)
    mutation_sigma: float = 0.15
    mutation_rate: float = 0.3      # chance each weight mutates
    # connectome genomes are big (one gene per synapse), so mutate far fewer genes at once
    worm_mutation_rate: float = 0.02
    worm_population: int = 60
    # structural mutations (per child): silence a synapse, restore one, knock out a whole neuron
    p_silence: float = 0.3
    p_restore: float = 0.2
    p_knockout: float = 0.05
    p_flip: float = 0.2

    # ---- predators (Step 8; 0 = none). GPU code only (batch3_fast). Pristionchus-style v1:
    # fixed hunting rule (chase the nearest prey within pred_sense, else wander), bite on contact,
    # then a handling pause. Prey feel a predator by touch (front -> ALM/AVM, back -> PLM/PVM).
    predators: int = 0              # per world
    pred_speed: float = 2.5         # prey max speed is 5: fast prey can outrun, slow/resting prey can't
    pred_sense: float = 150.0       # chase range (for prey at full speed when pred_sense_still >= 0)
    pred_sense_still: float = -1.0  # Step 8b: range for motionless prey; range grows with prey speed up to
                                    # pred_sense. -1 = off (every prey seen at pred_sense, as in Step 8)
    pred_bite: float = 12.0         # contact distance
    pred_damage: float = 150.0      # energy taken per bite (1.5 food)
    pred_cooldown: int = 60         # ticks a predator stops after a bite (handling time)
    touch_radius: float = 40.0      # prey touch range
    touch_gain: float = 3.0         # touch input strength; 0 = prey can't feel predators
    # Step 14b selfish-herd predators (0 = off, as before). nbr = living worms within herd_radius of a prey.
    herd_radius: float = 40.0
    pred_loner: float = 0.0         # targeting: prey counts as (1 + pred_loner * nbr) x farther away -> loners chased first
    pred_confuse: float = 0.0       # confusion effect: a bite lands with chance 1 / (1 + pred_confuse * nbr);
                                    # a missed bite still costs the predator its handling pause

    # ---- digestion (Step 8c; off by default). GPU code only (batch3_fast). Eaten food goes into the gut first and
    # becomes usable energy over time: fastest when still, slower when moving (real worms rest after meals).
    digestion: bool = False
    stomach_cap: float = 300.0      # gut holds 3 meals; a full gut blocks eating until digestion frees room
    dig_rate: float = 1.5           # energy per tick moved from gut to body when still (a meal = ~67 ticks)
    dig_moving: float = 0.25        # fraction of dig_rate left at full speed (4x slower)

    # ---- worm-to-worm scent (Step 11, "ascarosides"; off by default). GPU code only (batch3_fast).
    # Every living worm leaves scent; the field is the blurred worm density, refreshed with the food smell.
    # Level -> ASKL/ASKR (the main ascaroside-sensing neurons), rising -> ADLL, falling -> ADLR.
    pheromone: bool = False
    pher_gain: float = 3.0          # input strength (like the food sensors' starting gain)
    pher_sigma_cells: float = 3.0   # how far the scent spreads (grid cells of smell_cell units)
    pher_full: float = 5.0          # this many worms in one spot = scent level 1 (field is capped at 1)

    # ---- obstacles (Step 18; off by default). GPU code only. Pillars, walls and caves (C-shaped walls with an
    # opening) block worms and predators; predators can't see prey through them. A worm that bumps into one feels
    # it with its nose-touch neurons (FLP, OLQ). Counts are per 1,000,000 square units (the normal world is ~2.07M),
    # at least 1 of each per world.
    obstacles: bool = False
    obs_cell: float = 8.0           # obstacle grid resolution
    obs_pillars: float = 3.0        # per 1M sq units; radius 25-50
    obs_walls: float = 2.0          # per 1M sq units; 12 thick, 150-300 long, any angle
    obs_caves: float = 1.5          # per 1M sq units; ring radius 60-90, 12 thick, 80-degree opening
    nose_gain: float = 3.0

    # ---- Step 19: all worm senses (off by default). GPU code only. Each sense needs something in the world:
    #   temperature  smooth hot/cold field; comfortable in the middle, cost per tick grows with distance from it
    #   light        a few bright zones (UV): cost while in them
    #   toxic        a few toxic patches: strong cost while in them
    #   predator     scent spreading from each predator (needs predators)
    #   co2          from crowds of worms and from food (bacteria); cost when very high
    #   o2           lower where food (bacteria) is: a second food cue, no cost
    #   on_food      food within 20 units (touch/texture of the lawn)
    # Zones per 1,000,000 square units (normal world ~2.07M), at least 1 of each.
    senses: bool = False
    sense_gain: float = 3.0
    # ---- Step 22 (2026-11-13): RED LIGHT / GREEN LIGHT, the "Reward Hacking experiment" (off by default). GPU only.
    # Time is split into red and green phases of random length (red_min..red_max blocks of 10 ticks, per world).
    #   red phase    moving is punished: energy per tick - red_cost x speed command (0..1). Standing still is free.
    #   green phase  nothing special: the worm should forage as usual.
    # The worm cannot see the phase. The ONLY cue is the peptide channel: with redlight on, the broadcast peptide
    # level is set from OUTSIDE (it no longer follows the worm's own hunger): red_signal =
    #   'true'       peptide = 1 during red, 0 during green (an honest command)
    #   'scrambled'  peptide follows a different random schedule with the same statistics (an uninformative signal)
    # A brain with no peptide receptors (hunger=False) gets no signal at all.
    redlight: bool = False
    red_cost: float = 3.0           # per tick at full speed command (base_cost is 0.6): moving on red is very costly
    red_min: int = 3                # phase length in blocks of 10 ticks: 30..100 ticks by default
    red_max: int = 10
    red_signal: str = 'true'
    # ---- Step 21 (2026-11-13): gravity pattern (off by default). GPU code only (batch3_fast.FastSim).
    # Local gravity = 1 g + strength x pattern. The PATTERN is made the way the original Java game made its cave
    # walls (java-original/src/Enviroment/Obstacle.java): simplex noise sampled at a feature size, "wall" where the
    # noise is above a threshold. Here the walls are HEAVY-gravity regions, the open ground is light, and the hard wall
    # edge is replaced by a soft ramp (feathered, like blending paint). Values -1..+1 with mean 0. The pattern is
    # the same in every world and every generation; the STRENGTH is set per world (FastSim.grav_s), so one run can
    # hold worlds from "almost uniform Earth gravity" to "0 g to 2 g". dg below = local gravity - 1.
    #   sensed   dg is fed (x grav_gain) into the PVD neurons, the mechanosensory neurons implicated in C. elegans
    #            gravity sensing (Ackley et al., negative gravitaxis needs MEC-7 / MEC-12 / TRPA-1 and PVD)
    #   slowed   speed x (1 - grav_slow x dg): heavier ground is slower, lighter ground faster (limits 0.25x - 1.75x)
    #   paid     energy per tick + grav_cost x dg: heavier ground costs more, lighter ground less (base_cost is 0.6)
    # These effects are MODEL ASSUMPTIONS (heavier = slower and costlier), not measured worm physiology.
    gravity: bool = False
    grav_gain: float = 3.0
    grav_slow: float = 0.5
    grav_cost: float = 0.3
    grav_feature: float = 220.0     # size of the cave-like features in world units (the Java game used 14 pixels)
    grav_wall: float = 0.25         # noise level (noise scaled to -1..1) above which ground is "wall" = heavy
    grav_feather: float = 0.25      # half-width of the soft edge in noise units; 0 = hard cave-wall edge
    grav_seed: int = 20261113       # fixes the pattern's layout (same pattern for every world and run)
    temp_cost: float = 0.4          # per tick at the hottest/coldest spot (base_cost is 0.6)
    light_cost: float = 0.3
    toxic_cost: float = 1.5
    co2_cost: float = 0.3           # per tick at maximum CO2, starts above half
    temp_bumps: float = 2.0
    light_zones: float = 1.5
    toxic_zones: float = 1.5
