"""Same jobs as sim.py (same seeds -> identical numbers), run in parallel across CPU cores.
Usage: python run_cpu.py [seeds] [gens] [workers]   -> results_cpu_<gens>g.json, progress in run_cpu_log.txt
SAFE TO INTERRUPT: results are only written at the end; an interrupted run just leaves no results file."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import json, sys, time
from multiprocessing import Pool
import numpy as np
import sim

def job(a):
    name, s, gens = a
    t = time.time()
    if name == "random_walk":
        c = dict(smell=1, H=8, plastic=0); b = np.zeros(sim.glen(c)); curve = []
    else:
        c = sim.CONDS[name]; curve = []
        b = sim.evolve(c, s, gens, log=curve)
    out = dict(name=name, seed=s, normal=sim.test(b, c, s, 30, sim.NPATCH), sparse=sim.test(b, c, s, 30, 2),
               curve=curve, genome=b.tolist(), sec=time.time() - t)
    with open("run_cpu_log.txt", "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {name} seed {s}: normal {out['normal']:.1f} sparse {out['sparse']:.1f} ({out['sec']:.0f} s)\n")
    return out

if __name__ == "__main__":
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    gens = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    jobs = [(n, s, gens) for n in sim.CONDS for s in range(seeds)] + [("random_walk", s, gens) for s in range(seeds)]
    open("run_cpu_log.txt", "w").write(f"{time.strftime('%H:%M:%S')} start: {len(jobs)} jobs, {seeds} seeds x {gens} gens, {workers} workers\n")
    t0 = time.time()
    with Pool(workers) as p:
        outs = p.map(job, jobs, chunksize=1)
    res = {}
    for o in outs:
        r = res.setdefault(o["name"], dict(normal=[], sparse=[], curves=[], genomes=[]))
        r["normal"].append(o["normal"]); r["sparse"].append(o["sparse"]); r["curves"].append(o["curve"]); r["genomes"].append(o["genome"])
    json.dump(res, open(f"results_cpu_{gens}g.json", "w"))
    with open("run_cpu_log.txt", "a") as f:
        for n, r in res.items():
            f.write(f"{n:26s} normal {np.mean(r['normal']):6.1f}  sparse {np.mean(r['sparse']):6.1f}\n")
        f.write(f"CPU_DONE in {time.time()-t0:.0f} s\n")
