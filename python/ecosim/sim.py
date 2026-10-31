"""One generation of the ecosystem: bodies move, burn energy, eat, grow, and die."""
import numpy as np

from .brain import Brains
from .connectome import WormBrains
from .config import Config
from .world import World

TAU = 2 * np.pi


def max_speed(cfg: Config, size):
    """Cell.size2speed: bigger cells are slower."""
    return np.clip(cfg.speed_slope * size + cfg.speed_max, cfg.speed_min, cfg.speed_max)


def make_controller(kind, cfg, genomes, conn=None):
    if kind == 'brain':
        return Brains(genomes, cfg.hidden)
    if kind == 'worm':
        return WormBrains(conn, genomes)
    return None   # 'random'


def run_generation(cfg: Config, genomes, rng, controller='brain', record=None, conn=None):
    """Simulate one generation.

    controller: 'brain' (tiny evolved network), 'worm' (C. elegans connectome),
                or 'random' (fixed random walk, the baseline).
    record: optional list; if given, per-tick snapshots are appended for rendering.
    Returns per-agent fitness (food eaten) and a stats dict.
    """
    P = genomes.shape[0]
    world = World(cfg, rng)
    pos = np.column_stack([rng.uniform(0, cfg.width, P), rng.uniform(0, cfg.height, P)])
    heading = rng.uniform(0, TAU, P)
    size = np.full(P, cfg.start_size)
    energy = np.full(P, cfg.start_energy)
    alive = np.ones(P, bool)
    eaten = np.zeros(P)
    lifetime = np.zeros(P)
    brains = make_controller(controller, cfg, genomes, conn)
    prev_smell = world.smell_at(pos)

    for t in range(cfg.ticks_per_generation):
        if t % cfg.smell_update_every == 0:
            world.update_smell()
        smell = world.smell_at(pos)
        d_smell = np.clip((smell - prev_smell) * 20.0, -1, 1)
        prev_smell = smell

        turn = 0.0
        if controller == 'brain':
            x = np.column_stack([smell, d_smell, energy / cfg.start_energy, np.ones(P)])
            p_tumble, speed_frac = brains.step(x)
        elif controller == 'worm':
            p_tumble, speed_frac, turn = brains.step(smell, d_smell, energy / cfg.start_energy)
        else:
            p_tumble, speed_frac = np.full(P, 0.1), np.full(P, 0.7)

        tumble = rng.random(P) < p_tumble
        heading = np.where(tumble, rng.uniform(0, TAU, P), heading + np.clip(turn, -0.5, 0.5))
        speed = speed_frac * max_speed(cfg, size)
        step = np.column_stack([np.cos(heading), np.sin(heading)]) * speed[:, None]
        pos = np.where(alive[:, None], (pos + step) % [cfg.width, cfg.height], pos)

        energy -= np.where(alive, cfg.base_cost + cfg.move_cost * speed, 0.0)
        ate = world.eat(pos, alive)
        energy += ate * cfg.food_value
        size += ate * cfg.size_per_food
        eaten += ate
        lifetime += alive
        alive &= energy > 0
        world.regrow()

        if record is not None and t % 3 == 0:
            record.append((pos.copy(), alive.copy(), world.food[world.food_alive].copy(), size.copy()))
        if not alive.any():
            break

    fitness = eaten + lifetime / cfg.ticks_per_generation   # food first, survival breaks ties
    return fitness, dict(mean_food=eaten.mean(), best_food=eaten.max(),
                         survivors=int(alive.sum()), ticks=t + 1)
