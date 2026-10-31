package Models.Worm;

import Constants.Constants;
import Enviroment.Coord;
import Models.Facts;
import Models.State.State;
import Request.InteractionRequest;
import Request.SightRequest;
import Result.SightResult;
import Technical.IDGen;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class Worm {

    public final State state = new State(true);
    public final int diet = new Random().nextInt(4);
    public final int sight = new Random().nextInt(100);
    public final int threatTolerance = new Random().nextInt(100);
    public final int hungerTolerance = 1000;
    public final int id;
    final Facts facts = new Facts();
    final Random random = new Random();
    public wormHead head;
    public ArrayList<wormBody> wormBodies;
    public int size = 100;
    public int score;
    public int type;
    public wormBody tail;
    public double speed;
    public double movementSpeed;
    public int goalXSpeed;
    public int goalYSpeed;
    public int xSpeed;
    public int ySpeed;
    Coord lastDirection;
    int energy = 50;
    ArrayList<Coord> threatDirection = new ArrayList<>();
    Constants constants = new Constants();
    //private final Coord lastSearch;


    public Worm(final int length, final IDGen idGen) {
        initialize(length);
        id = idGen.makeOtherID();
    }

    public void initialize(final int length) {

        this.head = new wormHead(new Random().nextInt(new Constants().WIDTH), 2);

        this.wormBodies = new ArrayList<>();
        wormBody prev = null;
        for (int i = 0; i < length; i++) {

            if (i == 0) {
                final wormBody current = new wormBody(this.head.getX() + 5, this.head.getY() + 5);
                this.wormBodies.add(current);
                prev = current;
            } else {
                final wormBody current = new wormBody(prev.x + 5, prev.y);
                this.wormBodies.add(current);
                prev = current;
            }

        }
        size = this.wormBodies.size() * 10;
        this.tail = prev;

    }

    public int moveCoord(final Coord coord) {
        int xSpeed = 0;
        int ySpeed = 0;

        //final int movementSpeed = (int) this.size2speed(this.size);
        final int movementSpeed = 5;
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
        this.move(xSpeed, ySpeed);

        return 1;
    }

    public void move(final int xSpeed, final int ySpeed) {

        this.head.x += xSpeed;
        this.head.y += ySpeed;

        wormBody prev = null;
        boolean first = true;
        int[] prevSpeed = {0, 0};
        for (final wormBody body : wormBodies) {

            if (first) {
                prevSpeed = body.move(this.head.x, this.head.y, xSpeed, ySpeed);
                first = false;
            } else {
                //body.move(prev.x, prev.y, xSpeed, ySpeed);
                body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
            }
            prev = body;
        }

    }

    public SightRequest examineWorld() {
        return new SightRequest(this.head.x, this.head.y, this.sight, this);
    }

    public void age() {
        head.age++;
        for (final wormBody body : this.wormBodies) {
            body.age++;
        }
    }

    /**
     * Simulating time passing and energy usage by living.
     *
     * @param cost How much energy is consumed in one tick.
     */
    public void metabolism(final int cost) {
        energy -= cost;
        state.hungry = energy < this.hungerTolerance;
        if (energy <= 0) {
            if (wormBodies.size() > 0) {
                energy += 100;
                final int smaller = size / wormBodies.size();
                this.size -= smaller;
                this.loseHead();
            } else {
                state.dead = true;
            }
        }
    }

    public void loseHead() {
        if (this.wormBodies.size() > 0) {
            head = this.wormBodies.get(0).toHead();
            if (this.wormBodies.size() == 1) {
                wormBodies = new ArrayList<>();
            } else {
                wormBodies.remove(0);
            }
        } else {
            state.dead = true;
        }
    }

    public InteractionRequest actOnKnowledge(final SightResult result) {
        //move
        this.age();
        metabolism(1);

        //obstacleAvoidance();
        //this.obstacleArrayList = new ArrayList<>();
        final Coord closestThreat;

        //eat first then run, mate and explore

        if (state.hungry) {
            //go get food
            final Coord closestFood = this.analyzeFoodSources(result.getFoodDirection());
            if (closestFood != null && !state.scared) {
                lastDirection = closestFood;
                this.burnCalories(this.move(closestFood, true));

                //if touching, return an Interaction request!
                if (this.facts.touching(this.head, closestFood)) {
                    if (closestFood.meat) {
                        return new InteractionRequest(1, closestFood.x, closestFood.y);
                    } else {
                        return new InteractionRequest(2, closestFood.x, closestFood.y);
                    }
                }
            }
        } else {
            closestThreat = this.analyzeThreats(result.getThreatDirection());
            // } while (noMoreThan2(closestThreat,result.getThreatDirection()));
            if (closestThreat != null) {
                lastDirection = new Coord(-closestThreat.x, -closestThreat.y);

                //burnCalories(moveCoord(closestThreat));
                this.burnCalories(this.move(closestThreat, false));
                state.scared = true;
                return null;
            } else {
                state.scared = false;
            }
            //run, mate and explore
            final Coord closestMate;
            //do {
            closestMate = this.analyzePotentialMates(result.getReproductionDirection());
            //} while (!noMoreThan2(closestMate, result.getReproductionDirection()));
            if (closestMate != null && !state.hungry && !state.scared) {
                //Movement temp = new Movement(closestMate, this.getCenter(), true, this.size, this.strategy);
                //this.move(temp);
                lastDirection = closestMate;
                //burnCalories(moveCoord(closestMate));
                this.burnCalories(this.move(closestMate, true));
                //if touching, return an Interaction request!
                if (this.facts.touching(this.head, closestMate)) {
                    return new InteractionRequest(3, closestMate.x, closestMate.y);
                }
            }
        }
        if (this.type != 3 || result.getReproductionDirection().size() < 3) {
            if (lastDirection != null) {
                final Random random = new Random();
                final int tem = random.nextInt(500);
                if (tem <= 10) {
                    //new direction
                    final Coord newDirection = new Coord(random.nextInt(Constants.WIDTH), random.nextInt(Constants.HEIGHT));
                    //this.burnCalories(moveCoord(newDirection));
                    burnCalories(this.move(newDirection, true));
                    lastDirection = newDirection;
                } else {
                    //same direction
                    burnCalories(this.moveCoord(this.lastDirection));
                }
            } else {
                final Coord newDirection = new Coord(this.random.nextInt(Constants.WIDTH), this.random.nextInt(Constants.HEIGHT));
                burnCalories(this.move(newDirection, true));
                lastDirection = newDirection;
            }
        }
        return null;
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
     *
     * @param growthFactor int
     */
    public void grow(final double growthFactor) {
        score++;
        //this.size += growthFactor; //The cell grows in size.
        size += 5;
        //this.body.growBody(this.size); //might break everything.. Slows everything down.
        energy += growthFactor; //the cell gains more energy

        if (this.size % 10 == 0 && !this.state.dead) {
            if (this.tail == null) {
                wormBody temp = new wormBody(this.head.x + 5, this.head.y);
                this.tail = temp;
                wormBodies.add(temp);
                return;
            }
            if (this.tail.state.dead == true) {
                wormBody temp = new wormBody(this.head.x + 5, this.head.y);
                this.tail = temp;
                wormBodies.add(temp);
            } else {
                wormBodies.add(new wormBody(this.tail.x + 5, this.tail.y));
            }
        }

        //this.color = this.color - this.energy * 1000 - this.size * 10; //For changing color based off of energy and size.
    }

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
        //final int xOld = this.head.x;
        //final int yOld = this.head.y;
        boolean xAssigned = false;
        boolean yAssigned = false;
        temp++;
        if (!good) {

            //final Random random = new Random();
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
                }  /*
                    int t = 1;
                    if (random.nextInt(100) <= 50) {
                        t *= -1;
                    }
                    x += strategy;

                     */
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

    public Worm splitWorm(final IDGen idGen) {

        //determine the halfway point
        final int halfway = wormBodies.size() / 2;

        final ArrayList<wormBody> newWormBody = (ArrayList<wormBody>) wormBodies.subList(halfway, wormBodies.size() - 1);
        wormBodies = (ArrayList<wormBody>) wormBodies.subList(0, halfway);
        tail = this.wormBodies.get(this.wormBodies.size() - 1);
        final Worm split = new Worm(0, idGen);
        split.wormBodies = newWormBody;
        split.loseHead();
        return null;
    }

    public Worm splitWormOffset(final IDGen idGen, final int offset) {

        //determine the halfway point

        final List<wormBody> bodyList = wormBodies.subList(offset, wormBodies.size() - 1);

        final List<wormBody> temp = wormBodies.subList(0, offset);
        wormBodies = new ArrayList<>(temp);
        final ArrayList<wormBody> newWormBody = new ArrayList<>(bodyList);
        tail = this.wormBodies.get(this.wormBodies.size() - 1);
        final Worm split = new Worm(0, idGen);
        split.wormBodies = newWormBody;
        split.loseHead();
        return split;
    }

}

