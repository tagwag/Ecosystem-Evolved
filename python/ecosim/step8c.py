"""Step 8c: Step 8b + digestion while still. Two reasons to rest: predators notice moving prey, and food
only becomes usable energy as it is digested, fastest when still (a meal ~67 ticks still, 4x slower at full
speed; the gut holds 3 meals and a full gut blocks eating). Energy is needed both to flee and to search.

Same 2 x 2 as Step 8b (peptide on/off x predators notice motion / blind), 32 seeds, 100 generations.

    python -m ecosim.step8c run        (~20-25 min on an RTX 3080)
    python -m ecosim.step8c analyze    -> results/step8c_*
"""
import sys
from pathlib import Path

from . import step8b as b

b.TAG, b.DIGESTION, b.OUT = 'step8c', True, Path('runs/step8c')
b.register()

if __name__ == '__main__':
    {'run': b.run, 'analyze': b.analyze}[sys.argv[1]]()
