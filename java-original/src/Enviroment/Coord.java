package Enviroment;

import Constants.Constants;

import java.util.Objects;

/**
 * The coordinate location of a body part.
 */
public class Coord {

    final int XBOUND = new Constants().WIDTH;
    final int YBOUND = new Constants().HEIGHT;

    public int x;
    public int y;
    public boolean meat;

    public Coord(final int x, final int y) {
        this.x = x;
        this.y = y;
    }

    public int getX() {
        return this.x;
    }

    public void setX(final int x) {
        this.x = x;
    }

    public int getY() {
        return this.y;
    }

    public void setY(final int y) {
        this.y = y;
    }

    public void moveX(final int xTranslation) {

        if (x + xTranslation > this.XBOUND - 1) {
            x = (x + xTranslation) - (this.XBOUND - 1);
        } else if (x + xTranslation < 0) {
            x = (this.XBOUND - 1) - (x + xTranslation);
        } else {
            x += xTranslation;
        }
    }

    public void moveY(final int yTranslation) {

        if (y + yTranslation > this.YBOUND - 1) {
            y = (y + yTranslation) - (this.YBOUND - 1);
        } else if (y + yTranslation < 0) {
            y = (this.YBOUND - 1) - (y + yTranslation);
        } else {
            y += yTranslation;
        }
    }

    /**
     * Finds the distance between two points.
     *
     * @param object Coord Object
     * @return int describing how much distance is between two Coord objects.
     */
    public int distance(final Coord object) {

        //distance between two points.
        try {
            final double est = Math.sqrt(Math.pow((((double) getX()) - ((double) object.getX())), 2) + Math.pow((((double) getY()) - ((double) object.getY())), 2));
            return Math.toIntExact(Math.round(est));
        } catch (final Exception e) {
            return 0;
        }
    }

    public int distanceX(final Coord object) {

        return getX() - object.getX();

    }

    public int distanceY(final Coord object) {

        return getY() - object.getY();

    }


    public boolean compareCoords(Coord comp) {

        if (this.x == comp.x && this.y == comp.y) {
            return true;
        }
        return false;
    }



    @Override
    public boolean equals(final Object o) {
        if (this == o) return true;
        if (!(o instanceof Coord)) return false;
        if (this.hashCode() == o.hashCode()) return true;
        final Coord coord = (Coord) o;
        return this.getX() == coord.getX() &&
                this.getY() == coord.getY();
    }

    public boolean touching(final Body object) {
        for (final Coord part : object.bodyList) {
            if (part.equals(this)) {
                return true;
            }
        }

        return false;
    }

    public boolean touching(final Coord part) {

        return part.equals(this);

    }

    @Override
    public int hashCode() {
        return Objects.hash(this.getX(), this.getY());
    }
}
