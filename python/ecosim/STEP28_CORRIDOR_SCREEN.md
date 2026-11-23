# Step 28: corridor combination screen (results, 2026-11-16)
Design, rules and commands: the docstring of `python/ecosim/step28.py`. Raw results: `python/runs/step28/b4/`,
`python/results/step28_b4_stats.txt`, `python/results/step28_b4_epistasis.csv`, `python/results/step28_corridor_calibration.txt`.

## What was tested
The owner's definition of a stable worm: it can still navigate to one piece of food down a corridor. Corridor variants
were compared first on intact brains (400 / 300 / 200 / 150 units: 2-3 / 8 / 49 / 74 % arrivals; 1500 ticks no better
than 600 because worms run out of energy first). Owner's rule "pick the most reliable" -> **150 units, one piece of
food, 600 ticks**. Screen brains: the 4 most reliable Step 23 control brains (seeds 2, 5, 8, 9; each >= 95 % intact).
A combination is UNSTABLE if fewer than 2 of the 4 reach their food. False-alarm rate on 64 intact worlds: 0 %.
Every single (300), pair (44,850) and triple (4,455,100) of removed neurons was tested once (continuous refill,
~2,600 combinations per second on the RTX 3080; whole screen ~40 min incl. a stop and resume). Then every candidate
(an unstable pair whose singles are stable, or an unstable triple with no unstable single or pair inside) was re-tested
5 more times; CONFIRMED if unstable in at least 4 of the 6 tests.

## Results
| | Count | Unstable | Confirmed epistasis |
|---|---|---|---|
| singles | 300 | **1 (AVEL)** | - |
| pairs | 44,551 tested (299 contain AVEL) | 353 (0.8 %) | **82** (23 % of candidates) |
| triples | 4,315,887 tested (139,213 contain a broken part) | 37,989 (0.9 %) | **5,683** (15 % of candidates) |

- No neuron was silent in the intact brains (all 300 carry activity), so that shortcut saved nothing.
- **Most single flags were noise**: only 15-23 % of candidates were confirmed on re-testing. Single-test screens with
  4 brains need re-tests, as planned.
- **RIAL dominates**: in 52 of 82 confirmed pairs and 2,660 of 5,683 confirmed triples. RIA is a head interneuron
  that integrates sensory input and controls head movement in real worms; here removing it alone leaves the worm
  close to failing, so almost anything removed with it tips it over.
- **Strong caveat (readout artefact):** 5,762 of the 5,765 confirmed combinations contain at least one of the 28
  neurons the motor DECODER reads directly (AVA, AVB, AVD, AVE, PVC, AIB, AIY, AIZ, RIA, RIM, SMD, RMD). Removing
  those removes decoder inputs, so much of the "epistasis" is about how this model turns brain activity into movement,
  not about the wiring. Only 3 confirmed triples contain no decoder-read neuron: ASHL + AWAR + DA08,
  AWAL + AWCR + DA06, AWAR + BAGR + PHCR (all sensory neurons + one motor neuron).
- Strongest (unstable in all 6 tests): pairs AIYL+PVCR, AIYR+AWAR, AIZR+AVDL, AIZR+RMDDL, AVAL+PVCR, PVCR+SMDDL,
  RIAL+SABVR, RIAL+VC01; 456 such triples.

## What to do with it
- The single-neuron knockout guide (Step 26, queued) gives graded effects for every neuron on 16 brains; compare.
- To separate wiring from readout: repeat the screen with brains that read MUSCLES (Step 20b body readout) or exclude
  decoder-read neurons from the combinations. Not queued.

## Repeat with every navigating brain (2026-11-23 10:40-12:03, watcher job e18 combo_screen16)
"16" in the job name = the screen considered all 16 evolved brains; 8 of them navigate well enough to use (brains 2, 5,
8, 9, 10, 11, 13, 16; the 4-brain screen used 2, 5, 8, 9). Same corridor (150 units), same rules, unstable = fewer
than half of the brains reach their food, candidates re-tested 5 more times. Results: results/step28_b16_stats.txt,
results/step28_b16_epistasis.csv.

| | 4 brains | 8 brains | In both lists |
|---|---|---|---|
| Single neurons that break navigation | AVEL | **RIML** (not AVEL) | none |
| Unstable pairs (screen) | 353 | 233 | |
| Confirmed epistatic pairs | 82 | 20 | **2** (AIZR + RMDDL, PVCR + SMDDL) |
| Unstable triples (screen) | 37,989 | 26,954 | |
| Confirmed epistatic triples | 5,683 | 3,207 | **89** |
| Hub neuron (in most confirmed combinations) | RIAL | AVEL, then RMDDL | |
| Confirmed combinations with no decoder-read neuron | 3 | 1 (ASER + AWCR + VA12) | |

**Reading (blunt):** the 4-brain results do NOT generalise. Adding 4 more brains changed the single breaking neuron,
the hub neuron, and kept only 2 of 82 pairs and 89 of 5,683 triples. So what a combination knockout breaks is mostly
specific to the individual evolved brain (each brain has its own weak points), not a property of the worm wiring.
Both screens are still dominated by decoder-read neurons (all but 1 of 3,227 confirmed), so the readout artefact
stands. The 2 pairs found in both screens (AIZR + RMDDL, PVCR + SMDDL) are the only candidates worth following up;
both involve decoder-read neurons.

