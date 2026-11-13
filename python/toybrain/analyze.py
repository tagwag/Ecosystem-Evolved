"""Analyze toy brain results: means, 95% CIs, pairwise tests, plateau check, chart.
Usage: python analyze.py results_gpu_300g_30s.json  -> <name>.png + <name>_stats.txt"""
import json, sys
import numpy as np
from scipy import stats
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

f = sys.argv[1]; r = json.load(open(f)); base = f.rsplit(".", 1)[0]
order = ["random_walk", "normal", "no_smell", "no_smell+frontal", "no_smell+frontal+hippo", "normal+frontal+hippo"]
order = [o for o in order if o in r]
out = []
def ci(x):
    x = np.asarray(x); m = x.mean(); h = stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0
    return m, h
out.append(f"{'brain':26s} {'normal arena':>18s} {'sparse arena':>18s}  plateau (last 50 gens slope /100 gens)")
for o in order:
    mn, hn = ci(r[o]["normal"]); ms, hs = ci(r[o]["sparse"])
    pl = ""
    if r[o].get("curves") and len(r[o]["curves"][0]) >= 100:
        c = np.array(r[o]["curves"]); last = c[:, -50:].mean(0)
        slope = np.polyfit(np.arange(50), last, 1)[0] * 100
        pl = f"{slope:+6.1f} food"
    out.append(f"{o:26s} {mn:8.1f} ± {hn:5.1f}    {ms:8.1f} ± {hs:5.1f}    {pl}")
out.append("\nComparisons (Welch t-test, independent seeds; Holm-corrected over the 4 planned tests):")
pairs = [("normal", "no_smell"), ("no_smell", "no_smell+frontal"), ("no_smell+frontal", "no_smell+frontal+hippo"),
         ("normal", "normal+frontal+hippo")]
for arena in ("normal", "sparse"):
    ps = []
    for a, b in pairs:
        t, p = stats.ttest_ind(r[a][arena], r[b][arena], equal_var=False); ps.append(p)
    order_p = np.argsort(ps); holm = np.empty(len(ps)); run = 0
    for k, i in enumerate(order_p):
        run = max(run, min(1, ps[i] * (len(ps) - k))); holm[i] = run
    for (a, b), p, h in zip(pairs, ps, holm):
        d = np.mean(r[b][arena]) - np.mean(r[a][arena])
        out.append(f"  [{arena:6s}] {b} vs {a}: {d:+6.1f} food  p={p:.2g}  Holm p={h:.2g}")
txt = "\n".join(out); print(txt); open(base + "_stats.txt", "w").write(txt)

fig, ax = plt.subplots(1, 2, figsize=(14, 5.5))
labels = [o.replace("+", "\n+") for o in order]; x = np.arange(len(order)); w = .38
for k, (arena, col) in enumerate((("normal", "#4C72B0"), ("sparse", "#DD8452"))):
    m = [ci(r[o][arena])[0] for o in order]; e = [ci(r[o][arena])[1] for o in order]
    ax[0].bar(x + (k - .5) * w, m, w, yerr=e, capsize=3, color=col, label=f"{arena} arena ({'5' if arena=='normal' else '2'} food patches)")
    for i, o in enumerate(order):
        ax[0].scatter(np.full(len(r[o][arena]), x[i] + (k - .5) * w), r[o][arena], s=6, color="k", alpha=.35, zorder=3)
ax[0].set_xticks(x); ax[0].set_xticklabels(labels, fontsize=8); ax[0].set_ylabel("food eaten per lifetime (unseen arenas)")
n = len(r[order[1]]["normal"]); ax[0].set_title(f"Fair test: {n} evolved lineages per brain, 95% CI; dots = lineages"); ax[0].legend()
for o in order[1:]:
    c = np.array(r[o]["curves"]); ax[1].plot(c.mean(0), label=o)
ax[1].set_xlabel("generation"); ax[1].set_ylabel("mean food in training (population)"); ax[1].set_title("Evolution curves (mean over lineages)"); ax[1].legend(fontsize=8)
plt.tight_layout(); plt.savefig(base + ".png", dpi=110)
