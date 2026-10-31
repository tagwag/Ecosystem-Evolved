package Models;

import Technical.IDGen;

public class CellImpl extends Cell {
    public CellImpl(final IDGen idGen, final boolean smol) {
        super(idGen, smol);
    }

    public CellImpl(final IDGen idGen, final boolean smol, final int threatTolerance, final int obstacleTolerance, final int sight, final double size, final int diet, final int strategy, final int[] priorities, final int splitChance, final int splitRequirement, final int type, final int flockingTolerance) {
        super(idGen, smol, threatTolerance, obstacleTolerance, sight, size, diet, strategy, priorities, splitChance, splitRequirement, type, flockingTolerance);
    }

    public CellImpl(final IDGen idGen, final int threatTolerance, final int obstacleTolerance, final int sight, final double size, final int diet, final int strategy, final int[] priorities, final int splitChance, final int splitRequirement, final int type, final int flockingTolerance) {
        super(idGen, threatTolerance, obstacleTolerance, sight, size, diet, strategy, priorities, splitChance, splitRequirement, type, flockingTolerance);
    }

    public CellImpl() {
    }

    public CellImpl(final int x, final int y, final int id, final int threatTolerance, final int obstacleTolerance, final int sight, final double size, final int energy, final int diet, final int strategy, final int splitChance, final int splitRequirement) {
        super(x, y, id, threatTolerance, obstacleTolerance, sight, size, energy, diet, strategy, splitChance, splitRequirement);
    }
}
