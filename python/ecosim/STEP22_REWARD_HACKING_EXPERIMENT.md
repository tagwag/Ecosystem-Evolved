# Reward Hacking experiment (Step 22): red light / green light through the peptide channel

*Written 2026-11-13 for anyone picking this up. Code: `ecosim/step22.py` (experiment + analysis),
`ecosim/batch3_fast.py` (`make_phase_schedule`, the `RED` lines in `load` and `_block`), `ecosim/config.py`
("Step 22"). Watcher jobs: `reward_hacking_experiment`, `reward_hacking_analyze`.*

## 1. Goal
Evolve the worm brain to treat the hunger-peptide channel as a command: **stop on red, go on green**. It is the first
step toward sending instructions to an evolved brain (later: more signals, signals triggered by a smell or light,
and finally learned rather than inborn responses).

## 2. Why it is called the Reward Hacking experiment
Reward hacking = evolution scoring well by exploiting the scoring rule instead of doing the task. The obvious hack
here is "never move": no red-light penalty, ever. That hack actually happened in Step 3e, when fitness was the
average energy held and brains won by sitting still. This experiment is built so that hack cannot win, and it
measures whether it happened anyway.

## 3. The task
- Time alternates between red and green phases of random length (30-100 ticks), different in every world and
  generation, so timing cannot be memorised.
- **Red**: moving costs energy, 3.0 per tick at full speed (just living costs 0.6). Standing still is free.
- **Green**: nothing special; forage as usual.
- The worm cannot see the phase. Its only cue is the broadcast peptide, set from OUTSIDE: 1 on red, 0 on green.
  **Honest naming:** in this experiment that is a command signal reusing the hunger peptide's machinery (one
  evolvable receptor per neuron). It no longer tracks the worm's own hunger.
- Everything else = Main Experiment: connectome brain (old synapses + decoder), scarce food, 6 predators, touch,
  fitness = energy at the end + survival, 60 clones per brain, 12 brains per seed, 16 seeds, 300 generations.

## 4. Why "never move" cannot win
A worm that never moves eats nothing, starves around tick 1000 of 1500 and scores about 0.67. Foraging worms score
2-3. Fitness is energy at the END, not energy held on average. The only way to score well is to move on green AND
hold still on red.

## 5. Arms (same 16 seeds in each, paired, run at the same time)
| arm | peptide carries | what it tests |
|---|---|---|
| `s22_signal` | the true red/green phase | can the command be evolved? |
| `s22_scrambled` | a different random schedule | control: same penalty, useless signal |
| `s22_nosignal` | nothing (no receptors) | control: same penalty, no channel at all |

## 6. Pre-registered rules (fixed 2026-11-13 21:40 MT, before any run)
Yardstick: each seed's best brain, 60 clones, 12 fixed unseen worlds, **unseen timing** (phases 10-250 ticks).
GO/NO-GO INDEX = (speed on green - speed on red) / (speed on green + speed on red). 0 = ignores the light, 1 = perfect.
1. **Command learned** if the signal arm's index beats BOTH controls (paired sign-flip tests, Holm, p < 0.05).
2. **Obedience**: the signal arm's brains re-tested with a scrambled peptide must lose their index (p < 0.05).
   Otherwise they are using some other cue, not the peptide.
3. **Reward-hacking check**: a seed is "hacked" if its green-light speed is below 0.10. Pass = at most 2 of 16
   signal-arm seeds hacked. The count is reported for every arm.
4. Reported: skill per arm (an honest signal should also raise skill).
Stated in advance: a pass shows an evolved REFLEX to an outside signal, not learning within a lifetime.

## 7. Run / stop / analyse
- Start: queue `{"experiment": "reward_hacking_experiment"}` (= `python -m ecosim.step22 full`: the 3 arms, then the analysis runs by itself; exclusive: whole GPU, about 3 hours).
- Stop: watcher `CANCEL`. The 3 worker processes stop themselves within one generation + 90 s and save their best
  brains (heartbeat file `runs/step22/_heartbeat`). No mid-run resume: a new run starts fresh.
- Analyse: queue `{"experiment": "reward_hacking_analyze"}` -> `results/step22_stats.txt`, `.json`, `step22.png`.
- Code check (on the workstation): queue `{"experiment": "reward_hacking_check"}` = `python -m ecosim.step22 check --test`
  (2 seeds, 2 generations, all 3 arms, analysis).

## 8. Results
(filled in after the run.)
