"""Genealogy tools: rebuild family trees from a run's birth/death log (results/<run>_tree/, written when
run.record_tree = true) and measure evolution through ancestry.

Usage:  python genealogy.py <run> <command> [options]
Commands (all take --world W; default 0. Worlds are numbered arm by arm: frozen 0..R-1, shadow R..2R-1, real 2R..3R-1;
          the script prints which arm/replicate a world is):
  summary              births, deaths, generations deep, branching and extinction rates, mutations per generation
  trace --uid U        the line of descent of worm U back to its founder: every ancestor, birth tick, mutation size
  living               the worms alive at the end, their founder family and generation depth (top 20 families)
  mrca                 most recent common ancestor of everyone alive at the end (when did today's population coalesce?)
  muller [--top K]     Muller plot: share of the population held by each founder family over time -> PNG
  family --uid U       one family: how many descendants of U were alive over time, + a drawing of its tree -> PNG
  fixation [--level 0.95]  when (if ever) one founder family took over (>= level of the population)
  report               all of the above for one world (summary, living, mrca, fixation, muller, tree of the top
                       family, trace of the deepest living worm) -> results/<run>_w<W>_genealogy.txt + PNGs
Worm ids: founders are 0..slots-1; every newborn gets the next number in its world.
Mutation sizes are stored x1e4 as integers in the log (converted back here).
"""
import argparse, glob, json
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def load(run, world):
    files = sorted(glob.glob(str(HERE / "results" / f"{run}_tree" / "*.npz")))
    if not files:
        raise SystemExit(f"no family-tree log for {run} (needs run.record_tree = true)")
    B = np.concatenate([np.load(f)["births"] for f in files]); D = np.concatenate([np.load(f)["deaths"] for f in files])
    meta = json.loads((HERE / "results" / f"{run}.json").read_text()) if (HERE / "results" / f"{run}.json").exists() else {}
    B = B[B[:, 1] == world]; D = D[D[:, 1] == world]
    cfg = meta.get("config", {}); slots = int(cfg.get("world", {}).get("slots", meta.get("slots", 640)))
    n0 = int(slots * float(cfg.get("world", {}).get("start_fill", 0.25)))
    R = int(meta.get("replicates", 1)); arms = meta.get("arms", ["?"])
    T = int(meta.get("ticks", int(B[:, 0].max()) if len(B) else 0))
    return dict(B=B, D=D, n0=n0, slots=slots, T=T, arm=arms[world // R] if R else "?", rep=world % R if R else 0,
                every=int(cfg.get("run", {}).get("every", 500)))


class Tree:
    def __init__(self, d):
        self.d = d
        self.parent, self.born, self.msize = {}, {}, {}
        for t, _, p, c, m in d["B"]:
            self.parent[int(c)] = int(p); self.born[int(c)] = int(t); self.msize[int(c)] = m / 1e4
        self.died = {int(u): int(t) for t, _, u in d["D"]}
        for f in range(d["n0"]):
            self.born.setdefault(f, 0)
        self._root, self._depth = {}, {}

    def root(self, u):
        path = []
        while u in self.parent and u not in self._root:
            path.append(u); u = self.parent[u]
        r = self._root.get(u, u)
        for x in path:
            self._root[x] = r
        return r

    def depth(self, u):
        path = []
        while u in self.parent and u not in self._depth:
            path.append(u); u = self.parent[u]
        dd = self._depth.get(u, 0)
        for x in reversed(path):
            dd += 1; self._depth[x] = dd
        return self._depth.get(path[0], dd) if path else dd

    def chain(self, u):
        out = [u]
        while u in self.parent:
            u = self.parent[u]; out.append(u)
        return out

    def living(self):
        return [u for u in self.born if u not in self.died]

    def alive_at(self, t):
        return [u for u, b in self.born.items() if b <= t and self.died.get(u, 10 ** 12) > t]


def header(d, run, world):
    print(f"{run}, world {world} = {d['arm']} arm, replicate {d['rep']} ({len(d['B'])} births, {len(d['D'])} deaths logged)")


def cmd_summary(tr, d):
    liv = tr.living(); deps = [tr.depth(u) for u in liv]
    T = max(d["T"], 1)
    roots = defaultdict(int)
    for u in liv:
        roots[tr.root(u)] += 1
    ms = [m for m in tr.msize.values()]
    print(f"  alive at end: {len(liv)} worms from {len(roots)} of {d['n0']} founder families")
    print(f"  generations deep (births on the line from founder): mean {np.mean(deps):.1f}, max {max(deps) if deps else 0}")
    print(f"  births {len(d['B'])}  ({1000 * len(d['B']) / T:.1f} per 1000 ticks)   deaths {len(d['D'])}  "
          f"({1000 * len(d['D']) / T:.1f} per 1000 ticks)")
    if ms:
        print(f"  mutation size per birth: mean {np.mean(ms):.3f} (0 = exact copy, e.g. frozen arm)")
    ext = d["n0"] - len(roots)
    print(f"  founder families extinct: {ext} of {d['n0']} ({1000 * ext / T:.2f} per 1000 ticks)")


def cmd_trace(tr, d, uid):
    ch = tr.chain(uid)
    print(f"  worm {uid}: {len(ch) - 1} births back to founder {ch[-1]}; total mutation size "
          f"{sum(tr.msize.get(u, 0) for u in ch):.3f}")
    print("  generation  worm id   born at tick   mutation size   died at")
    for i, u in enumerate(reversed(ch)):
        print(f"  {i:10d}  {u:8d}  {tr.born.get(u, 0):12d}   {tr.msize.get(u, 0):13.3f}   {tr.died.get(u, 'alive')}")


def cmd_living(tr, d):
    fam = defaultdict(list)
    for u in tr.living():
        fam[tr.root(u)].append(u)
    print("  founder  alive descendants  share   mean generations")
    tot = sum(len(v) for v in fam.values())
    for r, us in sorted(fam.items(), key=lambda kv: -len(kv[1]))[:20]:
        print(f"  {r:7d}  {len(us):17d}  {len(us) / tot:5.1%}   {np.mean([tr.depth(u) for u in us]):.1f}")


def cmd_mrca(tr, d):
    liv = tr.living()
    if not liv:
        print("  nobody alive"); return
    common = None
    for u in liv:
        s = set(tr.chain(u))
        common = s if common is None else common & s
        if not common:
            break
    if not common:
        fams = len({tr.root(u) for u in liv})
        print(f"  no single common ancestor: the living descend from {fams} different founders (not coalesced)")
        return
    m = max(common, key=lambda u: tr.depth(u))
    print(f"  most recent common ancestor of all {len(liv)} living worms: worm {m}, born at tick {tr.born.get(m, 0)}, "
          f"generation {tr.depth(m)} from founder {tr.root(m)}")
    print(f"  coalescence time: {d['T'] - tr.born.get(m, 0)} ticks before the end")


def cmd_muller(tr, d, run, world, top):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    ts = np.arange(0, d["T"] + 1, max(d["every"], d["T"] // 200 or 1))
    born = np.array(list(tr.born.values())); uids = np.array(list(tr.born.keys()))
    died = np.array([tr.died.get(int(u), 10 ** 12) for u in uids]); roots = np.array([tr.root(int(u)) for u in uids])
    fams = defaultdict(int)
    for r in roots[died > 10 ** 11]:
        fams[r] += 1
    keep = [r for r, _ in sorted(fams.items(), key=lambda kv: -kv[1])[:top]]
    M = np.zeros((len(keep) + 1, len(ts)))
    for j, t in enumerate(ts):
        al = (born <= t) & (died > t)
        for i, r in enumerate(keep):
            M[i, j] = (al & (roots == r)).sum()
        M[-1, j] = al.sum() - M[:-1, j].sum()
    share = M / M.sum(0).clip(min=1)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(ts, share, labels=[f"founder {r}" for r in keep] + ["all other families"], alpha=.9)
    ax.set_xlim(0, d["T"]); ax.set_ylim(0, 1); ax.set_xlabel("tick"); ax.set_ylabel("share of living worms")
    ax.set_title(f"Muller plot: {run}, world {world} ({d['arm']} arm) - which founder families take over")
    ax.legend(loc="upper left", fontsize=7, ncol=2); plt.tight_layout()
    out = HERE / "results" / f"{run}_w{world}_muller.png"; plt.savefig(out, dpi=110); print(f"  saved {out.name}")


def cmd_family(tr, d, run, world, uid, max_nodes=400):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    kids = defaultdict(list)
    for c, p in tr.parent.items():
        kids[p].append(c)
    desc, stack = [], [uid]
    while stack:
        u = stack.pop(); desc.append(u); stack.extend(kids.get(u, []))
    ts = np.arange(0, d["T"] + 1, max(d["every"], 1))
    size = [sum(1 for u in desc if tr.born.get(u, 0) <= t < tr.died.get(u, 10 ** 12)) for t in ts]
    print(f"  worm {uid}: {len(desc) - 1} descendants ever, {sum(1 for u in desc if u not in tr.died)} alive at the end")
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    ax[0].plot(ts, size); ax[0].set_xlabel("tick"); ax[0].set_ylabel("living members"); ax[0].set_title(f"family of worm {uid} over time")
    shown = set(desc[:max_nodes]); order = {}
    def place(u, y=[0]):
        ch = [c for c in kids.get(u, []) if c in shown]
        if not ch:
            order[u] = y[0]; y[0] += 1
        else:
            for c in ch:
                place(c)
            order[u] = np.mean([order[c] for c in ch])
    import sys; sys.setrecursionlimit(100000); place(uid)
    for u in shown:
        if u in tr.parent and tr.parent[u] in shown:
            p = tr.parent[u]
            ax[1].plot([tr.born.get(p, 0), tr.born.get(p, 0), tr.born[u]], [order[p], order[u], order[u]], lw=.6, color="#555")
        end = tr.died.get(u, d["T"])
        ax[1].plot([tr.born.get(u, 0), end], [order[u], order[u]], lw=1.2, color="#e07b39" if u not in tr.died else "#bbb")
    ax[1].set_xlabel("tick"); ax[1].set_yticks([]); ax[1].set_title(f"family tree (first {len(shown)} members; orange = alive at end)")
    plt.tight_layout(); out = HERE / "results" / f"{run}_w{world}_family{uid}.png"; plt.savefig(out, dpi=110); print(f"  saved {out.name}")


def cmd_fixation(tr, d, level):
    born = np.array(list(tr.born.values())); uids = list(tr.born.keys())
    died = np.array([tr.died.get(u, 10 ** 12) for u in uids]); roots = np.array([tr.root(u) for u in uids])
    for t in range(0, d["T"] + 1, max(d["every"], 1)):
        al = (born <= t) & (died > t)
        if al.sum() == 0:
            continue
        vals, cnt = np.unique(roots[al], return_counts=True)
        if cnt.max() / al.sum() >= level:
            print(f"  founder family {vals[cnt.argmax()]} reached {cnt.max() / al.sum():.0%} at tick {t}"); return
    print(f"  no founder family reached {level:.0%} during the run")


def cmd_report(tr, d, run, world):
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        header(d, run, world)
        print("\n## Summary"); cmd_summary(tr, d)
        print("\n## Biggest founder families alive at the end"); cmd_living(tr, d)
        print("\n## Most recent common ancestor"); cmd_mrca(tr, d)
        print("\n## Takeover (fixation)"); cmd_fixation(tr, d, 0.95); cmd_fixation(tr, d, 0.5)
        liv = tr.living()
        if liv:
            deep = max(liv, key=tr.depth)
            print(f"\n## Line of descent of the deepest living worm ({deep})"); cmd_trace(tr, d, deep)
            fam = defaultdict(int)
            for u in liv:
                fam[tr.root(u)] += 1
            top = max(fam, key=fam.get)
            print(f"\n## Top family (founder {top})"); cmd_family(tr, d, run, world, top)
        print("\n## Muller plot"); cmd_muller(tr, d, run, world, 10)
    out = HERE / "results" / f"{run}_w{world}_genealogy.txt"; out.write_text(buf.getvalue())
    print(buf.getvalue()); print(f"saved {out.name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run"); ap.add_argument("command", choices=["summary", "trace", "living", "mrca", "muller", "family", "fixation", "report"])
    ap.add_argument("--world", type=int, default=0); ap.add_argument("--uid", type=int)
    ap.add_argument("--top", type=int, default=10); ap.add_argument("--level", type=float, default=0.95)
    a = ap.parse_args()
    d = load(a.run, a.world); tr = Tree(d); header(d, a.run, a.world)
    if a.command in ("trace", "family") and a.uid is None:
        raise SystemExit("--uid needed (see `living` or `summary` for ids)")
    {"summary": lambda: cmd_summary(tr, d), "trace": lambda: cmd_trace(tr, d, a.uid), "living": lambda: cmd_living(tr, d),
     "mrca": lambda: cmd_mrca(tr, d), "muller": lambda: cmd_muller(tr, d, a.run, a.world, a.top),
     "family": lambda: cmd_family(tr, d, a.run, a.world, a.uid), "fixation": lambda: cmd_fixation(tr, d, a.level),
     "report": lambda: cmd_report(tr, d, a.run, a.world)}[a.command]()


if __name__ == "__main__":
    main()
