"""Step 28 = CORRIDOR COMBINATION SCREEN (2026-11-16): which COMBINATIONS of removed neurons break navigation?
Owner's definition of a stable worm: it can still navigate to one piece of food down a corridor of a fair length.

THE TEST (config.py "Step 28", batch3_fast corridor mode)
  Each world = ONE combination of removed neurons. In it, one corridor per screen brain (400 units long, 40 wide,
  sliding walls), one worm per corridor: each worm is a different evolved brain (best brain of a Step 23 control
  seed), all with the same neurons removed. Each worm starts at the closed end with a random heading; one food at the
  far end. Smell only reaches the last ~256 units, so the first ~150 units must be crossed without smell. No predators,
  no regrowth. A brain NAVIGATES if it gets within 20 units of its food before the time limit.
  Each combination is tested ONCE, as the owner asked. Removal = activity held at 0 + all gap junctions cut
  (gpu_brains.Worm2Brain.set_knockout_mask), separately per world.

BRAINS:  --brains 4 (DEFAULT, owner's choice 2026-11-16 07:59): the 4 most reliable navigating brains per
         combination (fewer worms per combination = about 4x faster than 16, a bit noisier).
         --brains 16: every Step 23 control brain that navigates when intact.
         Outputs go to runs/step28/b<N>/ so both versions can coexist.

SPEED-UPS (2026-11-16, owner approved 1-4; none changes what counts as a failure)
  1 corridor mode does no unneeded work: 1 food slot per corridor, smell map built once (food never moves),
    no nearest-neighbour bookkeeping (worms are walled apart).
  2 SILENT neurons (|v| never above 1e-4 in any intact brain during calibration) are dropped from the TRIPLES only.
    Singles and pairs keep all 300 neurons, which also checks the assumption: the report says whether any single or
    pair containing a silent neuron broke navigation.
  3 TIME LIMIT from calibration: 2 x the tick by which 95 % of intact successful arrivals happened, rounded up to 10,
    at most 600 (calibration itself runs 600).
  4 combinations that contain an already-broken single (or, for triples, an already-broken pair) are not tested:
    they are recorded as broken (code 255). Silent-neuron skips are code 254.

CONTINUOUS REFILL (owner's design, 2026-11-16 08:29): the GPU holds K worlds ("cups") at once. A world is DECIDED as
  soon as its verdict is certain: STABLE the moment ceil(N/2) of its N worms have reached their food, UNSTABLE when it
  reaches the time limit. Every 20 ticks each decided cup records its result and immediately starts the next untested
  combination from one shared queue (the whole phase's list), so no cup ever waits for the slowest one. Results are
  saved every few minutes; on a stop, finished combinations are kept and only the in-flight ones are re-tested.
  Stored count for a stable combination = arrivals at decision time (>= ceil(N/2)); unstable = arrivals by the limit.

PHASES (one job, resumes where it stopped)
  calibrate  64 worlds of intact brains (different random headings), 600 ticks; records arrival times and |v| maxima.
             Saved in calibration.json. CORRIDOR LENGTH = 150 units with ONE piece of food (owner's choice, 2026-11-16
             09:45, after results/step28_corridor_calibration.txt: at 400 / 300 / 200 / 150 units intact brains arrived
             in 2-3 / 8 / 49 / 74 % of tries; 1500 ticks did not help because worms run out of energy before ~600;
             a 20-food patch did no better). Screen brains = the most reliable navigating brains (>= 95 % if enough).
  singles, pairs, triples, then confirm: every TESTED unstable pair / triple with no broken part inside is re-tested
             5 more times (new headings); CONFIRMED if unstable in at least 4 of the 6 tests.

PRE-REGISTERED RULES (written 2026-11-16 08:40 MT, before any run; speed-ups added 09:05 MT, also before any run)
  Navigating brain = reaches the food in >= 75 % of the 64 intact tries (calibration, 600 ticks).
  A combination is UNSTABLE if fewer than half of the screen brains reach their food.
  False-alarm rate = share of the 64 intact worlds the rule flags (with the screen brains and the time limit);
  must be below 2 %, else the results are marked as noisy.
  EPISTASIS = an unstable pair whose singles are both stable, or an unstable triple with no unstable single or pair
  inside it.

    python -m ecosim.step28 full [--brains 16]         # all phases, every triple (watcher: combo_screen = 4 brains,
                                                       #   combo_screen16 = 16 brains)
    python -m ecosim.step28 analyze [--brains 16]
    python -m ecosim.step28 check --test               # tiny version (watcher: combo_check)
Results: runs/step28/b<N>/ (calibration.json, <phase>_pass.npy, <phase>_progress.json incl. measured speed,
         confirm.json), results/step28_b<N>_stats.txt, results/step28_b<N>_epistasis.csv
"""
import itertools
import json
import os
import sys
import time
from math import comb
from pathlib import Path

import numpy as np

TAU_ = 2 * np.pi

from . import step23 as s23            # registers s23_ctrl
from .step3 import CONDITIONS, CFG_OVERRIDES

ARM, SRC = 's23_ctrl', Path('runs/step23')
ALL_SEEDS = list(range(1, 17))
NB = int(sys.argv[sys.argv.index('--brains') + 1]) if '--brains' in sys.argv else 4   # owner's choice, 2026-11-16
OUT, RES = Path('runs/step28') / f'b{NB}', Path('results')
WORMS_PER_BATCH, CAL_WORLDS, CONFIRM_N, CAL_TICKS = 16384, 64, 5, 600
SILENT_V = 1e-4
TEST = bool(os.environ.get('STEP28_TEST')) or '--test' in sys.argv
LIMITS = {}
if TEST:
    ALL_SEEDS, OUT, WORMS_PER_BATCH, CAL_WORLDS, CONFIRM_N = [1, 2, 3, 4], Path('runs/step28_test') / f'b{NB}', 256, 16, 2
    LIMITS = dict(pairs=120, triples=120)        # all 300 singles (cheap), so every neuron has a single result
SKIP_BROKEN, SKIP_SILENT, PENDING = 255, 254, 253
REFILL_EVERY = 2                        # blocks of 10 ticks between refills (20 ticks)
SAVE_EVERY_S = 120                      # seconds between progress saves
CFG = dict(CFG_OVERRIDES[ARM], gravity=False, magnetism=False, field_circles=False, predators=0,
           food_regrow_per_tick=0.0, corridor=True)


def calcompare():
    """Owner's choice 2026-11-16 09:45: compare corridor variants on intact brains before fixing the screen's
    definition. 64 worlds x 16 brains each. Results -> results/step28_corridor_calibration.txt."""
    variants = [('one piece, 300 units, 600 ticks (as built)', dict(length=300.0, ticks=600, food=1)),
                ('one piece, 200 units, 600 ticks', dict(length=200.0, ticks=600, food=1)),
                ('one piece, 150 units, 600 ticks', dict(length=150.0, ticks=600, food=1)),
                ('one piece, 300 units, 1500 ticks', dict(length=300.0, ticks=1500, food=1)),
                ('patch of 20, 300 units, 600 ticks', dict(length=300.0, ticks=600, food=20)),
                ('patch of 20, 400 units, 600 ticks', dict(length=400.0, ticks=600, food=20)),
                ('patch of 20, 400 units, 1500 ticks', dict(length=400.0, ticks=1500, food=20))]
    L = [f'Step 28 corridor calibration comparison: intact brains (Step 23 control, seeds {ALL_SEEDS}), '
         f'{CAL_WORLDS} worlds each', 'variant                                  arrive  per brain (sorted)       '
         'brains >=75 %  >=95 %  median / 95th arrival tick']
    for name, v in variants:
        global CFG
        CFG0 = CFG
        CFG = dict(CFG0, corridor_food=v['food'])
        sc = Screen(ALL_SEEDS, v['length'], v['ticks'])
        CFG = CFG0
        arr = sc.arrivals([()] * CAL_WORLDS); ok = arr < v['ticks']; rate = ok.mean(0)
        succ = arr[ok]
        L.append(f'{name:40s} {ok.mean():6.1%}  {" ".join(f"{r:.2f}" for r in sorted(rate, reverse=True)[:8])}...  '
                 f'{(rate >= 0.75).sum():5d}   {(rate >= 0.95).sum():5d}    '
                 + (f'{np.median(succ):.0f} / {np.percentile(succ, 95):.0f}' if len(succ) else '-'))
        print(L[-1], flush=True)
    RES.mkdir(exist_ok=True)
    (RES / 'step28_corridor_calibration.txt').write_text('\n'.join(L) + '\n')
    print('\n'.join(L)); print('CORRIDOR_CALIBRATION_DONE', flush=True)


class Screen:
    """A corridor simulator for a fixed set of brains (one corridor each), reused for every batch of combinations."""
    def __init__(self, seeds, length, ticks, track=False):
        import torch
        from .batch3_fast import FastSim
        from .config import Config
        from .connectome import Connectome, _is_muscle
        from .worm2_gpu import pick_device
        self.dev, self.conn = pick_device('cuda'), Connectome()
        self.P = len(seeds)
        self.cfg = Config(**dict(CFG, corridor_len=length, ticks_per_generation=ticks, worm_population=self.P))
        self.N = self.conn.N
        self.neurons = [i for i, n in enumerate(self.conn.names) if not _is_muscle(n)]
        self.K = max(1, WORMS_PER_BATCH // self.P)
        g = np.stack([np.load(SRC / f'{ARM}_s{s}' / 'best_genome.npy') for s in seeds]).astype(np.float32)
        self.G = np.ascontiguousarray(np.broadcast_to(g[None], (self.K,) + g.shape))
        self.gen = torch.Generator(device=self.dev); self.gen.manual_seed(2828)
        self.sim = FastSim(self.cfg, CONDITIONS[ARM], self.conn, self.K, self.P, self.dev, self.dev.type == 'cuda', self.gen)
        self.sim.brain.enable_knockout()
        if track:
            self.sim.brain.vmax = torch.zeros(self.N, dtype=torch.float32, device=self.dev)
        self.calls, self.worlds_run, self.seconds = 0, 0, 0.0

    def arrivals(self, combos):
        """combos: list of tuples of positions in self.neurons. Returns (n, P) arrival ticks (= ticks if never)."""
        out = []
        for i in range(0, len(combos), self.K):
            chunk = combos[i:i + self.K]
            m = np.ones((self.K, self.P, self.N), np.float32)
            for w, c in enumerate(chunk):
                if c:
                    m[w, :, [self.neurons[j] for j in c]] = 0.0
            self.sim.brain.set_knockout_mask(m.reshape(self.K * self.P, self.N))
            rng = [np.random.default_rng((self.calls, w)) for w in range(self.K)]
            self.calls += 1
            t0 = time.time()
            _, st = self.sim.run(self.G, rng)
            self.seconds += time.time() - t0; self.worlds_run += len(chunk)
            out.append(np.array([s['corr_arrival'] for s in st[:len(chunk)]]))
        return np.concatenate(out) if out else np.zeros((0, self.P))


def _stream(sc, combos, save_cb):
    """Continuous-refill run of a list of combinations (tuples of positions in sc.neurons) through sc's K worlds.
    Returns counts (n,) int: worms that reached their food (at decision time). save_cb(counts_so_far, done_mask)
    is called every SAVE_EVERY_S seconds and at the end."""
    import torch
    sim, b, K, P, N = sc.sim, sc.sim.brain, sc.K, sc.P, sc.N
    Q = len(combos)
    if Q == 0:
        return np.zeros(0, int)
    dev, T = sc.dev, float(sc.cfg.ticks_per_generation)
    need = (len(cal_brains(sc)) + 1) // 2
    ids = np.array([[sc.neurons[j] for j in (c + (c[-1],) * (3 - len(c)))] for c in combos], np.int64)   # pad to 3
    qcomb = torch.as_tensor(ids, device=dev)
    qres = torch.full((Q + 1,), -1, dtype=torch.int16, device=dev)      # last slot = dump for inactive worlds
    # first K combinations through a normal run (captures the CUDA graph); extra worlds stay intact and inactive
    first = min(K, Q)
    m = np.ones((K, P, N), np.float32)
    for w in range(first):
        m[w, :, ids[w]] = 0.0
    b.set_knockout_mask(m.reshape(K * P, N))
    wcombo = torch.as_tensor(np.r_[np.arange(first), -np.ones(K - first)].astype(np.int64), device=dev)
    qptr = torch.tensor(first, dtype=torch.int64, device=dev)
    sim.run(sc.G, [np.random.default_rng((sc.calls, w)) for w in range(K)]); sc.calls += 1
    pos0 = sim.goal.clone(); pos0[..., 0] = 100.0
    prev0 = sim._smell_at(pos0)
    H0 = max(0.0, 1.0 - sc.cfg.start_energy / sim.gut_cap)
    step = sim.graph.replay if sim.graph is not None else sim._block
    t0 = tsave = time.time(); blocks = 0

    def refill():
        narr = (sim.carr < T).sum(1)
        act = wcombo >= 0
        fin = act & ((narr >= need) | (sim.wage >= T))
        qres.scatter_(0, torch.where(fin, wcombo, torch.full_like(wcombo, Q)), narr.to(torch.int16))
        order = torch.cumsum(fin.long(), 0) - 1
        newc = qptr + order
        valid = fin & (newc < Q)
        wcombo.copy_(torch.where(fin, torch.where(valid, newc, torch.full_like(newc, -1)), wcombo))
        qptr.add_(fin.long().sum())
        vm = valid[:, None]
        z = torch.zeros((), device=dev)
        sim.pos.copy_(torch.where(vm[..., None], pos0, sim.pos))
        sim.heading.copy_(torch.where(vm, sim._rand(K, P) * TAU_, sim.heading))
        for name, val in (('energy', sc.cfg.start_energy), ('size', sc.cfg.start_size), ('H', H0), ('eaten', 0.0),
                          ('lifetime', 0.0), ('esum', 0.0), ('stomach', 0.0), ('carr', T), ('touchF', 0.0),
                          ('touchB', 0.0), ('bump', 0.0)):
            x = getattr(sim, name); x.copy_(torch.where(vm, z + val, x))
        sim.alive.copy_(sim.alive | vm)
        sim.prev.copy_(torch.where(vm, prev0, sim.prev))
        sim.falive.copy_(sim.falive | vm)
        sim.wage.copy_(torch.where(valid, z, sim.wage))
        rows = vm.expand(K, P).reshape(-1)[:, None]
        b.v.copy_(torch.where(rows, z, b.v)); b.rbar.copy_(torch.where(rows, z, b.rbar))
        b.ko.copy_(torch.where(rows, z + 1.0, b.ko))
        idx = qcomb[newc.clamp(0, Q - 1)][:, None, :].expand(K, P, 3)
        kv = b.ko.view(K, P, N)
        kv.scatter_(2, idx, torch.where(valid[:, None, None], z, kv.gather(2, idx)))
        b.gdeg_b.copy_(torch.where(rows, b.G_deg[None, :] - (1.0 - b.ko) @ b.G, b.gdeg_b))

    while True:
        refill()
        for _ in range(REFILL_EVERY):
            sim.bi.zero_()                        # (block counter only indexes the regrowth schedule; none here)
            step()
        blocks += REFILL_EVERY
        if time.time() - tsave > SAVE_EVERY_S or blocks % 20 == 0:
            if bool((qptr >= Q).item()) and bool((wcombo < 0).all().item()):
                break
            if time.time() - tsave > SAVE_EVERY_S:
                r = qres[:Q].cpu().numpy(); save_cb(r, r >= 0); tsave = time.time()
    refill()
    r = qres[:Q].cpu().numpy()
    sc.seconds += time.time() - t0; sc.worlds_run += Q
    save_cb(r, r >= 0)
    return r.astype(int)


def cal_brains(sc):
    return list(range(sc.P))


def calibrate():
    f = OUT / 'calibration.json'
    if f.exists():
        return json.loads(f.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for length in (150.0,):                  # owner's choice 2026-11-16 09:45 after the variant comparison
        sc = Screen(ALL_SEEDS, length, CAL_TICKS, track=True)
        arr = sc.arrivals([()] * CAL_WORLDS)                          # (worlds, 16)
        ok = arr < CAL_TICKS
        rate, overall = ok.mean(0), float(ok.mean())
        print(f'calibration, corridor {length:.0f}: intact brains arrive in {overall:.1%} of tries; per brain '
              + ' '.join(f'{r:.2f}' for r in rate), flush=True)
        if overall >= 0.75 or length == 300.0:
            break
    nav = [i for i in range(len(ALL_SEEDS)) if rate[i] >= 0.75]
    if NB < len(nav) and sum(rate[i] >= 0.95 for i in nav) >= NB:   # prefer brains that pass >= 95 % when intact
        nav = [i for i in nav if rate[i] >= 0.95]
    if NB < len(nav):                                                   # the most reliable NB navigating brains
        nav = sorted(sorted(nav, key=lambda i: -rate[i])[:NB])
    succ = arr[:, nav][ok[:, nav]]
    p95 = float(np.percentile(succ, 95)) if len(succ) else CAL_TICKS / 2
    limit = int(min(CAL_TICKS, max(50, np.ceil(2 * p95 / 10) * 10)))
    fa = float(((arr[:, nav] < limit).sum(1) < len(nav) / 2).mean()) if nav else float('nan')
    vmax = sc.sim.brain.vmax.cpu().numpy()
    silent = [j for j, n in enumerate(sc.neurons) if vmax[n] < SILENT_V]
    cal = dict(length=length, overall=overall, per_brain=rate.tolist(), all_seeds=ALL_SEEDS,
               screen_brains=[ALL_SEEDS[i] for i in nav], arrival_p50=float(np.median(succ)) if len(succ) else None,
               arrival_p95=p95, limit=limit, false_alarm=fa,
               silent=[sc.conn.names[sc.neurons[j]] for j in silent], silent_pos=silent)
    f.write_text(json.dumps(cal, indent=1))
    print(f'screen brains {cal["screen_brains"]}; intact arrival median {cal["arrival_p50"]} / 95th {p95:.0f} ticks '
          f'-> time limit {limit}; false-alarm rate {fa:.1%}; silent neurons {len(silent)} of {len(sc.neurons)}', flush=True)
    return cal


def broken(code, nb):
    """Per-combination 'navigation broken' from stored codes (number of screen brains that arrived, or a skip code)."""
    code = np.asarray(code)
    return (code == SKIP_BROKEN) | ((code < PENDING) & (code < nb / 2))


def run_phase(sc, cal, phase):
    """Mark skips (codes 255 / 254), then stream every still-pending combination through the GPU with continuous
    refill. Resumes: combinations already holding a result are not re-tested."""
    k = dict(singles=1, pairs=2, triples=3)[phase]
    n = len(sc.neurons)
    total = min(comb(n, k), LIMITS.get(phase, comb(n, k)))
    f, pf = OUT / f'{phase}_pass.npy', OUT / f'{phase}_progress.json'
    new = not f.exists()
    res = np.lib.format.open_memmap(f, mode='w+' if new else 'r+', dtype=np.uint8, shape=(total,))
    if new:
        res[:] = PENDING
    prog = json.loads(pf.read_text()) if pf.exists() else dict(tested=0, seconds=0.0)
    nb = len(cal['screen_brains'])
    bad1 = broken(np.load(OUT / 'singles_pass.npy'), nb) if k > 1 else np.zeros(n, bool)
    bad2 = set()
    if k == 3:
        bad2 = {p for p, b in zip(itertools.combinations(range(n), 2), broken(np.load(OUT / 'pairs_pass.npy'), nb)) if b}
    silent = set(cal['silent_pos']) if k == 3 else set()
    todo_i, todo_c = [], []
    for i, c in enumerate(itertools.islice(itertools.combinations(range(n), k), total)):
        if res[i] != PENDING:
            continue
        if any(bad1[x] for x in c) or (k == 3 and any(q in bad2 for q in itertools.combinations(c, 2))):
            res[i] = SKIP_BROKEN
        elif silent and any(x in silent for x in c):
            res[i] = SKIP_SILENT
        else:
            todo_i.append(i); todo_c.append(c)
    res.flush()
    todo_i = np.array(todo_i, dtype=np.int64)
    print(f'{phase}: {total:,} combinations, {len(todo_i):,} still to test '
          f'({(res == SKIP_BROKEN).sum():,} contain a broken part, {(res == SKIP_SILENT).sum():,} a silent neuron)', flush=True)
    t0, sec0, tested0 = time.time(), prog['seconds'], prog['tested']

    def save(r, ok):
        res[todo_i[ok]] = np.clip(r[ok], 0, 252).astype(np.uint8); res.flush()
        el = sec0 + time.time() - t0
        p = dict(tested=tested0 + int(ok.sum()), seconds=el, total=total, remaining=int((res == PENDING).sum()))
        p['combos_per_s'] = (p['tested'] - tested0) / max(time.time() - t0, 1e-9)
        pf.write_text(json.dumps(p))
        print(f'{phase}: {int(ok.sum()):,}/{len(todo_i):,} tested this run, {p["combos_per_s"]:.0f} combos/s, '
              f'{el / 60:.1f} min, ~{(len(todo_i) - ok.sum()) / max(p["combos_per_s"], 1e-9) / 60:.0f} min left', flush=True)

    _stream(sc, todo_c, save)


def candidates(cal, n):
    """TESTED unstable pairs with stable singles, and TESTED unstable triples (skips already exclude broken parts)."""
    nb = len(cal['screen_brains'])
    s = broken(np.load(OUT / 'singles_pass.npy'), nb)
    out = []
    pc = np.load(OUT / 'pairs_pass.npy')
    for p, code in zip(itertools.combinations(range(n), 2), pc):
        if code < PENDING and code < nb / 2 and not (s[p[0]] or s[p[1]]):
            out.append(p)
    tc = np.load(OUT / 'triples_pass.npy')
    hit = set(np.where((tc < PENDING) & (tc < nb / 2))[0].tolist())
    if hit:
        for i, t in enumerate(itertools.combinations(range(n), 3)):
            if i in hit:
                out.append(t)
            if i >= len(tc) - 1:
                break
    return out


def confirm(sc, cal):
    f = OUT / 'confirm.json'
    if f.exists():
        return
    cand = candidates(cal, len(sc.neurons))
    print(f'confirming {len(cand)} epistasis candidates x {CONFIRM_N} re-tests', flush=True)
    nb, T = len(cal['screen_brains']), sc.cfg.ticks_per_generation
    fails = np.ones(len(cand), int)                                       # the original flagged test
    for _ in range(CONFIRM_N):
        if cand:
            fails += ((sc.arrivals(cand) < T).sum(1) < nb / 2)
    need = 4 if not TEST else 2
    res = [dict(neurons=[sc.conn.names[sc.neurons[j]] for j in c], unstable_in=int(x), of=CONFIRM_N + 1,
                confirmed=bool(x >= need)) for c, x in zip(cand, fails)]
    f.write_text(json.dumps(res, indent=1))


def run():
    cal = calibrate()
    sc = Screen(cal['screen_brains'], cal['length'], cal['limit'])
    for phase in ('singles', 'pairs', 'triples'):
        run_phase(sc, cal, phase)
    confirm(sc, cal)
    print('COMBO_RUN_DONE', flush=True)


def analyze():
    from .connectome import Connectome, _is_muscle
    conn = Connectome()
    names = [n for n in conn.names if not _is_muscle(n)]
    cal = json.loads((OUT / 'calibration.json').read_text())
    nb = len(cal['screen_brains'])
    s = broken(np.load(OUT / 'singles_pass.npy'), nb)
    sil = set(cal['silent_pos'])
    L = [f'Step 28 / corridor combination screen, {nb} screen brains {cal["screen_brains"]}: corridor {cal["length"]:.0f} units, '
         f'time limit {cal["limit"]} ticks (intact arrival median {cal["arrival_p50"]}, 95th {cal["arrival_p95"]:.0f}); '
         f'intact arrival {cal["overall"]:.1%}; false-alarm rate {cal["false_alarm"]:.1%}'
         + ('  (ABOVE the 2 % limit: results judged noisy)' if cal['false_alarm'] >= 0.02 else ''),
         f'silent neurons (dropped from triples only): {len(sil)} of {len(names)}',
         f'singles: {s.sum()} of {len(s)} break navigation alone: ' + ', '.join(names[i] for i in np.where(s)[0])]
    if s[list(sil)].any() if sil else False:
        L.append('  WARNING: a silent neuron broke navigation as a single -> the silent-neuron shortcut is not safe')
    for ph, k in (('pairs', 2), ('triples', 3)):
        pf = OUT / f'{ph}_progress.json'
        if not pf.exists():
            continue
        code = np.load(OUT / f'{ph}_pass.npy'); prog = json.loads(pf.read_text())
        tested = code < PENDING
        L.append(f'{ph}: {len(code):,} combinations, {tested.sum():,} tested ({(code == SKIP_BROKEN).sum():,} skipped as '
                 f'containing a broken part, {(code == SKIP_SILENT).sum():,} as containing a silent neuron); '
                 f'{(tested & (code < nb / 2)).sum():,} tested ones unstable; measured {prog.get("combos_per_s", 0):.0f} combos/s')
        if ph == 'pairs' and sil:
            ps = [i for i, p in enumerate(itertools.combinations(range(len(names)), 2)) if (p[0] in sil or p[1] in sil)]
            ps = [i for i in ps if i < len(code)]
            nbad = int((tested[ps] & (code[ps] < nb / 2)).sum()) if ps else 0
            L.append(f'  check of the silent-neuron shortcut: {nbad} tested pairs containing a silent neuron were unstable'
                     + (' -> shortcut questionable' if nbad else ' -> shortcut looks safe'))
    if (OUT / 'confirm.json').exists():
        c = json.loads((OUT / 'confirm.json').read_text())
        ok = [x for x in c if x['confirmed']]
        L.append(f'EPISTASIS: {len(c)} candidates, {len(ok)} confirmed (unstable in >= 4 of 6 tests)')
        L += ['  ' + ' + '.join(x['neurons']) + f'  ({x["unstable_in"]}/{x["of"]})' for x in ok[:60]]
        import csv
        RES.mkdir(exist_ok=True)
        tag = 'test_' if TEST else ''
        with open(RES / f'step28_{tag}b{NB}_epistasis.csv', 'w', newline='') as fh:
            w = csv.writer(fh); w.writerow(['neurons', 'unstable_in', 'of', 'confirmed'])
            for x in c:
                w.writerow([' + '.join(x['neurons']), x['unstable_in'], x['of'], x['confirmed']])
    txt = '\n'.join(L); print(txt)
    RES.mkdir(exist_ok=True)
    (RES / f'step28_{"test_" if TEST else ""}b{NB}_stats.txt').write_text(txt + '\n')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--') and not x.isdigit()]
    if a[:1] in (['full'], ['check']):
        run(); analyze(); print('COMBO_CHECK_OK' if a[0] == 'check' else 'COMBO_FULL_DONE', flush=True)
    elif a[:1] == ['analyze']:
        analyze()
    elif a[:1] == ['calcompare']:
        calcompare()
    else:
        print(__doc__)
