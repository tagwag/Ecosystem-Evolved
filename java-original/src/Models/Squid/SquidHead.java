package Models.Squid;

import Enviroment.Coord;

public class SquidHead {

    public int x;
    public int y;
    public int age;

    public SquidHead(final int x, final int y) {
        this.x = x;
        this.y = y;
    }

    public int getX() {
        return this.x;
    }

    public int getY() {
        return this.y;
    }

    public Coord getCenter() {
        return new Coord(this.x, this.y);
    }

}
