package Models;

import Enviroment.Body;
import Enviroment.Coord;
import Technical.IDGen;

import java.awt.*;

/**
 * If it is not Food, a Cell, or an Obstacle, than it is something else.
 * Preferably this class should not be used, but it exists to help with error checking
 * and possibly in the future allow for cells to determine usage.
 */
public class Other {

    public boolean edible;
    public Body body;
    public int color = Color.MAGENTA.getRGB();
    public int id;
    private int size;
    public Coord center;

    public Other(final boolean edible, final Body body, final IDGen idGen) {
        this.edible = edible;
        this.body = body;
        size = body.bodyList.size();
        id = idGen.makeOtherID();
        center = this.body.calcCenter();
    }

    public boolean isEdible() {
        return this.edible;
    }

    public void setEdible(final boolean edible) {
        this.edible = edible;
    }

    public Body getBody() {
        return this.body;
    }

    public void setBody(final Body body) {
        this.body = body;
    }

    public int getColor() {
        return this.color;
    }

    public void setColor(final int color) {
        this.color = color;
    }

    public int getId() {
        return this.id;
    }

    public void setId(final int id) {
        this.id = id;
    }

    public Coord getCenter() {
        return center;
    }

    public Other(){} //default constructor

    public int getSize() {
        return size;
    }
}
