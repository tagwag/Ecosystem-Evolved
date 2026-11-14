"""Step 22 = the REWARD HACKING EXPERIMENT (red light / green light).

GOAL (owner, 2026-11-13): evolve the worm brain to use the hunger-peptide channel as a COMMAND: stop on "red light",
go on "green light". It is the first step toward "sending instructions" to an evolved brain.
WHY THE NAME: the obvious way to fail is reward hacking - evolution scoring well by exploiting the scoring rule rather
than doing the task. Here the hack is "never move" (no red-light penalty, ever). That exact hack happened in Step 3e.
The experiment is built so the hack cannot win, and it measures whether it happened anyway.

THE TASK (config.py "Step 22", batch3_fast: RED)
  Time alternates between red and green phases of random length (30-100 ticks), different in every world and every
  generation. On red, moving costs energy (3.0 per tick at full speed; just living costs 0.6). On green, nothing
  special. The worm cannot see the phase. Its only cue is the broadcast peptide, whose level is now set from OUTSIDE:
  1 on red, 0 on green. (So in this experiment it is a command signal that reuses the hunger peptide's machinery -
  every neuron's evolvable receptor - not a hunger signal. Evolution has to turn "peptide high" into "stop".)
  World, brain and scoring otherwise = Main Experiment / Step 19: connectome brain (old synapses + decoder output),
  scarce food, 6 predators, touch, fitness = energy at the end + survival, 60 clones per brain, 12 brains per seed.

WHY "NEVER MOVE" CANNOT WIN
  A worm that never moves eats nothing, starves at tick ~1000 of 1500 and scores about 0.67; foraging worms score 2-3.
  Fitness is energy at the END (not energy held on average, the Step 3e flaw). The only way to do well is to move on
  green AND hold still on red.

ARMS (3, same 16 seeds, paired by seed, run side by side)
  s22_signal     peptide = the true red/green phase                  (can the command be learned?)
  s22_scrambled  peptide = a different random schedule               (same penalty, useless signal: the control)
  s22_nosignal   no peptide receptors at all                          (same penalty, no channel)

PRE-REGISTERED RULES (written 2026-11-13 21:40 MT, before any run)
  Yardstick: each seed's best brain at the last common checkpoint, 60 clones on 12 fixed unseen worlds (6000-6011)
  with UNSEEN TIMING: phases of 10-250 ticks instead of 30-100.
  GO/NO-GO INDEX = (speed on green - speed on red) / (speed on green + speed on red): 0 = ignores the light,
  1 = full speed on green and still on red.
  1. COMMAND LEARNED if the signal arm's index is higher than BOTH controls' (paired sign-flip tests, Holm over the
     two comparisons, p < 0.05).
  2. OBEDIENCE (is it really following the peptide?): the signal arm's own brains re-tested with a SCRAMBLED peptide
     must lose the index (paired sign-flip, p < 0.05). If the index survives, they found some other cue.
  3. REWARD HACKING CHECK: a seed is "hacked" if its green-light speed is below 0.10 (it just sits). The experiment
     passes this check if at most 2 of 16 signal-arm seeds are hacked, and reports the count for every arm.
  4. Reported: skill (fitness) per arm - an honest signal should also raise skill over the controls.
  Stated in advance: this shows an EVOLVED REFLEX to an outside signal, not learning within a lifetime.

    python -m ecosim.step22 all [--gens 300] [--until HHMM]   # the 3 arms at once (the watcher job)
    python -m ecosim.step22 run <arm> [--gens 300]
    python -m ecosim.step22 analyze
    python -m ecosim.step22 check --test    # tiny version (2 seeds, 2 generations, all arms) + analysis: the code
                                            # check, run on the workstation (watcher: reward_hacking_check)
Watcher: {"experiment": "reward_hacking_experiment"} then {"experiment": "reward_hacking_analyze"}
Results: runs/step22/<arm>_s<seed>/ (ckpt_g<N>.npy every 20 gens, best_genome.npy, history.json with speed_red /
         speed_green per generation), worker logs runs/step22/<arm>_log.txt,
         results/step22_stats.json + step22_stats.txt + step22.png
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

from .step3 import CONDITIONS, CFG_OVERRIDES
from . import step14 as s14
from .step20 import deadline_from, signflip

SEEDS, BRAINS, GENS, EVERY = list(range(1, 17)), 12, 300, 20
OUT, RES = Path('runs/step22'), Path('results')
TEST_WORLDS = list(range(6000, 6012))
TEST_TIMING = dict(red_min=1, red_max=25)            # unseen timing for the yardstick: 10-250 tick phases
HEARTBEAT_STALE = 90
if os.environ.get('STEP22_TEST') or '--test' in sys.argv:
    os.environ['STEP22_TEST'] = '1'                      # worker processes inherit the test settings
    SEEDS, BRAINS, EVERY, OUT, TEST_WORLDS = [1, 2], 2, 1, Path('runs/step22_test'), [6000, 6001]
ARMS = {'s22_signal': ('hunger', 'true'), 's22_scrambled': ('hunger', 'scrambled'), 's22_nosignal': ('nohunger', 'true')}
for _c, (_base, _sig) in ARMS.items():
    CONDITIONS[_c] = dataclasses.replace(CONDITIONS[_base], fitness='end')
    CFG_OVERRIDES[_c] = dict(s14.PRED, redlight=True, red_signal=_sig)


def run(arm, gens=GENS, until=None, heartbeat=None, device='cuda'):
    """One arm. Stops cleanly at `until` or when the launcher's heartbeat file goes stale (job cancelled)."""
    import time
    from .batch3_fast import evolve
    dl = deadline_from(until)
    def stop():
        if dl is not None and time.time() >= dl:
            return True
        return heartbeat is not None and (not os.path.exists(heartbeat) or time.time() - os.path.getmtime(heartbeat) > HEARTBEAT_STALE)
    evolve(arm, SEEDS, gens, out=OUT, device=device, checkpoint_every=EVERY, clonal=60, brains=BRAINS, eval_worlds=1,
           deadline=stop)


def run_all(gens=GENS, until=None):
    """The watcher job: the 3 arms as 3 worker processes at the same time (equal GPU time). Same launcher design as
    step20.run_all: a heartbeat file lets the workers stop themselves if this process is cancelled."""
    import subprocess, time
    OUT.mkdir(parents=True, exist_ok=True)
    hb = OUT / '_heartbeat'; hb.touch()
    procs = {}
    for a in ARMS:
        lf = open(OUT / f'{a}_log.txt', 'a')
        cmd = [sys.executable, '-u', '-m', 'ecosim.step22', 'run', a, '--gens', str(gens), '--heartbeat', str(hb)]
        if until and until != 'none':
            cmd += ['--until', until]
        procs[a] = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        print(f'started {a} (pid {procs[a].pid})', flush=True)
    last = 0
    while any(p.poll() is None for p in procs.values()):
        hb.touch(); time.sleep(5)
        if time.time() - last > 120:
            last = time.time()
            for a in ARMS:
                lines = [l for l in (OUT / f'{a}_log.txt').read_text(errors='ignore').splitlines() if ' gen ' in l]
                print(f'{time.strftime("%H:%M:%S")} {lines[-1] if lines else a + ": starting"}', flush=True)
    codes = {a: p.returncode for a, p in procs.items()}
    print('workers finished, exit codes', codes, flush=True)
    if any(codes.values()):
        raise SystemExit(f'a worker failed: {codes} (see runs/step22/<arm>_log.txt)')
    print('REWARD_HACKING_EXPERIMENT_DONE', flush=True)


def test(arm, genomes, conn, dev, signal=None, worlds=None):
    """Genomes as 60 clones on the test worlds with the unseen timing. signal: override the arm's peptide signal
    ('true' / 'scrambled') for the obedience test. Returns {measure: array (n_genomes,)}."""
    import torch
    from .batch3_fast import FastSim
    from .config import Config
    worlds = worlds or TEST_WORLDS
    ov = dict(CFG_OVERRIDES[arm], **TEST_TIMING)
    if signal:
        ov['red_signal'] = signal
    opts, cfg = CONDITIONS[arm], Config(**ov)
    P, keys = cfg.worm_population, ('mean_food', 'speed_red', 'speed_green', 'bites')
    out = {k: [] for k in ('fitness',) + keys}
    for i in range(0, len(genomes), 32):
        gs = genomes[i:i + 32]
        pairs = [(j, wd) for j in range(len(gs)) for wd in worlds]
        G = np.stack([np.repeat(gs[j][None], P, 0) for j, _ in pairs])
        gen = torch.Generator(device=dev); gen.manual_seed(4242)
        fit, st = FastSim(cfg, opts, conn, len(pairs), P, dev, False, gen).run(G, [np.random.default_rng(w) for _, w in pairs])
        nw = len(worlds)
        out['fitness'] += fit.mean(1).reshape(len(gs), nw).mean(1).tolist()
        for k in keys:
            out[k] += np.array([x[k] for x in st]).reshape(len(gs), nw).mean(1).tolist()
    r = {k: np.array(v) for k, v in out.items()}
    r['index'] = (r['speed_green'] - r['speed_red']) / np.maximum(r['speed_green'] + r['speed_red'], 1e-9)
    return r


def analyze():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .connectome import Connectome
    from .worm2_gpu import pick_device
    RES.mkdir(exist_ok=True)
    dev, conn = pick_device('cuda'), Connectome()
    have = {a: min(max([int(p.stem[6:]) for p in (OUT / f'{a}_s{s}').glob('ckpt_g*.npy')] or [0]) for s in SEEDS) for a in ARMS}
    g_end = min(have.values())
    if g_end == 0:
        raise SystemExit(f'no common checkpoint yet: {have}')
    load = lambda a: [np.load(OUT / f'{a}_s{s}' / f'ckpt_g{g_end}.npy') for s in SEEDS]
    Y = {a: test(a, load(a), conn, dev) for a in ARMS}
    obey = test('s22_signal', load('s22_signal'), conn, dev, signal='scrambled')
    sig = Y['s22_signal']
    d1, d2 = sig['index'] - Y['s22_scrambled']['index'], sig['index'] - Y['s22_nosignal']['index']
    p1, p2 = signflip(d1), signflip(d2)
    h = sorted([p1, p2]); holm = min(1.0, max(2 * h[0], h[1]))            # both must pass: the larger Holm-adjusted p
    learned = d1.mean() > 0 and d2.mean() > 0 and holm < 0.05
    d3 = sig['index'] - obey['index']; p3 = signflip(d3)
    hacked = {a: int((Y[a]['speed_green'] < 0.10).sum()) for a in ARMS}
    lines = [f'Step 22 / Reward Hacking experiment: yardstick at generation {g_end}, {len(SEEDS)} seeds, unseen timing',
             'arm            go/no-go index   speed green   speed red   skill    food   hacked seeds (green speed < 0.10)']
    for a in ARMS:
        r = Y[a]
        lines.append(f'{a:14s} {r["index"].mean():+.3f}           {r["speed_green"].mean():.3f}         {r["speed_red"].mean():.3f}       '
                     f'{r["fitness"].mean():.3f}   {r["mean_food"].mean():.2f}   {hacked[a]}/{len(SEEDS)}')
    lines += [f'1. COMMAND LEARNED: signal - scrambled = {d1.mean():+.3f} (higher in {(d1 > 0).sum()}/{len(SEEDS)}, p={p1:.3g}); '
              f'signal - nosignal = {d2.mean():+.3f} (higher in {(d2 > 0).sum()}/{len(SEEDS)}, p={p2:.3g}); Holm p={holm:.3g} -> {"YES" if learned else "NO"}',
              f'2. OBEDIENCE: signal-arm brains with a scrambled peptide: index {obey["index"].mean():+.3f} (drop {d3.mean():+.3f}, p={p3:.3g}) -> '
              f'{"follows the peptide" if d3.mean() > 0 and p3 < 0.05 else "NOT shown to follow the peptide"}',
              f'3. REWARD HACKING CHECK: {hacked["s22_signal"]}/{len(SEEDS)} signal-arm seeds just sit still -> {"PASS" if hacked["s22_signal"] <= 2 else "FAIL"}',
              f'4. skill: signal - scrambled = {(sig["fitness"] - Y["s22_scrambled"]["fitness"]).mean():+.3f} '
              f'(p={signflip(sig["fitness"] - Y["s22_scrambled"]["fitness"]):.3g}), signal - nosignal = '
              f'{(sig["fitness"] - Y["s22_nosignal"]["fitness"]).mean():+.3f} (p={signflip(sig["fitness"] - Y["s22_nosignal"]["fitness"]):.3g})']
    txt = '\n'.join(lines); print(txt)
    (RES / 'step22_stats.txt').write_text(txt + '\n')
    (RES / 'step22_stats.json').write_text(json.dumps(dict(
        g_end=g_end, seeds=SEEDS, hacked=hacked, p=dict(vs_scrambled=p1, vs_nosignal=p2, holm=holm, obedience=p3),
        yardstick={a: {k: v.tolist() for k, v in Y[a].items()} for a in ARMS},
        obedience={k: v.tolist() for k, v in obey.items()})))
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    for a in ARMS:
        hs = [json.loads((OUT / f'{a}_s{s}' / 'history.json').read_text()) for s in SEEDS]
        n = min(len(x) for x in hs)
        g = np.mean([[r['speed_green'] for r in x[:n]] for x in hs], 0); r_ = np.mean([[r['speed_red'] for r in x[:n]] for x in hs], 0)
        ax[0].plot((g - r_) / np.maximum(g + r_, 1e-9), label=a)
        ax[1].plot(np.mean([[r['fitness'] for r in x[:n]] for x in hs], 0), label=a)
    ax[0].set(title='Go/no-go index during training (1 = go on green, still on red)', xlabel='generation')
    ax[1].set(title='Training fitness', xlabel='generation')
    for a_ in ax:
        a_.legend()
    fig.tight_layout(); fig.savefig(RES / 'step22.png', dpi=120)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--test']
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[:1] == ['full']:                       # the watcher job: the 3 arms, then the analysis
        run_all(gens=int(opt('--gens', GENS)), until=opt('--until')); analyze(); print('REWARD_HACKING_FULL_DONE', flush=True)
    elif a[:1] == ['check']:                      # workstation code check: tiny run of all arms + the analysis
        run_all(gens=2); analyze()
        print('REWARD_HACKING_CHECK_OK', flush=True)
    elif a[:1] == ['all']:
        run_all(gens=int(opt('--gens', GENS)), until=opt('--until'))
    elif a[:1] == ['run']:
        if len(a) < 2 or a[1] not in ARMS:
            raise SystemExit(f'arm must be one of {list(ARMS)}')
        import torch
        run(a[1], gens=int(opt('--gens', GENS)), until=opt('--until'), heartbeat=opt('--heartbeat'),
            device='cuda' if torch.cuda.is_available() else 'cpu')
    elif a[:1] == ['analyze']:
        analyze()
    else:
        print(__doc__)
