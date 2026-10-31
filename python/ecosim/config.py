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
