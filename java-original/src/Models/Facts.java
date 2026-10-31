package Models;

import Constants.Constants;
import Enviroment.Coord;
import Models.Mental.Examination;
import Models.Squid.Squid;
import Models.Squid.SquidHead;
import Models.Squid.SquidLeg;
import Models.Worm.Worm;
import Models.Worm.wormHead;

public class Facts {

    public Constants constant = new Constants();

    public Facts() {
    }

    public int distance(final Cell c1, final Cell c2) {
        int radius = 1;
        if (c1.size / Constants.sizeThreshold > 1) {
            radius += (c1.size / Constants.sizeThreshold);
        }

        //determine if it's on the opposite side of the map
        if (c2.x <= 10 && c1.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
        }

        if (c1.x <= 10 && c2.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
        }
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
    }

    public int distance(final Cell c1, final Food c2) {
        int radius = 1;
        if (c1.size / Constants.sizeThreshold > 1) {
            radius += (c1.size / Constants.sizeThreshold);
        }
        //determine if it's on the opposite side of the map
        if (c2.x <= 10 && c1.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
        }

        if (c1.x <= 10 && c2.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
        }
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
    }

    public int distance(final Cell c1, final Coord c2) {
        int radius = 1;
        if (c1.size / Constants.sizeThreshold > 1) {
            radius += (c1.size / Constants.sizeThreshold);
        }

        //determine if it's on the opposite side of the map
        if (c2.x <= 10 && c1.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
        }

        if (c1.x <= 10 && c2.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
        }

        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
    }

    public int distance(final Cell c1, final Examination c2) {
        int radius = 1;
        if (c1.size / Constants.sizeThreshold > 1) {
            radius += (c1.size / Constants.sizeThreshold);
        }

        //determine if it's on the opposite side of the map
        if (c2.x <= 10 && c1.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
        }

        if (c1.x <= 10 && c2.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
        }
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
    }

    public int distance(final Coord c1, final Coord c2) {
        int radius = 1;
        if (5 / Constants.sizeThreshold > 1) {
            radius += (5 / Constants.sizeThreshold);
        }

        //determine if it's on the opposite side of the map
        if (c2.x <= 10 && c1.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow(((Constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c2.y <= 10 && c1.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((Constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
        }

        if (c1.x <= 10 && c2.x >= Constants.WIDTH - 10) {
            //opposite x's
            if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
                //opposite y's as well
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
            } else {
                return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - (Constants.WIDTH - c1.x)), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
            }

        } else if (c1.y <= 10 && c2.y >= Constants.HEIGHT - 10) {
            //opposite y's
            return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - (Constants.HEIGHT - c1.y)), 2))) - radius;
        }
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
    }

    public boolean touching(final Coord c1, final Coord c2) {

        return this.distance(c1, c2) <= 3;

    }

    public boolean touching(final Cell c1, final Cell c2) {

        return this.distance(c1, c2) <= 1;

    }

    public boolean touching(final Cell c, final Food f) {

        return this.distance(c, f) <= 1;

    }

    public boolean touching(final Cell c, final Coord f) {

        return this.distance(c, f) <= 1;

    }

    public boolean touching(final wormHead c, final Coord f) {

        return this.distance(c, f) <= 2;

    }

    public boolean touching(final wormHead c, final Food f) {

        return this.distance(c, f) <= 1;

    }

    public boolean touching(final wormHead c1, final Cell c2) {

        return this.distance(c1, c2) <= 1;

    }

    public boolean touching(final SquidHead c, final Food f) {

        return this.distance(c, f) <= 1;

    }

    public boolean touching(final SquidHead c1, final Cell c2) {

        return this.distance(c1, c2) <= 1;

    }

    public boolean touching(final SquidHead c1, final Coord c2) {

        return this.distance(c1, c2) <= 1;

    }

    public boolean touching(final SquidLeg c1, final Cell c2) {

        return this.distance(c1, c2) <= 1;

    }

    public boolean touching(final SquidLeg c1, final Coord c2) {

        return this.distance(c1, c2) <= 2;

    }

    public int distance(final SquidLeg c1, final Food c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final SquidLeg c1, final Cell c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final SquidLeg c1, final Coord c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final SquidHead c1, final Food c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final SquidHead c1, final Cell c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final SquidHead c1, final Coord c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final wormHead c1, final Food c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final wormHead c1, final Cell c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final wormHead c1, final Coord c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final Food c1, final Coord c2) {
        return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow((c2.y - c1.y), 2)));
    }

    public int distance(final Worm cell, final Coord reqCell) {
        return this.distance(cell.head, reqCell);
    }

    public int distance(final Squid cell, final Coord reqCell) {
        return this.distance(cell.head, reqCell);
    }

    public int direction(Coord c1, Coord c2) {
        
        int xDifnonABS = c1.x - c2.x;
        int yDifnonABS = c1.y - c2.y;

        int direction = -1;

        if (c1.x == c2.x && c1.y == c2.y) {
            if (xDifnonABS < 0) {
                if (yDifnonABS < 0) {
                    direction = 7;
                } else if (yDifnonABS > 0) {
                    direction = 5;
                }
            } else if (xDifnonABS > 0) {
                if (yDifnonABS < 0) {
                    direction = 3;
                } else if (yDifnonABS > 0) {
                    direction = 1;
                }
            }
        }

        if (c1.x > c2.x) {

            if (c1.y > c2.y) {
                direction = 1;
            } else if (c1.y < c2.y) {
                direction = 3;
            }

        } else if (c1.x < c2.x) {

            if (c1.y > c2.y) {
                direction = 7;
            } else if (c1.y < c2.y) {
                direction = 5;
            }

        } else if (c1.x == c2.x) {

            if (c1.y > c2.y) {
                direction = 0;
            } else if (c1.y < c2.y) {
                direction = 4;
            }

        }
        if (c1.y == c2.y) {

            if (c1.x > c2.x) {
                direction = 2;
            } else if (c1.x < c2.x) {
                direction = 6;
            }

        }
        return direction;


    }


}
