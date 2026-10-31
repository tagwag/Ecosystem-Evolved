package Enviroment;

import java.util.ArrayList;

/**
 * The "physical" manifestation of a Cell, Food, Obstacle, or Other.
 */
public class Body {

    //everything has a body of some sorts. the body contains the coordinates of the object/Models.Cell.
    public final ArrayList<Coord> bodyList = new ArrayList<Coord>();
    public final int size;
    public int bodyX;
    public int bodyY;
    public int bodyRadius;
    public int fat;
    //private int[][] bounds = new int[720][540];

    public Body() {
        size = 0;
    }

    public Body(final Coord coord) {
        bodyList.add(coord);
        size = 1;
    }

    /**
     * Returns true if the body successfully grew, false if the growth failed.
     *
     * @param absorbed the object consumed for growth.
     * @return
     */
    public boolean grow(final Object absorbed) {

        System.out.println("ERROR - MUST PROGRAM BODY GROWTH");

        return false;
    }

    public ArrayList<Coord> getBodyList() {
        return this.bodyList;
    }

    /**
     * Moves the Body by movement.
     *
     * @param movement
     * @return True if moved, False if blocked
     */
    public boolean move(final Movement movement) {
        /*

        try {
            for (Coord bodyPart : bodyList) {
                int movingX = bodyPart.x;
                int movingY = bodyPart.y;

                if (bounds[movingX][movingY] == 0) {
                    bodyPart.moveX(movement.xSpeed);
                    bodyPart.moveY(movement.ySpeed);
                } else if (bounds[bodyPart.x][movingY] == 0) {
                    bodyPart.moveY(movement.ySpeed);
                } else if (bounds[movingX][bodyPart.y] == 0) {
                    bodyPart.moveX(movement.xSpeed);
                } else {
                    //don't move there
                }
            }
            return true;
        } catch (Exception e) {
            return false;
        }

         */
        int failed = 0;
        try {
            for (final Coord bodyPart : this.bodyList) {

                bodyPart.moveX(movement.xSpeed);

            }
        } catch (final Exception e) {
            System.out.println("Failed move1");
            failed++;
        }
        try {
            for (final Coord bodyPart : this.bodyList) {

                bodyPart.moveY(movement.ySpeed);

            }
        } catch (final Exception e) {
            System.out.println("Failed move2");
            failed++;
        }

        //moved somewhere
        return failed != 2; // couldn't move anywhere

    }

    /**
     * Calculates the average distance an object is from all of the Body parts.
     *
     * @param object
     * @return
     */
    public int distanceFromSelf(final Coord object) {

        int sum = 0;
        int mean;

        for (final Coord bodyPart : bodyList) {

            sum += bodyPart.distance(object);

        }

        mean = Math.toIntExact(Math.round(sum / bodyList.size()));

        return mean;
    }

    /**
     * @return the Centroid
     */
    public Coord calcCenter() {

        int xSum = 0;
        int ySum = 0;

        for (final Coord part : this.bodyList) {

            xSum += part.getX();
            ySum += part.getY();

        }
        //will not like it if the center is 0;
        return new Coord(Math.toIntExact(Math.round(xSum / bodyList.size())), Math.toIntExact(Math.round(ySum / bodyList.size())));
    }

    public boolean touching(final Body object) {

        for (final Coord bodyPart : bodyList) {
            for (final Coord part : object.bodyList) {
                if (part.equals(bodyPart)) {
                    return true;
                }
            }
        }
        return false;
    }

    public void growBody() {
        //if (radius < 1) {
        //    radius = 2;
        //}
        double radius = 1;
        fat += radius;
        if (fat % 100 == 0) {
            bodyRadius += radius;
            for (int y = bodyY - this.bodyRadius; y < bodyY + this.bodyRadius; y++) {

                for (int x = bodyX - this.bodyRadius; x < bodyX + this.bodyRadius; x++) {

                    if (!bodyList.contains(new Coord(x, y))) {
                        bodyList.add(new Coord(x, y));
                    }
                }
            }
            fat = 0;
        }
    /*
        radius = radius / 10000;
        this.bodyList = null;
        this.bodyList = new ArrayList<Coord>();
        if (radius > 9) {
            for (int y = bodyY - (int) radius; y < bodyY + radius; y++) {

                for (int x = bodyX - (int) radius; x < bodyX + radius; x++) {

                    if (this.bodyList.indexOf(new Coord(x, y)) == -1) {
                        this.bodyList.add(new Coord(x, y));
                    }

                }

            }
        }
        /*
        if (radius > 20) {

            double centerX = this.calcCenter().x;
            double centerY = this.calcCenter().y;
            double radiusSquared = radius * radius;
            double rightEdge = centerX + radius;
            double bottomEdge = centerY + radius;

            for (double x = centerX - radius; x <= centerX; x++) {
                for (double y = centerY - radius; y <= centerY; y++) {
                    // we don't have to take the square root, it's slow
                    if ((x - centerX) * (x - centerX) + (y - centerY) * (y - centerY) <= radius * radius) {
                        double xSym = centerX - (x - centerX);
                        double ySym = centerY - (y - centerY);
                        // (x, y), (x, ySym), (xSym , y), (xSym, ySym) are in the circle

                        if (this.bodyList.indexOf(new Coord((int) x, (int) y)) == -1) {
                            this.bodyList.add(new Coord((int) x, (int) y));
                            this.bodyList.add(new Coord((int) x, (int) ySym));
                            this.bodyList.add(new Coord((int) xSym, (int) y));
                            this.bodyList.add(new Coord((int) xSym, (int) ySym));
                        }

                    }
                }
            }
        } else {
            for (int y = this.calcCenter().y; y < this.calcCenter().y + bodyY + radius; y++) {

                for (int x = this.calcCenter().x; x < this.calcCenter().x + bodyX + radius; x++) {

                    if (this.bodyList.indexOf(new Coord(x, y)) == -1) {
                        this.bodyList.add(new Coord(x, y));
                    }

                }

            }
        }
        /*
        for (double x = centerX; x <= rightEdge; x++) {
            double xSquared = x * x;
            for (double y = centerY; y <= bottomEdge; y++) {
                double ySquared = y * y;
                double distSquared = xSquared + ySquared;
                if (distSquared <= radiusSquared) {
                    // Get positions for the other quadrants.
                    double otherX = centerX - (x - centerX);
                    double otherY = centerY - (y - centerY);
                    // Do something for all four quadrants.
                    if (this.bodyList.indexOf(new Coord((int) x, (int) y)) == -1) {
                        this.bodyList.add(new Coord((int) x, (int) y));
                        this.bodyList.add(new Coord((int) x, (int) otherY));
                        this.bodyList.add(new Coord((int) otherX, (int) y));
                        this.bodyList.add(new Coord((int) otherX, (int) otherY));
                    }
                    //doSomething(x, y);
                    //doSomething(x, otherY);
                    //doSomething(otherX, y);
                    //doSomething(otherX, otherY);
                }
            }
        }

        */
    }


}
























