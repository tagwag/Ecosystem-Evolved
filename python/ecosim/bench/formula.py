"""Formula worlds: every world feature is a seeded formula evaluated only where a worm is (no stored map).

    F(x, y, t) = b + a * sum_k c_k * cos(2*pi*(n_k*x/W + m_k*y/H) + w_k*t + phi_k) / norm

    a = strength, b = baseline, scale = typical patch size (world units; sets the wave numbers n, m),
    period = ticks for the pattern to drift through one cycle (0 = never changes), cost = energy lost per tick
    at full strength, neurons = which sensory neurons feel it, gain = how strongly.
Integer wave numbers make every feature wrap seamlessly around the (torus) world. The same seed always gives the
same world (like Minecraft chunks): it is just a function of (x, y, t, seed). Evaluated on the GPU for every worm
every tick, so it costs almost nothing and needs no CPU world-building.
"""
import numpy as np

N_WAVES = 6

# Built-in features. Unsigned features are clamped to 0..1, signed ones (temperature) to -1..1 (0 = comfortable).
CATALOG = {
    'temperature': dict(neurons=['AFD'], signed=True, a=1.0, b=0.0, scale=500.0, period=0, cost=0.4, gain=3.0),
    'light': dict(neurons=['ASJ'], signed=False, a=1.0, b=-0.3, scale=300.0, period=0, cost=0.3, gain=3.0),
    'toxin': dict(neurons=['PHA', 'PHB'], signed=False, a=1.5, b=-0.6, scale=150.0, period=0, cost=1.5, gain=3.0),
    'oxygen': dict(neurons=['URX', 'AQR', 'PQR'], signed=False, a=0.5, b=0.5, scale=400.0, period=0, cost=0.0, gain=3.0),
}
FIELDS = ('a', 'b', 'scale', 'period', 'cost', 'gain')


def feature_specs(world_cfg):
    """[world.features.<name>] tables -> list of full specs (catalog defaults + overrides)."""
    specs = []
    for name, over in (world_cfg or {}).items():
        base = dict(CATALOG.get(name, dict(neurons=[], signed=False, a=1.0, b=0.0, scale=300.0, period=0,
                                           cost=0.0, gain=3.0)))
        base.update(over or {})
        if not base['neurons']:
            raise ValueError(f'world feature {name!r} needs neurons = [...] (it is not a built-in feature)')
        specs.append(dict(name=name, **base))
    return specs


def draw_waves(rng, width, height, scale, period):
    """Wave numbers, phases, coefficients and drift speeds for one feature in one world."""
    th = rng.uniform(0, np.pi, N_WAVES)
    lam = scale * rng.uniform(0.7, 1.3, N_WAVES)
    n = np.round(width / lam * np.cos(th)); m = np.round(height / lam * np.sin(th))
    n[(n == 0) & (m == 0)] = 1
    phi = rng.uniform(0, 2 * np.pi, N_WAVES)
    c = rng.normal(0, 1, N_WAVES)
    c /= np.sqrt((c ** 2).sum() / 2) + 1e-9                     # field roughly in -1..1 before a, b
    om = (2 * np.pi / period * rng.uniform(0.8, 1.2, N_WAVES) * rng.choice([-1, 1], N_WAVES)) if period else np.zeros(N_WAVES)
    return n, m, phi, c, om
