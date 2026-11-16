# Step 25 (DESIGN, not built yet): the BEACON series, one experiment per sense
Written 2026-11-16 07:40 MT for the owner's goal: **find ways to lead worms to a chosen location.**
Status: design only. Nothing below has been coded or run.

## 1. Why a new design (what Step 23 taught)
- Gravity at the food (Step 23, H3): brains learned to USE the gravity sense, because the field told them where food was.
- Magnetism at the food (H2, H4): nothing. The food was already findable by SMELL, so a second cue pointing at the same
  food added no information, and selection had nothing to gain from wiring it in.
- Light gravity at the food (H5/H6, 2026-11-16): skill +1.24 (16/16), but the sense was NOT used (H6, p 0.13). The gain
  came from physics (faster, cheaper movement on the food), not from navigation.
**Lesson:** a cue gets used only if it is the ONLY way to find something worth having, and it must have no physical
side effect, or the side effect gets credited instead of the steering.

## 2. The world (same as the Main Experiment world, plus a hidden reward zone)
- Everything as Step 23 control: connectome brain, scarce food (smell works as before so worms survive), predators, touch,
  60-clone scoring, 12 brains per seed, a new world every generation.
- **Reward zone:** ONE circle per world (radius 100, feathered to 0 at 240, the Step 23 circle shape), at a random place
  each generation. While inside it a worm gains energy every tick (+0.3 per tick at the centre, scaled by the circle value;
  base cost of living is 0.6). The zone has no food, no smell and no physical effect: **it is invisible except through
  the one sense the arm's cue is fed into.**
- **Cue:** the circle value x gain 3 is fed into the arm's sensory neurons only (the same way Step 23 fed AFD/PVD). Pure
  cue: no slowing, no cost, no other world change.

## 3. Arms (16 seeds each, paired by seed, 300 generations)
| Arm | Sense | Neurons the cue goes into | Note |
|---|---|---|---|
| s25_none | no cue | - | the reference: the zone exists but nothing senses it |
| s25_smell | smell (positive control) | ASEL, ASER, AWCL/R, AWAL/R | already wired for food; should steer best |
| s25_afd | temperature = magnetism | AFDL/R | in this model magnetism and temperature both go into AFD, so one arm covers both |
| s25_light | light / UV | ASJL/R | |
| s25_toxic | chemical repellent | PHAL/R, PHBL/R | worms normally avoid this; can evolution flip it into an attractant? |
| s25_predator | nociception | ASHL/R | same question as toxic |
| s25_co2 | CO2 | BAGL/R | |
| s25_o2 | oxygen | URXL/R, AQR, PQR | |
| s25_dopamine | "on food" signal | CEPDL/R, CEPVL/R, ADEL/R, PDEL/R | |
| s25_pheromone | worm scent | ASKL/R, ADLL/R | |
| s25_gravity | gravity (pure cue) | PVDL/R | Step 23 gravity without the speed/energy side effects |
| s25_vibration | body touch | ALML/R, AVM, PLML/R, PVM | a "plate tap" style signal, not contact |
| s25_nose | nose touch | FLPL/R, OLQDL/R, OLQVL/R | |
13 arms. Measured timing (e3, 2026-11-16): one 16-seed x 300-generation arm alone on the RTX 3080 takes ~45 min.

**Two phases (uses the prediction result of 14 Nov: arm rankings are reliable after 50 generations, rho 0.95+):**
1. Pilot: all 13 arms x 50 generations (~2.5 h). Ranks the senses.
2. Full: all 13 arms to 300 generations, continuing from the pilot checkpoints (~8 h more), or only the top half if
   the owner prefers (~4 h).

## 4. The measure that answers the goal: the STEERING TEST
Done on each seed's best brain at generation 300, 60 clones x 12 fixed unseen worlds, **with the reward switched off**
(cue only, nothing to gain):
- **Steering index** = time spent inside the cue circle with the cue ON minus with the cue OFF (same brains, same
  worlds, same circle position). > 0 means the cue alone pulls worms to the spot we chose.
- **Arrival time**: ticks until half the worms have entered the circle (cue on vs off).
- **Moving beacon**: the cue circle moves slowly along a fixed path across the world; mean distance from worms to the
  beacon, cue on vs off. This is the "lead them somewhere" test.
- Also reported: skill in the training world vs s25_none, sense-cut test (does skill drop when the cue neurons are
  unplugged?).

## 5. Rules to fix BEFORE the run (draft; final wording when the code is written)
- For each of the 12 cue arms: steering index > 0, paired sign-flip test over 16 seeds, **Holm over the 12 senses**.
  A sense PASSES if Holm p < 0.05. That sense is a candidate "steering channel".
- s25_smell must pass, or the design is broken (positive control).
- Reported, not tested: arrival time, moving-beacon distance, skill vs s25_none, sense-cut, which senses work
  ATTRACTIVE vs REPULSIVE (toxic / predator).

## 6. Expected problems (stated in advance)
- Cue strength (gain 3) is arbitrary; a weak sense may fail only because its input is small. Fix if needed: a second
  run at gain 6 for the failed senses.
- Senses with short paths to the steering neurons (AIY, AIZ, RIA, AVA, AVB...) should win; that would describe this
  model's wiring, not prove anything about real worms.
- The real worm's magnetic sense is disputed (Vidal-Gadea et al. 2015, eLife 4:e07493 vs Landler et al. 2018,
  eLife 7:e30187). In the model it is just an input to AFD.

## 7. What it costs to build
New `ecosim/step25.py` (arms, reward zone, cue injection into any neuron list, steering + moving-beacon tests),
reward zone in `batch3_fast.py` (reuses the Step 23 circle code), watcher jobs `beacon_check`, `beacon_pilot`,
`beacon_full`. About one session of coding, then a workstation code check.
