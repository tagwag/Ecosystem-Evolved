"""Open-ended ecosystem: no generations. Cells eat, grow, split, mutate, and die continuously.

python -m ecosim.ecosystem --brain worm --ticks 20000

Rules (from the Java version, adapted):
- eating food: +energy, size +10 (size slows you down: Cell.size2speed)
- split: when energy > split_energy, the cell divides; the child gets half the energy and a
  MUTATED copy of the brain (structural mutations included for worm brains)
- death: energy <= 0
- the population is capped (oldest-lowest-energy cells are culled) so memory stays bounded
Every split is logged with its mutations so you can trace lineages afterwards.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import connectome as cx
from .brain import Brains, genome_size
from .config import Config
from .evolve import mutate
from .sim import TAU, max_speed
from .world import World


class Ecosystem:
    def __init__(self, cfg: Config, controller='worm', start=40, cap=160, split_energy=900.0, seed=1):
        self.cfg, self.kind, self.cap, self.split_energy = cfg, controller, cap, split_energy
        self.rng = np.random.default_rng(seed)
        self.world = World(cfg, self.rng)
        self.conn = cx.Connectome() if controller == 'worm' else None
        if controller == 'worm':
            self.genomes = cx.random_genomes(self.conn, start, self.rng)
        else:
            self.genomes = self.rng.normal(0, 0.5, (start, genome_size(cfg.hidden)))
        P = start
        self.pos = np.column_stack([self.rng.uniform(0, cfg.width, P), self.rng.uniform(0, cfg.height, P)])
        self.heading = self.rng.uniform(0, TAU, P)
        self.size = np.full(P, cfg.start_size)
        self.energy = np.full(P, cfg.start_energy)
        self.lineage = np.arange(P)          # id of each living cell
        self.parent = {int(i): -1 for i in range(P)}
        self.next_id = P
        self.births = []                     # (tick, child_id, parent_id, mutations)
        self.prev_smell = self.world.smell_at(self.pos)
        self._rebuild()

    def _rebuild(self):
        self.brains = self._make(self.genomes)

    def _make(self, genomes):
        if self.kind == 'worm':
            return cx.WormBrains(self.conn, genomes)
        return Brains(genomes, self.cfg.hidden)

    def _brain_arrays(self, b):
        """Per-agent arrays inside a brain object (leading axis = agent)."""
        n = len(self.genomes)
        return [k for k, v in vars(b).items() if isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[0] == n
                and k not in ('G', 'G_deg', 's_on', 's_off', 's_lvl', 'fwd', 'bwd', 'hd', 'hv', 'rd')]

    def _mutate(self, g):
        if self.kind == 'worm':
            return cx.mutate_worm(g, self.conn, self.cfg, self.rng)
        return mutate(g, self.cfg, self.rng), [('tweak', 0)]

    def step(self, t):
        cfg, rng, P = self.cfg, self.rng, len(self.genomes)
        if t % cfg.smell_update_every == 0:
            self.world.update_smell()
        smell = self.world.smell_at(self.pos)
        d_smell = np.clip((smell - self.prev_smell) * 20.0, -1, 1)
        self.prev_smell = smell
        if self.kind == 'worm':
            p_t, sf, turn = self.brains.step(smell, d_smell, self.energy / cfg.start_energy)
        else:
            x = np.column_stack([smell, d_smell, self.energy / cfg.start_energy, np.ones(P)])
            (p_t, sf), turn = self.brains.step(x), 0.0
        tumble = rng.random(P) < p_t
        self.heading = np.where(tumble, rng.uniform(0, TAU, P), self.heading + np.clip(turn, -0.5, 0.5))
        speed = sf * max_speed(cfg, self.size)
        self.pos = (self.pos + np.column_stack([np.cos(self.heading), np.sin(self.heading)]) * speed[:, None]) \
            % [cfg.width, cfg.height]
        self.energy -= cfg.base_cost + cfg.move_cost * speed
        ate = self.world.eat(self.pos, np.ones(P, bool))
        self.energy += ate * cfg.food_value
        self.size += ate * cfg.size_per_food
        self.world.regrow()

        # births
        for i in np.flatnonzero(self.energy > self.split_energy):
            child, ev = self._mutate(self.genomes[i])
            self.energy[i] /= 2
            self.size[i] = max(cfg.start_size, self.size[i] / 2)
            cid = self.next_id; self.next_id += 1
            self.parent[cid] = int(self.lineage[i])
            self.births.append((t, cid, int(self.lineage[i]), ev))
            self._append(child, self.pos[i] + rng.normal(0, 5, 2), self.energy[i], self.size[i], cid)
        # deaths
        alive = self.energy > 0
        if len(alive) > self.cap:                      # crowding: cull the weakest
            order = np.argsort(self.energy)
            alive[order[:len(alive) - self.cap]] = False
        if not alive.all():
            self._keep(alive)

    def _append(self, g, pos, energy, size, cid):
        keys = self._brain_arrays(self.brains)
        nb = self._make(g[None])                       # brain for the newborn only
        for k in keys:
            setattr(self.brains, k, np.concatenate([getattr(self.brains, k), getattr(nb, k)]))
        self.genomes = np.vstack([self.genomes, g[None]])
        self.pos = np.vstack([self.pos, pos[None] % [self.cfg.width, self.cfg.height]])
        self.heading = np.append(self.heading, self.rng.uniform(0, TAU))
        self.energy = np.append(self.energy, energy)
        self.size = np.append(self.size, size)
        self.lineage = np.append(self.lineage, cid)
        self.prev_smell = np.append(self.prev_smell, self.world.smell_at(pos[None])[0])
        self._pending_new = getattr(self, '_pending_new', 0) + 1

    def _keep(self, m):
        for k in self._brain_arrays(self.brains):    # living cells keep their neural state
            setattr(self.brains, k, getattr(self.brains, k)[m])
        for a in ('genomes', 'pos', 'heading', 'energy', 'size', 'lineage', 'prev_smell'):
            setattr(self, a, getattr(self, a)[m])
        self._keep_mask = m

    def run(self, ticks, log_every=1000, log=print):
        hist = []
        for t in range(ticks):
            if len(self.genomes) == 0:
                log(f'tick {t}: extinct'); break
            self.step(t)
            if t % log_every == 0:
                h = dict(tick=t, population=len(self.genomes), births=len(self.births),
                         mean_energy=float(self.energy.mean()) if len(self.energy) else 0)
                hist.append(h)
                log(f"tick {t:6d}  population {h['population']:4d}  total births {h['births']:5d}")
        return hist


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--brain', choices=['brain', 'worm'], default='worm')
    ap.add_argument('--ticks', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', default='runs/ecosystem')
    a = ap.parse_args()
    eco = Ecosystem(Config(), a.brain, seed=a.seed)
    hist = eco.run(a.ticks)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'history.json').write_text(json.dumps(hist, indent=1))
    (out / 'births.json').write_text(json.dumps(eco.births, default=str))
    if len(eco.genomes):
        np.save(out / 'survivor_genomes.npy', eco.genomes)
        np.save(out / 'survivor_ids.npy', eco.lineage)
    print('saved', out)
