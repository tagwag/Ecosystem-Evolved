"""Run an experiment form (config file) with the factor engine.

Usage:  python run.py configs/<form>.toml [--quick] [--from-tick T --as NEW_NAME [--seed S]] [--fresh]
  (default)   if this run was interrupted, it RESUMES from its latest checkpoint automatically
  --fresh     ignore old checkpoints and start over
  --from-tick T --as NEW : branch: start a NEW run from this run's checkpoint at tick T (same world, same moment);
              add --seed S to give it new luck (otherwise it repeats the original exactly)
  --quick : 1 replicate, 3000 ticks, measure every 100 ticks (seconds on a CPU) - for checking a form works.
  --preflight : don't run; print JSON {ok, errors, gpu_mb, ram_mb} (the watcher's safety gate uses this).
Output: results/<name>.json (every measurement, per world, plus the full settings used) and results/<name>.png +
        <name>_stats.txt from analyze.py. Progress: run_log.txt. Safe to interrupt (results are written at the end).
"""
import json, sys, time
from pathlib import Path

import torch

import config as C
import checkpoint as CK
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "remote"))
from simctl import SimControl                    # live view, replay recording, quiet mode, slow motion
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
    args = sys.argv[1:]; quick = "--quick" in args; pre = "--preflight" in args
    args = [a for a in args if a not in ("--quick", "--preflight")]
    if quick:
        args.append("--fresh")
    try:
        cfg, active = C.load(args[0])
    except Exception as e:                               # bad form -> clear error, no traceback noise
        if pre:
            print(json.dumps(dict(ok=False, errors=[str(e)], gpu_mb=0, ram_mb=0))); return
        raise
    run = cfg["run"]
    if quick:
        run.update(replicates=1, ticks=3000, every=100); run["name"] += "_quick"
    est = C.estimate(cfg)
    if pre:                                              # used by the watcher's safety gate: check only, run nothing
        print(json.dumps(dict(ok=not est["errors"], **est))); return
    if est["errors"]:
        raise SystemExit("REFUSED (unsafe for this computer): " + " | ".join(est["errors"]))
    log = (HERE / "run_log.txt").open("a")
    def say(m):
        line = f"{time.strftime('%H:%M:%S')} [{run['name']}] {m}"; print(line, flush=True); log.write(line + "\n"); log.flush()
    on = [n for n, v in cfg["factors"].items() if v["params"] is not None]
    say(f"start on {DEV}: {run['replicates']} replicates x {run['arms']}, {run['ticks']} ticks; factors on: {on or 'none (equilibrium baseline)'}")
    def opt(name):
        return args[args.index(name) + 1] if name in args else None
    w = World(cfg, founders(run["founders"], int(run["replicates"])), active)
    series, tree_rows = [], 0
    src_name = run["name"]
    branch_t, new_name, seed = opt("--from-tick"), opt("--as"), opt("--seed")
    if branch_t:                                         # BRANCH from another run's checkpoint
        ck = HERE / "results" / f"{src_name}_ckpt" / f"t{int(branch_t)}.pt"
        if not ck.exists():
            raise SystemExit(f"no checkpoint at tick {branch_t} for {src_name} (have: "
                             f"{sorted(p.stem for p in ck.parent.glob('t*.pt'))})")
        series, tree_rows = CK.load(w, ck, reseed=seed)
        run["name"] = new_name or f"{src_name}_from{branch_t}"
        import shutil
        src_tree = HERE / "results" / f"{src_name}_tree"; dst_tree = HERE / "results" / f"{run['name']}_tree"
        dst_tree.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_tree.glob("*.npz"))[:tree_rows]:
            shutil.copy(f, dst_tree / f.name)
        say(f"BRANCHED from {src_name} at tick {w.t} as {run['name']} ({'new seed ' + seed if seed else 'same random stream'})")
    elif "--fresh" not in args:                          # RESUME after an interruption
        ck = CK.latest(HERE / "results" / f"{src_name}_ckpt")
        done = (HERE / "results" / f"{src_name}.json").exists()
        if ck is not None and not done:
            series, tree_rows = CK.load(w, ck)
            say(f"RESUMED {src_name} from checkpoint at tick {w.t}")
    tree_dir = HERE / "results" / f"{run['name']}_tree"; ck_dir = HERE / "results" / f"{run['name']}_ckpt"

    def flush_tree():
        nonlocal tree_rows
        if not w.record_tree:
            return
        b = torch.cat(w.tree_log["births"]).numpy() if w.tree_log["births"] else np.zeros((0, 5), np.int64)
        d = torch.cat(w.tree_log["deaths"]).numpy() if w.tree_log["deaths"] else np.zeros((0, 3), np.int64)
        tree_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(tree_dir / f"part{tree_rows:05d}_t{w.t}.npz", births=b, deaths=d)
        w.tree_log = dict(births=[], deaths=[]); tree_rows += 1

    t0 = time.time()
    ctl = SimControl(run["name"], sync=(torch.cuda.synchronize if torch.cuda.is_available() else None))
    cke = int(run.get("checkpoint_every", 0))
    for t in range(w.t + 1, int(run["ticks"]) + 1):
        w.tick()
        ctl.after_tick(t, w.frame)
        if t % int(run["every"]) == 0:
            m = w.measure(); m["t"] = t; series.append(m)
            if t % (int(run["every"]) * 10) == 0 or t == int(run["ticks"]):
                R = int(run["replicates"]); A = len(run["arms"])
                pops = [sum(m["pop"][a * R:(a + 1) * R]) / R for a in range(A)]
                say(f"t {t:7d}  pop " + " / ".join(f"{a} {p:.0f}" for a, p in zip(run["arms"], pops)) + f"  ({time.time() - t0:.0f} s)")
        if cke and t % cke == 0 and t < int(run["ticks"]):
            flush_tree(); CK.save(w, series, tree_rows, ck_dir / f"t{t}.pt")
    flush_tree()
    out = HERE / "results" / f"{run['name']}.json"; out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(config=cfg, arms=run["arms"], replicates=int(run["replicates"]), ticks=int(run["ticks"]),
                                   founders=run["founders"], series=series, slots=int(cfg["world"]["slots"]))))
    say(f"saved {out.name}; analysing")
    import analyze
    analyze.main(str(out))
    say("RUN_DONE")


if __name__ == "__main__":
    main()
