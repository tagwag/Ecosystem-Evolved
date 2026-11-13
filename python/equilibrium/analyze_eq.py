"""Analyze an equilibrium-world run (results/eq_*.json) -> chart + stats text.

Rules fixed BEFORE the first full run (2026-11-13):
  EQUILIBRIUM  the frozen arm's population stays within +-10 % of its own mean over the last 75 % of the run,
               in EVERY replicate world.
  ZERO POINT   the frozen arm's genetic distance from its founder is exactly 0 (sanity check: no mutation = no change).
  ADAPTATION   real vs shadow genetic distance, behaviour and eating rate at the end, paired by replicate
               (sign-flip permutation test, 2-sided). "Selection changes X" only if p < 0.05.

Usage: python analyze_eq.py results/eq_50000t_30s.json
"""
import json, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt


def signflip(d, n=20000, seed=0):
    d = np.asarray(d, float); rng = np.random.default_rng(seed)
    obs = abs(d.mean()); s = rng.choice([-1, 1], size=(n, len(d)))
    return float(((np.abs((s * d).mean(1)) >= obs - 1e-12).sum() + 1) / (n + 1))


def main(path):
    r = json.load(open(path)); R = r["replicates"]; ser = r["series"]
    t = np.array([s["t"] for s in ser])
    get = lambda k: np.array([s[k] for s in ser]).reshape(len(ser), 3, R)   # (time, arm, replicate)
    pop, gd, div, lin = get("pop"), get("gdist"), get("diversity"), get("lineages")
    eat, spd, turn, births = get("eat_rate"), get("speed"), get("turn"), get("births")
    out = [f"Equilibrium world: {R} replicates x 3 arms, {r['ticks']} ticks, founders: {r['founders']}\n"]
    late = t > 0.25 * t[-1]
    fz = pop[late, 0]; m = fz.mean(0); dev = np.abs(fz / m - 1).max(0)
    ok = bool((dev <= 0.10).all())
    out.append(f"EQUILIBRIUM rule (frozen within +-10% of its mean, last 75%, every replicate): {'PASS' if ok else 'FAIL'}")
    out.append(f"  frozen population mean {m.mean():.1f} (replicates {m.min():.1f}-{m.max():.1f}); "
               f"worst swing {dev.max() * 100:.1f}% (median {np.median(dev) * 100:.1f}%)")
    out.append(f"ZERO POINT (frozen genetic distance == 0): {'PASS' if gd[:, 0].max() == 0 else 'FAIL'} (max {gd[:, 0].max():.3g})")
    out.append(f"\nEnd of run, mean over replicates (frozen / shadow / real):")
    last = slice(-max(1, len(t) // 10), None)                                  # last 10 % of samples
    rows = [("population", pop), ("genetic distance from founder", gd), ("genetic diversity", div),
            ("founder lineages alive", lin), ("eating rate (food/worm/tick)", eat), ("speed", spd),
            ("turning", turn), ("births per sample", births)]
    for name, x in rows:
        e = x[last].mean(0)                                                   # (3, R)
        out.append(f"  {name:32s} {e[0].mean():9.4g} {e[1].mean():9.4g} {e[2].mean():9.4g}")
    out.append("\nADAPTATION = real minus shadow (paired by replicate, sign-flip test):")
    for name, x in rows[1:7]:
        e = x[last].mean(0); d = e[2] - e[1]
        out.append(f"  {name:32s} {d.mean():+9.4g}   real higher in {(d > 0).sum()}/{R}   p={signflip(d):.3g}")
    txt = "\n".join(out); print(txt)
    base = path.rsplit(".", 1)[0]; open(base + "_stats.txt", "w").write(txt)

    fig, ax = plt.subplots(2, 3, figsize=(16, 8.5)); ax = ax.ravel()
    cols = {"frozen": "#7f7f7f", "shadow": "#4C72B0", "real": "#DD8452"}
    for i, (name, x) in enumerate([("population", pop), ("genetic distance from founder", gd), ("genetic diversity", div),
                                   ("founder lineages alive", lin), ("eating rate (food/worm/tick)", eat), ("speed", spd)]):
        for k, arm in enumerate(r["arms"]):
            mu = x[:, k].mean(1); lo, hi = np.percentile(x[:, k], [10, 90], axis=1)
            ax[i].plot(t, mu, color=cols[arm], label=arm); ax[i].fill_between(t, lo, hi, color=cols[arm], alpha=.15)
        ax[i].set_title(name); ax[i].set_xlabel("tick")
    ax[0].legend(); fig.suptitle(f"Equilibrium world: {R} replicate worlds per arm (line = mean, band = 10-90% of replicates)")
    plt.tight_layout(); plt.savefig(base + ".png", dpi=105)


if __name__ == "__main__":
    main(sys.argv[1])
