package Enviroment;

import java.util.Random;

/**
 * Things can move! This contains their speed and slope (direction) or if stationary.
 * Their max speed is determined by their size.
 */
public class Movement {

    public boolean stationary;
    public int xSpeed;
    public int ySpeed;
    public int energyLost;

    /**
     * Moving. If both xSpeed and ySpeed = 0 then set a random movement.
     *
     * @param xSpeed int
     * @param ySpeed int
     */
    public Movement(final int xSpeed, final int ySpeed, final double size) {
        stationary = false;
        final double movementSpeed = this.size2speed(size);

        costInCalories(size);

        if (xSpeed == 0 && ySpeed == 0) {

            this.xSpeed = new Random().nextInt(2);
            this.ySpeed = new Random().nextInt(2);
        } else {
            if (xSpeed != 0) {
                this.xSpeed = xSpeed * 2;
            }
            if (ySpeed != 0) {
                this.ySpeed = ySpeed * 2;
            }
        }
        /*
        if (xSpeed == 1) {
            //this.xSpeed = Math.toIntExact((long) movementSpeed);
            this.xSpeed = 1;
        }
        if (ySpeed == 1) {
            //this.ySpeed = Math.toIntExact((long) movementSpeed);
            this.ySpeed = 1;
        }
        if (xSpeed == -1) {
            //this.xSpeed = -Math.toIntExact((long) movementSpeed);
            this.xSpeed = -1;
        }
        if (ySpeed == -1) {
            //this.ySpeed = -Math.toIntExact((long) movementSpeed);
            this.ySpeed = -1;
        }
        */
    }

    /**
     * Move towards or away from an object.
     *
     * @param object   Threat or Food
     * @param myCenter Self
     * @param good     Food or Threat
     */
    public Movement(final Coord object, final Coord myCenter, final boolean good, final double size, int strategy) {

        //movement speed
        //double movementSpeed = (-1.15957/(1+(-1.02527 * Math.exp(0.0640627*size))));
        final double movementSpeed = this.size2speed(size);
        costInCalories(size);
        final int moving = Math.toIntExact(Math.round(movementSpeed));
        int temp = moving / 2;
        if (temp == 0) {
            temp = 1;
        }

        if (!good) {

            final Random random = new Random();
            if (random.nextInt(100) <= 50) {
                strategy *= -1;
            }
            //int temp = random.nextInt(2);
            if (object.getX() > myCenter.getX()) {
                xSpeed = -temp;
                //this.ySpeed += strategy;
            } else if (object.getX() < myCenter.getX()) {
                xSpeed = temp;
                //this.ySpeed += strategy;
            } else {
                int t = 1;
                if (random.nextInt(100) <= 50) {
                    t *= -1;
                }
                xSpeed = strategy;
            }

            if (object.getY() > myCenter.getY()) {
                ySpeed = -temp;
                //this.xSpeed += strategy;
            } else if (object.getY() < myCenter.getY()) {
                ySpeed = temp;
                //this.xSpeed += strategy;
            } else {
                int t = 1;
                if (random.nextInt(100) <= 50) {
                    t *= -1;
                }
                ySpeed = strategy;
            }

            try {
                final int slope = xSpeed / ySpeed;
                if (slope == 1) {
                    if (random.nextInt(100) <= 50) {
                        ySpeed = 0;
                    } else {
                        xSpeed = 0;
                    }
                }
            } catch (final Exception e) {
                //dividing by 0;
            }

        } else {

            //Random random = new Random();
            //int temp = random.nextInt(2);

            if (object.getX() > myCenter.getX()) {
                xSpeed = temp;
            } else if (object.getX() < myCenter.getX()) {
                xSpeed = -temp;
            } else {
                xSpeed = 0;
            }

            if (object.getY() > myCenter.getY()) {
                ySpeed = temp;
            } else if (object.getY() < myCenter.getY()) {
                ySpeed = -temp;
            } else {
                ySpeed = 0;
            }


        }


    }

    public Movement(final Coord closestObstacle, final Coord myCenter, final double size) {

        //mimic threat avoidance but without running in opposite direction.
        final double movementSpeed = this.size2speed(size);
        costInCalories(size);
        final int moving = Math.toIntExact(Math.round(movementSpeed));

        int temp = moving / 2;
        if (temp == 0) {
            temp = 1;
        }
        //if move in direction furthest away.
        //determine which is closer, x axis or y axis. and then determine positive or negative.

        if (Math.abs(myCenter.distanceX(closestObstacle)) > Math.abs(myCenter.distanceY(closestObstacle))) {
            //closer on x axis.
            //which direction?
            if (myCenter.distanceX(closestObstacle) <= 0) {
                //move to the right
                xSpeed = -1 - temp;
            } else {
                //move to the left
                xSpeed = 1 + temp;
            }
        } else {
            //closer on y axis
            if (myCenter.distanceY(closestObstacle) <= 0) {
                //move up
                ySpeed = -1 - temp;
            } else {
                //move down
                ySpeed = 1 + temp;
            }
        }
    }

    public Movement(final Coord coord, final int size) {


    }

    public double size2speed(final double size) {
        final double a = 1393.49;
        final double b = 1.34247;
        final double t = 0.00918484;
        return (a / (1 + (b * Math.exp(t * size))));
    }

    public void costInCalories(final double size) {
        final double a = -0.688954;
        final double b = -1.33401;
        final double t = -0.000454068;
        energyLost = (int) (a / (1 + (b * Math.exp(t * size))));
    }


}
