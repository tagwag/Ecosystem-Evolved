"""GPU (PyTorch) port of sim.py: same world, brains, evolution and tests, but every seed of a condition
evolves at once on the 3080 (seeds x population x 3 arenas = thousands of worms per step).
Not number-for-number identical to sim.py (different random streams, float32) -> compare statistically.

Usage: python sim_gpu.py [seeds] [gens] [conds comma-list or 'all']
Writes results_gpu_<gens>g_<seeds>s.json (+ best genomes, learning curves) and a progress log run_gpu_log.txt.
SAFE TO INTERRUPT: each condition's results are saved when it finishes; a rerun skips finished conditions.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import torch

from sim import A, STEPS, NPATCH, PR, FMAX, SIG_SMELL, SIG_TASTE, I, CONDS, shapes, glen

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
LOG = Path("run_gpu_log.txt")

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")

def unpack(G, c):
    """G (..., L) -> dict of (..., *shape)."""
    out, i = {}, 0
    for n, sh in shapes(c):
        k = int(np.prod(sh)); out[n] = G[..., i:i + k].reshape(G.shape[:-1] + sh); i += k
    return out

@torch.no_grad()
def run(G, c, patches, gen):
    """G: (B, L) genomes, one worm each. patches: (B, NP, 2) arena per worm. Returns food eaten (B,)."""
    B = G.shape[0]; H, Pl = c["H"], c["plastic"]; p = unpack(G, c)
    u = lambda *s: torch.rand(*s, generator=gen, device=DEV)
    nrm = lambda *s: torch.randn(*s, generator=gen, device=DEV)
    xy = 10 + 80 * u(B, 2); hd = 2 * np.pi * u(B)
    food = torch.full(patches.shape[:2], FMAX, device=DEV); h = torch.zeros(B, H, device=DEV)
    hebb = torch.zeros(B, H, H, device=DEV) if Pl else None
    alive = torch.ones(H, device=DEV); born = {}
    if Pl:
        alive[H - Pl:] = 0
        for k in range(Pl): born[k * (STEPS // (Pl + 1)) + 20] = H - Pl + k
        eta = torch.tanh(p["eta"])[:, :, None]                       # (B,1,1)
    prev = None; score = torch.zeros(B, device=DEV); sm_on = float(c["smell"])
    for t in range(STEPS):
        if t in born: alive[born[t]] = 1
        d2 = ((xy[:, None, :] - patches) ** 2).sum(-1)               # (B, NP)
        frac = food / FMAX
        sm = (frac * torch.exp(-d2 / (2 * SIG_SMELL ** 2))).sum(1) * sm_on
        ta = (frac * torch.exp(-d2 / (2 * SIG_TASTE ** 2))).sum(1)
        sm = sm + 0.01 * nrm(B) * sm_on; ta = ta + 0.01 * nrm(B)
        cur = torch.stack([sm, ta], 1)
        dcur = torch.zeros_like(cur) if prev is None else (cur - prev) * 10
        prev = cur
        eat = torch.clamp(food, max=0.5) * (d2 < PR ** 2)
        food = food - eat; ate = eat.sum(1); score += ate
        food = food + 0.003 * (FMAX - food)
        x = torch.stack([sm, dcur[:, 0], ta, dcur[:, 1], (ate > 0).float()], 1)
        W = p["Wrec"] + p["alpha"] * hebb if Pl else p["Wrec"]
        pre = h
        h = torch.tanh(torch.einsum("bhi,bi->bh", p["Win"], x) + torch.einsum("bhj,bj->bh", W, h) + p["b"]) * alive
        if Pl:
            hebb = torch.clamp(0.98 * hebb + eta * h[:, :, None] * pre[:, None, :], -1, 1)
        o = torch.tanh(torch.einsum("bkh,bh->bk", p["Wout"], h) + p["bout"])
        hd = hd + o[:, 0] * 0.6 + 0.1 * nrm(B)
        sp = 0.3 + 0.7 * (o[:, 1] + 1) / 2
        xy = xy + sp[:, None] * torch.stack([torch.cos(hd), torch.sin(hd)], 1)
        lo, hi = xy < 0, xy > A                                      # reflect off walls
        xy = torch.where(lo, -xy, torch.where(hi, 2 * A - xy, xy))
        hd = hd + np.pi * (lo | hi).any(1).float()
    return score

def arenas(n, npatch, gen):
    return 10 + 80 * torch.rand(n, npatch, 2, generator=gen, device=DEV)

def evolve(c, S, gens, gen, pop=48, elite=8, reps=3):
    """All S seeds at once. Returns best genome per seed (S, L) and the mean-fitness curve per seed (S, gens)."""
    L = glen(c)
    G = 0.5 * torch.randn(S, pop, L, generator=gen, device=DEV)
    curve = torch.zeros(S, gens)
    for g in range(gens):
        pt = arenas(S * reps, NPATCH, gen)                           # one arena per seed per rep, shared by its pop
        pt = pt.view(S, reps, 1, NPATCH, 2).expand(S, reps, pop, NPATCH, 2).reshape(-1, NPATCH, 2)
        Gx = G[:, None].expand(S, reps, pop, L).reshape(-1, L)
        f = run(Gx, c, pt, gen).view(S, reps, pop).mean(1)          # (S, pop)
        curve[:, g] = f.mean(1).cpu()
        idx = torch.argsort(-f, 1)[:, :elite]
        E = torch.gather(G, 1, idx[:, :, None].expand(S, elite, L))
        par = torch.randint(0, elite, (S, pop - elite), generator=gen, device=DEV)
        kids = torch.gather(E, 1, par[:, :, None].expand(S, pop - elite, L)) + 0.1 * torch.randn(S, pop - elite, L, generator=gen, device=DEV)
        G = torch.cat([E, kids], 1)
        if g % 25 == 0 or g == gens - 1:
            log(f"  gen {g:3d}  mean food {curve[:, g].mean():6.1f}  (seed range {curve[:, g].min():.1f}-{curve[:, g].max():.1f})")
    # final pick: best of the elite over 10 arenas
    E = G[:, :elite]; reps = 10
    pt = arenas(S * reps, NPATCH, gen).view(S, reps, 1, NPATCH, 2).expand(S, reps, elite, NPATCH, 2).reshape(-1, NPATCH, 2)
    f = run(E[:, None].expand(S, reps, elite, L).reshape(-1, L), c, pt, gen).view(S, reps, elite).mean(1)
    best = E[torch.arange(S), f.argmax(1)]
    return best, curve

def test(best, c, npatch, gen, n=30):
    """best (S, L) -> mean food per seed over n fresh arenas (S,)."""
    S, L = best.shape
    pt = arenas(S * n, npatch, gen)
    return run(best[:, None].expand(S, n, L).reshape(-1, L), c, pt, gen).view(S, n).mean(1)

if __name__ == "__main__":
    S = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    gens = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    names = list(CONDS) if len(sys.argv) <= 3 or sys.argv[3] == "all" else sys.argv[3].split(",")
    out = Path(f"results_gpu_{gens}g_{S}s.json")
    res = json.loads(out.read_text()) if out.exists() else {}
    log(f"start on {DEV} ({torch.cuda.get_device_name(0) if DEV.type == 'cuda' else 'cpu'}): {S} seeds x {gens} gens")
    gen = torch.Generator(device=DEV); gen.manual_seed(12345)
    if "random_walk" not in res:
        c = dict(smell=1, H=8, plastic=0); z = torch.zeros(S, glen(c), device=DEV)
        res["random_walk"] = dict(normal=test(z, c, NPATCH, gen).tolist(), sparse=test(z, c, 2, gen).tolist())
    for name in names:
        if name in res:
            log(f"{name}: already done, skipped"); continue
        c = CONDS[name]; t0 = time.time(); log(f"{name}: evolving")
        gen.manual_seed(1000 + list(CONDS).index(name))
        best, curve = evolve(c, S, gens, gen)
        r = dict(normal=test(best, c, NPATCH, gen).tolist(), sparse=test(best, c, 2, gen).tolist(),
                 curves=curve.tolist(), genomes=best.cpu().tolist(), sec=time.time() - t0)
        res[name] = r
        out.write_text(json.dumps(res))
        log(f"{name}: normal {np.mean(r['normal']):6.1f}  sparse {np.mean(r['sparse']):6.1f}  ({r['sec']:.0f} s)")
    log("GPU_DONE")
