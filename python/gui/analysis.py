"""Analysis tools for the GUI's Analysis page: the statistics a published study would report, for any results file.

WHAT IT READS (adapters turn every format into one shape, see `load`):
  engine      engine/results/<name>.json          arms (frozen/shadow/real) x replicates, time series of ~50 measures
  equilibrium equilibrium/results/eq_*.json        same layout as the engine
  toybrain    toybrain/results_gpu_*.json          2nd Experiment: brain types x lineages; fair-test scores, mutations,
                                                   reproductive share, combined score, training curves
  step20      results/step20_stats.json            Main Experiment: 4 arms x 16 seeds, yardstick skill per checkpoint
  generic     results/step*_*.json                 older connectome steps: any {group: {measure: [numbers]}} found
The common shape ("dataset"):
  groups   {group: {measure: [value per replicate]}}            values at the chosen time point (default: the end)
  series   {group: {measure: [[value per replicate] per time]}} when the format has time courses
  times    [t, ...]                                              the time axis of the series (ticks / generations)
  paired   True when replicate i is the same seed/world in every group (engine, equilibrium, step20), so paired
           tests are valid; False for independent groups (toybrain lineages are separately seeded per brain type)

WHAT IT COMPUTES (`analyse`) - each line says what a reader of a paper would look for:
  describe      n, mean, SD, SEM, median, IQR, min/max, 95 % CI of the mean (t-based and bootstrap)
  compare       every selected group vs the reference group: difference with bootstrap 95 % CI; effect size
                (Hedges g, or Cohen dz for paired data) with its CI; Welch t-test + Mann-Whitney U (independent) or
                paired t-test + Wilcoxon signed-rank + sign-flip permutation (paired); p-values adjusted for the
                number of comparisons (Holm, the default, or Benjamini-Hochberg false discovery rate); normality check
                (Shapiro-Wilk) to say which test to trust; achieved power and the n needed for 80 % power
  omnibus       one-way ANOVA (Welch's version if spreads differ) + Kruskal-Wallis across all selected groups
  trend         per replicate: slope over the last third of the time course (units per 100 time steps), mean slope
                with 95 % CI and sign-flip p -> "still rising" / "plateau" / "falling"
  correlations  Spearman rank correlations between all measures inside one group, BH-adjusted p-values
  text          an auto-written Methods + Results paragraph with every number, ready to paste into a report
  csv           tidy table (file, group, replicate, measure, value) for Excel / R / Python
Nothing here needs the GPU. numpy + scipy only.
"""
import csv
import io
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

PY = Path(__file__).resolve().parent.parent
SOURCES = {"engine": PY / "engine" / "results", "equilibrium": PY / "equilibrium" / "results",
           "toybrain": PY / "toybrain", "results": PY / "results"}
LABELS = {"engine": "Factor engine", "equilibrium": "Equilibrium world", "toybrain": "2nd Experiment (toy brain)",
          "results": "Connectome steps (Main Experiment = step20)"}
_CACHE = {}



# ------------------------------------------------------------------------------------------------ files + adapters
def list_files():
    """Every analysable results file, newest first, with the folder it came from."""
    out = []
    for key, d in SOURCES.items():
        if not d.exists():
            continue
        for p in d.glob("*.json"):
            if key == "toybrain" and not p.name.startswith("results_"):
                continue
            out.append(dict(id=f"{key}/{p.name}", source=LABELS[key], name=p.stem, mtime=p.stat().st_mtime,
                            mb=round(p.stat().st_size / 1e6, 2)))
    return sorted(out, key=lambda r: -r["mtime"])


def _path(fid):
    key, name = fid.split("/", 1)
    p = (SOURCES[key] / Path(name).name).resolve()
    if key not in SOURCES or p.parent != SOURCES[key].resolve() or not p.exists():
        raise ValueError(f"unknown file {fid}")
    return p


def _num_list(v, n=None):
    return isinstance(v, list) and len(v) > 0 and (n is None or len(v) == n) and \
        all(isinstance(x, (int, float)) or x is None for x in v)


def load(fid):
    """-> dataset (see module docstring). Cached by file id + modification time."""
    p = _path(fid)
    key = (fid, p.stat().st_mtime)
    if key in _CACHE:
        return _CACHE[key]
    d = json.loads(p.read_text())
    kind = fid.split("/")[0]
    if isinstance(d, dict) and "series" in d and "arms" in d and "replicates" in d:
        ds = _from_arms_series(d)
    elif kind == "toybrain":
        ds = _from_toybrain(d)
    elif isinstance(d, dict) and "yardstick" in d and "g_end" in d:
        ds = _from_step20(d)
    else:
        ds = _from_generic(d)
    ds["file"] = fid
    _CACHE.clear(); _CACHE[key] = ds
    return ds


def _from_arms_series(d):
    arms, R, ser = d["arms"], int(d["replicates"]), d["series"]
    A = len(arms)
    measures = [k for k, v in ser[-1].items() if k != "t" and _num_list(v, A * R)]
    times = [m.get("t", i) for i, m in enumerate(ser)]
    series = {a: {} for a in arms}
    for k in measures:
        arr = np.array([[np.nan if x is None else x for x in m[k]] if _num_list(m.get(k), A * R) else [np.nan] * (A * R)
                        for m in ser], float)                                     # (T, A*R), arm-major
        for i, a in enumerate(arms):
            series[a][k] = arr[:, i * R:(i + 1) * R]
    return dict(kind="arms x replicates over time", groups_order=arms, measures=measures, times=times,
                series=series, paired=True, unit_time="tick", note="replicate i = the same world (seed) in every arm")


def _from_toybrain(d):
    groups = [k for k in d if isinstance(d[k], dict) and k != "random_walk"]
    per = ("normal", "sparse", "mutations", "mutation_size", "repro_share", "combined", "slope_last100", "variety")
    names = {"normal": "fair test, normal arena", "sparse": "fair test, sparse arena"}
    vals, series, measures = {}, {}, []
    for g in groups:
        vals[g] = {}
        for k in per:
            if _num_list(d[g].get(k)):
                vals[g][names.get(k, k)] = np.array(d[g][k], float)
                if names.get(k, k) not in measures:
                    measures.append(names.get(k, k))
        c = d[g].get("curves")
        if isinstance(c, list) and c and isinstance(c[0], list):
            series[g] = {"training food (mean of population)": np.array(c, float).T}      # (T, lineages)
    if "random_walk" in d:
        vals["random_walk"] = {names[k]: np.array(d["random_walk"][k], float) for k in ("normal", "sparse") if k in d["random_walk"]}
        groups.append("random_walk")
    T = max((s["training food (mean of population)"].shape[0] for s in series.values()), default=0)
    if series:
        measures.append("training food (mean of population)")
    return dict(kind="brain types x lineages", groups_order=groups, measures=measures, values=vals, series=series,
                times=list(range(T)), paired=False, unit_time="generation",
                note="lineages are independent per brain type (unpaired tests)")


def _from_step20(d):
    arms = list(d["yardstick"])
    cks = [int(c) for c in d["checkpoints"]]
    first = d["yardstick"][arms[0]][str(cks[-1])]
    measures = [k for k, v in first.items() if _num_list(v)]
    series = {a: {k: np.array([d["yardstick"][a][str(c)][k] for c in cks], float) for k in measures} for a in arms}
    return dict(kind="Main Experiment arms x seeds (yardstick at checkpoints)", groups_order=arms, measures=measures,
                times=cks, series=series, paired=True, unit_time="generation",
                note="the same 16 seeds in every arm (paired)")


AXIS_KEYS = {"checkpoints", "gens", "generations", "t", "time", "times", "ticks", "x"}


def _from_generic(d):
    """Older step files: collect {group: {measure: list of numbers | list of lists}} wherever found (two levels)."""
    vals, series, measures = {}, {}, []
    if isinstance(d, dict):
        for g, v in d.items():
            if not isinstance(v, dict):
                continue
            for k, x in v.items():
                if k in AXIS_KEYS:                                   # time axes, not measurements
                    continue
                if _num_list(x) and len(x) >= 3:
                    vals.setdefault(g, {})[k] = np.array([np.nan if y is None else y for y in x], float)
                elif isinstance(x, list) and x and all(_num_list(r) for r in x) and len({len(r) for r in x}) == 1:
                    series.setdefault(g, {})[k] = np.array(x, float).T            # rows = replicates -> (T, R)
                else:
                    continue
                if k not in measures:
                    measures.append(k)
    groups = list(dict.fromkeys(list(vals) + list(series)))
    if not groups:
        raise ValueError("this file has no per-replicate numbers to analyse (it may hold summary statistics only)")
    T = max((a.shape[0] for s in series.values() for a in s.values()), default=0)
    return dict(kind="groups (generic reader)", groups_order=groups, measures=measures, values=vals, series=series,
                times=list(range(T)), paired=False, unit_time="step",
                note="read by the generic reader; check that replicates are what you expect")


def values_at(ds, measure, ti=-1):
    """{group: values per replicate} for a measure, at time index ti of the series (default end) or its plain values."""
    out = {}
    for g in ds["groups_order"]:
        s = ds.get("series", {}).get(g, {}).get(measure)
        if s is not None and len(s):
            out[g] = np.asarray(s[ti if ti < len(s) else -1], float)
        elif measure in ds.get("values", {}).get(g, {}):
            out[g] = np.asarray(ds["values"][g][measure], float)
    return out


# ------------------------------------------------------------------------------------------------ statistics
def _ci_t(x, level=0.95):
    x = x[~np.isnan(x)]; n = len(x)
    if n < 2:
        return [float("nan")] * 2
    h = stats.t.ppf(0.5 + level / 2, n - 1) * x.std(ddof=1) / math.sqrt(n)
    return [float(x.mean() - h), float(x.mean() + h)]


def _boot(f, *xs, n=5000, seed=0, paired=False):
    rng = np.random.default_rng(seed); out = np.empty(n)
    if paired:
        m = len(xs[0])
        for i in range(n):
            idx = rng.integers(0, m, m); out[i] = f(*[x[idx] for x in xs])
    else:
        for i in range(n):
            out[i] = f(*[x[rng.integers(0, len(x), len(x))] for x in xs])
    return [float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))]


def describe(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    if n == 0:
        return dict(n=0)
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    return dict(n=n, mean=float(x.mean()), sd=float(x.std(ddof=1)) if n > 1 else 0.0,
                sem=float(x.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0, median=float(med), q1=float(q1), q3=float(q3),
                min=float(x.min()), max=float(x.max()), ci95_t=_ci_t(x),
                ci95_boot=_boot(np.mean, x) if n > 2 else [float("nan")] * 2,
                shapiro_p=float(stats.shapiro(x).pvalue) if 3 <= n <= 5000 and x.std() > 0 else None)


def hedges_g(a, b):
    na, nb = len(a), len(b)
    sp = math.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)) if na + nb > 2 else float("nan")
    d = (a.mean() - b.mean()) / sp if sp > 0 else 0.0
    return float(d * (1 - 3 / (4 * (na + nb) - 9)))


def signflip(d, n=20000, seed=0):
    d = d[~np.isnan(d)]
    if len(d) == 0 or np.allclose(d, 0):
        return 1.0
    rng = np.random.default_rng(seed); fl = rng.choice([-1.0, 1.0], size=(n, len(d)))
    return float(((np.abs((fl * d).mean(1)) >= abs(d.mean()) - 1e-12).sum() + 1) / (n + 1))


def power_t(effect, n, paired, alpha=0.05):
    """Achieved power of a two-sided t-test for a standardized effect, and n for 80 % power (noncentral t)."""
    if not np.isfinite(effect) or effect == 0 or n < 2:
        return None, None
    def pw(m):
        df = m - 1 if paired else 2 * m - 2
        nc = abs(effect) * (math.sqrt(m) if paired else math.sqrt(m / 2))
        tc = stats.t.ppf(1 - alpha / 2, df)
        p = 1 - stats.nct.cdf(tc, df, nc) + stats.nct.cdf(-tc, df, nc)
        if not np.isfinite(p):                       # huge effects overflow the noncentral t: use the normal approx.
            p = stats.norm.sf(tc - nc) + stats.norm.cdf(-tc - nc)
        return float(min(1.0, p))
    need = next((m for m in range(3, 5001) if pw(m) >= 0.8), None)
    return pw(n), need


def compare(a, b, paired):
    """Group a vs reference b. Paired = replicate i of a and b share a seed/world."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    r = dict(paired=bool(paired))
    if paired:
        ok = ~np.isnan(a) & ~np.isnan(b); a, b = a[ok], b[ok]; d = a - b
        r.update(n=int(len(d)), diff=float(d.mean()), diff_ci95=_boot(np.mean, d),
                 wins=int((d > 0).sum()), losses=int((d < 0).sum()))
        sd = d.std(ddof=1) if len(d) > 1 else 0
        r["effect"] = float(d.mean() / sd) if sd > 0 else 0.0; r["effect_name"] = "Cohen dz (paired)"
        r["effect_ci95"] = _boot(lambda x: x.mean() / x.std(ddof=1) if x.std(ddof=1) > 0 else 0.0, d)
        r["tests"] = {"paired t-test": float(stats.ttest_rel(a, b).pvalue) if sd > 0 else 1.0,
                      "Wilcoxon signed-rank": float(stats.wilcoxon(d).pvalue) if np.any(d != 0) else 1.0,
                      "sign-flip permutation": signflip(d)}
        r["normality_p"] = float(stats.shapiro(d).pvalue) if 3 <= len(d) and sd > 0 else None
        r["primary"] = "sign-flip permutation"              # assumption-free; the project's standard paired test
        n_pow = len(d)
    else:
        a, b = a[~np.isnan(a)], b[~np.isnan(b)]
        r.update(n=[int(len(a)), int(len(b))], diff=float(a.mean() - b.mean()),
                 diff_ci95=_boot(lambda x, y: x.mean() - y.mean(), a, b))
        r["effect"] = hedges_g(a, b); r["effect_name"] = "Hedges g"
        r["effect_ci95"] = _boot(hedges_g, a, b)
        var = a.std() > 0 or b.std() > 0
        r["tests"] = {"Welch t-test": float(stats.ttest_ind(a, b, equal_var=False).pvalue) if var else 1.0,
                      "Mann-Whitney U": float(stats.mannwhitneyu(a, b).pvalue) if var else 1.0}
        sh = [stats.shapiro(x).pvalue for x in (a, b) if len(x) >= 3 and x.std() > 0]
        r["normality_p"] = float(min(sh)) if sh else None
        r["primary"] = "Welch t-test" if (r["normality_p"] or 0) > 0.05 or min(len(a), len(b)) >= 30 else "Mann-Whitney U"
        n_pow = min(len(a), len(b))
    r["power"], r["n_for_80pct_power"] = power_t(r["effect"], n_pow, paired)
    return r


def adjust(ps, method="holm"):
    """Holm (family-wise error) or Benjamini-Hochberg (false discovery rate) adjusted p-values, same order as given."""
    ps = np.asarray(ps, float); m = len(ps)
    if m == 0 or method == "none":
        return ps.tolist()
    o = np.argsort(ps); adj = np.empty(m)
    if method == "holm":
        run = 0.0
        for rank, i in enumerate(o):
            run = max(run, min(1.0, (m - rank) * ps[i])); adj[i] = run
    else:                                                    # "bh"
        run = 1.0
        for rank in range(m - 1, -1, -1):
            i = o[rank]; run = min(run, ps[i] * m / (rank + 1)); adj[i] = min(1.0, run)
    return adj.tolist()


def omnibus(vals):
    xs = [v[~np.isnan(v)] for v in vals.values() if len(v[~np.isnan(v)]) >= 2]
    if len(xs) < 3:
        return None
    out = {"one-way ANOVA": float(stats.f_oneway(*xs).pvalue), "Kruskal-Wallis": float(stats.kruskal(*xs).pvalue)}
    try:
        out["Levene (equal spread?)"] = float(stats.levene(*xs).pvalue)
        out["Alexander-Govern (Welch-type ANOVA)"] = float(stats.alexandergovern(*xs).pvalue)
    except Exception:
        pass
    return out


def trend(series, times, frac=1 / 3, per=100):
    """Per replicate OLS slope over the last `frac` of the time course, in units per `per` time steps
    (100 generations, or 10,000 ticks for tick-based runs, so the numbers are readable)."""
    s = np.asarray(series, float)
    if s.ndim != 2 or s.shape[0] < 4:
        return None
    k = max(3, int(round(s.shape[0] * frac)))
    t = np.asarray(times[-k:], float); t = t - t.mean()
    sl = np.array([np.polyfit(t, s[-k:, j], 1)[0] * per if np.all(np.isfinite(s[-k:, j])) else np.nan
                   for j in range(s.shape[1])])
    sl = sl[np.isfinite(sl)]
    if len(sl) < 2:
        return None
    p = signflip(sl); m = float(sl.mean())
    verdict = "still rising" if m > 0 and p < 0.05 else "falling" if m < 0 and p < 0.05 else "plateau (no detectable trend)"
    return dict(window=f"last {k} of {s.shape[0]} points", slope=m, per=per, ci95=_ci_t(sl), p=p, verdict=verdict,
                rising=int((sl > 0).sum()), n=int(len(sl)))


def band(series):
    """(T, R) -> mean, 95 % CI low, high per time point."""
    s = np.asarray(series, float)
    m = np.nanmean(s, 1); n = np.sum(~np.isnan(s), 1)
    se = np.nanstd(s, 1, ddof=1) / np.sqrt(np.maximum(n, 1))
    h = stats.t.ppf(0.975, np.maximum(n - 1, 1)) * se
    return [None if not np.isfinite(x) else float(x) for x in m], \
           [None if not np.isfinite(x) else float(x) for x in m - h], [None if not np.isfinite(x) else float(x) for x in m + h]


def correlations(ds, group, ti=-1, max_measures=14):
    ms = [m for m in ds["measures"]]
    cols = {}
    for m in ms:
        v = values_at(ds, m, ti).get(group)
        if v is not None and np.nanstd(v) > 0:
            cols[m] = v
    names = list(cols)[:max_measures]
    if len(names) < 2:
        return None
    k = len(names); rho = np.eye(k); p = np.zeros((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            x, y = cols[names[i]], cols[names[j]]; ok = ~np.isnan(x) & ~np.isnan(y)
            if ok.sum() >= 4:
                r = stats.spearmanr(x[ok], y[ok]); rho[i, j] = rho[j, i] = r.statistic; p[i, j] = p[j, i] = r.pvalue
            else:
                rho[i, j] = rho[j, i] = np.nan; p[i, j] = p[j, i] = np.nan
    iu = np.triu_indices(k, 1); pv = p[iu]; ok = np.isfinite(pv)
    padj = np.full(k * (k - 1) // 2, np.nan); padj[ok] = adjust(pv[ok], "bh")
    P = np.zeros((k, k)); P[iu] = padj; P = P + P.T
    clean = lambda M: [[None if not np.isfinite(x) else float(x) for x in row] for row in M]
    return dict(group=group, measures=names, rho=clean(rho), p_bh=clean(P))


# ------------------------------------------------------------------------------------------------ the main call
def analyse(fid, measure, ref=None, groups=None, ti=-1, correction="holm", paired=None, alpha=0.05, corr_group=None):
    ds = load(fid)
    vals_all = values_at(ds, measure, ti)
    groups = [g for g in (groups or ds["groups_order"]) if g in vals_all]
    if not groups:
        raise ValueError(f"no group has the measure '{measure}'")
    ref = ref if ref in groups else groups[0]
    vals = {g: vals_all[g] for g in groups}
    pair = ds["paired"] if paired is None else bool(paired)
    lens = {len(v) for v in vals.values()}
    if pair and len(lens) > 1:
        pair = False                                          # different n -> cannot pair
    desc = {g: describe(v) for g, v in vals.items()}
    comps = []
    for g in groups:
        if g != ref:
            c = compare(vals[g], vals[ref], pair); c["group"] = g; comps.append(c)
    padj = adjust([c["tests"][c["primary"]] for c in comps], correction)
    for c, pa in zip(comps, padj):
        c["p_primary"] = c["tests"][c["primary"]]; c["p_adjusted"] = pa
        c["verdict"] = ("higher than" if c["diff"] > 0 else "lower than") + " reference" if pa < alpha else "no detectable difference"
    # time course with 95 % CI bands + trends
    tc, tr = {}, {}
    for g in groups:
        s = ds.get("series", {}).get(g, {}).get(measure)
        if s is not None and np.asarray(s).ndim == 2 and len(s) > 1:
            m, lo, hi = band(s)
            step = max(1, len(m) // 400)                     # at most ~400 points sent to the page
            tc[g] = dict(t=list(ds["times"][:len(m)])[::step], mean=m[::step], lo=lo[::step], hi=hi[::step])
            tr[g] = trend(s, list(ds["times"][:len(m)]), per=10000 if ds["unit_time"] == "tick" else 100)
    times = ds.get("times") or []
    has_series = any(measure in g for g in ds.get("series", {}).values())
    t_label = (f"{ds['unit_time']} {times[ti]}" if has_series and times and -len(times) <= ti < len(times)
               else "end of run (this measure is only recorded once)")
    res = dict(file=fid, kind=ds["kind"], note=ds["note"], measure=measure, groups=groups, ref=ref, paired=pair,
               correction=correction, alpha=alpha, at=t_label, n_times=len(times) if ds.get("series") else 0,
               values={g: [None if not np.isfinite(x) else float(x) for x in v] for g, v in vals.items()},
               describe=desc, comparisons=comps, omnibus=omnibus(vals), timecourse=tc, trends=tr,
               unit_time=ds["unit_time"],
               correlations=correlations(ds, corr_group if corr_group in groups else ref, ti))
    res["text"] = write_up(res)
    return res


def write_up(r):
    """Methods + Results paragraph in the style of a paper, with every number."""
    f = lambda x, k=3: "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{k}g}"
    pf = lambda p: "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
    corr = {"holm": "Holm's step-down correction", "bh": "the Benjamini-Hochberg false-discovery-rate correction",
            "none": "no correction for multiple comparisons"}[r["correction"]]
    test = "sign-flip permutation tests on paired differences (20,000 permutations; replicates share seeds across groups)" \
        if r["paired"] else "Welch's t-tests (Mann-Whitney U where normality was rejected)"
    m = (f"Methods. We compared '{r['measure']}' at {r['at']} across {len(r['groups'])} groups ({r['kind']}; {r['note']}). "
         f"Each group was compared with the reference '{r['ref']}' using {test}, with {corr} across "
         f"{len(r['comparisons'])} comparison(s) at alpha = {r['alpha']}. Effect sizes are "
         f"{'Cohen dz' if r['paired'] else 'Hedges g'} with bootstrap 95 % confidence intervals (5,000 resamples). ")
    if r["omnibus"]:
        m += "An omnibus one-way ANOVA and Kruskal-Wallis test were run across all groups. "
    m += "Trends are ordinary-least-squares slopes (per 100 generations or 10,000 ticks) over the last third of each replicate's time course, tested with sign-flip permutation."
    d = r["describe"]
    res = [f"Results. Reference '{r['ref']}': mean {f(d[r['ref']]['mean'])} (95 % CI {f(d[r['ref']]['ci95_t'][0])} to "
           f"{f(d[r['ref']]['ci95_t'][1])}, n = {d[r['ref']]['n']})."]
    for c in r["comparisons"]:
        g = c["group"]
        res.append(f"'{g}': mean {f(d[g]['mean'])} (95 % CI {f(d[g]['ci95_t'][0])} to {f(d[g]['ci95_t'][1])}); difference "
                   f"{c['diff']:+.3g} (95 % CI {f(c['diff_ci95'][0])} to {f(c['diff_ci95'][1])}), {c['effect_name']} = "
                   f"{c['effect']:.2f} (95 % CI {f(c['effect_ci95'][0], 2)} to {f(c['effect_ci95'][1], 2)}), "
                   f"{c['primary']} {pf(c['p_primary'])}, adjusted {pf(c['p_adjusted'])}: {c['verdict']}."
                   + (f" Power to detect this effect was {c['power']:.0%}" + (f"; about {c['n_for_80pct_power']} replicates would give 80 %." if c['n_for_80pct_power'] else ".")
                      if c.get("power") is not None else ""))
    if r["omnibus"]:
        o = r["omnibus"]
        res.append(f"Across all groups: ANOVA {pf(o['one-way ANOVA'])}, Kruskal-Wallis {pf(o['Kruskal-Wallis'])}.")
    for g, t in r["trends"].items():
        if t:
            res.append(f"Trend in '{g}' ({t['window']}): {t['slope']:+.3g} per {t['per']:,} {r['unit_time']}s "
                       f"(95 % CI {f(t['ci95'][0])} to {f(t['ci95'][1])}, {pf(t['p'])}; {t['rising']}/{t['n']} rising): {t['verdict']}.")
    return m + "\n\n" + " ".join(res)


def tidy_csv(fid, measures=None, ti=-1):
    """Long-format table: file, group, replicate, measure, time, value (end values, or the chosen time point)."""
    ds = load(fid)
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["file", "group", "replicate", "measure", f"time ({ds['unit_time']})", "value"])
    times = ds.get("times") or []
    for m in (measures or ds["measures"]):
        for g, v in values_at(ds, m, ti).items():
            for i, x in enumerate(v):
                w.writerow([fid, g, i, m, times[ti] if times and ds.get("series") else "end", "" if not np.isfinite(x) else x])
    return out.getvalue()


def info(fid):
    ds = load(fid)
    return dict(file=fid, kind=ds["kind"], note=ds["note"], groups=ds["groups_order"], measures=ds["measures"],
                series_measures=sorted({m for g in ds.get("series", {}).values() for m in g}),
                paired=ds["paired"], times=list(ds.get("times") or []) if ds.get("series") else [],
                n_times=len(ds.get("times") or []) if ds.get("series") else 0,
                unit_time=ds["unit_time"])


def clean(o):
    """JSON-safe copy: NaN / infinity -> None (browsers reject NaN in JSON), numpy numbers -> Python numbers."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


# ------------------------------------------------------------------------------------------------ experiment key
# One plain-language line per experiment, shown at the bottom of the Analysis page ("Key"). When you add an experiment,
# add its line here (or it falls back to a description built from its file name).
STEP_KEY = {
    "step10": "Step 10: head-to-head of early vs late brains. Found the 'tragedy of the commons' (brains that win by competing make the group worse).",
    "step11": "Step 11: clonal-group scoring (each brain scored as a group of its own copies) and worm scent.",
    "step12": "Step 12: hunger peptide re-tested under clonal scoring (the freeze trap disappears).",
    "step13a": "Step 13a: predators with touch sensing - do worms evolve escape?",
    "step13b": "Step 13b: starvation alarm into the ASH pain neuron.",
    "step13c": "Step 13c: brain growth (new neurons and synapses) re-tested.",
    "step14a": "Step 14a: is the hunger peptide entrenched? Keep / freeze / knock out / never had it.",
    "step14b": "Step 14b: selfish-herd predators - does clumping evolve?",
    "step15": "Step 15: lineage takeover and the skill plateau (one family wins within ~7 generations).",
    "step16": "Step 16: new worlds (seasons, fast predators, digestion) to break the plateau.",
    "step17": "Step 17: plateau follow-up with the fixed control.",
    "step18": "Step 18: obstacles (rocks) and nose touch - does hiding evolve?",
    "step19": "Step 19: matched scoring (train and test in full-size worlds) + worlds using every sense.",
    "step20": "MAIN EXPERIMENT (Step 20): connectome brain with reversal potentials and/or muscle output, 2 x 2 = 4 arms x 16 seeds.",
    "bench": "Test bench: teacher / curriculum and brain-dial experiments on the connectome worm.",
    "sweep": "Factor sweep: many world settings screened side by side.",
}
ARM_KEY = {
    "frozen": "no mutation: the code check (genetic change must be exactly 0) and the steady-population reference",
    "shadow": "chance only: same births and deaths as 'real' but random survivors (neutral shadow)",
    "real": "natural selection. Adaptation = real minus shadow",
    "normal": "brain with smell", "no_smell": "smell removed", "no_smell+frontal": "no smell + extra 'thinking' layer",
    "no_smell+frontal+hippo": "no smell + thinking layer + neurons born during life",
    "normal+frontal+hippo": "smell + thinking layer + neurons born during life", "random_walk": "no brain (baseline)",
    "s20_old": "old connectome model", "s20_rev": "+ reversal potentials", "s20_mus": "+ muscle output",
    "s20_both": "reversal potentials + muscle output",
}


def describe_file(fid):
    """One sentence saying what experiment a results file is."""
    import re
    kind, name = fid.split("/", 1); stem = Path(name).stem
    if kind == "engine":
        st = SOURCES["engine"] / f"{stem}_stats.txt"
        first = st.read_text(errors="ignore").splitlines()[0] if st.exists() else ""
        m = re.search(r"Run: (\d+) replicates x (\[.*?\]), (\d+) ticks.*factors on: (.*)", first)
        if m:
            fac = m.group(4).strip()
            what = "the equilibrium baseline (no factors)" if fac == "none" else f"factors switched on: {fac}"
            return f"Factor engine run '{stem}': {what}; {m.group(1)} worlds per arm, {int(m.group(3)):,} ticks."
        return f"Factor engine run '{stem}' (form engine/configs/{stem}.toml)."
    if kind == "equilibrium":
        m = re.match(r"eq_w(\d+)_(\d+)t_(\d+)s", stem)
        if m:
            return f"Equilibrium world: world {m.group(1)} copied {m.group(3)} times and run on for {int(m.group(2)):,} ticks (does the steady state hold long-term?)."
        m = re.match(r"eq_replay_(\d+)t_(\d+)s", stem)
        if m:
            return f"Equilibrium world: exact replay of the first {int(m.group(1)):,} ticks ({m.group(2)} worlds), to confirm runs repeat bit-for-bit."
        m = re.match(r"eq_(\d+)t_(\d+)s", stem)
        if m:
            return f"Equilibrium world: {m.group(2)} worlds x frozen / shadow / real for {int(m.group(1)):,} ticks. Tests the steady population and measures adaptation."
        return f"Equilibrium world run '{stem}'."
    if kind == "toybrain":
        m = re.match(r"results_(gpu|cpu)_(\d+)g(?:_(\d+)s)?(_fair)?(.*)", stem)
        if m:
            parts = [f"2nd Experiment (toy brain), {m.group(2)} generations" + (f", {m.group(3)} lineages" if m.group(3) else ""),
                     "fair mode (mutation scaled by genome size)" if m.group(4) else "ORIGINAL unfair mutation scaling (kept for comparison)"]
            rest = m.group(5) or ""
            c = re.search(r"_cont(\d+)_from_(\w+?)(?:_cross|$)", rest)
            if c:
                parts.append(f"continued for {c.group(1)} more generations from the champions of the {c.group(2)} run")
            x = re.search(r"_cross([\d.]+)_g(\d+)", rest)
            if x:
                parts.append(f"interbreeding: {float(x.group(1)):.0%} of children are crosses, "
                             + ("one shared pool" if x.group(2) in ("0", "1") else f"{x.group(2)} independent groups"))
            elif not c:
                parts.append("no interbreeding")
            if m.group(1) == "cpu":
                parts.append("CPU code")
            return "; ".join(parts) + "."
        return f"2nd Experiment (toy brain) results '{stem}'."
    for k in sorted(STEP_KEY, key=len, reverse=True):
        if stem.startswith(k):
            tail = stem[len(k):].strip("_")
            return STEP_KEY[k] + (f" (file: {tail.replace('_', ' ')})" if tail else "")
    return f"Results file '{stem}'."


def key():
    """Everything the Analysis page can name: each results file and each arm / group label."""
    return dict(files=[dict(id=f["id"], name=f["name"], source=f["source"], what=describe_file(f["id"])) for f in list_files()],
                groups=ARM_KEY)
