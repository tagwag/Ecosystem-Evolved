"""Run an experiment form (config file) with the factor engine.

Usage:  python run.py configs/<form>.toml [--quick]
  --quick : 1 replicate, 3000 ticks, measure every 100 ticks (seconds on a CPU) - for checking a form works.
Output: results/<name>.json (every measurement, per world, plus the full settings used) and results/<name>.png +
        <name>_stats.txt from analyze.py. Progress: run_log.txt. Safe to interrupt (results are written at the end).
"""
import json, sys, time
from pathlib import Path

import torch

import config as C
from engine import DEV, World, from_toy, glen

HERE = Path(__file__).resolve().parent
FOUNDERS = {"toybrain_fair": HERE.parent / "toybrain" / "results_gpu_300g_30s_fair.json",
            "toybrain": HERE.parent / "toybrain" / "results_gpu_300g_30s.json"}


def founders(spec, R):
    if spec == "random":
        return 0.5 * torch.randn(R, glen(), generator=torch.Generator().manual_seed(0))
    path = FOUNDERS.get(spec, spec)
    g = json.loads(Path(path).read_text())["normal"]["genomes"]
    g = torch.tensor(g, dtype=torch.float32)
    return from_toy(g[torch.arange(R) % len(g)])


def main():
    args = sys.argv[1:]; quick = "--quick" in args; args = [a for a in args if a != "--quick"]
    cfg, active = C.load(args[0])
    run = cfg["run"]
    if quick:
        run.update(replicates=1, ticks=3000, every=100); run["name"] += "_quick"
    log = (HERE / "run_log.txt").open("a")
    def say(m):
        line = f"{time.strftime('%H:%M:%S')} [{run['name']}] {m}"; print(line, flush=True); log.write(line + "\n"); log.flush()
    on = [n for n, v in cfg["factors"].items() if v["params"] is not None]
    say(f"start on {DEV}: {run['replicates']} replicates x {run['arms']}, {run['ticks']} ticks; factors on: {on or 'none (equilibrium baseline)'}")
    w = World(cfg, founders(run["founders"], int(run["replicates"])), active)
    series, t0 = [], time.time()
    for t in range(1, int(run["ticks"]) + 1):
        w.tick()
        if t % int(run["every"]) == 0:
            m = w.measure(); m["t"] = t; series.append(m)
            if t % (int(run["every"]) * 10) == 0 or t == int(run["ticks"]):
                R = int(run["replicates"]); A = len(run["arms"])
                pops = [sum(m["pop"][a * R:(a + 1) * R]) / R for a in range(A)]
                say(f"t {t:7d}  pop " + " / ".join(f"{a} {p:.0f}" for a, p in zip(run["arms"], pops)) + f"  ({time.time() - t0:.0f} s)")
    out = HERE / "results" / f"{run['name']}.json"; out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(config=cfg, arms=run["arms"], replicates=int(run["replicates"]), ticks=int(run["ticks"]),
                                   founders=run["founders"], series=series)))
    say(f"saved {out.name}; analysing")
    import analyze
    analyze.main(str(out))
    say("RUN_DONE")


if __name__ == "__main__":
    main()
