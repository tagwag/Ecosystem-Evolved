"""Traits: what evolves, measured as numbers, plus how fast and why (breeder's equation R = h^2 * S).

Every-generation traits (measured on every brain while it is scored):
    skill, foraging (food eaten), survival (worms alive at the end), escape (-bites), speed (mean speed),
    rest_when_full (speed when hungry - speed when full), clumping (-nearest-worm distance),
    avoid_<feature> (-exposure to each formula-world feature, e.g. avoid_toxin)
  S = selection differential: (mean of the brains selected to breed) - (mean of all brains), per generation
  R = response: change of the population mean from one generation to the next
  h^2 = realized heritability = sum R / sum S (how much of the selection actually gets passed on; noise and
        mutation make it < 1). R = h^2 * S is the breeder's equation.

Start-vs-end traits (measured on the best brain per seed at the start and the end, on the fixed test worlds):
    intelligence = mean skill on a battery of worlds the brain never trained in (generalization)
    sense_<name> = importance of a sense: skill lost when its sensory neurons are silenced
                   (rising importance = evolution is putting that sense to use)
"""
import numpy as np

STEP_TRAITS = ('skill', 'foraging', 'survival', 'escape', 'speed', 'rest_when_full', 'clumping')


def step_values(fit_b, st, specs):
    v = dict(skill=fit_b, foraging=st.get('mean_food', np.nan), survival=st.get('survivors', np.nan),
             escape=-st.get('bites', np.nan), speed=st.get('mean_speed', np.nan),
             rest_when_full=st.get('speed_hungry', np.nan) - st.get('speed_full', np.nan),
             clumping=-st.get('nn_dist', np.nan))
    fe = st.get('feature_exposure')
    for i, sp in enumerate(specs):
        v[f'avoid_{sp["name"]}'] = -fe[i] if fe is not None else np.nan
    return v


class Tracker:
    """Collects population and elite means of every trait, every generation, every seed."""
    def __init__(self, specs):
        self.specs, self.pop, self.eli, self.first_best = specs, {}, {}, {}

    def __call__(self, g, k, fit, per, order, popk):
        vals = [step_values(float(fit[b]), per[b], self.specs) for b in range(len(per))]
        for t in vals[0]:
            col = np.array([v[t] for v in vals], float)
            self.pop.setdefault(k, {}).setdefault(t, []).append(np.nanmean(col))
            self.eli.setdefault(k, {}).setdefault(t, []).append(np.nanmean(col[order]))
        if g == 0:
            self.first_best[k] = popk[order[0]].copy()

    def per_seed(self, k):
        out = {}
        for t, pm in self.pop[k].items():
            pm, em = np.array(pm), np.array(self.eli[k][t])
            S, R = (em - pm)[:-1], np.diff(pm)
            ok = np.isfinite(S) & np.isfinite(R)
            sS, sR = S[ok].sum(), R[ok].sum()
            out[f'S_{t}'] = float(S[ok].mean()) if ok.any() else np.nan
            out[f'R_{t}'] = float(R[ok].mean()) if ok.any() else np.nan
            out[f'h2_{t}'] = float(sR / sS) if ok.any() and abs(sS) > 1e-9 else np.nan
            out[f'change_{t}'] = float(pm[-1] - pm[0]) if np.isfinite(pm[[0, -1]]).all() else np.nan
        return out

    def curves(self):
        ks = sorted(self.pop)
        return {t: np.nanmean([self.pop[k][t] for k in ks], 0).round(4).tolist() for t in self.pop[ks[0]]}


def sense_groups(base, specs):
    """Senses present in this world -> neurons to silence when measuring importance."""
    from ..gpu_brains import SENSE_NEURONS
    g = {'food_smell': ['AWA', 'ASEL', 'ASER', 'AWC']}
    if base.get('predators', 0):
        g['touch'] = ['ALM', 'AVM', 'PLM', 'PVM']
    if base.get('pheromone'):
        g['worm_scent'] = ['ASK', 'ADL']
    if base.get('obstacles'):
        g['nose_touch'] = ['FLP', 'OLQ']
    if base.get('senses'):
        for n, ids in SENSE_NEURONS.items():
            g[f'step19_{n}'] = ids
    for sp in specs:
        g[sp['name']] = sp['neurons']
    return g


DEFAULT_BATTERY = [
    dict(name='scarcer_food', cfg_scale={'food_regrow_per_tick': 0.5}),
    dict(name='richer_food', cfg_scale={'food_regrow_per_tick': 2.0}),
    dict(name='moving_food', cfg={'season_every': 300}),
    dict(name='faster_predators', cfg={'pred_speed': 3.5, 'pred_sense': 200.0}),
    dict(name='new_poison', feature={'name': 'toxin', 'a': 1.5}),
]


def battery_worlds(over, specs, vals, battery=None):
    """Variants of a world for the intelligence test: (name, cfg overrides, feature specs, feature dial values)."""
    from .formula import feature_specs, FIELDS
    out = []
    for item in (battery or DEFAULT_BATTERY):
        o = dict(over)
        for k, f in (item.get('cfg_scale') or {}).items():
            from ..config import Config
            o[k] = o.get(k, getattr(Config(), k)) * f
        o.update(item.get('cfg') or {})
        if item.get('cfg', {}).get('pred_speed') and not o.get('predators'):
            continue
        sp, vv = list(specs), {n: dict(v) for n, v in vals.items()}
        ft = item.get('feature')
        if ft:
            name = ft['name']
            if name not in vv:
                s = feature_specs({name: {}})[0]
                sp.append(s); vv[name] = {k: float(s[k]) for k in FIELDS}
            for k, v in ft.items():
                if k != 'name':
                    vv[name][k] = float(v)
        out.append((item['name'], o, sp, vv))
    return out
