"""GPU (PyTorch) port of sim.py: same world, brains, evolution and tests, but every seed of a condition
evolves at once on the 3080 (seeds x population x 3 arenas = thousands of worms per step).
Not number-for-number identical to sim.py (different random streams, float32) -> compare statistically.

2nd EXPERIMENT (the toy brain; "Main Experiment" is now the connectome brain, ecosim/step20.py).
Usage: python sim_gpu.py [seeds] [gens] [conds comma-list or 'all'] [--fair] [--resume RESULTS.json] [--until HH:MM]
                          [--from-gen G [--as NAME] [--seed S]]
  Checkpoints: the whole population of every lineage is saved every 50 generations to checkpoints/. An interrupted run
  RESUMES from its latest checkpoint automatically (finished brain types are skipped as before).
  --from-gen G : BRANCH a new run from generation G of the same run (same settings), e.g. a Lenski-style replay;
                 --seed S gives it new luck (otherwise it repeats exactly).
  --cross F --groups K : INTERBREEDING. A fraction F of each lineage's children are crosses with elites of other
                 lineages in the same group (K groups; e.g. 30 lineages, --groups 10 = 10 independent groups of 3).
                 Output name gets _cross<F>_g<K>. Analyse per GROUP (group means), not per lineage.
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

FAIR = False        # set by --fair: scale init by fan-in and mutation by genome size (see below)
REF = dict(smell=1, H=8, plastic=0)   # the 8-neuron brain is the reference size


def init_scale(c):
    """Per-gene standard deviation of the starting genome. Original: 0.5 everywhere.
    Fair: recurrent weights scaled so every brain size starts with the same total recurrent input as the 8-neuron
    brain (0.5 * sqrt(8 / H)); plastic 'alpha' weights the same way. Everything else keeps 0.5."""
    L = glen(c)
    if not FAIR:
        return torch.full((L,), 0.5, device=DEV)
    sc, i = [], 0
    for n, sh in shapes(c):
        k = int(np.prod(sh))
        v = 0.5 * (REF["H"] / c["H"]) ** 0.5 if n in ("Wrec", "alpha") else 0.5
        sc.append(torch.full((k,), v, device=DEV)); i += k
    return torch.cat(sc)


def mut_sigma(c):
    """Per-gene mutation size. Original: 0.1 for every brain. Fair: 0.1 * sqrt(L_ref / L), so the TOTAL change per
    child (length of the mutation vector) is the same for every brain size."""
    return 0.1 * (glen(REF) / glen(c)) ** 0.5 if FAIR else 0.1


CKPT_EVERY = 50          # save the WHOLE population of every lineage every 50 generations (checkpoints/)


CROSS = 0.0             # fraction of each lineage's non-elite children made by crossing with ANOTHER lineage's elite
DEADLINE = None         # --until HH:MM: at this clock time save a checkpoint and stop cleanly (re-run the same command to finish)
GROUPS = 0              # lineages interbreed only inside their group (0 = no grouping: any lineage with any other)


def evolve(c, S, gens, gen, pop=48, elite=8, reps=3, init=None, ckpt=None, start=None):
    """All S lineages (seeds) at once.
    init: optional (S, L) starting champions (continuation): each lineage starts as its champion + pop-1 mutants of it.
    Tracks, for every individual: its gen-0 ANCESTOR (which of the 48 starting genomes it descends from), the number of
    MUTATION EVENTS on its line of descent (one per child birth; elites copied unchanged add none) and the total SIZE
    of those changes (sum of mutation vector lengths).
    ckpt: file-name prefix for checkpoints (Path); start: a checkpoint dict to continue from (resume / branch).
    INTERBREEDING (CROSS > 0): each generation, a fraction CROSS of every lineage's children are crosses: each gene
    comes with chance 1/2 from the lineage's own elite parent, otherwise from a random elite of another lineage in the
    same group (GROUPS groups of S/GROUPS lineages; groups never mix, so each group is an independent replicate).
    Crosses are then mutated like any child. Their ancestor label stays the own-lineage parent's.
    Returns dict: best (S, L), curve (S, gens), and for the best: nmut, mutsize, ancestor share of the final population."""
    L = glen(c)
    sig = mut_sigma(c)
    if init is None:
        G = init_scale(c) * torch.randn(S, pop, L, generator=gen, device=DEV)
        nmut = torch.zeros(S, pop, device=DEV); msize = torch.zeros(S, pop, device=DEV)
    else:
        G = init.to(DEV)[:, None].repeat(1, pop, 1)
        d = sig * torch.randn(S, pop - 1, L, generator=gen, device=DEV)
        G[:, 1:] += d
        nmut = torch.zeros(S, pop, device=DEV); nmut[:, 1:] = 1
        msize = torch.zeros(S, pop, device=DEV); msize[:, 1:] = d.norm(dim=-1)
    anc = torch.arange(pop, device=DEV)[None].repeat(S, 1)
    curve = torch.zeros(S, gens); g0 = 0
    if start is not None:                                          # resume / branch from a saved generation
        G, nmut, msize, anc = (start[k].to(DEV) for k in ("G", "nmut", "msize", "anc"))
        g0 = start["g"]; curve[:, :g0] = start["curve"][:, :g0]
        if start.get("rng") is not None:
            gen.set_state(start["rng"])
        log(f"  continuing from generation {g0}")
    for g in range(g0, gens):
        if DEADLINE is not None and time.time() >= DEADLINE and ckpt is not None:   # --until: stop cleanly, resumable
            ckpt.parent.mkdir(exist_ok=True)
            torch.save(dict(g=g, G=G.cpu(), nmut=nmut.cpu(), msize=msize.cpu(), anc=anc.cpu(), curve=curve.clone(),
                            rng=gen.get_state()), f"{ckpt}_g{g}.pt")
            log(f"  DEADLINE reached at generation {g}: checkpoint saved. Run the same command again to finish.")
            log("STOPPED_AT_DEADLINE"); sys.exit(0)
        if ckpt is not None and g > 0 and g % CKPT_EVERY == 0:
            ckpt.parent.mkdir(exist_ok=True)
            torch.save(dict(g=g, G=G.cpu(), nmut=nmut.cpu(), msize=msize.cpu(), anc=anc.cpu(), curve=curve.clone(),
                            rng=gen.get_state()), f"{ckpt}_g{g}.pt")
        pt = arenas(S * reps, NPATCH, gen)                           # one arena per seed per rep, shared by its pop
        pt = pt.view(S, reps, 1, NPATCH, 2).expand(S, reps, pop, NPATCH, 2).reshape(-1, NPATCH, 2)
        Gx = G[:, None].expand(S, reps, pop, L).reshape(-1, L)
        f = run(Gx, c, pt, gen).view(S, reps, pop).mean(1)          # (S, pop)
        curve[:, g] = f.mean(1).cpu()
        idx = torch.argsort(-f, 1)[:, :elite]
        E = torch.gather(G, 1, idx[:, :, None].expand(S, elite, L))
        eN, eS, eA = (torch.gather(x, 1, idx) for x in (nmut, msize, anc))
        par = torch.randint(0, elite, (S, pop - elite), generator=gen, device=DEV)
        d = sig * torch.randn(S, pop - elite, L, generator=gen, device=DEV)
        kids = torch.gather(E, 1, par[:, :, None].expand(S, pop - elite, L))
        if CROSS > 0 and S > 1:                                     # interbreed with other successful lineages
            n_x = int(round(CROSS * (pop - elite)))
            gsz = S // GROUPS if GROUPS else S
            grp = torch.arange(S, device=DEV) // gsz
            # partner lineage: another lineage of the same group, picked at random for every cross child
            off = torch.randint(1, max(gsz, 2), (S, n_x), generator=gen, device=DEV)
            mate_lin = grp[:, None] * gsz + ((torch.arange(S, device=DEV)[:, None] % gsz) + off) % gsz
            mate_el = torch.randint(0, elite, (S, n_x), generator=gen, device=DEV)
            mates = E[mate_lin, mate_el]                            # (S, n_x, L)
            mask = torch.rand(S, n_x, L, generator=gen, device=DEV) < 0.5
            kids[:, :n_x] = torch.where(mask, mates, kids[:, :n_x])
        kids = kids + d
        G = torch.cat([E, kids], 1)
        nmut = torch.cat([eN, torch.gather(eN, 1, par) + 1], 1)
        msize = torch.cat([eS, torch.gather(eS, 1, par) + d.norm(dim=-1)], 1)
        anc = torch.cat([eA, torch.gather(eA, 1, par)], 1)
        if g % 25 == 0 or g == gens - 1:
            log(f"  gen {g:3d}  mean food {curve[:, g].mean():6.1f}  (seed range {curve[:, g].min():.1f}-{curve[:, g].max():.1f})")
    # final pick: best of the elite over 10 arenas
    E = G[:, :elite]; reps = 10
    pt = arenas(S * reps, NPATCH, gen).view(S, reps, 1, NPATCH, 2).expand(S, reps, elite, NPATCH, 2).reshape(-1, NPATCH, 2)
    f = run(E[:, None].expand(S, reps, elite, L).reshape(-1, L), c, pt, gen).view(S, reps, elite).mean(1)
    j = f.argmax(1); ar = torch.arange(S, device=DEV)
    best_anc = anc[ar, j]
    share = (anc == best_anc[:, None]).float().mean(1)               # reproductive success of the best's founder line
    variety = G.var(1).mean(1)                                      # population variety: mean gene variance per lineage
    return dict(best=E[ar, j], curve=curve, nmut=nmut[ar, j].cpu(), mutsize=msize[ar, j].cpu(), share=share.cpu(),
                variety=variety.cpu())


def combined_score(fair, share, curve, slope_window=100):
    """'Best' as chosen by the owner (2026-11-13): COMBINED SCORE = reproductive success x fair-test score.
       reproductive success = share of the lineage's final population descended from the winner's gen-0 ancestor (0-1)
       fair-test score      = food eaten on 30 fresh unseen arenas (normal arena)
       tie-break            = slope of mean training food over the last `slope_window` generations (still rising?)
    Returns (score, slope) per lineage."""
    c = np.asarray(curve)[:, -slope_window:]
    slope = np.polyfit(np.arange(c.shape[1]), c.T, 1)[0] * 100
    return np.asarray(share) * np.asarray(fair), slope


def test(best, c, npatch, gen, n=30):
    """best (S, L) -> mean food per seed over n fresh arenas (S,)."""
    S, L = best.shape
    pt = arenas(S * n, npatch, gen)
    return run(best[:, None].expand(S, n, L).reshape(-1, L), c, pt, gen).view(S, n).mean(1)

if __name__ == "__main__":
    argv = sys.argv[1:]
    def opt(name, default=None):
        if name in argv:
            i = argv.index(name); v = argv[i + 1]; del argv[i:i + 2]; return v
        return default
    resume = opt("--resume")                       # continue from the champions saved in a results file
    from_gen = opt("--from-gen"); branch_as = opt("--as"); bseed = opt("--seed")   # branch from a checkpoint
    FAIR = "--fair" in argv; argv = [a for a in argv if a != "--fair"]
    CROSS = float(opt("--cross", 0.0)); GROUPS = int(opt("--groups", 0))
    until = opt("--until")                                 # e.g. 19:00 (today, local time; tomorrow if already past)
    if until and until != "none":
        import datetime as _dt
        u = until.replace(":", ""); hh, mm = int(u[:-2]), int(u[-2:]); now = _dt.datetime.now()   # 19:00 or 1900
        dl = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dl <= now:
            dl += _dt.timedelta(days=1)
        DEADLINE = dl.timestamp()
    cp = opt("--cross-pct")                                # same as --cross, as a whole-number percent (watcher form)
    if cp is not None:
        CROSS = int(cp) / 100
    S = int(argv[0]) if len(argv) > 0 else 30
    gens = int(argv[1]) if len(argv) > 1 else 300
    names = list(CONDS) if len(argv) <= 2 or argv[2] == "all" else argv[2].split(",")
    prev = json.loads(Path(resume).read_text()) if resume else None
    tag = f"_cont{gens}_from_{Path(resume).stem.replace('results_gpu_', '')}" if resume else ""
    if CROSS > 0:
        tag += f"_cross{CROSS:g}_g{GROUPS}"
    out = Path(f"results_gpu_{gens}g_{S}s{'_fair' if FAIR else ''}{tag}.json")
    src_out = out
    if from_gen:
        out = Path(f"results_gpu_{gens}g_{S}s{'_fair' if FAIR else ''}{tag}_{branch_as or 'from' + from_gen}.json")
    res = json.loads(out.read_text()) if out.exists() else {}
    log(f"{'FAIR mode (mutation scaled by genome size, init by brain size). ' if FAIR else ''}"
        f"{'CONTINUING from ' + resume + '. ' if resume else ''}start on {DEV} "
        f"({torch.cuda.get_device_name(0) if DEV.type == 'cuda' else 'cpu'}): {S} lineages x {gens} gens")
    gen = torch.Generator(device=DEV); gen.manual_seed(12345 + (7 if resume else 0))
    if "random_walk" not in res:
        c = dict(smell=1, H=8, plastic=0); z = torch.zeros(S, glen(c), device=DEV)
        res["random_walk"] = dict(normal=test(z, c, NPATCH, gen).tolist(), sparse=test(z, c, 2, gen).tolist())
    for name in names:
        if name in res:
            log(f"{name}: already done, skipped"); continue
        c = CONDS[name]; t0 = time.time(); log(f"{name}: evolving")
        gen.manual_seed(1000 + list(CONDS).index(name) + (500 if resume else 0))
        init = torch.tensor(prev[name]["genomes"], dtype=torch.float32)[:S] if prev else None
        ck = Path("checkpoints") / f"{out.stem}_{name.replace('+', '-')}"
        start = None
        if from_gen:                                               # BRANCH: start from the source run's checkpoint
            f = Path("checkpoints") / f"{src_out.stem}_{name.replace('+', '-')}_g{int(from_gen)}.pt"
            if not f.exists():
                log(f"{name}: no checkpoint {f.name}, skipped"); continue
            start = torch.load(f, weights_only=False)
            if bseed:
                start["rng"] = None; gen.manual_seed(int(bseed))
        else:                                                      # RESUME: latest checkpoint of this run, if any
            have = sorted(Path("checkpoints").glob(f"{ck.name}_g*.pt"), key=lambda p: int(p.stem.rsplit("_g", 1)[1])) if Path("checkpoints").exists() else []
            if have:
                start = torch.load(have[-1], weights_only=False); log(f"{name}: RESUMING from {have[-1].name}")
        ev = evolve(c, S, gens, gen, init=init, ckpt=ck, start=start)
        fair_n = test(ev["best"], c, NPATCH, gen); fair_s = test(ev["best"], c, 2, gen)
        score, slope = combined_score(fair_n.cpu().numpy(), ev["share"].numpy(), ev["curve"].numpy())
        prev_n = prev[name]["normal"][:S] if prev else None
        r = dict(normal=fair_n.tolist(), sparse=fair_s.tolist(), curves=ev["curve"].tolist(),
                 genomes=ev["best"].cpu().tolist(), sec=time.time() - t0,
                 mutations=ev["nmut"].tolist(), mutation_size=ev["mutsize"].tolist(), repro_share=ev["share"].tolist(),
                 combined=score.tolist(), slope_last100=slope.tolist(),
                 previous_normal=prev_n, mutations_counted_from=("continuation start" if prev else "generation 0"),
                 variety=ev["variety"].tolist(), cross=CROSS, groups=GROUPS, group_of_lineage=[(i // (S // GROUPS)) if GROUPS else 0 for i in range(S)])
        res[name] = r
        out.write_text(json.dumps(res))
        k = int(np.lexsort((-slope, -score))[0])
        log(f"{name}: normal {np.mean(r['normal']):6.1f}  sparse {np.mean(r['sparse']):6.1f}  "
            f"{'(was ' + format(np.mean(prev_n), '.1f') + ') ' if prev else ''}| best lineage {k}: combined {score[k]:.1f} "
            f"= share {r['repro_share'][k]:.2f} x fair {r['normal'][k]:.1f}, {int(r['mutations'][k])} mutations  ({r['sec']:.0f} s)")
    log("GPU_DONE")
