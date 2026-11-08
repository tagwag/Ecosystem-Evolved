"""Response surface: fit a quadratic to each result over the factor levels and find its best point.

    y = b0 + sum_i b_i x_i + sum_i b_ii x_i^2 + sum_{i<j} b_ij x_i x_j        (x = factor level scaled to -1..1)
b_i = straight-line effect, b_ii = curve (a peak or a dip inside the range), b_ij = interaction (one dial's effect
depends on another's). Square terms need >= 3 levels of that factor. Every seed/brain is one data point, so the fit
also tells how much is real (R^2) versus noise.
"""
import itertools

import numpy as np


def _code(v, lv):
    lo, hi = min(lv), max(lv)
    return 0.0 if hi == lo else 2 * (v - lo) / (hi - lo) - 1


def design(X, nlev, fn=None):
    d = X.shape[1]
    fn = fn or [f'x{i}' for i in range(d)]
    cols, names = [np.ones(len(X))], ['const']
    for i in range(d):
        cols.append(X[:, i]); names.append(fn[i])
    for i in range(d):
        if nlev[i] >= 3:
            cols.append(X[:, i] ** 2); names.append(f'{fn[i]}^2')
    for i, j in itertools.combinations(range(d), 2):
        cols.append(X[:, i] * X[:, j]); names.append(f'{fn[i]} x {fn[j]}')
    return np.column_stack(cols), names


def fit(names, factors, results, metric):
    lv = [f['levels'] for f in factors]
    nlev = [len(set(l)) for l in lv]
    X, y = [], []
    for r in results:
        for p in r['metrics_per_seed']:
            if metric in p and np.isfinite(p[metric]):
                X.append([_code(r['combo'][n], l) for n, l in zip(names, lv)]); y.append(p[metric])
    X, y = np.array(X), np.array(y)
    if len(y) == 0:
        return None
    A, terms = design(X, nlev, names)
    if len(y) <= A.shape[1]:
        return None
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-12)
    resid = y - pred
    se = np.sqrt(np.diag(np.linalg.pinv(A.T @ A)) * (resid ** 2).sum() / max(len(y) - A.shape[1], 1))
    grid = np.array(list(itertools.product(*[np.linspace(-1, 1, 21 if len(names) <= 3 else 9)] * len(names))))
    G, _ = design(grid, nlev)
    gp = G @ beta
    best = grid[int(np.argmax(gp))]
    decode = lambda c, l: min(l) + (c + 1) / 2 * (max(l) - min(l))
    return dict(r2=float(r2), n=int(len(y)),
                terms={t: dict(coef=float(b), se=float(s), clear=bool(abs(b) > 2 * s)) for t, b, s in zip(terms, beta, se)},
                best_settings={n: float(decode(c, l)) for n, c, l in zip(names, best, lv)},
                best_predicted=float(gp.max()), worst_predicted=float(gp.min()))


def fit_all(names, results, factors):
    if not names:
        return {}
    metrics = list(results[0]['metrics_per_seed'][0])
    return {m: fit(names, factors, results, m) for m in metrics}
