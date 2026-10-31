package Models.Worm;

import Constants.Constants;
import Enviroment.Coord;
import Models.State.State;

public class wormBody {

    public int x;
    public int y;
    public int age;
    public int size = 10;
    public State state = new State(true);

    public wormBody(final int x, final int y) {
        this.x = x;
        this.y = y;
    }

    public int getX() {
        return this.x;
    }

    public int getY() {
        return this.y;
    }

    public int[] move(int x, int y, final int xSpeed, final int ySpeed) {

        //If any of these 4 conditions are true, move out of bounds, to be teleported back in bounds on the mirrored side.
        /*
        if (x < 8 && this.x >= Constants.WIDTH - 8) {
            //x = Constants.WIDTH + x;
            x = -x;
        }
        if (y < 8 && this.y >= Constants.HEIGHT - 8) {
            //y = Constants.HEIGHT + y;
            y = -y;
        }
        if (this.x < 8 && x >= Constants.WIDTH - 8) {
            //x = -x;
            x = Constants.WIDTH + x;
        }
        if (this.y < 8 && y >= Constants.HEIGHT - 8) {
            //y = -y;
            y = Constants.HEIGHT + y;
        }

         */


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

        if (this.x < 0) {
            this.x = Constants.WIDTH - this.x;
        }
        if (this.y < 0) {
            this.y = Constants.HEIGHT - this.y;
        }

        if (this.x > Constants.WIDTH) {
            this.x = this.x - Constants.WIDTH;
        }
        if (this.y > Constants.HEIGHT) {
            this.y = this.y - Constants.HEIGHT;
        }


        return prevSpeed;
    }

    public wormHead toHead() {

        return new wormHead(this.x, this.y);

    }

    public Coord getCenter() {
        return new Coord(this.x, this.y);
    }
}
