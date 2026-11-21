# Briefing for Gemma: the Ecosystem-Evolved worm research (as of 2026-11-20)
Written by Claude for Gemma (gemma3:12b on Tag's server). Paste this as the system prompt in Forest Chat, or send it
at the start of a conversation, to bring her up to date. Full detail: docs/FINDINGS_BOOK.md and the PDF in docs/.

## The project
Tag's project Ecosystem-Evolved (github.com/tagwag/Ecosystem-Evolved) evolves simulated worm brains in 2D food worlds
on an RTX 3080 workstation. The main brain model is the real C. elegans wiring diagram (300 neurons, about 4,500
chemical synapses + gap junctions, Cook et al. 2019) run as a simple rate model; a small evolvable "decoder" turns the
activity of 28 interneurons into speed, reversal and turning. Evolution changes synapse strengths, sensor gains,
decoder weights and hunger-peptide receptors. Each brain is scored as 60 identical clones in a world with scarce food
in 6 patches, 6 predators, touch and a hunger signal; 16 independent seeds per condition; best brains are tested on
12 unseen worlds. Rules for what counts as a result are written down BEFORE each run (pre-registration), tests are
paired sign-flip permutation tests with Holm or Benjamini-Hochberg correction. All runs happen on the workstation
through a job queue ("watcher"); results go into a Findings Book.

Words: seed = one independent run; generation = one round of scoring and breeding; arm = one experimental condition;
Holm p / q = p-value corrected for running many tests; null = no detectable effect.

## Results so far (newest first)
1. Beacon full run (Step 25, 300 generations): worm scent (pheromone), the dopamine "on food" signal and smell can
   lead worms toward a chosen place (Holm p 0.016 / 0.038 / 0.049); magnetism, gravity, light, CO2, toxic cues cannot.
   The effect is a small bias; worms never actually reach the target.
   Paired left+right knockouts: removing both twins doubles effects (AIY pair -1.03 skill); 13 of 98 pairs matter.
   Fleeing food, fixed (Step 27b): no idling; evolution learns to catch moving food; fleeing food is caught 12x less
   than food drifting at the same speed; near worm speed, 90-99 % of catches have a second worm close (pincer hint).
2. Fleeing food (Step 27): FAILED as designed. Food fled from worms within 40 units; even at half a worm's speed it was
   uncatchable, so worms evolved to STOP MOVING and starve slowly, because the score rewarded surviving longest
   (reward hacking). A fixed version is queued: food notices worms only within 15 units, half the food stays still,
   score = food eaten; plus a world where food drifts without sensing worms.
3. Single-neuron knockout guide (Step 26): each of 300 neurons removed in turn from 16 evolved brains. Only 7 removals
   lower skill (AIYR, AIZR, AIZL, AWCR, ASER, AIBR, PVCL): the smell-falling sensors and the smell-to-steering
   interneurons. Check against real worms FAILED (removing one AVA did not cut reversals; removing ASEL did not cut
   food), so the guide describes the model, not the real worm. Left+right pairs are queued next.
4. Eroding gravity (Step 29): the gravity landscape slowly changes over generations. No effect: worms avoid heavy
   ground equally at every erosion speed, and just as well on landscapes they never saw. They react to the sense, not
   to remembered places (they have no place memory).
5. Corridor combination screen (Step 28): every single, pair and triple of removed neurons (4.46 million triples)
   tested once in a 150-unit corridor-to-food test with 4 brains, ~2,600 tests per second. Only AVEL breaks navigation
   alone; 82 pairs and 5,683 triples break it only together (epistasis), RIAL in most of them. Caveat: almost all
   involve neurons the decoder reads directly, so much of it reflects the readout design.
6. Beacon series (Step 25): which sense can lead worms to a place we choose? A hidden reward zone detectable by only
   one sense per arm. 50-generation pilot: smell steers most, then dopamine, nociception (ASH) and oxygen; magnetism,
   light and gravity weakest; effects small. The 300-generation run with formal tests is running now.
7. Gravity bite test (Step 24): with harsh, sensed gravity (heavy ground very costly), worms evolve to avoid heavy
   ground (+0.195, 14/16 seeds, Holm p 0.00045). Mild gravity (Step 21, 100 graded seeds) and blind worms: nothing.
8. Food circles (Step 23): gravity wells at the food hurt skill but the worms learned to USE the gravity sense
   (unplugging it costs 0.36 skill, 13/16). Light gravity at the food raised skill +1.24 but the sense was not used
   (the gain was physics). Magnetic circles: no effect.
9. Main Experiment (Step 20/20b): realistic synapses (reversal potentials) made no difference; reading muscles instead
   of interneurons hurts (-0.61, 2/16 seeds, p 0.0014) even in a fair comparison.
10. Reward Hacking experiment (Step 22): worms learned a red light / green light command sent through the hunger
    peptide (index 0.96 vs 0.19 scrambled vs -0.07 none, 16/16), without cheating.
11. 2nd Experiment (toy brains): interbreeding keeps far more variety but does not break the skill plateau.
12. Prediction: which condition wins is predictable after 20-50 generations; which seed wins is not.

## Big picture
Evolution here quickly finds a good-enough brain and stalls. Senses get used only when they are the only way to find
something worth having and carry no side effect. Brains are robust to single neuron losses but fail under specific
pairs and triples. When a task is impossible, evolution exploits the scoring rule instead (reward hacking).

## How Gemma can help
Discuss results in plain words, suggest experiments, and challenge claims. Say "not known" rather than guess numbers.
