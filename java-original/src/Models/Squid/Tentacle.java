package Models.Squid;

import Constants.Constants;
import Enviroment.Coord;
import Exceptions.UnexpectedState;
import Models.Facts;
import Models.State.State;
import Request.InteractionRequest;
import Request.SightRequest;
import Result.SightResult;

import java.util.ArrayList;
import java.util.Random;

public class Tentacle {

    public final State state = new State(true);
    public final int diet = 1;
    public final Facts facts = new Facts();
    public final Random random = new Random();
    public final int threatTolerance = 10;
    public ArrayList<SquidLeg> segment = new ArrayList<>();
    public int sight = 10;
    public Coord headLocation;
    public SquidLeg touchingHead;
    public SquidLeg grabber;
    public Constants constants = new Constants();
    public Coord lastDirection;
    public Coord target = null;
    public boolean assignedTarget = false;
    public boolean targetReached = false;
    public boolean retracting = false;
    public int type;
    public int size = 100;
    public int still = 0;
    public boolean addTentacle = false;
    public int energyContributed = 0;
    public int score = 0;
    private InteractionRequest request = null;

    public Tentacle(final int length, final int x, final int y) {
        initialize(length, x, y);
    }

    public void initialize(final int length, final int x, final int y) {
        SquidLeg prev = null;
        this.headLocation = new Coord(x, y);
        for (int i = 0; i < length; i++) {

            if (i == 0) {
                this.touchingHead = new SquidLeg(x + 5, y + 5);
                this.touchingHead.parent = new Coord(x, y);
                this.segment.add(this.touchingHead);
                prev = this.touchingHead;
            } else {

                final SquidLeg current = new SquidLeg(prev.x + 5, prev.y);
                this.segment.get(i - 1).setChild(current);
                current.setParent(this.segment.get(i - 1));
                prev = current;
                if (i + 1 == length) {
                    this.grabber = current;
                    this.grabber.grabber = true;
                    this.segment.add(this.grabber);
                } else {
                    this.segment.add(current);
                }
            }
        }
    }

    public void updateHeadLocation(Coord headLocation) {
        this.headLocation = headLocation;
    }

    public void attack(final Coord pos) {


    }

    public void moveCoord(final Coord coord) {
        this.moveGrabber(coord.x, coord.y);
    }

    public void move(final int xSpeed, final int ySpeed) {

        this.headLocation = new Coord(xSpeed, ySpeed);
        this.headLocation.x = xSpeed;
        this.headLocation.y = ySpeed;
        int prevGrabberX = grabber.x;
        int prevGrabberY = grabber.y;
        boolean first = true;
        Coord prevLcoation = null;

        if (retracting) {
            retractGrabber();
        } else {
            for (final SquidLeg body : segment) {

                if (first) {
                    body.move(this.headLocation);
                    first = false;
                    prevLcoation = body.getCenter();
                } else {
                    body.move(prevLcoation);
                    prevLcoation = body.getCenter();
                }
            }
        }

        //if (grabber.x == prevGrabberX && grabber.y == preGrabberY) {
        if (Math.abs(grabber.x - prevGrabberX) <= 3 && Math.abs(grabber.y - prevGrabberY) <= 3) {
            //stuck?
            still++;
        }
        if (still == 20) {
            this.retracting = true;
            still = 0;
        }

    }

    public void retractGrabber() {

        //move the grabber to the head.
        if (this.retracting) {
            int lastGrabberX = grabber.x;
            int lastGrabberY = grabber.y;
            int tempX = touchingHead.x;
            int tempY = touchingHead.y;

            if (tempX + 4 < grabber.x) {
                grabber.x -= 1;
            }
            if (tempX + 4 > grabber.x) {
                grabber.x += 1;
            }
            if (tempY + 4 < grabber.y) {
                grabber.y -= 1;
            }
            if (tempY + 4 > grabber.y) {
                grabber.y += 1;
            }


            if (facts.touching(grabber, touchingHead.getCenter())) {
                this.retracting = false;
                //targetReached = false;
                //assignedTarget = false;
            } else if (lastGrabberX == grabber.x && lastGrabberY == grabber.y) {
                this.retracting = false;
                //targetReached = false;
                //assignedTarget = false;
            }
        }
    }

    public InteractionRequest getRequest() {
        return request;
    }

    public void getTarget(final SightResult result, ArrayList<Coord> listOfTargets) {
        if (result == null) {
            throw new NullPointerException();
        }
        if (result.getFoodDirection().size() != 0) {
            final Coord closestFood = this.analyzeFoodSources(result.getFoodDirection());
            if (listOfTargets.indexOf(closestFood) == -1) {
                if (closestFood != null && !state.scared) {
                    this.target = closestFood;
                    this.assignedTarget = true;
                }
            } else if (result.getFoodDirection().size() != 1) {

                final Coord nextClosestFood = this.analyzeFoodSources(result.getFoodDirection(), listOfTargets);
                if (nextClosestFood != null && !state.scared) {
                    this.target = nextClosestFood;
                }
                this.assignedTarget = true;
            } else {
                this.assignedTarget = false;
            }

        }
    }

    public Coord stateTarget() {
        return this.target;
    }

    /**
     * @return False if no assigned target, True if a target is assigned.
     */
    public boolean attackTarget() throws UnexpectedState {
        if (!assignedTarget && !retracting) { // if not assigned a target and not retracting
            return false; // get a target assigned by searching for one
        }
        if (!retracting && target != null) { // if not retracting
            /*
            if (!targetReached) { // if the target is not reached, move towards the target
                if (target != null) {
                    moveGrabberToTarget(); //might cause stuttering, migrate to an update position style method
                } else {
                    retracting = true;
                    assignedTarget = false;
                    targetReached = false;
                }
            }

             */
            if (facts.touching(grabber, target)) { // if touching. Prepare an interaction request.
                assignedTarget = false;
                targetReached = true;
                retracting = true;
                if (target.meat) {
                    this.request = new InteractionRequest(1, target.x, target.y);
                } else {
                    this.request = new InteractionRequest(2, target.x, target.y);
                }
            } else {
                if (target != null) {
                    moveGrabberToTarget(); //might cause stuttering, migrate to an update position style method
                } else {
                    retracting = true;
                    assignedTarget = false;
                    targetReached = false;
                }
                //throw new UnexpectedState(); // This should never be reached but it's good to have.
            }

        } else {

            //retractGrabber(); // once retracting destination is reached, then retracting becomes false
            this.retracting = false;
        }
        return true; // a target was assigned the whole time, we simply used this opportunity to check if a target is assigned
        //to increment movement towards the target.
    }

    public void moveGrabberToTarget() {
        int lastGrabberX = grabber.x;
        int lastGrabberY = grabber.y;

        int xMovement = 0;
        int yMovement = 0;

        //i need to move in increments of 1
        if (target.x > grabber.x) {
            xMovement += 1;
        } else if (target.x < grabber.x) {
            xMovement -= 1;
        }

        if (target.y > grabber.y) {
            yMovement += 1;
        } else if (target.y < grabber.y) {
            yMovement -= 1;
        }
        //moveGrabber(target.x, target.y);
        moveGrabber(xMovement, yMovement);
        if (lastGrabberX == grabber.x && lastGrabberY == grabber.y) {
            //target is out of range! retract!
            //System.out.println("Out of Range! Or maybe we are stuck?");
            retracting = true;
            assignedTarget = false;
            targetReached = false; //do not make an interaction request, you never reached your target.
        }

    }

    public void moveGrabber(final int x, final int y) {

        final SquidLeg grabber = this.segment.get(this.segment.size() - 1);

        final int xDistanceParent = Math.abs(grabber.parent.getX() - grabber.x);
        final int yDistanceParent = Math.abs(grabber.parent.getY() - grabber.y);
        //if ((xDistanceParent < 8) && (yDistanceParent < 8)) {
        grabber.x += x;
        grabber.y += y;
        //}

        //SquidLeg temp = new SquidLeg(grabber.x, grabber.y);

        final int[] prevLocation = {0, 0};
        prevLocation[0] = grabber.getX();
        prevLocation[1] = grabber.getY();
        boolean first = true;
        final boolean last = true;
        Coord prevLcoation = null;
        for (int i = this.segment.size() - 1; i >= 0; i--) {
            if (first) {
                prevLcoation = this.segment.get(i).moveGrabberUntil(grabber.getCenter(), true, last, grabber.x - x, grabber.y - y);
                first = false;
            } else {
                try {
                    prevLcoation = this.segment.get(i).moveRev(prevLcoation, false, last);
                } catch (final Exception e) {
                    System.out.println(e.getMessage());
                }
                this.segment.get(i + 1).parent = prevLcoation;
            }
        }
    }

    public InteractionRequest actOnKnowledge(final SightResult result) {
        //move
        //age();
        //this.metabolism(1);

        //obstacleAvoidance();
        //this.obstacleArrayList = new ArrayList<>();
        final Coord closestThreat;

        //eat first then run, mate and explore
        state.hungry = true;
        if (state.hungry) {
            //go get food
            final Coord closestFood = this.analyzeFoodSources(result.getFoodDirection());
            if (closestFood != null && !state.scared) {
                lastDirection = closestFood;
                this.moveCoord(closestFood);
/*
                //if touching, return an Interaction request!
                if (this.facts.touching(this.grabber, closestFood)) {
                    if (closestFood.meat) {
                        return new InteractionRequest(1, closestFood.x, closestFood.y);
                    } else {
                        return new InteractionRequest(2, closestFood.x, closestFood.y);
                    }
                }

 */
            }
        }
        /*else {
            closestThreat = this.analyzeThreats(result.getThreatDirection());
            // } while (noMoreThan2(closestThreat,result.getThreatDirection()));
            if (closestThreat != null) {
                final Coord temp = new Coord(-closestThreat.x, -closestThreat.y);
                lastDirection = temp;

                //burnCalories(moveCoord(closestThreat));
                this.moveCoord(temp);
                //move(closestThreat);
                state.scared = true;
                return null;
            } else {
                state.scared = false;
            }
            //run, mate and explore
        }

         */
        if (lastDirection != null) {
            final Random random = new Random();
            final int tem = random.nextInt(500);
            if (tem <= 10) {
                //new direction
                final Coord newDirection = new Coord(random.nextInt(Constants.WIDTH), random.nextInt(Constants.HEIGHT));
                //this.burnCalories(moveCoord(newDirection));
                this.moveCoord(newDirection);
                lastDirection = newDirection;
            } else {
                //same direction
                this.moveCoord(this.lastDirection);
            }
        } else {
            final Coord newDirection = new Coord(this.random.nextInt(Constants.WIDTH), this.random.nextInt(Constants.HEIGHT));
            this.moveCoord(newDirection);
            lastDirection = newDirection;
        }

        return null;
    }

    public int getDirection4Head() {

        int grabberX = grabber.x;
        int grabberY = grabber.y;
        //maybe I should use the direction of the target instead of the tentacles. this is because the target is in the end where the squid wants to go.

        if (target == null) { // if no target, then the tentacle has no say in direction.
            return -1;
        }
        //int grabberX = target.x;
        //int grabberY = target.y;

        int headX = headLocation.x;
        int headY = headLocation.y;

        //int xDif = Math.abs(headX - grabberX);
        int xDifnonABS = grabberX - headX;
        //int yDif = Math.abs(headY - grabberY);
        int yDifnonABS = grabberY - headY;

        int direction = -1;

        if (grabberX == headX && grabberY == headY) {
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

        if (grabberX > headX) {

            if (grabberY > headY) {
                direction = 1;
            } else if (grabberY < headY) {
                direction = 3;
            }

        } else if (grabberX < headX) {

            if (grabberY > headY) {
                direction = 7;
            } else if (grabberY < headY) {
                direction = 5;
            }

        } else if (grabberX == headX) {

            if (grabberY > headY) {
                direction = 0;
            } else if (grabberY < headY) {
                direction = 4;
            }

        }
        if (grabberY == headY) {

            if (grabberX > headX) {
                direction = 2;
            } else if (grabberX < headX) {
                direction = 6;
            }

        }
        return direction;
            /*
            int direction = 0;
            if (xDif >= yDif) {
                if (grabberX > headX) {
                    direction = 1;
                } else {
                    direction = 2;
                }
            } else {
                if (grabberY > headY) {
                    direction = 3;
                } else {
                    direction = 4;
                }
            }
            return direction;

             */
    }

    public int getDirection() {
        /*
        int grabberX = grabber.x;
        int grabberY = grabber.y;
        //maybe I should use the direction of the target instead of the tentacles. this is because the target is in the end where the squid wants to go.
         */
        if (target == null) { // if no target, then the tentacle has no say in direction.
            return -1;
        }
        int grabberX = target.x;
        int grabberY = target.y;

        int headX = headLocation.x;
        int headY = headLocation.y;

        //int xDif = Math.abs(headX - grabberX);
        int xDifnonABS = grabberX - headX;
        //int yDif = Math.abs(headY - grabberY);
        int yDifnonABS = grabberY - headY;

        int direction = -1;

        if (grabberX == headX && grabberY == headY) {
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

        if (grabberX > headX) {

            if (grabberY > headY) {
                direction = 1;
            } else if (grabberY < headY) {
                direction = 3;
            }

        } else if (grabberX < headX) {

            if (grabberY > headY) {
                direction = 7;
            } else if (grabberY < headY) {
                direction = 5;
            }

        } else if (grabberX == headX) {

            if (grabberY > headY) {
                direction = 0;
            } else if (grabberY < headY) {
                direction = 4;
            }

        }
        if (grabberY == headY) {

            if (grabberX > headX) {
                direction = 2;
            } else if (grabberX < headX) {
                direction = 6;
            }

        }
        return direction;
        /*
        int direction = 0;
        if (xDif >= yDif) {
            if (grabberX > headX) {
                direction = 1;
            } else {
                direction = 2;
            }
        } else {
            if (grabberY > headY) {
                direction = 3;
            } else {
                direction = 4;
            }
        }
        return direction;

         */
    }

    public Coord analyzeFoodSources(final Iterable<Coord> foodDirection) {

        Coord closestFood = null;
        boolean first = true;

        if (diet == 0) { // carnivore
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestFood) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                closestFood = food;
                            }
                        }
                    }
                }
            }
            return closestFood;
        }
        if (diet == 1) { // omnivore favoring meat
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestMeat) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestPlant) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                closestPlant = food;
                            }
                        }
                    }
                }
            }
            if (closestMeat != null) {
                return closestMeat;
            } else {
                return closestPlant;
            }
        }
        if (diet == 2) { // omnivore favoring plants
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestMeat) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestPlant) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                closestPlant = food;
                            }
                        }
                    }
                }
            }
            if (closestPlant != null) {
                return closestPlant;
            } else {
                return closestMeat;
            }
        }
        if (diet == 3) { // herbivore
            for (final Coord food : foodDirection) {
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestFood) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                closestFood = food;
                            }
                        }
                    }
                }
            }
            return closestFood;
        }
        return null;
    }

    public boolean isInList(Coord coord, ArrayList<Coord> attacking) {

        for (Coord compareTo : attacking) {

            if (compareTo.x == coord.x && compareTo.y == coord.y) {
                return true;
            }
        }
        return false;
    }

    public Coord analyzeFoodSources(final Iterable<Coord> foodDirection, ArrayList<Coord> listOfTargets) {

        Coord closestFood = null;
        boolean first = true;

        if (diet == 0) { // carnivore
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (first) {
                            //if (listOfTargets.indexOf(food) != 1) {
                            if (!isInList(food, listOfTargets)) {
                                closestFood = food;
                                first = false;
                            }
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestFood) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {

                                //if (listOfTargets.indexOf(food) != 1) {
                                if (!isInList(food, listOfTargets)) {
                                    closestFood = food;
                                }
                            }

                        }
                    }
                }
            }
            return closestFood;
        }
        if (diet == 1) { // omnivore favoring meat
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstMeat) {
                            //if (listOfTargets.indexOf(food) != 1) {
                            if (!isInList(food, listOfTargets)) {

                                closestMeat = food;
                                firstMeat = false;
                            }
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestMeat) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                //if (listOfTargets.indexOf(food) != 1) {
                                if (!isInList(food, listOfTargets)) {
                                    closestMeat = food;
                                }
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstPlant) {
                            //if (listOfTargets.indexOf(food) != 1) {
                            if (!isInList(food, listOfTargets)) {

                                closestPlant = food;
                                firstPlant = false;
                            }
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestPlant) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                //if (listOfTargets.indexOf(food) != 1) {
                                if (!isInList(food, listOfTargets)) {

                                    closestPlant = food;
                                }
                            }
                        }
                    }
                }
            }
            if (closestMeat != null) {
                return closestMeat;
            } else {
                return closestPlant;
            }
        }
        if (diet == 2) { // omnivore favoring plants
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstMeat) {
                            //if (listOfTargets.indexOf(food) != 1) {
                            if (!isInList(food, listOfTargets)) {

                                closestMeat = food;
                                firstMeat = false;
                            }
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestMeat) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                //if (listOfTargets.indexOf(food) != 1) {
                                if (!isInList(food, listOfTargets)) {

                                    closestMeat = food;
                                }
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (firstPlant) {
                            //if (listOfTargets.indexOf(food) != 1) {
                            if (!isInList(food, listOfTargets)) {

                                closestPlant = food;
                                firstPlant = false;
                            }
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestPlant) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                //if (listOfTargets.indexOf(food) != 1) {
                                if (!isInList(food, listOfTargets)) {

                                    closestPlant = food;
                                }
                            }
                        }
                    }
                }
            }
            if (closestPlant != null) {
                return closestPlant;
            } else {
                return closestMeat;
            }
        }
        if (diet == 3) { // herbivore
            for (final Coord food : foodDirection) {
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food) <= this.sight) {
                        if (first) {
                            //if (listOfTargets.indexOf(food) != 1) {
                            if (!isInList(food, listOfTargets)) {

                                closestFood = food;
                                first = false;
                            }
                        } else {
                            if (this.facts.distance(new Coord(this.grabber.x, this.grabber.y), closestFood) >= this.facts.distance(new Coord(this.grabber.x, this.grabber.y), food)) {
                                //if (listOfTargets.indexOf(food) != 1) {
                                if (!isInList(food, listOfTargets)) {

                                    closestFood = food;
                                }
                            }
                        }
                    }
                }
            }
            return closestFood;
        }
        return null;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Coord analyzeThreats(final Iterable<Coord> threatDirection) {

        Coord closestThreat = null;
        boolean first = true;

        for (final Coord threat : threatDirection) {

            if (this.facts.distance(this.grabber, threat) <= threatTolerance) {
                if (first) {
                    closestThreat = threat;
                    first = false;
                } else {
                    if (this.facts.distance(this.grabber, closestThreat) <= this.facts.distance(this.grabber, threat)) {
                        closestThreat = threat;
                    }
                }
            }

        }

        return closestThreat;
    }

    public void lostASegment() {
        if (segment.size() != 0) {
            this.grabber.state.dead = true;
            this.grabber = this.segment.get(segment.size() - 2);
            this.grabber.grabber = true;
            this.size -= 50;
            this.addTentacle = false;
            ArrayList<SquidLeg> buffer = new ArrayList<>();
            for (SquidLeg seg : this.segment) {
                if (!seg.state.dead) {
                    buffer.add(seg);
                }
            }
            this.segment = buffer;
        } else {
            state.dead = true;
        }
    }

    public void grow(final int score) {
        energyContributed += score * 1000;
        if (!this.addTentacle) {
            this.score += 5;
            size += score;
        }
        if (size % 100 == 0) {
            SquidLeg newSegment = new SquidLeg(grabber.x + 1, grabber.y);
            this.grabber.child = newSegment.getCenter();
            newSegment.parent = grabber.getCenter();
            this.grabber.grabber = false;
            this.grabber = newSegment;
            this.grabber.grabber = true;
            this.segment.add(newSegment);
        }
        if (size % 1500 == 0) {
            this.addTentacle = true;
        }
    }

    public SightRequest examineWorld() throws UnexpectedState {
        if (this.grabber == null) {
            throw new UnexpectedState();
        }
        return new SightRequest(this.grabber.x, this.grabber.y, this.sight, this);
    }

    public Coord getCenter() {
        return new Coord(grabber.x, grabber.y);
    }
}
