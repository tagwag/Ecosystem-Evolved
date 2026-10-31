package Models.Squid;

import Constants.Constants;
import Enviroment.Coord;
import Models.Facts;
import Models.State.State;
import Request.InteractionRequest;
import Request.SightRequest;
import Result.SightResult;
import Technical.IDGen;

import java.lang.reflect.Array;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class Squid {

    public final State state = new State(true);
    public final int diet = new Random().nextInt(4);
    public final int size = 100;
    public final int threatTolerance = new Random().nextInt(100);
    public final int id;
    final Facts facts = new Facts();
    final Random random = new Random();
    private final Coord lastSearch = null;
    private final int lastLegSize = 0;
    public int sight = 50;
    //public ArrayList<ArrayList<SquidLeg>> tentacles = new ArrayList<>();
    public ArrayList<Tentacle> tentacles = new ArrayList<>();
    public SquidHead head;
    public List<SquidLeg> squidLegs;
    public int score;
    public int type;
    public int hungerTolerance = 1000;
    public SquidLeg tail;
    public double speed;
    public double movementSpeed;
    public int goalXSpeed;
    public int goalYSpeed;
    public int xSpeed;
    public int ySpeed;
    public ArrayList<Grabber> grabbers = new ArrayList<>(); //location is where the tails are located normally for worms.
    public int still = 0;
    public int lastDirection;
    public int lastDirectionCounter = 0;
    public boolean gotHungryFull = true;
    public int squidDirection = -1;
    int energy = 500;
    ArrayList<Coord> threatDirection = new ArrayList<>();
    Constants constants = new Constants();
    int currentTentacle;
    ArrayList<Coord> targets = new ArrayList<>(); //

    public Squid(final int length, final int numTent, final IDGen idGen) {
        sight = random.nextInt(100);
        initialize(length, numTent);
        id = idGen.makeOtherID();
    }

    public ArrayList<Coord> getTargetList() {
        return this.targets;
    }

    public void addToTargets(Coord add) {
        this.targets.add(add);
    }

    public void removeFromTargets(Coord toRemove) {
        this.targets.remove(toRemove);
    }

    public boolean alreadyTargeted(Coord toExamine) {
        if (targets.indexOf(toExamine) == -1) {
            return false;
        } else {
            return true;
        }
    }

    public void initialize(final int length, int numTent) {

        this.head = new SquidHead(this.random.nextInt(Constants.WIDTH - 50) + 50, this.random.nextInt(Constants.HEIGHT - 50) + 50);

        if (numTent == 0) {
            numTent = 2;
        }
        for (int j = 0; j < numTent; j++) {
            Tentacle newTent = new Tentacle(length, this.head.x, this.head.y);
            newTent.sight = sight;
            this.tentacles.add(newTent);

        }
    }

    public int moveCoord(final Coord coord) {
        int xSpeed = 0;
        int ySpeed = 0;

        final int movementSpeed = (int) this.size2speed(this.size);

        if (Math.abs(coord.x - this.head.x) > 2) {
            if (coord.x > this.head.x) {
                xSpeed = movementSpeed;
            } else if (coord.x < this.head.x) {
                xSpeed = -movementSpeed;
            }
        }

        if (Math.abs(coord.y - this.head.y) > 2) {
            if (coord.y > this.head.y) {
                ySpeed = movementSpeed;
            } else if (coord.y < this.head.y) {
                ySpeed = -movementSpeed;
            }
        }

        if (head.x < 0) {
            head.x = Constants.WIDTH - head.x;
        }
        if (head.y < 0) {
            head.y = Constants.HEIGHT - head.y;
        }

        if (head.x > Constants.WIDTH) {
            head.x = head.x - Constants.WIDTH;
        }
        if (head.y > Constants.HEIGHT) {
            head.y = head.y - Constants.HEIGHT;
        }

        return 1;
    }

    public void move(final int xSpeed, final int ySpeed) {
        int prevHeadX = head.x;
        int prevHeadY = head.y;
        this.head.x += xSpeed;
        this.head.y += ySpeed;

        if (head.x < 0) {
            head.x = Constants.WIDTH - head.x;
        }
        if (head.y < 0) {
            head.y = Constants.HEIGHT - head.y;
        }

        if (head.x > Constants.WIDTH) {
            head.x = head.x - Constants.WIDTH;
        }
        if (head.y > Constants.HEIGHT) {
            head.y = head.y - Constants.HEIGHT;
        }

        for (final Tentacle squidLegs : tentacles) {

            squidLegs.move(this.head.x, this.head.y);

        }
        /*
        if (Math.abs(head.x - prevHeadX) <= 3 && Math.abs(head.y - prevHeadY) <= 3) {
            //stuck?
            still++;
        }
        if (still == 20) {
            head.x -= 1;
            head.y += 1;
            still = 0;
        }

         */

    }



    public void assignJobs(Coord[] targets) {

        int toAssignCounter = 0;
        for (Tentacle tent : this.tentacles) {
            if (tent.target == null) { // assign a job
                tent.target = targets[toAssignCounter];
                toAssignCounter++;
            }
        }

    }

    public void assignAllGrabbers(Coord target) {

        for (Tentacle tent: this.tentacles) {
            tent.moveGrabber(target.x, target.y);
        }


    }




    public int testDirectionSet() {

        Coord headPosition = new Coord(head.x, head.y);
        int[] directional = {0, 0, 0, 0, 0, 0, 0, 0};
        int directionTemp = -1;
        for (Tentacle tent : tentacles) {

            directionTemp = tent.getDirection();
            if (directionTemp != -1) {
                directional[directionTemp]++;
            }


        }
        int goThisWay = -1;
        int directionCounter = 1;
        for (int x = 0; x < directional.length; x++) {

            if (directional[x] > directionCounter && directional[x] > 0) {
                goThisWay = x;
                directionCounter = directional[x];
            }

        }

       return goThisWay;
    }


    public void setDirection() {

        int mean = 0;


        if (lastDirectionCounter >= 10) {

            int[] directional = {0, 0, 0, 0, 0, 0, 0, 0};

            int directionTemp = -1;
            for (Tentacle tent : tentacles) {
                //mean += tent.getDirection();
                //numTent++;
                directionTemp = tent.getDirection();
                if (directionTemp != -1) {
                    directional[directionTemp]++;
                }

            }
            int goThisWay = -1;
            int directionCounter = 1;
            for (int x = 0; x < directional.length; x++) {

                if (directional[x] > directionCounter && directional[x] > 0) {
                    goThisWay = x;
                    directionCounter = directional[x];
                }

            }

            mean = goThisWay;
            //squid.lastDirection = mean;
            //squid.lastDirectionCounter = 0;
        } else {
            mean = lastDirection;
            //squid.lastDirectionCounter++;
        }

        //float sum = mean / numTent;
        //mean = Math.round(sum/numTent);
        if (mean == -1) {
            //do not move
            return;
        }
        if (mean == 0) {
            //squid.move(0, 1);
        } else if (mean == 1) {
            //squid.move(1, 1);
        } else if (mean == 2) {
            //squid.move(1, 0);
        } else if (mean == 3) {
            //squid.move(1, -1);
        } else if (mean == 4) {
            //squid.move(0, -1);
        } else if (mean == 5) {
            //squid.move(-1, -1);
        } else if (mean == 6) {
            //squid.move(-1, 0);
        } else if (mean == 7) {
            //squid.move(-1, 1);
        }


    }

    public SightRequest examineWorld() {
        return new SightRequest(this.head.x, this.head.y, this.sight, this);
    }

    public void age() {
        head.age++;
        for (final SquidLeg body : this.squidLegs) {
            body.age++;
        }
        //this.metabolism(0);
    }

    /**
     * Simulating time passing and energy usage by living.
     *
     * @param cost How much energy is consumed in one tick.
     */
    public void metabolism(final int cost) {

        ArrayList<Tentacle> tentacleBuffer = new ArrayList<>();

        for (Tentacle tent : this.tentacles) {
            if (!tent.state.dead) {
                this.energy += tent.energyContributed;
                if (tent.addTentacle == true) {
                    tentacleBuffer.add(new Tentacle(3, this.head.x, this.head.y));
                }
                tent.energyContributed = 0;
                tentacleBuffer.add(tent);
            }
        }
        tentacles = tentacleBuffer;
        this.state.hungry = this.energy < 400;
        //energy -= cost;
        if (this.state.hungry) {
            if (gotHungryFull) {
                for (Tentacle tent : this.tentacles) {
                    tent.state.hungry = true;
                }
                gotHungryFull = false;
            }

            if (this.energy <= 0) {

                if (tentacles.size() <= 0) {
                    this.state.dead = true;
                }
                ArrayList<Tentacle> buffer = new ArrayList<>();
                for (Tentacle tent : this.tentacles) {
                    if (tent.segment.size() > 1) {
                        //tent.lostASegment();
                        buffer.add(tent);
                    }
                }
                tentacles = buffer;
                this.energy += 50;
            }

        } else {
            if (!gotHungryFull) {
                for (Tentacle tent : this.tentacles) {
                    tent.state.hungry = false;
                }
                gotHungryFull = true;
            }
        }
        /*
        this.state.hungry = this.energy < hungerTolerance;
        if (this.energy <= 0) {
            if (this.squidLegs.size() > 0) {
                this.energy += 100;
                int smaller = this.size / this.squidLegs.size();
                size -= smaller;
                loseHead();
            } else {
                this.state.dead = true;
            }
        }

         */
    }

    public void loseHead() {
        if (this.squidLegs.size() > 0) {
            head = this.squidLegs.get(0).toHead();
            if (this.squidLegs.size() == 1) {
                squidLegs = new ArrayList<>();
            } else {
                squidLegs.remove(0);
            }
        } else {
            state.dead = true;
        }
    }

    public InteractionRequest actOnKnowledge(final SightResult result) {
        //move
        //age();
        //metabolism(1);
        state.hungry = true;
        //obstacleAvoidance();
        //this.obstacleArrayList = new ArrayList<>();
        Coord closestThreat;

        //eat first then run, mate and explore
        this.currentTentacle++;
        if (this.currentTentacle >= this.tentacles.size()) {
            this.currentTentacle = 0;
        }
        return this.tentacles.get(this.currentTentacle).actOnKnowledge(result);
        //for (Tentacle tent : tentacles) {
        //    tent.actOnKnowledge(result);
        //}
        //return null;
        /*
        if (this.state.hungry) {
            //go get food
            Coord closestFood = analyzeFoodSources(result.getFoodDirection());
            if (closestFood != null && !this.state.scared) {
                this.lastDirection = closestFood;
                burnCalories(move(closestFood, true));

                //if touching, return an Interaction request!
                if (facts.touching(head, closestFood)) {
                    if (closestFood.meat) {
                        return new InteractionRequest(1, closestFood.x, closestFood.y);
                    } else {
                        return new InteractionRequest(2, closestFood.x, closestFood.y);
                    }
                }
            }
        } else {
            closestThreat = analyzeThreats(result.getThreatDirection());
            // } while (noMoreThan2(closestThreat,result.getThreatDirection()));
            if (closestThreat != null) {
                Coord temp = new Coord(-closestThreat.x, -closestThreat.y);
                this.lastDirection = temp;

                //burnCalories(moveCoord(closestThreat));
                burnCalories(move(closestThreat, false));
                this.state.scared = true;
                return null;
            } else {
                this.state.scared = false;
            }
            //run, mate and explore
            Coord closestMate;
            //do {
            closestMate = analyzePotentialMates(result.getReproductionDirection());
            //} while (!noMoreThan2(closestMate, result.getReproductionDirection()));
            if (closestMate != null && !this.state.hungry && !this.state.scared) {
                //Movement temp = new Movement(closestMate, this.getCenter(), true, this.size, this.strategy);
                //this.move(temp);
                this.lastDirection = closestMate;
                //burnCalories(moveCoord(closestMate));
                burnCalories(move(closestMate, true));
                //if touching, return an Interaction request!
                if (facts.touching(head, closestMate)) {
                    return new InteractionRequest(3, closestMate.x, closestMate.y);
                }
            }
        }
        if (type != 3 || (type == 3 && result.getReproductionDirection().size() < 3)) {
            if (this.lastDirection != null) {
                Random random = new Random();
                int tem = random.nextInt(500);
                if (tem <= 10) {
                    //new direction
                    Coord newDirection = new Coord(random.nextInt(constants.WIDTH), random.nextInt(constants.HEIGHT));
                    //this.burnCalories(moveCoord(newDirection));
                    this.burnCalories(move(newDirection, true));
                    this.lastDirection = newDirection;
                } else {
                    //same direction
                    this.burnCalories(moveCoord(lastDirection));
                }
            } else {
                Coord newDirection = new Coord(random.nextInt(constants.WIDTH), random.nextInt(constants.HEIGHT));
                this.burnCalories(move(newDirection, true));
                this.lastDirection = newDirection;
            }
        }
        return null;

         */
    }

    /**
     * For how much energy is lost during a movement.
     *
     * @param energyLost
     */
    public void burnCalories(final int energyLost) {
        energy -= energyLost;
    }

    public Coord analyzeFoodSources(final Iterable<Coord> foodDirection) {

        Coord closestFood = null;
        boolean first = true;

        if (diet == 0) { // carnivore
            for (final Coord food : foodDirection) {
                if (food.meat) {
                    if (this.facts.distance(new Coord(this.head.x, this.head.y), food) <= this.sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (this.facts.distance(new Coord(this.head.x, this.head.y), closestFood) >= this.facts.distance(new Coord(this.head.x, this.head.y), food)) {
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
                    if (this.facts.distance(new Coord(this.head.x, this.head.y), food) <= this.sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (this.facts.distance(new Coord(this.head.x, this.head.y), closestMeat) >= this.facts.distance(new Coord(this.head.x, this.head.y), food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.head.x, this.head.y), food) <= this.sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (this.facts.distance(new Coord(this.head.x, this.head.y), closestPlant) >= this.facts.distance(new Coord(this.head.x, this.head.y), food)) {
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
                    if (this.facts.distance(new Coord(this.head.x, this.head.y), food) <= this.sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (this.facts.distance(new Coord(this.head.x, this.head.y), closestMeat) >= this.facts.distance(new Coord(this.head.x, this.head.y), food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (this.facts.distance(new Coord(this.head.x, this.head.y), food) <= this.sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (this.facts.distance(new Coord(this.head.x, this.head.y), closestPlant) >= this.facts.distance(new Coord(this.head.x, this.head.y), food)) {
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
                    if (this.facts.distance(new Coord(this.head.x, this.head.y), food) <= this.sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (this.facts.distance(new Coord(this.head.x, this.head.y), closestFood) >= this.facts.distance(new Coord(this.head.x, this.head.y), food)) {
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

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Coord analyzeThreats(final Iterable<Coord> threatDirection) {

        Coord closestThreat = null;
        boolean first = true;

        for (final Coord threat : threatDirection) {

            if (this.facts.distance(this.head, threat) <= threatTolerance) {
                if (first) {
                    closestThreat = threat;
                    first = false;
                } else {
                    if (this.facts.distance(this.head, closestThreat) <= this.facts.distance(this.head, threat)) {
                        closestThreat = threat;
                    }
                }
            }

        }

        return closestThreat;
    }

    /**
     * @param reproductionDirection
     * @return
     */
    public Coord analyzePotentialMates(final Iterable<Coord> reproductionDirection) {
        Coord closestMate = null;
        boolean first = true;
        for (final Coord mate : reproductionDirection) {
            if (this.facts.distance(this.head, mate) <= this.sight) {
                if (first) {
                    closestMate = mate;
                    first = false;
                } else {
                    if (this.facts.distance(this.head, closestMate) >= this.facts.distance(this.head, mate)) {
                        closestMate = mate;
                    }
                }
            }

        }
        return closestMate;
    }


    /**
     * When a Cell consumes it grows. This grows the cell in size and gives the cell energy
     * allowing the cell to survive longer.
     * <p>
     * // * @param growthFactor int
     */
    /*
    public void grow(double growthFactor) {
        this.score++;
        //this.size += growthFactor; //The cell grows in size.
        this.size += 10;
        //this.body.growBody(this.size); //might break everything.. Slows everything down.
        this.energy += growthFactor; //the cell gains more energy
        ArrayList<SquidLeg> temp = this.tentacles.get((tentacles.size() - 1));
        this.lastLegSize = temp.size();
        if (lastLegSize < 6) {
            if (size % 10 == 0) {
                SquidLeg tail = temp.get(lastLegSize - 1);
                temp.add(new SquidLeg(tail.x + 5, tail.y));
            }
        } else {
            this.lastLegSize = 1;
            ArrayList<SquidLeg> temper = new ArrayList<>();
            temper.add(new SquidLeg(head.x, head.y));
            this.tentacles.add(temper);
        }

        //this.color = this.color - this.energy * 1000 - this.size * 10; //For changing color based off of energy and size.
    }

     */
    public Coord getCenter() {
        return new Coord(this.head.getX(), this.head.getY());
    }

    public double size2speed(final double size) {
                /*
                double a = 1393.49;
                double b = 1.34247;
                double t = 0.00918484;
                speed = (a / (1 + (b * Math.exp(t * size))));
                 */

        if (state.smol) {
            this.speed = (((-1.0 / 80.0) * size) + 15.0);
            if (this.speed == 1) {
                state.fat = true;
            }
            return this.speed;
        } else {

            this.speed = (((-5.0 / 8000.0) * size) + 5.0);
            if (this.speed == 1) {
                state.fat = true;
            }
            return this.speed;
        }
    }

    public int move(final Coord object, final boolean good) {

        //movement speed
        //double movementSpeed = (-1.15957/(1+(-1.02527 * Math.exp(0.0640627*size))));
        final double movementSpeed = this.size2speed(this.size);
        this.movementSpeed = movementSpeed;
        final int moving = Math.toIntExact(Math.round(movementSpeed));
        int temp = moving / 2;
        if (temp == 0) {
            temp = 1;
        }
        final int xOld = this.head.x;
        final int yOld = this.head.y;
        boolean xAssigned = false;
        boolean yAssigned = false;
        temp++;
        if (!good) {

            final Random random = new Random();
            //determine if moving to opposite sides of map.
            if (object.x <= 10 && this.head.x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (object.y <= 10 && this.head.y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    this.goalXSpeed = -temp;
                    this.goalYSpeed = -temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    this.goalXSpeed = -temp;
                }

            } else if (object.y <= 10 && this.head.y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                this.goalYSpeed = -temp;
            }

            if (this.head.x <= 10 && object.x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (this.head.y <= 10 && object.y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    this.goalXSpeed = temp;
                    this.goalYSpeed = temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    this.goalXSpeed = temp;
                }

            } else if (this.head.y <= 10 && object.y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                this.goalYSpeed = temp;
            }


            //int temp = random.nextInt(2);
            if (!xAssigned) {
                if (object.getX() > this.head.x) {
                    //x += -temp;
                    this.goalXSpeed = -temp;
                    //this.ySpeed += strategy;
                } else if (object.getX() < this.head.x) {
                    //x += temp;
                    this.goalXSpeed = temp;
                    //this.ySpeed += strategy;
                }
            }
            if (!yAssigned) {
                if (object.getY() > this.head.y) {
                    //y += -temp;
                    this.goalYSpeed = -temp;
                    //this.xSpeed += strategy;
                } else if (object.getY() < this.head.y) {
                    //y += temp;
                    this.goalYSpeed = temp;
                    //this.xSpeed += strategy;
                }  /*
                        int t = 1;
                        if (random.nextInt(100) <= 50) {
                            t *= -1;
                        }
                        y += strategy;

                         */
            }
            xSpeed += goalXSpeed / 16;
            ySpeed += goalYSpeed / 16;
        } else {

            //Random random = new Random();
            //int temp = random.nextInt(2);
            if (object.x <= 10 && this.head.x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (object.y <= 10 && this.head.y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    this.goalXSpeed = temp;
                    this.goalYSpeed = temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    this.goalXSpeed = temp;
                }

            } else if (object.y <= 10 && this.head.y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                this.goalYSpeed = temp;
            }

            if (this.head.x <= 10 && object.x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (this.head.y <= 10 && object.y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    this.goalXSpeed = -temp;
                    this.goalYSpeed = -temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    this.goalXSpeed = -temp;
                }

            } else if (this.head.y <= 10 && object.y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                this.goalYSpeed = -temp;
            }

            //int temp = random.nextInt(2);
            if (!xAssigned) {
                if (object.getX() > this.head.x) {
                    // x += temp;
                    this.goalXSpeed = temp;
                } else if (object.getX() < this.head.x) {
                    //x += -temp;
                    this.goalXSpeed = -temp;
                }
            }
            if (!yAssigned) {
                if (object.getY() > this.head.y) {
                    //y += temp;
                    this.goalYSpeed = temp;
                } else if (object.getY() < this.head.y) {
                    //y += -temp;
                    this.goalYSpeed = -temp;
                }
                xSpeed += goalXSpeed / 3;
                ySpeed += goalYSpeed / 3;

            }
        }
        if (Math.abs(this.xSpeed) >= Math.abs(goalXSpeed)) {
            goalXSpeed = 0;
            xSpeed = 0;
        }
        if (Math.abs(this.ySpeed) >= Math.abs(goalYSpeed)) {
            goalYSpeed = 0;
            ySpeed = 0;
        }
                   /*
                   if (this.goalXSpeed - 2 <= this.xSpeed && this.xSpeed <= this.goalXSpeed + 2) {
                       if (this.goalYSpeed - 2 <= this.ySpeed && this.ySpeed <= this.goalYSpeed + 2) {
                           this.goalXSpeed = 0;
                           this.goalYSpeed = 0;
                           this.ySpeed = 0;
                           this.xSpeed = 0;
                       }
                   }

                    */

        if (this.head.x < 0) {
            this.head.x += Constants.WIDTH;
        } else if (this.head.x > Constants.WIDTH) {
            this.head.x -= Constants.WIDTH;
        }

        if (this.head.y < 0) {
            this.head.y += Constants.HEIGHT;
        } else if (this.head.y > Constants.HEIGHT) {
            this.head.y -= Constants.HEIGHT;
        }
        return 1;
    }
}
