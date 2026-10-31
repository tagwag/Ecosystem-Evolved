package Models;

import static java.lang.StrictMath.atan2;

public class ImageProperties {


    public double directionAngle;
    public double goalAngle;
    public double stepAmount;


    public ImageProperties() {
    }

    public void calcDirection(final int xOld, final int yOld, final int xNew, final int yNew) {
        final double delta_x = xNew - xOld;
        //double delta_y = yNew - yOld;
        final double delta_y = yOld - yNew;
        goalAngle = atan2(delta_y, delta_x);
        int step = 8;
        if (directionAngle > goalAngle) {
            stepAmount = (directionAngle - goalAngle) / step;
        } else if (directionAngle < goalAngle){
            stepAmount = (goalAngle - directionAngle) / step;
        } else {
            stepAmount = 0;
        }
        /*
        if (this.directionAngle < this.goalAngle - 1 || this.directionAngle > this.goalAngle + 1) {
            this.stepAmount = 0;
        }
*/
    }

    public void stepRotate() {
        if (directionAngle != goalAngle) {
            directionAngle += this.stepAmount;
        } else {
            stepAmount = 0;
        }
    }

    public double getDirectionAngle() {
        return this.directionAngle;
    }
}
