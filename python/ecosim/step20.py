"""Step 20 = the MAIN EXPERIMENT (from 2026-11-13): does a more realistic connectome brain evolve better foragers?

Two realism upgrades to the C. elegans connectome brain (gpu_brains.Worm2Brain, switches in worm2.Opts):
  REVERSAL POTENTIALS  each chemical synapse's current = |w| x presynaptic activity x (E_rev - v_post).
                       Excitatory synapses push the target toward e_exc (+1), inhibitory ones (GABA, or any synapse
                       whose sign evolution flipped) toward e_inh (-1). Old model: current = w x activity, whatever
                       the target's voltage. At rest (v = 0) both give the same current, so the change is only in how
                       synapses saturate and shunt as neurons depolarise.
  MUSCLE OUTPUT        movement comes from the body: mean activation of the 95 body-wall muscles -> forward speed,
                       AVA minus AVB command activity -> reversals, dorsal minus ventral head muscles -> steering.
                       Old model: an evolved decoder reading 28 interneurons (it skipped the motor circuit entirely).

Design: a 2 x 2 factorial, 4 arms side by side, same 16 seeds (paired by seed), Step 19 world (scarce food,
6 predators, touch; hunger peptide on; fitness = energy at the end + survival) and Step 19 scoring (each brain = 60
clones in a full-size world). To fit by 19:00: 12 brains per seed, 1 world per generation, best brain saved every
10 generations, and evolution stops cleanly at the deadline (--until HHMM).
    s20_old     old synapses, decoder output           (= Step 19 base, smaller)
    s20_rev     reversal potentials, decoder output
    s20_mus     old synapses, muscle output
    s20_both    reversal potentials + muscle output

PRE-REGISTERED RULE (written 2026-11-13 15:50 MT, before any run):
  Yardstick = skill on 12 fixed unseen worlds (4000-4011), 60 clones each (step14.test), measured on each seed's
  best brain at the LAST checkpoint generation that all 4 arms reached.
  Main effect of a feature = mean over seeds of [(arms with it) - (arms without it)] / 2, paired by seed:
      reversal = ((rev - old) + (both - mus)) / 2         muscles = ((mus - old) + (both - rev)) / 2
  Sign-flip permutation test per effect, Holm-corrected over the 2 effects.
  A feature HELPS if its effect > 0 with Holm p < 0.05; HURTS if < 0 with Holm p < 0.05; otherwise no detectable
  effect at this length. Secondary (reported, not tested for the rule): interaction, learning curves, food, bites.
  Caveat stated in advance: ~150-250 generations is short; Step 19 skill was still rising at 300.

    python -m ecosim.step20 quick                  # 2 seeds x 4 brains x 2 gens per arm, CPU ok (seconds-minutes)
    python -m ecosim.step20 all [--until 1900] [--gens 1000]   # all 4 arms at once (the watcher job)
    python -m ecosim.step20 run <arm> [--until 1900] [--gens 1000]
    python -m ecosim.step20 analyze                # yardstick at the common checkpoint, stats, chart
Watcher: {"experiment": "connectome_main", "args": {"until": "1900"}}  (one EXCLUSIVE job: the 4 arms run as 4 worker
         processes at once; nothing else uses the GPU meanwhile; CANCEL stops all 4 within ~2 minutes, results kept)
Results: runs/step20/<arm>_s<seed>/ (ckpt_g<N>.npy every 10 gens, best_genome.npy, history.json),
         results/step20_stats.json + step20.png + step20_stats.txt
"""
import dataclasses
import datetime as _dt
import json
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14

SEEDS, BRAINS, WORLDS_PER_GEN, EVERY = list(range(1, 17)), 12, 1, 10
OUT, RES = Path('runs/step20'), Path('results')
import os as _os
if _os.environ.get('STEP20_TEST'):          # tiny settings to test the launcher end to end (also inherited by workers)
    SEEDS, BRAINS, EVERY, OUT = [1, 2], 2, 1, Path('runs/step20_test')
TEST_WORLDS = list(range(4000, 4012))
ARMS = {'s20_old': dict(reversal=False, muscle_out=False), 's20_rev': dict(reversal=True, muscle_out=False),
        's20_mus': dict(reversal=False, muscle_out=True), 's20_both': dict(reversal=True, muscle_out=True)}
for _c, _o in ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS['hunger'], fitness='end', **_o)
    CFG_OVERRIDES[_c] = dict(s14.PRED)


def deadline_from(until):
    """'1900' or '19:00' -> time.time() value today (tomorrow if already past); 'none' / None -> None."""
    if not until or until == 'none':
        return None
    u = until.replace(':', ''); now = _dt.datetime.now()
    dl = now.replace(hour=int(u[:-2]), minute=int(u[-2:]), second=0, microsecond=0)
    return (dl if dl > now else dl + _dt.timedelta(days=1)).timestamp()


def run(arm, gens=1000, until=None, seeds=None, out=None, brains=None, device='cuda', heartbeat=None):
    """heartbeat: a file the parent (run_all) touches every few seconds; if it goes stale for HEARTBEAT_STALE seconds
    the parent is gone (job cancelled / window closed) and this arm stops cleanly after its current generation."""
    import os, time
    from .batch3_fast import evolve
    seeds, out, brains = seeds or SEEDS, out or OUT, brains or BRAINS
    dl = deadline_from(until)
    def stop():
        if dl is not None and time.time() >= dl:
            return True
        return heartbeat is not None and (not os.path.exists(heartbeat) or time.time() - os.path.getmtime(heartbeat) > HEARTBEAT_STALE)
    evolve(arm, seeds, gens, out=out, device=device, checkpoint_every=EVERY, clonal=60, brains=brains,
           eval_worlds=WORLDS_PER_GEN, deadline=stop)


HEARTBEAT_STALE = 90


def run_all(gens=1000, until=None, out=None):
    """The watcher job: start the 4 arms as 4 worker processes AT THE SAME TIME (so they get equal GPU time and reach
    similar generations by the deadline), keep a heartbeat file fresh, and print each arm's progress every 2 minutes.
    If this process is stopped (watcher CANCEL), the heartbeat goes stale and every worker stops itself within about
    one generation + 90 s, saving its results. Worker logs: runs/step20/<arm>_log.txt."""
    import subprocess, time
    out = out or OUT
    out.mkdir(parents=True, exist_ok=True)
    hb = out / '_heartbeat'; hb.touch()
    procs = {}
    for a in ARMS:
        lf = open(out / f'{a}_log.txt', 'a')
        cmd = [sys.executable, '-u', '-m', 'ecosim.step20', 'run', a, '--gens', str(gens), '--heartbeat', str(hb)]
        if until:
            cmd += ['--until', until]
        procs[a] = (subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT), lf)
        print(f'started {a} (pid {procs[a][0].pid}): {" ".join(cmd[2:])}', flush=True)
    last = 0
    while any(p.poll() is None for p, _ in procs.values()):
        hb.touch(); time.sleep(5)
        if time.time() - last > 120:
            last = time.time()
            for a in ARMS:
                lines = [l for l in (out / f'{a}_log.txt').read_text(errors='ignore').splitlines() if ' gen ' in l]
                print(f'{time.strftime("%H:%M:%S")} {lines[-1] if lines else a + ": starting"}', flush=True)
    codes = {a: p.returncode for a, (p, _) in procs.items()}
    print('workers finished, exit codes', codes, flush=True)
    if any(codes.values()):
        raise SystemExit(f'a worker failed: {codes} (see runs/step20/<arm>_log.txt)')
    print('MAIN_EXPERIMENT_DONE', flush=True)


def signflip(d, n=20000, seed=0):
    d = np.asarray(d, float); rng = np.random.default_rng(seed)
    obs = abs(d.mean()); fl = rng.choice([-1, 1], size=(n, len(d)))
    return float(((np.abs((fl * d).mean(1)) >= obs - 1e-12).sum() + 1) / (n + 1))


def analyze(seeds=SEEDS, out=OUT):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    have = {a: min(max([int(p.stem[6:]) for p in (out / f'{a}_s{s}').glob('ckpt_g*.npy')] or [0]) for s in seeds)
            for a in ARMS}
    g_end = min(have.values())
    if g_end == 0:
        raise SystemExit(f'no common checkpoint yet: {have}')
    cks = sorted({EVERY, *range(50, g_end + 1, 50), g_end})
    Y = {}
    for a in ARMS:
        Y[a] = {g: s14.test(a, [np.load(out / f'{a}_s{s}' / f'ckpt_g{g}.npy') for s in seeds], conn, dev, TEST_WORLDS)
                for g in cks}
        print(a, 'yardstick skill:', {g: round(float(np.mean(Y[a][g]['fitness'])), 3) for g in cks}, flush=True)
    F = {a: np.asarray(Y[a][g_end]['fitness']) for a in ARMS}
    eff = {'reversal': ((F['s20_rev'] - F['s20_old']) + (F['s20_both'] - F['s20_mus'])) / 2,
           'muscles': ((F['s20_mus'] - F['s20_old']) + (F['s20_both'] - F['s20_rev'])) / 2,
           'interaction': (F['s20_both'] - F['s20_mus']) - (F['s20_rev'] - F['s20_old'])}
    p = {k: signflip(v) for k, v in eff.items()}
    order = sorted(['reversal', 'muscles'], key=lambda k: p[k])                       # Holm over the 2 main effects
    holm = {order[0]: min(1, 2 * p[order[0]]), order[1]: min(1, max(2 * p[order[0]], p[order[1]]))}
    lines = [f'Step 20 / Main Experiment: yardstick at generation {g_end} (common to all arms), {len(seeds)} seeds',
             'arm         skill    food   bites']
    for a in ARMS:
        r = Y[a][g_end]
        lines.append(f'{a:10s} {np.mean(r["fitness"]):6.3f}  {np.mean(r["food"]):6.2f}  {np.mean(r["bites"]):6.2f}')
    for k in ('reversal', 'muscles'):
        v = 'HELPS' if eff[k].mean() > 0 and holm[k] < 0.05 else 'HURTS' if eff[k].mean() < 0 and holm[k] < 0.05 else 'no detectable effect'
        lines.append(f'{k:9s} effect {eff[k].mean():+.3f}  (positive in {(eff[k] > 0).sum()}/{len(seeds)} seeds)  '
                     f'p={p[k]:.3g}  Holm p={holm[k]:.3g}  -> {v}')
    lines.append(f'interaction {eff["interaction"].mean():+.3f}  p={p["interaction"]:.3g} (secondary, not in the rule)')
    txt = '\n'.join(lines); print(txt)
    (RES / 'step20_stats.txt').write_text(txt + '\n')
    (RES / 'step20_stats.json').write_text(json.dumps(dict(
        g_end=g_end, checkpoints=cks, seeds=seeds, effects={k: v.tolist() for k, v in eff.items()}, p=p, holm=holm,
        yardstick={a: {str(g): {k: list(map(float, v)) for k, v in Y[a][g].items()} for g in cks} for a in ARMS})))
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    for a in ARMS:
        ax[0].plot(cks, [np.mean(Y[a][g]['fitness']) for g in cks], marker='o', label=a)
        h = [json.loads((out / f'{a}_s{s}' / 'history.json').read_text()) for s in seeds]
        n = min(len(x) for x in h)
        ax[1].plot(np.mean([[r['fitness'] for r in x[:n]] for x in h], 0), label=a)
    ax[0].set(title='Skill on 12 unseen worlds (yardstick)', xlabel='generation', ylabel='fitness')
    ax[1].set(title='Training fitness (mean over seeds)', xlabel='generation')
    for a_ in ax:
        a_.legend()
    fig.tight_layout(); fig.savefig(RES / 'step20.png', dpi=120)
    return eff, p, holm


def quick():
    """Smoke test: every arm, 2 seeds x 4 brains x 2 generations, small output folder. Checks the code runs."""
    import torch
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    for a in ARMS:
        run(a, gens=2, seeds=[1, 2], out=Path('runs/step20_quick'), brains=4, device=dev)


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[:1] == ['quick']:
        quick()
    elif a[:1] == ['run']:
        if len(a) < 2 or a[1] not in ARMS:
            raise SystemExit(f'arm must be one of {list(ARMS)}')
        run(a[1], gens=int(opt('--gens', 1000)), until=opt('--until'), heartbeat=opt('--heartbeat'))
    elif a[:1] == ['all']:
        run_all(gens=int(opt('--gens', 1000)), until=opt('--until'))
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
