package Models.Squid;

import Constants.Constants;
import Enviroment.Coord;
import Models.Facts;
import Models.State.State;

public class SquidLeg {

    public int x;
    public int y;
    public int age;
    public int size = 10;
    public State state = new State(true);
    public boolean grabber;
    public int sight = 20;
    public Coord parent;
    public Coord child;

    public SquidLeg(final int x, final int y) {
        this.x = x;
        this.y = y;
    }


    public int getX() {
        return this.x;
    }

    public int getY() {
        return this.y;
    }

    /**
     * @param parent This is the location of the SquidLeg that is viewed as the parent leg (leg directly neighboring and closest to head.)
     * @return Coordinates of this Leg parts condition.
     */
    public Coord move(final Coord parent) {
        this.parent = parent;

        final int xDistance = Math.abs(parent.getX() - x);
        final int yDistance = Math.abs(parent.getY() - y);
        if (xDistance > 8) {
            //move on x axis
            if (parent.x - x < -1) {
                x += -1;
            } else if (parent.x - x > 1) {
                x += 1;
            }
        }
        if (yDistance > 8) {
            //move on y axis
            if (parent.y - y < -1) {
                y += -1;
            } else if (parent.y - y > 1) {
                y += 1;
            }
        }

        //for mirror movement.
        if (parent.x < 20 && this.x >= Constants.WIDTH - 20) {
            this.x += 1;
        }
        if (parent.y < 20 && this.y >= Constants.HEIGHT - 20) {
            this.y += 1;
        }
        if (this.x < 20 && parent.x >= Constants.WIDTH - 20) {
            this.x -= 1;
        }
        if (this.y < 20 && parent.y >= Constants.HEIGHT - 20) {
            this.y -= 1;
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


        return this.getCenter();
    }

    public int[] move(final int x, final int y, final int xSpeed, final int ySpeed) {

        final int xDistance = Math.abs(x - this.x);
        final int yDistance = Math.abs(y - this.y);
        final int[] prevSpeed = {0, 0};
        final int parentDistance = new Facts().distance(getCenter(), this.parent);
        int childDistance = 0;
        if (this.child != null) {
            childDistance = new Facts().distance(getCenter(), this.child);
        }

        if (xDistance >= 8 || xSpeed == 0) {
            //move on x axis
            if (!(parentDistance > 6 || childDistance > 6)) {
                if (x - this.x < -1) {
                    this.x += xSpeed - 1;
                    prevSpeed[0] = xSpeed;
                } else if (x - this.x > 1) {
                    this.x += xSpeed + 1;
                    prevSpeed[0] = xSpeed;
                }
            }
        }
        if (yDistance >= 8 || ySpeed == 0) {
            //move on y axis
            if (!(parentDistance > 6 || childDistance > 6)) {
                if (y - this.y < -1) {
                    this.y += ySpeed - 1;
                    prevSpeed[1] = ySpeed;
                } else if (y - this.y > 1) {
                    this.y += ySpeed + 1;
                    prevSpeed[1] = ySpeed;
                }
            }
        }
        return prevSpeed;
    }

    public SquidHead toHead() {

        return new SquidHead(this.x, this.y);

    }

    public Coord getCenter() {
        return new Coord(this.x, this.y);
    }

    public Grabber toGrabber(final SquidLeg leg) {
        final int x = leg.x;
        final int y = leg.y;
        return new Grabber(x, y);
    }

    public void setParent(final SquidLeg parent) {
        this.parent = new Coord(parent.x, parent.y);
    }

    public void setChild(final SquidLeg child) {
        this.child = new Coord(child.x, child.y);
    }

    public Coord moveRev(final Coord child, final boolean grabber, final boolean last) throws Exception {
        if (!grabber) {
            this.child = child;
            if (!last) {
                final int xDistance = Math.abs(child.getX() - x);
                final int yDistance = Math.abs(child.getY() - y);
                if (xDistance > 8) {
                    //move on x axis
                    if (child.x - x < -1) {
                        x += -1;
                    } else if (child.x - x > 1) {
                        x += 1;
                    }
                }
                if (yDistance > 8) {
                    //move on y axis
                    if (child.y - y < -1) {
                        y += -1;

                    } else if (child.y - y > 1) {
                        y += 1;

                    }
                }
            } else {
                final int nonABSxParent = this.parent.getX() - x;
                final int nonABSYParent = this.parent.getY() - y;
                final int nonabsChildX = child.getX() - x;
                final int nonabsChildY = child.getY() - y;
                //System.out.println("xd: " + xd8 + " yd: " + yd8 + " xdp: " + xdp8 + " ydp: " + ydp8 + " NONABS X Parent: " + nonABSxParent + " NONABS Y Parent: " + nonABSYParent);
                //System.out.println("NONABS X Parent: " + nonABSxParent + " NONABS Y Parent: " + nonABSYParent + "\nnon abs child x: " + nonabsChildX + " non abs child y: " + nonabsChildY);
                if (nonabsChildX < -1) {
                    if (Math.abs(nonABSxParent + 1) < 9) {
                        x -= 1;
                    }
                }
                if (nonabsChildX > 1) {
                    if (Math.abs(nonABSxParent - 1) < 9) {
                        x += 1;
                    }
                }
                if (nonabsChildY < -1) {
                    if (Math.abs(nonABSYParent + 1) < 9) {
                        y -= 1;
                    }
                }
                if (nonabsChildY > 1) {
                    if (Math.abs(nonABSYParent - 1) < 9) {
                        y += 1;
                    }
                }
            }
            return this.getCenter();
        } else {
            final int xDistanceParent = Math.abs(this.parent.getX() - x);
            final int yDistanceParent = Math.abs(this.parent.getY() - y);
            if ((xDistanceParent < 8) && (yDistanceParent < 8)) {
                this.x += child.x - this.x;
                this.x += child.y - this.y;
            } else {
                if (xDistanceParent > 8) {
                    x = this.x - (xDistanceParent - 8);
                }
                if (yDistanceParent > 8)
                    y = this.y - (yDistanceParent - 8);
            }
        }
        return this.getCenter();

    }

    public Coord moveGrabberUntil(final Coord child, final boolean grabber, final boolean last, final int xOld, final int yOld) {
        if (!grabber) {
            this.child = child;
            if (!last) {
                final int xDistance = Math.abs(child.getX() - x);
                final int yDistance = Math.abs(child.getY() - y);
                if (xDistance >= 8) {
                    //move on x axis
                    if (child.x - x < -1) {
                        x += -1;
                    } else if (child.x - x > 1) {
                        x += 1;
                    }
                }
                if (yDistance >= 8) {
                    //move on y axis
                    if (child.y - y < -1) {
                        y += -1;

                    } else if (child.y - y > 1) {
                        y += 1;

                    }
                }
            } else {
                final int xDistance = Math.abs(child.getX() - x);
                final int yDistance = Math.abs(child.getY() - y);
                final int xDistanceParent = Math.abs(this.parent.getX() - x);
                final int yDistanceParent = Math.abs(this.parent.getY() - y);
                if (xDistance >= 8 && !(xDistanceParent >= 8)) {
                    //move on x axis
                    if (child.x - x <= -1) {
                        x += -1;
                    } else if (child.x - x >= 1) {
                        x += 1;
                    }
                }
                if (yDistance >= 8 && !(yDistanceParent >= 8)) {
                    //move on y axis
                    if (child.y - y <= -1) {
                        y += -1;

                    } else if (child.y - y >= 1) {
                        y += 1;

                    }
                }
            }
            return this.getCenter();
        } else {
            final int xDistanceParent = Math.abs(this.parent.getX() - x);
            final int yDistanceParent = Math.abs(this.parent.getY() - y);
            if ((xDistanceParent < 10) && (yDistanceParent < 10)) {
                this.x += child.x - this.x;
                this.x += child.y - this.y;
            } else {
                if (xDistanceParent >= 10) {
                    this.x = xOld;
                }
                if (yDistanceParent >= 10) {
                    this.y = yOld;
                }

                /*
                if (xDistanceParent > 8) {
                    this.x = x - (xDistanceParent - 8);
                }
                if (yDistanceParent > 8)
                    this.y = y - (yDistanceParent - 8);

                 */
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

        return this.getCenter();
    }


    public Coord moveRev(final int x, final int y) {

        final int xDistanceParent = Math.abs(this.parent.getX() - this.x);
        final int yDistanceParent = Math.abs(this.parent.getY() - this.y);
        if ((xDistanceParent < 8) && (yDistanceParent < 8)) {
            this.x = this.x - x;
            this.x = this.y - y;
        }

        return this.getCenter();
    }
}
