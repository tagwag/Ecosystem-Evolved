"""Environmental fields: a level of something (temperature, oxygen, salt, radiation dose, ...) at every point of the
arena, changing over time.

A field = SPACE pattern x TIME pattern, evaluated on a coarse grid (cells x cells per world) and read at each worm's
position. Every physical/chemical factor in the catalog uses one of these, so they all behave and are configured the
same way.

SPACE patterns (field `space`):
  uniform   the same level everywhere
  gradient  rises linearly from one edge to the other (`low` at x=0 -> `high` at x=size, direction `angle` degrees)
  spots     `n_spots` round spots of radius `spot_r` at `high`, background `low` (soft edges)
  hotspot   one spot (contaminated patch / heat source)
  patches   follows the food patches (e.g. CO2 from rotting fruit, bacteria on food)
TIME patterns (field `time`):
  constant  no change
  cycle     sine wave with `period` ticks and `amplitude` (fraction of the level), e.g. day/night or seasons
  shock     normal level, but between `shock_start` and `shock_start + shock_len` it jumps to `shock_level`;
            repeats every `shock_every` ticks if > 0
  random    random walk of the level (mean-reverting), step size `noise`
The final level = space value x time multiplier (+ shock override). All values are plain numbers in the factor's
own units (degrees C, % oxygen, Gy per 1000 ticks, ...), documented per factor in FACTOR_GUIDE.md.
"""
import math

import torch


class Field:
    def __init__(self, spec, n_worlds, size, cells, dev, gen, patches=None):
        self.s = dict(space="uniform", time="constant", low=0.0, high=0.0, level=0.0, angle=0.0, n_spots=3,
                      spot_r=40.0, period=10000, amplitude=0.0, shock_start=0, shock_len=0, shock_level=0.0,
                      shock_every=0, noise=0.0)
        self.s.update(spec or {})
        s = self.s
        self.N, self.size, self.cells, self.dev = n_worlds, size, cells, dev
        c = (torch.arange(cells, device=dev) + 0.5) * size / cells
        X, Y = torch.meshgrid(c, c, indexing="xy")                     # (cells, cells)
        if s["space"] == "uniform":
            base = torch.full((n_worlds, cells, cells), float(s["level"] or s["high"]), device=dev)
        elif s["space"] == "gradient":
            a = math.radians(s["angle"])
            u = ((X - size / 2) * math.cos(a) + (Y - size / 2) * math.sin(a)) / size + 0.5
            base = (s["low"] + (s["high"] - s["low"]) * u.clamp(0, 1))[None].expand(n_worlds, -1, -1).clone()
        elif s["space"] in ("spots", "hotspot"):
            k = 1 if s["space"] == "hotspot" else int(s["n_spots"])
            ctr = size * (0.1 + 0.8 * torch.rand(n_worlds, k, 2, generator=gen, device=dev))
            d2 = (X[None, None] - ctr[..., 0, None, None]) ** 2 + (Y[None, None] - ctr[..., 1, None, None]) ** 2
            bump = torch.exp(-d2 / (2 * s["spot_r"] ** 2)).amax(1)    # (N, cells, cells) 0..1
            base = s["low"] + (s["high"] - s["low"]) * bump
        elif s["space"] == "patches":
            assert patches is not None
            d2 = (X[None, None] - patches[..., 0, None, None]) ** 2 + (Y[None, None] - patches[..., 1, None, None]) ** 2
            bump = torch.exp(-d2 / (2 * s["spot_r"] ** 2)).amax(1)
            base = s["low"] + (s["high"] - s["low"]) * bump
        else:
            raise ValueError(f"unknown space pattern {s['space']!r}")
        self.base = base
        self.walk = torch.zeros(n_worlds, device=dev)
        self.gen = gen
        self.now = base.clone()

    def update(self, t):
        s = self.s
        mult = torch.ones(self.N, device=self.dev)
        if s["time"] == "cycle":
            mult = mult * (1 + s["amplitude"] * math.sin(2 * math.pi * t / s["period"]))
        elif s["time"] == "random":
            self.walk = 0.999 * self.walk + s["noise"] * torch.randn(self.N, generator=self.gen, device=self.dev)
            mult = mult * (1 + self.walk)
        lvl = self.base * mult[:, None, None]
        if s["time"] == "shock" or s["shock_len"] > 0:
            tt = t - s["shock_start"]
            if s["shock_every"] > 0 and tt >= 0:
                tt = tt % s["shock_every"]
            if 0 <= tt < s["shock_len"]:
                lvl = torch.full_like(lvl, float(s["shock_level"]))
        self.now = lvl

    def at(self, xy):
        """Level at each worm position. xy: (N, S, 2) -> (N, S)."""
        i = (xy / self.size * self.cells).long().clamp(0, self.cells - 1)
        n = torch.arange(self.N, device=self.dev)[:, None]
        return self.now[n, i[..., 1], i[..., 0]]
