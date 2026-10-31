"""The environment: food, the smell field, and agents' bodies.

Agents do NOT get food directions (the original SightService did). They only sense the
smell concentration at their own position -- like a real bacterium.
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from .config import Config


class World:
    def __init__(self, cfg: Config, rng: np.random.Generator):
        self.cfg, self.rng = cfg, rng
        self.gw = int(np.ceil(cfg.width / cfg.smell_cell))
        self.gh = int(np.ceil(cfg.height / cfg.smell_cell))
        self.patch_centers = np.column_stack([
            rng.uniform(100, cfg.width - 100, cfg.food_patches),
            rng.uniform(100, cfg.height - 100, cfg.food_patches),
        ])
        n = cfg.food_patches * cfg.food_per_patch
        self.food = np.zeros((n, 2))
        self.food_alive = np.zeros(n, bool)
        for i in range(n):
            self._respawn(i)
        self._regrow_acc = 0.0
        self.smell = np.zeros((self.gw, self.gh))
        self.update_smell()

    # ---- food ----
    def _respawn(self, i):
        c = self.patch_centers[self.rng.integers(len(self.patch_centers))]
        p = c + self.rng.normal(0, self.cfg.patch_spread, 2)
        self.food[i] = np.clip(p, [0, 0], [self.cfg.width - 1, self.cfg.height - 1])
        self.food_alive[i] = True

    def regrow(self):
        self._regrow_acc += self.cfg.food_regrow_per_tick
        dead = np.flatnonzero(~self.food_alive)
        k = min(int(self._regrow_acc), len(dead))
        self._regrow_acc -= k
        for i in self.rng.permutation(dead)[:k]:
            self._respawn(i)

    def update_smell(self):
        f = self.food[self.food_alive]
        grid = np.zeros((self.gw, self.gh))
        gx = np.clip((f[:, 0] / self.cfg.smell_cell).astype(int), 0, self.gw - 1)
        gy = np.clip((f[:, 1] / self.cfg.smell_cell).astype(int), 0, self.gh - 1)
        np.add.at(grid, (gx, gy), 1.0)
        self.smell = gaussian_filter(grid, self.cfg.smell_sigma_cells, mode='wrap')
        m = self.smell.max()
        if m > 0:
            self.smell /= m                      # 0..1

    def smell_at(self, pos):
        gx = np.clip((pos[:, 0] / self.cfg.smell_cell).astype(int), 0, self.gw - 1)
        gy = np.clip((pos[:, 1] / self.cfg.smell_cell).astype(int), 0, self.gh - 1)
        return self.smell[gx, gy]

    def eat(self, pos, alive):
        """Each living agent eats at most one food within eat_radius. Returns bool array 'ate'.

        Uses a spatial hash (grid buckets) instead of checking every agent against every food --
        the fix for the O(n^2) sight loop in the Java version.
        """
        ate = np.zeros(len(pos), bool)
        cell = self.cfg.eat_radius * 2
        fidx = np.flatnonzero(self.food_alive)
        if len(fidx) == 0:
            return ate
        buckets = {}
        keys = (self.food[fidx] // cell).astype(int)
        for j, (kx, ky) in zip(fidx, keys):
            buckets.setdefault((kx, ky), []).append(j)
        r2 = self.cfg.eat_radius ** 2
        for a in np.flatnonzero(alive):
            kx, ky = (pos[a] // cell).astype(int)
            done = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in buckets.get((kx + dx, ky + dy), ()):
                        if self.food_alive[j] and np.sum((self.food[j] - pos[a]) ** 2) <= r2:
                            self.food_alive[j] = False
                            ate[a] = True
                            done = True
                            break
                    if done: break
                if done: break
        return ate
