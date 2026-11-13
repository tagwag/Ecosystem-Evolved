"""Toy worm-brain lesion/upgrade experiment (CPU, numpy). Original from the 'neurogenesis' chat, 2026-11-12.

Brain = small recurrent net driving a constant-ish-speed worm in a 2D arena with
regrowing food patches. Same evolution budget per condition; compare food eaten.

Worm analogs:
  smell      -> AWA/AWC-like long-range volatile odor sensing (removable)
  taste      -> ASE-like short-range soluble taste (always kept)
  'frontal'  -> more interneurons (hidden units)
  'hippo'    -> adult-born hidden units with Hebbian-plastic synapses, born during life
Usage: python sim.py [seeds] [gens]      (run_cpu.py runs the same jobs in parallel)
"""
import numpy as np, json, sys, time

A = 100.0; STEPS = 500; NPATCH = 5; PR = 4.0; FMAX = 20.0
SIG_SMELL = 25.0; SIG_TASTE = 5.0; I = 5  # smell, dsmell, taste, dtaste, eating

CONDS = {
    "normal":               dict(smell=1, H=8,  plastic=0),
    "no_smell":             dict(smell=0, H=8,  plastic=0),
    "no_smell+frontal":     dict(smell=0, H=24, plastic=0),
    "no_smell+frontal+hippo": dict(smell=0, H=24, plastic=8),
    "normal+frontal+hippo": dict(smell=1, H=24, plastic=8),
}

def shapes(c):
    H, Pl = c["H"], c["plastic"]
    s = [("Win", (H, I)), ("Wrec", (H, H)), ("b", (H,)), ("Wout", (2, H)), ("bout", (2,))]
    if Pl: s += [("alpha", (H, H)), ("eta", (1,))]
    return s

def unpack(G, c):
    out, i = {}, 0
    for n, sh in shapes(c):
        k = int(np.prod(sh)); out[n] = G[:, i:i+k].reshape((G.shape[0],) + sh); i += k
    return out

def glen(c): return sum(int(np.prod(sh)) for _, sh in shapes(c))

def run(G, c, patches, rng):
    P = G.shape[0]; H, Pl = c["H"], c["plastic"]; p = unpack(G, c)
    xy = rng.uniform(10, 90, (P, 2)); hd = rng.uniform(0, 2*np.pi, P)
    food = np.full((P, len(patches)), FMAX); h = np.zeros((P, H))
    hebb = np.zeros((P, H, H)) if Pl else None
    alive = np.ones(H); born = {}
    if Pl:
        alive[H-Pl:] = 0
        for k in range(Pl): born[k * (STEPS // (Pl + 1)) + 20] = H - Pl + k
    prev = None; score = np.zeros(P)
    for t in range(STEPS):
        if t in born: alive[born[t]] = 1
        d2 = ((xy[:, None, :] - patches[None]) ** 2).sum(-1)
        frac = food / FMAX
        sm = (frac * np.exp(-d2 / (2*SIG_SMELL**2))).sum(1) * c["smell"]
        ta = (frac * np.exp(-d2 / (2*SIG_TASTE**2))).sum(1)
        sm += rng.normal(0, .01, P) * c["smell"]; ta += rng.normal(0, .01, P)
        cur = np.stack([sm, ta], 1)
        dcur = np.zeros_like(cur) if prev is None else (cur - prev) * 10
        prev = cur
        inside = d2 < PR**2
        eat = np.minimum(food, 0.5) * inside
        food -= eat; score += eat.sum(1)
        food += 0.003 * (FMAX - food)
        x = np.stack([sm, dcur[:, 0], ta, dcur[:, 1], (eat.sum(1) > 0).astype(float)], 1)
        W = p["Wrec"] + (p["alpha"] * hebb if Pl else 0)
        pre = h
        h = np.tanh(np.einsum("phi,pi->ph", p["Win"], x) + np.einsum("phj,pj->ph", W, h) + p["b"]) * alive
        if Pl:
            eta = np.tanh(p["eta"])[:, :, None]
            hebb = np.clip(0.98 * hebb + eta * h[:, :, None] * pre[:, None, :], -1, 1)
        o = np.tanh(np.einsum("pkh,ph->pk", p["Wout"], h) + p["bout"])
        hd += o[:, 0] * 0.6 + rng.normal(0, 0.1, P)
        sp = 0.3 + 0.7 * (o[:, 1] + 1) / 2
        xy += sp[:, None] * np.stack([np.cos(hd), np.sin(hd)], 1)
        for d in range(2):
            lo, hi = xy[:, d] < 0, xy[:, d] > A
            xy[lo, d] *= -1; xy[hi, d] = 2*A - xy[hi, d]
            hd[lo | hi] += np.pi
    return score

def arena(rng, n=NPATCH): return rng.uniform(10, 90, (n, 2))

def evolve(c, seed, gens, pop=48, elite=8, log=None):
    rng = np.random.default_rng(seed); L = glen(c)
    G = rng.normal(0, 0.5, (pop, L))
    for g in range(gens):
        f = np.mean([run(G, c, arena(rng), rng) for _ in range(3)], 0)
        if log is not None: log.append(float(f.mean()))
        idx = np.argsort(-f)[:elite]; E = G[idx]
        kids = E[rng.integers(0, elite, pop - elite)] + rng.normal(0, 0.1, (pop - elite, L))
        G = np.vstack([E, kids])
    f = np.mean([run(G[:elite], c, arena(rng), rng) for _ in range(10)], 0)
    return G[:elite][np.argmax(f)]

def test(best, c, seed, n, npatch):
    rng = np.random.default_rng(10_000 + seed)
    return float(np.mean([run(best[None], c, arena(rng, npatch), rng)[0] for _ in range(n)]))

if __name__ == "__main__":
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    gens = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    res = {}; t0 = time.time()
    rnd_c = dict(smell=1, H=8, plastic=0)
    rnd = np.zeros((1, glen(rnd_c)))
    res["random_walk"] = dict(normal=[test(rnd[0], rnd_c, s, 30, NPATCH) for s in range(seeds)],
                              sparse=[test(rnd[0], rnd_c, s, 30, 2) for s in range(seeds)])
    for name, c in CONDS.items():
        r = dict(normal=[], sparse=[])
        for s in range(seeds):
            b = evolve(c, s, gens)
            r["normal"].append(test(b, c, s, 30, NPATCH))
            r["sparse"].append(test(b, c, s, 30, 2))
        res[name] = r
        print(name, {k: round(float(np.mean(v)), 1) for k, v in r.items()},
              f"{time.time()-t0:.0f}s", flush=True)
    json.dump(res, open("results.json", "w"), indent=1)
