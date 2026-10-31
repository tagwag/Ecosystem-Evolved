package Models.Squid;

import Enviroment.Coord;
import Models.State.State;

public class Grabber {

    public int x;
    public int y;
    public final int size = 10;
    public final State state = new State(true);

    public Grabber(final int x, final int y) {
        this.x = x;
        this.y = y;
    }

    public int[] move(final int x, final int y, final int xSpeed, final int ySpeed) {
        final int xDistance = Math.abs(x - this.x);
        final int yDistance = Math.abs(y - this.y);
        final int[] prevSpeed = {0, 0};
        if (xDistance > 8 || xSpeed == 0) {
            //move on x axis
            if (x - this.x < -1) {
                this.x += xSpeed - 1;
                prevSpeed[0] = xSpeed;
            } else if (x - this.x > 1) {
                this.x += xSpeed + 1;
                prevSpeed[0] = xSpeed;
            }
        }
        if (yDistance > 8 || ySpeed == 0) {
            //move on y axis
            if (y - this.y < -1) {
                this.y += ySpeed - 1;
                prevSpeed[1] = ySpeed;
            } else if (y - this.y > 1) {
                this.y += ySpeed + 1;
                prevSpeed[1] = ySpeed;
            }
        }
        return prevSpeed;
    }

    public int moveCoord(final Coord coord) {
        int xSpeed = 0;
        int ySpeed = 0;

        final int movementSpeed = (int) this.size2speed(this.size);

        if (Math.abs(coord.x - this.x) > 2) {
            if (coord.x > this.x) {
                xSpeed += movementSpeed;
            } else if (coord.x < this.x) {
                xSpeed += -movementSpeed;
            }
        }

        if (Math.abs(coord.y - this.y) > 2) {
            if (coord.y > this.y) {
                ySpeed += movementSpeed;
            } else if (coord.y < this.y) {
                ySpeed += -movementSpeed;
            }
        }
        //move(xSpeed, ySpeed);
        this.x += xSpeed;
        this.y += ySpeed;
        return 1;
    }

    public double size2speed(final double size) {
        double speed = 0;
        if (state.smol) {
            speed = (((-1.0 / 80.0) * size) + 15.0);
            if (speed == 1) {
                state.fat = true;
            }
            return speed;
        } else {

            speed = (((-5.0 / 8000.0) * size) + 5.0);
            if (speed == 1) {
                state.fat = true;
            }
            return speed;
        }
    }

}
