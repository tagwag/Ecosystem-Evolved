"""Smoke test: every factor alone on 'auto' for a short run (1 replicate, real arm only). Prints the population
and any crash. Use after editing any factor:  python test_factors.py [ticks] [name ...]"""
import sys, time, traceback
import torch
import config as C
from engine import World
from run import founders

ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
names = sys.argv[2:] or ["(baseline)"] + list(C.REGISTRY)
for n in names:
    t0 = time.time()
    try:
        cfg = dict(run=dict(C.RUN_DEFAULTS, replicates=1, arms=["real"], founders="toybrain"), world=dict(C.WORLD_DEFAULTS),
                   factors={})
        act = [] if n == "(baseline)" else [C.REGISTRY[n][0](C.factor_params(n, {"mode": "auto"}))]
        w = World(cfg, founders("toybrain", 1), act)
        for _ in range(ticks):
            w.tick()
        m = w.measure()
        extra = {k: round(v[0], 3) for k, v in m.items() if k.startswith(n.split("_")[0]) or k.startswith("deaths_")}
        print(f"{n:20s} pop {m['pop'][0]:5.0f}  eat {m['eat_rate'][0]:.4f}  speed {m['speed'][0]:.2f}  {extra}  ({time.time()-t0:.0f}s)", flush=True)
    except Exception:
        print(f"{n:20s} CRASH\n" + traceback.format_exc(limit=3), flush=True)
