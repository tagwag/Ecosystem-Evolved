package Enviroment;

import Constants.Constants;

import java.awt.*;

public class Obstacle {

    //is not alive, cannot be eaten. maybe pushed later? stationary for now. not included in first iterations.
    public Body body;
    public int color = Color.GRAY.getRGB();
    public boolean edible;
    public Coord Center;

    public Constants constants = new Constants();
    public boolean changed = true;
    public boolean enabled;
    public final OpenSimplexNoise noise = new OpenSimplexNoise();
    private final int HEIGHT = Constants.HEIGHT;
    private final int WIDTH = Constants.WIDTH;
    public boolean[][] location = new boolean[this.WIDTH][this.HEIGHT];
    private double frequency;

    public Obstacle(final Body body, final Coord center) {
        this.body = body;
        this.Center = center;
    }


    public Obstacle(final int height) {
        frequency = height;
        for (int y = 0; y < this.HEIGHT; y++) {
            for (int x = 0; x < this.WIDTH; x++) {
                final double value = this.noise.eval(x / frequency, y / frequency, 0.0);
                if (Math.toIntExact(Math.round(value)) == 1) {
                    location[x][y] = true;
                }
            }
        }
        changed = true;
    }

    public void modifyHeight(final int height) {
        this.location = new boolean[this.WIDTH][this.HEIGHT];
        frequency += height;
        for (int y = 0; y < this.HEIGHT; y++) {
            for (int x = 0; x < this.WIDTH; x++) {
                final double value = this.noise.eval(x / frequency, y / frequency, 0.0);
                if (Math.toIntExact(Math.round(value)) == 1) {
                    location[x][y] = true;
                }
            }
        }
        changed = true;
    }


    public Coord calcNearestObstacle(final Coord myCenter) {
        final int i = myCenter.getX();
        final int j = myCenter.getY();

        Coord nearest = null;
        for (int y = j - 2; y <= j + 2; y++) {
            final int tempY = y;
            if (y < 0) {
                y = Constants.HEIGHT - y;
            } else if (y >= Constants.HEIGHT) {
                y = y - Constants.HEIGHT;
            }
            for (int x = i - 2; x <= i + 2; x++) {
                //if x is less than 0 subtract x from width, same with y
                final int tempX = x;
                if (x < 0) {
                    x = Constants.WIDTH - x;
                } else if (x >= Constants.WIDTH) {
                    x = x - Constants.WIDTH;
                }

                if (!this.isAt(x,y)) { // returns false if an obstacle is found
                    if (nearest == null) {
                        nearest = new Coord(x,y);
                    } else {
                        if (myCenter.distance(new Coord(x,y)) < myCenter.distance(nearest)) {
                            nearest = new Coord(x,y);
                        }
                    }
                }

                if (tempX < 0 || tempX >= Constants.WIDTH) {
                    x = tempX;
                }
            }
            if (tempY < 0 || tempY >= Constants.HEIGHT) {
                y = tempY;
            }
        }


        return nearest;
    }


    /**
     * @param x
     * @param y
     * @return False if an obstacle is found.
     */
    public boolean isAt(final int x, final int y) {

        return !this.location[x][y];
    }


    //public boolean isIn(Coord leftRange)

    public Coord getCenter() {
        return Center;
    }
}
