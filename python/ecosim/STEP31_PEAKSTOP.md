# Step 31: super worm under the PEAK-STOP rule (results, 2026-11-23 12:26-19:39 MT; confirmation 2026-11-24)

## What was run
The owner's new rule for breeding runs (ecosim/peakstop.py; owner's request 2026-11-23): when a seed's skill passes
its peak (2 checkpoints in a row at least 0.10 below the segment's peak; checkpoints every 25 generations re-tested
on the 24 hall worlds), the surviving worms (the peak brain, the segment's best other checkpoints, the current
elites) are interbred by uniform crossover and evolution continues; after 3 interbreedings the next peak ends the
seed; the run ends when all seeds have ended or at 600 generations.
Recipe otherwise = the Step 30 recipe that reproduced: the 12 hall-of-fame champions as founders, 4 worlds per brain
per generation, 12 brains, 60 clones, standard world. 16 new seeds (41-56). Code: ecosim/step31.py. Watcher jobs:
breed_peak_check (code check), breed_peak (the run, e19b), breed_peak_confirm (e20).

## Results (results/step31_stats.txt, results/step31_confirm.txt)
- Run length: 433 min. 8 seeds ended early (generations 425-600), 8 were still going at the 600-generation cap, so
  the run as a whole did NOT end early and saved no GPU time.
- 45 interbreedings in total (13 seeds used all 3). **Interbreeding did not clearly help:** the next segment's peak
  minus the previous segment's peak was +0.020 on average, 27 of 45 positive. That is inside the checkpoint noise
  (~ +/-0.1), and slightly favoured anyway because the peak brain is kept unchanged in every brood.
- Fresh worlds 5900-5947 (one scoring call): peak-stop seeds mean 3.648 (Step 30 4-world arm bests: 3.60 / 3.67, the
  same), best seed 50: 3.989; Step 30 super worms 3.882 / 3.800; champions best 3.521.
- **Confirmation on 96 new worlds 6000-6095** (rule written before the run: counts as a new super worm only if it
  beats BOTH Step 30 super worms by more than 0.1): seed 50 **4.070**, seed 46 3.961, seed 49 3.849; super worms
  3.899 / 3.825. **Seed 50 is the new super worm** (+0.171 over the best previous one, on two independent fresh-world
  sets). Genome: runs/step31/p31_pool_x4_peak_s50/peak_genome.npy, backup results/step31_SUPER_WORM_s50.npy.

## Reading (blunt)
- The new super worm should NOT be credited to the peak-stop rule. Seed 50 was already at 4.16 on the checkpoint
  worlds by generation 275, before its first interbreeding; its later segments hovered at 4.11-4.17 (noise).
  What it does show: with 4-world scoring, a strong line can keep (and slowly improve) its skill for 600 generations
  instead of degrading. Running longer is what helped, not interbreeding.
- The rule works as designed (detects peaks, keeps the peak brain, so nothing is lost), but on this evidence it adds
  neither skill nor time savings. A fair test would be a fixed-length 600-generation 4-world run with the same seeds
  and no peak-stop (a comparison, so fixed length).
