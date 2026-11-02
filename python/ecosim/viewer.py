"""Live viewer: watch evolution as it runs (Code Bullet style: the whole population overlaid in one world).

Start the evolution with --watch, then this viewer in a second window:
    python -m ecosim.batch3_fast run hunger_scarce 1 2 3 4 5 6 7 8 --gens 200 --watch 4
    python -m ecosim.viewer                       # or: python -m ecosim.viewer hunger_scarce

The evolution writes the last finished generation of the first N seeds to runs/live/<condition>/latest.npz.
This viewer replays it, then jumps to the newest finished generation. It runs in its own process,
so drawing never slows the evolution (recording costs the sim about 1-3%).

What you see
    green dots      food
    coloured dots   worms, all 60 of one population at once, half see-through so crowds show up;
                    colour = energy: red = starving, yellow = half full, cyan = full gut
    white ring      the worm that ended this generation with the best fitness, with its trail
    grey x          dead worm
    red triangles   predators (Step 8)
    right panel     generation, alive count, food left, fitness curve (this seed + mean of all seeds)

Keys
    space pause | up/down replay speed | left/right switch seed | T trails on/off | R restart replay
    C switch condition (if several are being watched) | Esc quit
"""
import os
import sys
import time
from pathlib import Path

import numpy as np
import pygame

LIVE = Path('runs/live')
W, H, PANEL = 960, 540, 330
BG, PANEL_BG, GRID, TXT, DIM = (14, 16, 22), (24, 27, 35), (30, 34, 44), (225, 228, 235), (140, 146, 160)
FOOD = (70, 200, 90)


def energy_colour(f):
    """0 -> red, 0.5 -> yellow, 1 -> cyan."""
    f = float(np.clip(f, 0, 1))
    if f < 0.5:
        t = f / 0.5
        return (235, int(60 + 175 * t), 50)
    t = (f - 0.5) / 0.5
    return (int(235 - 185 * t), int(235 - 15 * t), int(50 + 190 * t))


def load(path):
    for _ in range(5):                      # the writer renames atomically; retry just in case
        try:
            with np.load(path) as d:
                return {k: d[k] for k in d.files}
        except Exception:
            time.sleep(0.05)
    return None


def conditions():
    return sorted(p.parent.name for p in LIVE.glob('*/latest.npz'))


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    pygame.init()
    screen = pygame.display.set_mode((W + PANEL, H))
    pygame.display.set_caption('Ecosystem-Evolved live')
    font, big = pygame.font.SysFont('consolas', 15), pygame.font.SysFont('consolas', 20, bold=True)
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    clock = pygame.time.Clock()
    cond, data, mtime, t, speed, paused, seed_i, trails = want, None, 0, 0, 5, False, 0, True
    waiting_msg = 'waiting for runs/live/... (start batch3_fast with --watch N)'

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE: paused = not paused
                elif e.key == pygame.K_UP: speed = min(speed * 2, 80)
                elif e.key == pygame.K_DOWN: speed = max(speed // 2, 1)
                elif e.key == pygame.K_RIGHT and data is not None: seed_i = (seed_i + 1) % len(data['seeds'])
                elif e.key == pygame.K_LEFT and data is not None: seed_i = (seed_i - 1) % len(data['seeds'])
                elif e.key == pygame.K_t: trails = not trails
                elif e.key == pygame.K_r: t = 0
                elif e.key == pygame.K_c:
                    cs = conditions()
                    if cs:
                        cond = cs[(cs.index(cond) + 1) % len(cs)] if cond in cs else cs[0]
                        data, mtime, t = None, 0, 0

        # pick up a new generation: at the start, or when the current replay has finished
        if cond is None:
            cs = conditions()
            cond = cs[0] if cs else None
        if cond is not None:
            path = LIVE / cond / 'latest.npz'
            if path.exists() and path.stat().st_mtime != mtime and (data is None or t >= len(data['pos']) - 1):
                new = load(path)
                if new is not None:
                    data, mtime, t = new, path.stat().st_mtime, 0
                    seed_i = min(seed_i, len(data['seeds']) - 1)

        screen.fill(BG)
        if data is None:
            screen.blit(big.render(waiting_msg, True, TXT), (20, H // 2 - 10))
            pygame.display.flip(); clock.tick(10); continue

        T = len(data['pos'])
        sx, sy = W / float(data['width']), H / float(data['height'])
        k = seed_i
        pos, en, al = data['pos'][:, k].astype(np.float32), data['energy'][:, k].astype(np.float32), data['alive'][:, k]
        hd = data['heading'][:, k].astype(np.float32)
        fit = data['fitness'][k]
        best = int(np.argmax(fit))
        cap = float(data['gut_cap'])
        ti = min(int(t), T - 1)

        for x in range(0, W, 60):
            pygame.draw.line(screen, GRID, (x, 0), (x, H))
        for y in range(0, H, 60):
            pygame.draw.line(screen, GRID, (0, y), (W, y))
        fp, fa = data['food'][ti, k].astype(np.float32), data['falive'][ti, k]
        for x, y in fp[fa]:
            screen.fill(FOOD, (int(x * sx) - 1, int(y * sy) - 1, 3, 3))

        layer.fill((0, 0, 0, 0))
        if trails:                                     # best worm's path (break at screen wrap)
            tr = [(float(a), float(b)) for a, b in pos[max(0, ti - 150):ti + 1, best] * (sx, sy)]
            for a, b in zip(tr[:-1], tr[1:]):
                if abs(a[0] - b[0]) < W / 2 and abs(a[1] - b[1]) < H / 2:
                    pygame.draw.line(layer, (255, 255, 255, 90), a, b, 2)
        for i in range(pos.shape[1]):
            x, y = float(pos[ti, i, 0] * sx), float(pos[ti, i, 1] * sy)
            if not al[ti, i]:
                pygame.draw.line(layer, (110, 110, 110, 120), (x - 3, y - 3), (x + 3, y + 3), 1)
                pygame.draw.line(layer, (110, 110, 110, 120), (x - 3, y + 3), (x + 3, y - 3), 1)
                continue
            c = energy_colour(en[ti, i] / cap)
            pygame.draw.circle(layer, c + (150,), (x, y), 4)
            h = float(hd[ti, i])
            pygame.draw.line(layer, c + (200,), (x, y), (x + 7 * np.cos(h), y + 7 * np.sin(h)), 1)
        npred = int(data['predators']) if 'predators' in data else 0
        for q in range(npred):                         # predators: red triangles
            qx, qy = float(data['pred'][ti, k, q, 0] * sx), float(data['pred'][ti, k, q, 1] * sy)
            pygame.draw.polygon(layer, (230, 50, 60, 235), [(qx, qy - 8), (qx - 7, qy + 6), (qx + 7, qy + 6)])
        if al[ti, best]:
            pygame.draw.circle(layer, (255, 255, 255, 230), (float(pos[ti, best, 0] * sx), float(pos[ti, best, 1] * sy)), 8, 2)
        screen.blit(layer, (0, 0))

        # panel
        px = W + 16
        pygame.draw.rect(screen, PANEL_BG, (W, 0, PANEL, H))
        lines = [(big, f"{str(data['cond'])}"), (font, ''),
                 (big, f"generation {int(data['gen'])}"),
                 (font, f"seed {int(data['seeds'][k])}   ({k + 1}/{len(data['seeds'])}, left/right)"),
                 (font, f"tick {ti + 1}/{T}   speed x{speed}{'  PAUSED' if paused else ''}"),
                 (font, f"alive {int(al[ti].sum())}/{al.shape[1]}   food {int(fa.sum())}/{len(fa)}"),
                 (font, f"best fitness {fit.max():.2f}   mean {fit.mean():.2f}")]
        y = 14
        for f_, s in lines:
            screen.blit(f_.render(s, True, TXT), (px, y)); y += 24 if f_ is big else 19
        # fitness curve
        hist = data['history']
        gx, gy, gw, gh = px, 200, PANEL - 32, 170
        pygame.draw.rect(screen, BG, (gx, gy, gw, gh))
        screen.blit(font.render('fitness per generation', True, DIM), (gx, gy - 20))
        if hist.shape[1] > 1:
            lo, hi = float(hist.min()), float(hist.max()) + 1e-6
            def curve(v, col, wdt):
                pts = [(gx + gw * i / (len(v) - 1), float(gy + gh - gh * (val - lo) / (hi - lo))) for i, val in enumerate(v)]
                pygame.draw.lines(screen, col, False, pts, wdt)
            curve(hist.mean(0), (120, 125, 140), 2)
            curve(hist[k], (90, 200, 255), 2)
            screen.blit(font.render(f'{hi:.2f}', True, DIM), (gx + 2, gy + 2))
            screen.blit(font.render(f'{lo:.2f}', True, DIM), (gx + 2, gy + gh - 18))
        screen.blit(font.render('blue: this seed   grey: all seeds', True, DIM), (gx, gy + gh + 6))
        # colour key
        ky = gy + gh + 40
        screen.blit(font.render('worm energy', True, DIM), (gx, ky))
        for i in range(gw):
            pygame.draw.line(screen, energy_colour(i / gw), (gx + i, ky + 20), (gx + i, ky + 32))
        screen.blit(font.render('starving', True, DIM), (gx, ky + 36))
        screen.blit(font.render('full', True, DIM), (gx + gw - 32, ky + 36))
        screen.blit(font.render('space pause  T trails  C condition', True, DIM), (gx, H - 26))

        pygame.display.flip()
        if not paused:
            t = min(t + speed, T - 1)
        snap = os.environ.get('VIEWER_SNAPSHOT')          # testing: save one frame at tick N and quit
        if snap and t >= int(os.environ.get('VIEWER_SNAPSHOT_TICK', 400)):
            pygame.image.save(screen, snap); pygame.quit(); return
        clock.tick(60)


if __name__ == '__main__':
    main()
