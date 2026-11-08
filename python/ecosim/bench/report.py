"""Plain-English report (summary.md) + charts for a test-bench experiment. Written on the PC, readable without Claude."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .surface import design, _code

NICE = {'fitness': 'skill (energy left/100 + survival)', 'mean_food': 'food eaten per worm', 'bites': 'predator bites per worm',
        'survivors': 'worms alive at the end', 'speed_full': 'speed when full (vs max)', 'speed_hungry': 'speed when hungry',
        'nn_dist': 'distance to nearest worm (lower = clumped)'}
MAIN = ('fitness', 'mean_food', 'bites', 'survivors')


def nice(m):
    if m.startswith('exposure_'):
        return f'exposure to {m[9:]} (avg strength felt per tick)'
    if m.startswith('energy_lost_to_'):
        return f'energy lost to {m[15:]} per worm'
    return NICE.get(m, m)


def sentences(metric, fit):
    if not fit:
        return ['  (not enough data points to fit)']
    out = [f'  fit explains {fit["r2"] * 100:.0f}% of the variation (R^2 = {fit["r2"]:.2f}, {fit["n"]} data points)']
    for t, v in fit['terms'].items():
        if t == 'const' or not v['clear']:
            continue
        c = v['coef']
        if t.endswith('^2'):
            out.append(f'  - {t[:-2]}: {"peaks" if c < 0 else "dips"} inside the tested range (curve {c:+.3f})')
        elif ' x ' in t:
            out.append(f'  - {t}: interact ({c:+.3f}): the effect of one depends on the other')
        else:
            out.append(f'  - raising {t} {"increases" if c > 0 else "decreases"} it ({c:+.3f} from middle to top of the range)')
    if len(out) == 1:
        out.append('  - no clear effects (all within noise)')
    bs = ', '.join(f'{k} = {v:.3g}' for k, v in fit['best_settings'].items())
    out.append(f'  - predicted best: {bs} -> {fit["best_predicted"]:.3f} (worst in range {fit["worst_predicted"]:.3f})')
    return out


def report(R, out):
    names = [f['name'] for f in R['factors']]
    res = R['results']
    metrics = list(res[0]['metrics'])
    L = [f'# Experiment: {R["name"]}', '', R.get('description') or '', '',
         f'Mode: **{R["mode"]}** ({"world/brain dials -> evolution -> brain" if R["mode"] == "evolve" else "brains + dials -> one lifetime -> behaviour"})  ',
         f'Combinations: {len(res)}, time: {R["seconds"] // 60} min', '', '## Factors', '']
    for f in R['factors']:
        L.append(f'- `{f["name"]}`: {f["levels"]}')
    L += ['', '## Results per combination', '', '| ' + ' | '.join(names + [nice(m) for m in MAIN if m in metrics]) + ' |',
          '|' + '---|' * (len(names) + len([m for m in MAIN if m in metrics]))]
    for r in res:
        L.append('| ' + ' | '.join([f'{r["combo"][n]}' for n in names] + [f'{r["metrics"][m]:.3f}' for m in MAIN if m in metrics]) + ' |')
    if R['surface']:
        L += ['', '## What the quadratic fit says', '', '"Clear" = bigger than twice its uncertainty. Values in the units of each result.', '']
        for m in metrics:
            L += [f'**{nice(m)}**', '```'] + sentences(m, R['surface'].get(m)) + ['```']
    if R['mode'] == 'evolve':
        lay = list(res[0]['brain_change'])
        L += ['', '## What changed in the brain', '',
              'Mean |change| of incoming synapse strengths per layer (0 = still the original connectome). '
              '"Importance" = skill lost when the whole layer is silenced.', '',
              '| combination | ' + ' | '.join(lay) + ' | ' + ' | '.join(f'importance {k}' for k in res[0]['layer_importance']) + ' |',
              '|' + '---|' * (1 + len(lay) + len(res[0]['layer_importance']))]
        for r in res:
            L.append(f'| {r["combo"]} | ' + ' | '.join(f'{r["brain_change"][k]:.3f}' for k in lay) + ' | '
                     + ' | '.join(f'{v:+.3f}' for v in r['layer_importance'].values()) + ' |')
    L += ['', 'Charts: effects.png' + (', surface.png' if len(names) >= 2 else '') + (', brain.png' if R['mode'] == 'evolve' else '')]
    (out / 'summary.md').write_text('\n'.join(L))
    charts(R, out, names, metrics)


def charts(R, out, names, metrics):
    res = R['results']
    show = [m for m in metrics if m in MAIN or m.startswith('exposure_')][:6]
    if names:
        fig, axes = plt.subplots(len(show), len(names), figsize=(3.6 * len(names), 2.6 * len(show)), squeeze=False)
        for i, m in enumerate(show):
            for j, n in enumerate(names):
                lv = R['factors'][j]['levels']
                ys = [[p[m] for r in res if r['combo'][n] == v for p in r['metrics_per_seed']] for v in lv]
                mu = [np.mean(y) for y in ys]; se = [np.std(y) / np.sqrt(max(len(y), 1)) for y in ys]
                ax = axes[i, j]
                ax.errorbar([str(v) for v in lv], mu, yerr=[1.96 * s for s in se], marker='o', capsize=3)
                if i == len(show) - 1: ax.set_xlabel(n, fontsize=8)
                if j == 0: ax.set_ylabel(nice(m), fontsize=7)
                ax.grid(alpha=0.3)
        fig.suptitle(f'{R["name"]}: effect of each factor (averaged over the others, 95% CI)')
        fig.tight_layout(); fig.savefig(out / 'effects.png', dpi=110); plt.close(fig)
    fit = R['surface'].get('fitness') if R['surface'] else None
    if fit and len(names) >= 2:
        lv = [f['levels'] for f in R['factors']]
        g = np.linspace(-1, 1, 41)
        Xg = np.zeros((41 * 41, len(names)))
        Xg[:, 0] = np.repeat(g, 41); Xg[:, 1] = np.tile(g, 41)
        A, terms = design(Xg, [len(set(l)) for l in lv], names)
        beta = np.array([fit['terms'][t]['coef'] for t in terms])
        Z = (A @ beta).reshape(41, 41)
        fig, ax = plt.subplots(figsize=(6, 5))
        ext = [min(lv[1]), max(lv[1]), min(lv[0]), max(lv[0])]
        im = ax.imshow(Z, origin='lower', extent=ext, aspect='auto', cmap='viridis')
        ax.set_xlabel(names[1]); ax.set_ylabel(names[0]); fig.colorbar(im, label='predicted skill')
        for r in res:
            ax.plot(r['combo'][names[1]], r['combo'][names[0]], 'w.', ms=4)
        ax.set_title('quadratic fit of skill' + (' (other factors at middle)' if len(names) > 2 else ''))
        fig.tight_layout(); fig.savefig(out / 'surface.png', dpi=110); plt.close(fig)
    if R['mode'] == 'evolve':
        lay = list(res[0]['brain_change'])
        fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(res) * len(lay) / 3), 4))
        w = 0.8 / len(lay)
        for i, k in enumerate(lay):
            ax.bar(np.arange(len(res)) + i * w, [r['brain_change'][k] for r in res], w, label=k)
        ax.set_xticks(np.arange(len(res)) + 0.4, [str(i + 1) for i in range(len(res))])
        ax.set_xlabel('combination (see summary.md table order)'); ax.set_ylabel('mean |synapse change|')
        ax.legend(fontsize=7, ncol=4); ax.set_title('How far each layer moved from the original wiring')
        fig.tight_layout(); fig.savefig(out / 'brain.png', dpi=110); plt.close(fig)
