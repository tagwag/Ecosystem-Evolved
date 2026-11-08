"""Campaign: find the settings that make a chosen trait evolve fastest, with as few runs as possible.

  1. SCREEN  every factor at low/high in a fractional factorial (two-level orthogonal design): ~N+1 runs for N factors
             instead of 2^N. Ranks factors by their main effect on the target. Unimportant factors are fixed at their
             better level.
  2. ZOOM    the top factors in a face-centred central composite design (corners + edge centres + centre), fit the
             quadratic, jump to its predicted best point, shrink the box around it, repeat.
  3. LEARN   machine learning: a Gaussian-process model of target vs settings (fitted to every run so far, with
             its own uncertainty) picks the next settings where expected improvement is highest (Bayesian
             optimisation), runs them, refits, repeats.
Every run = one evolve combination (eval_combo). Output: runs/bench/<name>/campaign.json, summary.md, campaign.png
"""
import itertools
import json
import time

import numpy as np

from .run import eval_combo


# ------------------------------------------------------------------ designs
def two_level(k):
    """Orthogonal 2-level design for k factors: columns of a Sylvester-Hadamard matrix (runs = next power of 2 > k)."""
    n = 1
    while n <= k:
        n *= 2
    H = np.array([[1]])
    while len(H) < n:
        H = np.block([[H, H], [H, -H]])
    return H[:, 1:k + 1].astype(float)                    # rows = runs, values -1 / +1


def ccd(k):
    """Face-centred central composite design in coded units."""
    pts = [list(p) for p in itertools.product([-1, 1], repeat=k)]
    for i in range(k):
        for s in (-1, 1):
            p = [0.0] * k; p[i] = s; pts.append(p)
    pts.append([0.0] * k)
    return np.array(pts, float)


# ------------------------------------------------------------------ Gaussian process (numpy, small data)
def _k(A, B, ls):
    d = ((A[:, None, :] - B[None, :, :]) / ls) ** 2
    return np.exp(-0.5 * d.sum(-1))


def gp_fit(X, y, noise):
    """Pick the length-scale by marginal likelihood from a small grid. Returns a predict(Xs) -> (mean, sd)."""
    mu, sd = y.mean(), y.std() + 1e-9
    yn = (y - mu) / sd
    best = None
    for ls in (0.3, 0.5, 0.8, 1.2, 2.0):
        K = _k(X, X, ls) + (noise / sd ** 2 + 1e-6) * np.eye(len(X))
        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            continue
        a = np.linalg.solve(L.T, np.linalg.solve(L, yn))
        ll = -0.5 * yn @ a - np.log(np.diag(L)).sum()
        if best is None or ll > best[0]:
            best = (ll, ls, L, a)
    _, ls, L, a = best

    def predict(Xs):
        Ks = _k(Xs, X, ls)
        m = Ks @ a
        v = np.linalg.solve(L, Ks.T)
        var = np.clip(1 - (v ** 2).sum(0), 1e-12, None)
        return mu + sd * m, sd * np.sqrt(var)
    predict.length_scale = ls
    return predict


def expected_improvement(m, s, best):
    from math import erf, sqrt, pi
    z = (m - best) / s
    Phi = 0.5 * (1 + np.vectorize(erf)(z / sqrt(2)))
    phi = np.exp(-0.5 * z ** 2) / sqrt(2 * pi)
    return (m - best) * Phi + s * phi


# ------------------------------------------------------------------ campaign
def run_campaign(S, out, conn, dev):
    from .surface import design
    C = S.get('campaign', {})
    target = C.get('target', 'R_skill')
    F = S['factor']
    names = [f['name'] for f in F]
    lo = np.array([float(f['low']) for f in F]); hi = np.array([float(f['high']) for f in F])
    integer = [bool(f.get('integer', False)) for f in F]
    log, runs = [], []
    t_all = time.time()

    def real(code, lo_, hi_, idx=None):
        idx = list(range(len(F))) if idx is None else idx
        v = lo_ + (np.asarray(code) + 1) / 2 * (hi_ - lo_)
        return [float(round(x)) if integer[i] else float(x) for i, x in zip(idx, v)]

    def run(values, phase):
        combo = dict(zip(names, values))
        r = eval_combo(S, combo, len(runs), out, conn, dev, f'{phase} {len(runs) + 1}')
        y = r['metrics'].get(target, np.nan)
        ys = [p.get(target, np.nan) for p in r['metrics_per_seed']]
        runs.append(dict(phase=phase, combo=combo, target=y, target_per_seed=ys, metrics=r['metrics']))
        (out / 'campaign.json').write_text(json.dumps(dict(target=target, runs=runs, log=log), indent=1, default=float))
        print(f'   {target} = {y:.4f}', flush=True)
        return y

    # 1. screen
    fixed = {}
    keep = list(range(len(F)))
    if C.get('screen', True) and len(F) > 2:
        D = two_level(len(F))
        ys = np.array([run(real(row, lo, hi), 'screen') for row in D])
        eff = np.array([ys[D[:, i] > 0].mean() - ys[D[:, i] < 0].mean() for i in range(len(F))])
        order = list(np.argsort(-np.abs(eff)))
        keep = sorted(order[:C.get('top', 3)])
        for i in order[C.get('top', 3):]:
            fixed[i] = hi[i] if eff[i] > 0 else lo[i]
        log.append(dict(phase='screen', effects={names[i]: float(eff[i]) for i in range(len(F))},
                        kept=[names[i] for i in keep],
                        fixed={names[i]: float(v) for i, v in fixed.items()}))
        print('screen effects:', log[-1]['effects'], '-> keep', log[-1]['kept'], flush=True)

    def full(code_sub, lo_, hi_):
        v = np.array([fixed.get(i, 0.0) for i in range(len(F))], float)
        r = real(code_sub, lo_[keep], hi_[keep], keep)
        for j, i in enumerate(keep):
            v[i] = r[j]
        return [float(x) for x in v]

    # 2. zoom (sequential response surface)
    blo, bhi = lo.copy(), hi.copy()
    for z in range(C.get('zoom_rounds', 2)):
        D = ccd(len(keep))
        ys = np.array([run(full(row, blo, bhi), f'zoom{z + 1}') for row in D])
        A, terms = design(D, [3] * len(keep))
        beta, *_ = np.linalg.lstsq(A, ys, rcond=None)
        grid = np.array(list(itertools.product(*[np.linspace(-1, 1, 21)] * len(keep))))
        G, _ = design(grid, [3] * len(keep))
        b = grid[int(np.argmax(G @ beta))]
        centre = np.array(real(b, blo[keep], bhi[keep], keep))
        half = (bhi[keep] - blo[keep]) / 4                          # shrink the box to half its width
        nlo, nhi = np.maximum(lo[keep], centre - half), np.minimum(hi[keep], centre + half)
        log.append(dict(phase=f'zoom{z + 1}', box={names[i]: [float(blo[i]), float(bhi[i])] for i in keep},
                        quadratic={t: float(c) for t, c in zip(terms, beta)},
                        predicted_best={names[i]: float(centre[j]) for j, i in enumerate(keep)},
                        predicted_value=float((G @ beta).max())))
        print('zoom', z + 1, 'predicted best', log[-1]['predicted_best'], flush=True)
        blo[keep], bhi[keep] = nlo, nhi

    # 3. learn (Bayesian optimisation with a Gaussian process) over the kept factors, full range
    code = lambda vals: np.array([2 * (vals[i] - lo[i]) / max(hi[i] - lo[i], 1e-12) - 1 for i in keep])
    for m in range(C.get('ml_runs', 6)):
        X = np.array([code([r['combo'][n] for n in names]) for r in runs])
        y = np.array([r['target'] for r in runs])
        ok = np.isfinite(y)
        noise = float(np.nanmean([np.nanvar(r['target_per_seed']) / max(len(r['target_per_seed']), 1) for r in runs]))
        gp = gp_fit(X[ok], y[ok], max(noise, 1e-8))
        cand = np.random.default_rng(m).uniform(-1, 1, (4000, len(keep)))
        mu, sd = gp(cand)
        ei = expected_improvement(mu, sd, y[ok].max())
        nxt = cand[int(np.argmax(ei))]
        log.append(dict(phase=f'learn{m + 1}', length_scale=gp.length_scale, chosen=full(nxt, lo, hi),
                        predicted=float(mu[int(np.argmax(ei))]), uncertainty=float(sd[int(np.argmax(ei))])))
        run(full(nxt, lo, hi), f'learn{m + 1}')

    # final: the GP's best guess over the whole box, and the best run actually measured
    X = np.array([code([r['combo'][n] for n in names]) for r in runs]); y = np.array([r['target'] for r in runs])
    ok = np.isfinite(y)
    gp = gp_fit(X[ok], y[ok], max(noise if C.get('ml_runs', 6) else 1e-4, 1e-8)) if ok.sum() > 2 else None
    res = dict(target=target, runs=runs, log=log, seconds=round(time.time() - t_all),
               best_measured=runs[int(np.nanargmax(y))] if ok.any() else None)
    if gp is not None:
        cand = np.random.default_rng(99).uniform(-1, 1, (20000, len(keep)))
        mu, sd = gp(cand)
        i = int(np.argmax(mu))
        res['model_best'] = dict(settings=dict(zip(names, full(cand[i], lo, hi))), predicted=float(mu[i]), sd=float(sd[i]))
    (out / 'campaign.json').write_text(json.dumps(res, indent=1, default=float))
    campaign_report(S, res, out)
    from pathlib import Path
    import shutil
    Path('results').mkdir(exist_ok=True)
    for f in out.glob('*'):
        if f.is_file() and f.suffix in ('.json', '.png', '.md'):
            shutil.copy(f, Path('results') / f'bench_{S["name"]}_{f.name}')
    print(f'campaign done in {res["seconds"] // 60} min -> {out}', flush=True)


def campaign_report(S, res, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .report import nice
    t = res['target']
    L = [f'# Campaign: {S["name"]}', '', S.get('description', ''), '', f'Target: **{nice(t)}** (`{t}`), maximized.  ',
         f'Runs: {len(res["runs"])}, time: {res["seconds"] // 60} min', '']
    for e in res['log']:
        if e['phase'] == 'screen':
            L += ['## 1. Screen (which dials matter)', '', '| factor | effect low->high |', '|---|---|']
            L += [f'| {k} | {v:+.4f} |' for k, v in sorted(e['effects'].items(), key=lambda kv: -abs(kv[1]))]
            L += ['', f'Kept: {", ".join(e["kept"])}. Fixed at their better level: '
                  + (', '.join(f'{k} = {v:g}' for k, v in e['fixed'].items()) or 'none'), '']
        elif e['phase'].startswith('zoom'):
            L += [f'## 2. {e["phase"]}: quadratic in box ' + ', '.join(f'{k} [{a:g}, {b:g}]' for k, (a, b) in e['box'].items()), '',
                  'predicted best: ' + ', '.join(f'{k} = {v:.3g}' for k, v in e['predicted_best'].items())
                  + f' -> {e["predicted_value"]:.4f}', '']
    learn = [e for e in res['log'] if e['phase'].startswith('learn')]
    if learn:
        L += ['## 3. Machine learning (Gaussian process + expected improvement)', '', '| step | settings tried | predicted | measured |', '|---|---|---|---|']
        meas = [r for r in res['runs'] if r['phase'].startswith('learn')]
        for e, r in zip(learn, meas):
            L.append(f'| {e["phase"]} | ' + ', '.join(f'{v:.3g}' for v in r['combo'].values())
                     + f' | {e["predicted"]:.4f} +- {e["uncertainty"]:.4f} | {r["target"]:.4f} |')
        L.append('')
    b = res.get('best_measured')
    if b:
        L += ['## Result', '', f'Best measured: ' + ', '.join(f'{k} = {v:.3g}' for k, v in b['combo'].items()) + f' -> {b["target"]:.4f}  ']
    if res.get('model_best'):
        mb = res['model_best']
        L += ['Model\'s best guess: ' + ', '.join(f'{k} = {v:.3g}' for k, v in mb['settings'].items())
              + f' -> {mb["predicted"]:.4f} +- {mb["sd"]:.4f}', '',
              'Next step: run the best settings with more seeds (a confirmation run) before trusting them.']
    (out / 'summary.md').write_text('\n'.join(L))
    y = [r['target'] for r in res['runs']]
    fig, ax = plt.subplots(figsize=(9, 4))
    cols = {'screen': 'C0', 'zoom': 'C1', 'learn': 'C2'}
    for i, r in enumerate(res['runs']):
        ax.plot(i + 1, r['target'], 'o', color=cols[r['phase'].rstrip('0123456789')])
    ax.plot(range(1, len(y) + 1), np.maximum.accumulate(np.nan_to_num(y, nan=-np.inf)), 'k-', lw=1, label='best so far')
    for p, c in cols.items():
        ax.plot([], [], 'o', color=c, label=p)
    ax.set_xlabel('run'); ax.set_ylabel(nice(t)); ax.legend(); ax.grid(alpha=0.3)
    ax.set_title(f'Campaign {S["name"]}: screen -> zoom -> machine learning')
    fig.tight_layout(); fig.savefig(out / 'campaign.png', dpi=110); plt.close(fig)
