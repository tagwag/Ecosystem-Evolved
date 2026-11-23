"""PEAK-STOP RULE for breeding runs (owner's rule, 2026-11-23).

WHAT THE OWNER ASKED FOR
  "When the top of the curve is reached (discovered by the worm brains losing skill) that run/generation ends early
  and any surviving worms are interbred together." Scope chosen by the owner: BREEDING runs only (runs whose goal is
  the best brain, like the Step 30 super worm). Comparison experiments (arm A vs arm B) keep fixed lengths, because
  arms that stop at different generations cannot be compared fairly. After interbreeding, evolution CONTINUES until
  the next peak; at most 3 times, then that seed ends.
  The usual ML term for this is EARLY STOPPING on a plateau, "restoring the best weights" (keep the peak brain), with
  a RESTART from a recombined population (crossover of the survivors).

HOW IT WORKS (per seed; seeds of one run evolve side by side on the GPU)
  1. Every `every` generations (a CHECKPOINT) the seed's current best brain is re-tested on FIXED worlds
     (`score` callable; Step 30 uses the 24 hall worlds). Fixed worlds remove most of the luck in a single
     generation's score.
  2. PEAK = the best checkpoint score so far in the current SEGMENT (a segment = the stretch since the start or since
     the last interbreeding).
  3. LOSING SKILL = the checkpoint score is at least `drop` (default 0.10) below the segment peak. Measured noise of a
     single brain's score is about +/-0.07 (Step 30 replicate), so smaller dips are not counted. It must happen at
     `confirm` (default 2) checkpoints IN A ROW, so one unlucky checkpoint does not end the segment.
  4. Then the segment ENDS and the SURVIVORS are interbred: survivors = the segment's peak brain + its best other
     checkpoints (up to 3) + the current elites (the brains that survived selection this generation).
     The new population = the peak brain itself (kept unchanged, so nothing is lost) + children made by UNIFORM
     CROSSOVER of two different survivors (each gene copied from one parent or the other, 50/50).
     All survivors come from the same seed, i.e. they are relatives; crossing unrelated networks tends to break them
     (the "competing conventions" problem), which is why seeds are not mixed.
  5. Evolution continues from that population. After `restarts` (default 3) interbreedings, the next detected peak
     ENDS the seed. The run stops early when every seed has ended (or at the run's maximum generation count).
     Seeds that have ended keep being simulated (the GPU runs all seeds together) but nothing they do counts.

OUTPUT (per seed folder): peak_genome.npy (the best brain of the WHOLE run on the checkpoint worlds; the seed's
  result), peakstop.json (every checkpoint score, segment ends, interbreedings, whether/when it ended).

Usage: pass peakstop=PeakStop(score=..., ...) to batch3_fast.evolve(..., clonal=G, checkpoint_every=...).
"""
import json

import numpy as np


class PeakStop:
    def __init__(self, score, every=25, drop=0.10, confirm=2, restarts=3, keep_ckpts=3):
        self.score, self.every, self.drop, self.confirm = score, every, drop, confirm
        self.restarts, self.keep_ckpts = restarts, keep_ckpts
        self.s = None                                        # per-seed state, made on first call

    def _init(self, K):
        self.s = [dict(done=False, ended_gen=None, restarts=0, below=0, seg_peak=-np.inf, seg_peak_gen=None,
                       seg_genome=None, seg_ckpts=[], run_peak=-np.inf, run_peak_gen=None, run_genome=None,
                       log=[]) for _ in range(K)]

    def step(self, g, best, pop, rngs, n_elite):
        """Called after generation g (1-based count) at checkpoints. best: list of each seed's best brain this
        generation; pop: (K, P, genes) next population (its first n_elite rows are the survivors). Returns pop."""
        K = len(best)
        if self.s is None:
            self._init(K)
        act = [k for k in range(K) if not self.s[k]['done']]
        if not act:
            return pop
        sc = self.score([best[k] for k in act])
        for k, x in zip(act, sc):
            st, x = self.s[k], float(x)
            st['log'].append(dict(gen=g, score=round(x, 4)))
            if x > st['run_peak']:
                st['run_peak'], st['run_peak_gen'], st['run_genome'] = x, g, best[k].copy()
            st['seg_ckpts'] = sorted(st['seg_ckpts'] + [(x, g, best[k].copy())], key=lambda t: -t[0])[:self.keep_ckpts + 1]
            if x > st['seg_peak']:
                st['seg_peak'], st['seg_peak_gen'], st['seg_genome'], st['below'] = x, g, best[k].copy(), 0
            elif x <= st['seg_peak'] - self.drop:
                st['below'] += 1
            else:
                st['below'] = 0
            if st['below'] < self.confirm:
                continue
            ev = dict(gen=g, segment_peak=round(st['seg_peak'], 4), segment_peak_gen=st['seg_peak_gen'])
            if st['restarts'] >= self.restarts:
                st['done'], st['ended_gen'] = True, g
                st['log'].append(dict(ev, event='END (peak passed, no restarts left)'))
                print(f'  peak-stop: seed slot {k} ENDS at gen {g} (segment peak {st["seg_peak"]:.3f} at gen {st["seg_peak_gen"]})', flush=True)
                continue
            surv = [st['seg_genome']] + [c[2] for c in st['seg_ckpts'] if c[1] != st['seg_peak_gen']][:self.keep_ckpts] \
                + [pop[k, i] for i in range(n_elite)]
            P, r = pop.shape[1], rngs[k]
            brood = [st['seg_genome'].copy()]
            while len(brood) < P:
                a, b = r.choice(len(surv), 2, replace=False)
                m = r.random(surv[a].shape[0]) < 0.5
                brood.append(np.where(m, surv[a], surv[b]).astype(pop.dtype))
            pop[k] = np.stack(brood)
            st['restarts'] += 1
            st['log'].append(dict(ev, event=f'INTERBREED #{st["restarts"]} ({len(surv)} survivors)'))
            print(f'  peak-stop: seed slot {k} peak passed at gen {g} (segment peak {st["seg_peak"]:.3f} at gen '
                  f'{st["seg_peak_gen"]}); interbreeding {len(surv)} survivors, restart #{st["restarts"]}', flush=True)
            st.update(below=0, seg_peak=-np.inf, seg_peak_gen=None, seg_genome=None, seg_ckpts=[])
        return pop

    def all_done(self):
        return self.s is not None and all(st['done'] for st in self.s)

    def finish(self, out, cond, seeds, best):
        """Save each seed's run-peak brain + log. Seeds never checkpointed fall back to their last best."""
        if self.s is None:
            self._init(len(seeds))
        for k, sd in enumerate(seeds):
            st, d = self.s[k], out / f'{cond}_s{sd}'
            d.mkdir(parents=True, exist_ok=True)
            np.save(d / 'peak_genome.npy', st['run_genome'] if st['run_genome'] is not None else best[k])
            (d / 'peakstop.json').write_text(json.dumps(dict(
                run_peak=st['run_peak'] if np.isfinite(st['run_peak']) else None, run_peak_gen=st['run_peak_gen'],
                restarts=st['restarts'], ended_gen=st['ended_gen'], done=st['done'], log=st['log'],
                rule=dict(every=self.every, drop=self.drop, confirm=self.confirm, restarts=self.restarts)), indent=1))
