package Models.Mental;

import Enviroment.Coord;

public class Examination {

    public double theirSize;
    public int theirDiet;
    public int x;
    public int y;

    public Examination(final double theirSize, final int theirDiet, final int x, final int y) {
        this.theirSize = theirSize;
        this.theirDiet = theirDiet;
        this.x = x;
        this.y = y;
    }

    public Examination(){}

    public double getTheirSize() {
        return this.theirSize;
    }

    public void setTheirSize(final double theirSize) {
        this.theirSize = theirSize;
    }

    public double getTheirDiet() {
        return this.theirDiet;
    }

    public void setTheirDiet(final int theirDiet) {
        this.theirDiet = theirDiet;
    }

    public Coord theirDirection() {
        return new Coord(this.x, this.y);
    }
}
