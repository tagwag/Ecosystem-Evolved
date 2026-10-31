package Models;


import Constants.Constants;
import Enviroment.Coord;
import Enviroment.Movement;
import Models.Mental.Examination;
import Models.State.State;
import Request.InteractionRequest;
import Request.SightRequest;
import Result.SightResult;
import Technical.IDGen;

import java.util.*;

/**
 *
 */
public class Cell {

    public final Facts facts = new Facts();
    public final Random random = new Random();
    //If a cell is touching the this cell, and is edible to this cell. Typically will only ever contain 1 Cell.
    public final List<Cell> CellBeingEaten = new ArrayList<>();
    //If a cell is touching the this cell, and is a potential mate to this cell. Typically will only ever contain 1 Cell.
    public final List<Cell> soulMate = new ArrayList<>();
    //If a FoodBox is touching the this cell, and is edible to this cell. Typically will only ever contain 1 FoodBox.
    public final List<Food> FoodBeingEaten = new ArrayList<>();
    //If an Other object is touching the this cell.
    public final List<Other> OtherBeingEaten = new ArrayList<>();
    public final Constants constants = new Constants();
    public final boolean justRevived = true;
    public final ImageProperties prop = new ImageProperties();
    public State state = new State(true);
    public int x; // Center position coordinate.
    public int y; // Center position coordinate.
    public List<Coord> obstacleArrayList = new ArrayList<>();
    /**
     * These are the traits that change with each cell. These determine the cells ability to survive.
     */
    public int threatTolerance; //the closest this cell will allow a threat (A larger cell of a different species) to get near.
    public int sight; //How far a cell can see. Determines how large a cell's 'memory' is too.
    public int obstacleTolerance; // how close it will allow itself to approach an object, can never be 0.
    public double size; //How big the cell is. The larger it is, the slower it is.
    public int energy; //How much energy the cell has. This goes up as the cell eats food sources.
    public int diet; //Determines what this cell considers as food.
    public int strategy; //Avoidance modifier. Aids or causes problems with avoiding threats. I introduced this to add an
    // a strange level of intelligence into the cell. This will change in the future to be some sort of algorithm for threat avoidance.
    public int[] priorities; //What a Cell considers to be most important in it's life.
    public int splittChance;
    public int splitRequirement;
    public int score; // How many cells this cell has consumed.
    public int type;
    //public BiggerBrain biggerBrain = new BiggerBrain();
    //public NeuralNet neuralNet = new NeuralNet();
    public int age;
    public double speed;
    public Examination closestaiObject = new Examination();
    public double movementSpeed;
    public int hungerReq = 50;
    public int xSpeed;
    public int ySpeed;
    public int goalXSpeed;
    public int goalYSpeed;
    private int id; // Unique identifier.
    private Iterable<Coord> threatDirection = new ArrayList<>(); // contains nearby potential threats.
    private List<Coord> foodDirection = new ArrayList<>(); // contains nearby potential food.
    private List<Coord> ObstacleDirection = new ArrayList<>(); // for obstacle avoidance, but unsure how to proceed.
    private List<Coord> OtherDirection = new ArrayList<>();
    private List<Coord> reproductionDirection = new ArrayList<>(); //contains nearby potential mates.
    private Movement lastSearch;
    private Coord lastDirection;//Used in the search function to know it's last movement.
    //private NeuralNetwork brain;
    private Iterable<Examination> thoughts = new ArrayList<>();
    //private Brain thinker = new Brain();
    private boolean foodEaten;
    private int flockingTolerance;
    //action.getActionIndex()
    //private final int constantMotion;

    public Cell(IDGen idGen, boolean smol) {

        this.id = idGen.makeCellID();
        this.x = random.nextInt(Constants.WIDTH); //defines a random location for the cell to appear.
        this.y = random.nextInt(Constants.HEIGHT); //defines a random location for the cell to appear.
        this.state = new State(true, true);
        this.threatTolerance = random.nextInt(20);
        this.size = 2;
        this.sight = random.nextInt(100);
        this.energy = 500;
        random.nextInt(100);
        diet = random.nextInt(4);
        this.strategy = random.nextInt(3);
        random.nextInt(10);
        this.splittChance = random.nextInt(1000);
        type = 0;
        flockingTolerance = random.nextInt(100);
        this.hungerReq = random.nextInt(500);

        int flockDesire = random.nextInt(2);
        if (flockDesire == 0) {
            this.state.desire2Flock = true;
        } else {
            this.state.desire2Flock = false;
        }

    }

    public Cell(IDGen idGen, boolean smol, int threatTolerance, int obstacleTolerance, int sight, double size, int diet,
                int strategy, int[] priorities, int splitChance, int splitRequirement, int type, int flockingTolerance) {


        //gives a body.
        //I think this is the source for new cells just appearing after being born.
        x = random.nextInt(Constants.WIDTH); //defines a random location for the cell to appear.
        y = random.nextInt(Constants.HEIGHT); //defines a random location for the cell to appear.
        this.state = new State(true, true);
        //this.body.buildBody(x,y,(int)size); //might break everything, Slows everything down.
        this.id = idGen.makeCellID(); //makes a unique identifier.
        if (sight < threatTolerance) {
            threatTolerance = sight; //The cell should never be able to perceive threats beyond it's viewing range.
        }

        this.threatTolerance = threatTolerance; //sets threat tolerance
        this.sight = sight; //sets viewing range
        //this.size = size + energy; //leftover energy from previous generations grows the cell in size. Not sure if I will keep.
        this.size = size; //sets size
        this.energy = 200; //default energy

        this.diet = diet; //Determines what it considers food.
        this.priorities = priorities; //sets priorities
        this.strategy = strategy;
        this.splittChance = splitChance;
        this.splitRequirement = splitRequirement;
        //this.type = random.nextInt(2);
        this.type = 0;
        this.type = type;
        this.flockingTolerance = flockingTolerance;
        if (this.type == 1) {
            //give it a brain.
            //this.biggerBrain = new BiggerBrain();
            //this.brain = new NeuralNetwork();
            this.energy = 300;
        }
        if (type == 3) {
            this.diet = 3;
            this.energy = 1000;
        }
        this.hungerReq = random.nextInt(500);
        this.size = random.nextDouble() * 10;
        int flockDesire = random.nextInt(2);
        if (flockDesire == 0) {
            this.state.desire2Flock = true;
        } else {
            this.state.desire2Flock = false;
        }
    }

    /**
     * Main Cell Constructor. Used for evolution, reproduction. Contains traits that determine its ability to survive.
     *
     * @param idGen           IDGen Object
     * @param threatTolerance int
     * @param sight           int
     * @param size            int
     * @param diet            int
     * @param strategy        int
     * @param priorities      int[]
     */
    public Cell(IDGen idGen, int threatTolerance, int obstacleTolerance, int sight, double size, int diet,
                int strategy, int[] priorities, int splitChance, int splitRequirement, int type, int flockingTolerance) {

        //gives a body.
        //I think this is the source for new cells just appearing after being born.
        x = random.nextInt(Constants.WIDTH); //defines a random location for the cell to appear.
        y = random.nextInt(Constants.HEIGHT); //defines a random location for the cell to appear.

        //this.body.buildBody(x,y,(int)size); //might break everything, Slows everything down.
        this.id = idGen.makeCellID(); //makes a unique identifier.
        if (sight < threatTolerance) {
            threatTolerance = sight; //The cell should never be able to perceive threats beyond it's viewing range.
        }
        this.threatTolerance = threatTolerance; //sets threat tolerance
        this.sight = sight; //sets viewing range
        //this.size = size + energy; //leftover energy from previous generations grows the cell in size. Not sure if I will keep.
        this.size = size; //sets size
        this.energy = 200; //default energy
        this.diet = diet; //Determines what it considers food.
        this.priorities = priorities; //sets priorities
        this.strategy = strategy;
        this.splittChance = splitChance;
        this.splitRequirement = splitRequirement;
        //this.type = random.nextInt(2);
        this.type = 0;
        this.type = type;
        this.flockingTolerance = flockingTolerance;
        if (this.type == 1) {
            //give it a brain.
            //this.biggerBrain = new BiggerBrain();
            //this.brain = new NeuralNetwork();
            this.energy = 300;
        }
        if (type == 3) {
            this.diet = 3;
            this.energy = 1000;
        }
        this.hungerReq = random.nextInt(500);
        int flockDesire = random.nextInt(2);
        if (flockDesire == 0) {
            this.state.desire2Flock = true;
        } else {
            this.state.desire2Flock = false;
        }
    }

    /**
     * Default Constructor, empty.
     */
    public Cell() {
    }

    /**
     * Used in reproduction. This Constructor is refined and simple.
     *
     * @param x                 int
     * @param y                 int
     * @param id                int
     * @param threatTolerance   int
     * @param obstacleTolerance int
     * @param sight             int
     * @param size              int
     * @param energy            int
     * @param diet              int
     * @param strategy          int
     * @param splitChance       int
     * @param splitRequirement  int
     */
    public Cell(int x, int y, int id, int threatTolerance, int obstacleTolerance, int sight,
                double size, int energy, int diet, int strategy, int splitChance, int splitRequirement) {
        this.x = x;
        this.y = y;
        this.id = id;

        this.threatTolerance = threatTolerance;
        this.obstacleTolerance = obstacleTolerance;
        this.sight = sight;
        this.size = size;
        this.energy = energy;
        this.diet = diet;
        this.strategy = strategy;
        this.splittChance = splitChance;
        this.splitRequirement = splitRequirement;
        this.type = 1;
        this.hungerReq = random.nextInt(500);
    }

    public SightRequest examineWorld() {
        return new SightRequest(x, y, sight, this);
    }

    public final InteractionRequest actOnKnowledge(SightResult result) {
        //move
        this.metabolism(1);

        if (result.getFlockDirection() != null) {
            flocking(result);
        }

        //obstacleAvoidance();
        this.obstacleArrayList = new ArrayList<>();
        Coord closestThreat;

        //eat first then run, mate and explore
        if (type == 0 || (state.wormBody && type == 3)) {
            //if (this.state.hungry) {
            if (true) {
                //go get food
                Coord closestFood = analyzeFoodSources(result.getFoodDirection());
                if (closestFood != null && !this.state.scared) {
                    //Movement temp = new Movement(closestFood, this.getCenter(), true, this.size, this.strategy);
                    //this.move(temp);
                    //this.burnCalories(temp);
                    this.lastDirection = closestFood;
                    burnCalories(move(closestFood, true));

                    //if touching, return an Interaction request!
                    if (facts.touching(this, closestFood)) {
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
                    //Movement temp = new Movement(closestThreat, this.getCenter(), false, this.size, this.strategy);
                    //this.move(temp);
                    this.lastDirection = new Coord(-closestThreat.x, -closestThreat.y);

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
                    burnCalories(move(closestMate, true));

                    //if touching, return an Interaction request!
                    if (facts.touching(this, closestMate)) {
                        return new InteractionRequest(3, closestMate.x, closestMate.y);
                    }
                }
            }
        }
        if (type != 3 || reproductionDirection.size() < 3) {
            if (this.lastDirection != null) {
                Random random = new Random();
                int tem = random.nextInt(500);
                if (tem <= 10) {
                    //new direction
                    Coord newDirection = new Coord(random.nextInt(Constants.WIDTH), random.nextInt(Constants.HEIGHT));
                    this.burnCalories(move(newDirection, true));
                    this.lastDirection = newDirection;
                } else {
                    //same direction
                    this.burnCalories(move(lastDirection, true));
                }
            } else {
                Coord newDirection = new Coord(random.nextInt(Constants.WIDTH), random.nextInt(Constants.HEIGHT));
                this.burnCalories(move(newDirection, true));
                this.lastDirection = newDirection;
            }
            if (this.energy >= this.splitRequirement && !this.state.hungry) {
                if (doISplit()) {
                    return new InteractionRequest(4, x, y);
                }
            }
        }

        return null;
    }

    public boolean isFoodEaten() {
        if (foodEaten) {
            this.foodEaten = false;
            return true;
        }
        return false;
    }

    public InteractionRequest networkAnalysis(SightResult result) {
        //move
        this.metabolism(1);

        Examination closestObject = analyzeObjects(result);
        this.closestaiObject = closestObject;
        //Examination secondClosestObject = analyzeObjectsSecond(result);
        //Examination thirdClosestObject = analyzeObjectsThird(result);
        if (closestaiObject != null) {
            if (facts.touching(this, new Coord(closestObject.x, closestObject.y))) {
                if (closestObject.theirDiet != 5 && (this.diet != 1)) {
                    return new InteractionRequest(1, closestObject.x, closestObject.y);
                } else {
                    return new InteractionRequest(2, closestObject.x, closestObject.y);
                }
            }
        }
/*
        if (closestObject != null) {
            if (secondClosestObject != null) {
                if (thirdClosestObject != null) {
                    //move however it wants to

                    //action 1
                    burnCalories(move(this.thinker.decide(this.thinker.inputs(closestObject, x, y, (int) size, diet, energy))));
                    //action 2
                    burnCalories(move(this.thinker.decide(this.thinker.inputs(secondClosestObject, x, y, (int) size, diet, energy))));
                    //action 3
                    burnCalories(move(this.thinker.decide(this.thinker.inputs(thirdClosestObject, x, y, (int) size, diet, energy))));
                    //for now it just eats everything in sight
                } else {
                    //action 1
                    burnCalories(move(this.thinker.decide(this.thinker.inputs(closestObject, x, y, (int) size, diet, energy))));
                    //action 2
                    burnCalories(move(this.thinker.decide(this.thinker.inputs(secondClosestObject, x, y, (int) size, diet, energy))));
                }
            } else {
                //action 1
                burnCalories(move(this.thinker.decide(this.thinker.inputs(closestObject, x, y, (int) size, diet, energy))));
            }
        } else {
            //move wherever
            burnCalories(move(this.thinker.decide(this.thinker.inputs(null, x, y, (int) size, diet, energy))));
        }
        if (closestObject != null) {
            if (facts.touching(this, new Coord(closestObject.x, closestObject.y))) {
                if (closestObject.theirDiet != 5 && (this.diet != 1)) {
                    return new InteractionRequest(1, closestObject.x, closestObject.y);
                } else {
                    return new InteractionRequest(2, closestObject.x, closestObject.y);
                }
            }
        }
        if (secondClosestObject != null) {
            if (facts.touching(this, new Coord(secondClosestObject.x, secondClosestObject.y))) {
                if (secondClosestObject.theirDiet != 5 && (this.diet != 1)) {
                    return new InteractionRequest(1, secondClosestObject.x, secondClosestObject.y);
                } else {
                    return new InteractionRequest(2, secondClosestObject.x, secondClosestObject.y);
                }
            }
        }
        if (thirdClosestObject != null) {
            if (facts.touching(this, new Coord(thirdClosestObject.x, thirdClosestObject.y))) {
                if (thirdClosestObject.theirDiet != 5 && (this.diet != 1)) {
                    return new InteractionRequest(1, thirdClosestObject.x, thirdClosestObject.y);
                } else {
                    return new InteractionRequest(2, thirdClosestObject.x, thirdClosestObject.y);
                }
            }
        }

 */
        //if eating, or reproducing, or splitting, make request
        return null;
    }

    public boolean noMoreThan2(Coord target, Iterable<Coord> coords) {

        int count = 0;
        for (Coord cell : coords) {
            if (target.x == cell.x && target.y == cell.y) {
                count++;
            }
        }
        return count < 2;
    }

    public int move(int z) {
        double movementSpeed = size2speed(size);
        int burntCal = 0;
        switch (z) {
            case 0:
                x += movementSpeed;
                break;
            case 1:
                x += movementSpeed;
                y += movementSpeed;
                break;
            case 2:
                y += movementSpeed;
                break;
            case 3:
                x -= movementSpeed;
                y += movementSpeed;
                break;
            case 4:
                x -= movementSpeed;
                break;
            case 5:
                x -= movementSpeed;
                y -= movementSpeed;
                break;
            case 6:
                y -= movementSpeed;
                break;
            case 7:
                x += movementSpeed;
                y -= movementSpeed;
                break;
            case 8:
                //do nothing
                break;
            default:
                Coord newDirection = new Coord(random.nextInt(Constants.WIDTH), random.nextInt(Constants.HEIGHT));
                burntCal = move(newDirection, true);
                break;
        }
        return burntCal;
    }

    public final int move(Coord object, boolean good) {

        //movement speed
        //double movementSpeed = (-1.15957/(1+(-1.02527 * Math.exp(0.0640627*size))));
        double movementSpeed = size2speed(size);
        this.movementSpeed = movementSpeed;
        int moving = Math.toIntExact(Math.round(movementSpeed));
        int temp = moving / 2;
        if (temp == 0) {
            temp = 1;
        }
        int xOld = x;
        int yOld = y;
        boolean xAssigned = false;
        boolean yAssigned = false;
        temp++;
        if (!good) {

            Random random = new Random();
            if (random.nextInt(100) <= 50) {
                strategy *= -1;
            }
            //determine if moving to opposite sides of map.
            if (object.x <= 10 && x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (object.y <= 10 && y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    goalXSpeed = -temp;
                    goalYSpeed = -temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    goalXSpeed = -temp;
                }

            } else if (object.y <= 10 && y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                goalYSpeed = -temp;
            }

            if (x <= 10 && object.x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (y <= 10 && object.y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    goalXSpeed = temp;
                    goalYSpeed = temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    goalXSpeed = temp;
                }

            } else if (y <= 10 && object.y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                goalYSpeed = temp;
            }


            //int temp = random.nextInt(2);
            if (!xAssigned) {
                if (object.getX() > x) {
                    //x += -temp;
                    goalXSpeed = -temp;
                    //this.ySpeed += strategy;
                } else if (object.getX() < x) {
                    //x += temp;
                    goalXSpeed = temp;
                    //this.ySpeed += strategy;
                }
            }
            if (!yAssigned) {
                if (object.getY() > y) {
                    //y += -temp;
                    goalYSpeed = -temp;
                    //this.xSpeed += strategy;
                } else if (object.getY() < y) {
                    //y += temp;
                    goalYSpeed = temp;
                    //this.xSpeed += strategy;
                }
            }
            this.xSpeed += this.goalXSpeed / 16;
            this.ySpeed += this.goalYSpeed / 16;
        } else {

            //Random random = new Random();
            //int temp = random.nextInt(2);
            if (object.x <= 10 && x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (object.y <= 10 && y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    goalXSpeed = temp;
                    goalYSpeed = temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    goalXSpeed = temp;
                }

            } else if (object.y <= 10 && y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                goalYSpeed = temp;
            }

            if (x <= 10 && object.x >= Constants.WIDTH - 10) {
                //opposite x's
                xAssigned = true;
                if (y <= 10 && object.y >= Constants.HEIGHT - 10) {
                    yAssigned = true;
                    //opposite y's as well
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow(((constants.HEIGHT - c2.y) - c1.y), 2))) - radius;
                    goalXSpeed = -temp;
                    goalYSpeed = -temp;
                } else {
                    //return Math.toIntExact((long) Math.sqrt(Math.pow(((constants.WIDTH - c2.x) - c1.x), 2) + Math.pow((c2.y - c1.y), 2))) - radius;
                    goalXSpeed = -temp;
                }

            } else if (y <= 10 && object.y >= Constants.HEIGHT - 10) {
                yAssigned = true;
                //opposite y's
                //return Math.toIntExact((long) Math.sqrt(Math.pow((c2.x - c1.x), 2) + Math.pow(((constant.HEIGHT - c2.y) - c1.y), 2))) - radius;
                goalYSpeed = -temp;
            }

            //int temp = random.nextInt(2);
            if (!xAssigned) {
                if (object.getX() > x) {
                    // x += temp;
                    goalXSpeed = temp;
                } else if (object.getX() < x) {
                    //x += -temp;
                    goalXSpeed = -temp;
                }
            }
            if (!yAssigned) {
                if (object.getY() > y) {
                    //y += temp;
                    goalYSpeed = temp;
                } else if (object.getY() < y) {
                    //y += -temp;
                    goalYSpeed = -temp;
                }
                this.xSpeed += this.goalXSpeed / 3;
                this.ySpeed += this.goalYSpeed / 3;

            }
        }

        if (Math.abs(xSpeed) >= Math.abs(this.goalXSpeed)) {
            this.goalXSpeed = 0;
            this.xSpeed = 0;
        }
        if (Math.abs(ySpeed) >= Math.abs(this.goalYSpeed)) {
            this.goalYSpeed = 0;
            this.ySpeed = 0;
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

        if (x < 0) {
            x += Constants.WIDTH;
        } else if (x > Constants.WIDTH) {
            x -= Constants.WIDTH;
        }

        if (y < 0) {
            y += Constants.HEIGHT;
        } else if (y > Constants.HEIGHT) {
            y -= Constants.HEIGHT;
        }

        this.prop.calcDirection(xOld, yOld, x, y);
        return costInCalories(size);
    }

    public double size2speed(double size) {
        /*
        double a = 1393.49;
        double b = 1.34247;
        double t = 0.00918484;
        speed = (a / (1 + (b * Math.exp(t * size))));
         */

        if (this.state.smol) {
            speed = (((-1.0 / 80.0) * size) + 15.0);
        } else {

            speed = (((-5.0 / 8000.0) * size) + 5.0);
        }
        if (speed == 1) {
            this.state.fat = true;
        }
        return speed;
    }

    public int costInCalories(double size) {
        final double a = -0.688954;
        final double b = -1.33401;
        final double t = -0.000454068;
        return (int) (a / (1 + (b * Math.exp(t * size))));
    }

    /**
     * Generates priorities for the Cell.
     * Needs tuning, arrays suck.
     * Sets are ordered for some reason when converting to a normal array.
     *
     * @return An Integer array containing the priorities of the Cell.
     */
    public Integer[] setPriorities() {
        ArrayList<Integer> makePriorities = new ArrayList<>();
        do {
            Integer temp = random.nextInt(5);
            if (!makePriorities.contains(temp)) {
                makePriorities.add(temp);
            }
        } while (makePriorities.size() < 5);
        Integer[] p = new Integer[5];
        return makePriorities.toArray(p);
    }

    /**
     * Evolution of the cell. This returns a new cell that is similar to the but not entirely the same. This allows for
     * traits to change for the good or worse.
     *
     * @param idGen IDGen Object
     * @return A newly formed and evolved Cell
     */
    public Cell evolve(IDGen idGen) {
        Random random = new Random();
        int mutate = random.nextInt(10);
        int mutationFactor;
        //negative mutation factors must exist!
        int negativeMutation = 1;
        if (random.nextInt(200) < 10) {
            //negative mutation!!!
            negativeMutation = -1;
        }
        int sight;
        int threatTolerance;
        int obstacleTolerance;
        double size;
        int splitChance;
        int splitRequirement;
        if (mutate < 4) {
            mutationFactor = random.nextInt(3);
            if (mutationFactor == 0) {
                mutationFactor = 1;
            }
            sight = this.sight + random.nextInt(mutationFactor) * negativeMutation;
            threatTolerance = this.threatTolerance + random.nextInt(mutationFactor) * negativeMutation;
            //obstacleTolerance = this.obstacleTolerance + random.nextInt(mutationFactor) * negativeMutation;
            if (sight < 0) {
                //blind!
                sight = 0;
            }
            if (threatTolerance > sight) {
                threatTolerance = sight;
            }
            splitChance = this.splittChance + random.nextInt(mutationFactor) * negativeMutation;
            splitRequirement = this.splitRequirement + random.nextInt(mutationFactor) * negativeMutation;
            //size = this.size + random.nextInt(mutationFactor) * this.threatTolerance + random.nextInt(mutationFactor);
        } else {
            threatTolerance = this.threatTolerance;
            splitChance = this.splittChance;
            splitRequirement = this.splitRequirement;
            sight = this.sight;
            //size = this.size;
        }
        obstacleTolerance = this.obstacleTolerance;
        if (obstacleTolerance > sight) {
            obstacleTolerance = sight;
        }
        int carnivore = random.nextInt(10);

        if (carnivore < 4) {
            carnivore = this.diet;
        } else {
            carnivore = random.nextInt(4);
        }
        int strategy = random.nextInt(10);
        if (strategy < 2) {
            strategy = this.strategy;
        } else {
            strategy = random.nextInt(3);
        }
        int[] pr;
        if (random.nextInt(2) == 1) {
            List<Integer> makePriorities = new ArrayList<>();
            do {
                Integer temp = random.nextInt(5);
                if (!makePriorities.contains(temp)) {
                    makePriorities.add(temp);
                }
            } while (makePriorities.size() < 5);
            pr = makePriorities.stream().mapToInt(Number::intValue).toArray();
        } else {
            pr = this.priorities;
        }
        int flockingTolerance = random.nextInt(100);
        if (flockingTolerance < 2) {
            flockingTolerance = this.flockingTolerance;
        } else {
            flockingTolerance = this.flockingTolerance + random.nextInt(10);
            if (flockingTolerance > sight) {
                flockingTolerance = sight;
            }
        }
        int hungerReq = random.nextInt(100);


        size = 100;
        //Add to the environment.
        //Cell(IDGen idGen, int threatTolerance, int obstacleTolerance, int sight, double size, int carnivore, int strategy, int[] priorities)
        Cell temp = new Cell(idGen, threatTolerance, obstacleTolerance, sight, size, carnivore, strategy, pr, splitChance, splitRequirement, 0, flockingTolerance);
        /*
        if (type == 1) {
            if (this.brain != null) {
                temp.brain = this.brain;
                temp.brain.evolveBrain();
            } else {
                temp.brain = new NeuralNetwork();
            }
        }
         */
        //temp.biggerBrain.evolveBrain();
        if (hungerReq < 20) {
            hungerReq = this.hungerReq;
        } else {
            hungerReq = this.hungerReq + random.nextInt(10);
        }
        temp.hungerReq = hungerReq;
        return temp;
    }

    /**
     * Evolution of the cell. This returns a new cell that is similar to the but not entirely the same. This allows for
     * traits to change for the good or worse.
     *
     * @param idGen IDGen Object
     * @return A newly formed and evolved Cell
     */
    public Cell evolveUP(IDGen idGen) {
        Random random = new Random();
        int mutate = random.nextInt(10);
        int mutationFactor;
        //negative mutation factors must exist!
        int negativeMutation = 1;
        if (random.nextInt(200) < 10) {
            //negative mutation!!!
            negativeMutation = -1;
        }
        int sight;
        int threatTolerance;
        int obstacleTolerance;
        double size;
        int splitChance;
        int splitRequirement;
        if (mutate < 4) {
            mutationFactor = random.nextInt(3);
            if (mutationFactor == 0) {
                mutationFactor = 1;
            }
            sight = this.sight + random.nextInt(mutationFactor) * negativeMutation;
            threatTolerance = this.threatTolerance + random.nextInt(mutationFactor) * negativeMutation;
            //obstacleTolerance = this.obstacleTolerance + random.nextInt(mutationFactor) * negativeMutation;
            if (sight < 0) {
                //blind!
                sight = 0;
            }
            if (threatTolerance > sight) {
                threatTolerance = sight;
            }
            splitChance = this.splittChance + random.nextInt(mutationFactor) * negativeMutation;
            splitRequirement = this.splitRequirement + random.nextInt(mutationFactor) * negativeMutation;
            size = this.size + random.nextInt(mutationFactor) * this.threatTolerance + random.nextInt(mutationFactor);
        } else {
            threatTolerance = this.threatTolerance;
            splitChance = this.splittChance;
            splitRequirement = this.splitRequirement;
            sight = this.sight;
            size = this.size;
        }
        obstacleTolerance = this.obstacleTolerance;
        if (obstacleTolerance > sight) {
            obstacleTolerance = sight;
        }
        int carnivore = random.nextInt(10);

        if (carnivore < 4) {
            carnivore = this.diet;
        } else {
            carnivore = random.nextInt(4);
        }
        int strategy = random.nextInt(10);
        if (strategy < 2) {
            strategy = this.strategy;
        } else {
            strategy = random.nextInt(3);
        }
        int[] pr;
        if (random.nextInt(2) == 1) {
            List<Integer> makePriorities = new ArrayList<>();
            do {
                Integer temp = random.nextInt(5);
                if (!makePriorities.contains(temp)) {
                    makePriorities.add(temp);
                }
            } while (makePriorities.size() < 5);
            pr = makePriorities.stream().mapToInt(Number::intValue).toArray();
        } else {
            pr = this.priorities;
        }
        int flockingTolerance = random.nextInt(100);
        if (flockingTolerance < 2) {
            flockingTolerance = this.flockingTolerance;
        } else {
            flockingTolerance += this.flockingTolerance + random.nextInt(10);
            if (flockingTolerance > sight) {
                flockingTolerance = sight;
            }
        }
        //Add to the environment.
        //Cell(IDGen idGen, int threatTolerance, int obstacleTolerance, int sight, double size, int carnivore, int strategy, int[] priorities)
        //temp.brain = this.brain;
        //temp.brain.evolveBrain();
        //temp.biggerBrain.evolveBrain();

        //temp.biggerBrain.evolveBrainUP();
        return new Cell(idGen, threatTolerance, obstacleTolerance, sight, size, carnivore, strategy, pr, splitChance, splitRequirement, 0, flockingTolerance);
    }

    /**
     * Evolution of the cell. This returns a new cell that is similar to the but not entirely the same. This allows for
     * traits to change for the good or worse.
     *
     * @param idGen IDGen Object
     * @return A newly formed and evolved Cell
     */
    public Cell evolveDown(IDGen idGen) {
        Random random = new Random();
        int mutate = random.nextInt(10);
        int mutationFactor;
        //negative mutation factors must exist!
        int negativeMutation = 1;
        if (random.nextInt(200) < 10) {
            //negative mutation!!!
            negativeMutation = -1;
        }
        int sight;
        int threatTolerance;
        int obstacleTolerance;
        double size;
        int splitChance;
        int splitRequirement;
        if (mutate < 4) {
            mutationFactor = random.nextInt(3);
            if (mutationFactor == 0) {
                mutationFactor = 1;
            }
            sight = this.sight + random.nextInt(mutationFactor) * negativeMutation;
            threatTolerance = this.threatTolerance + random.nextInt(mutationFactor) * negativeMutation;
            //obstacleTolerance = this.obstacleTolerance + random.nextInt(mutationFactor) * negativeMutation;
            if (sight < 0) {
                //blind!
                sight = 0;
            }
            if (threatTolerance > sight) {
                threatTolerance = sight;
            }
            splitChance = this.splittChance + random.nextInt(mutationFactor) * negativeMutation;
            splitRequirement = this.splitRequirement + random.nextInt(mutationFactor) * negativeMutation;
            size = this.size + random.nextInt(mutationFactor) * this.threatTolerance + random.nextInt(mutationFactor);
        } else {
            threatTolerance = this.threatTolerance;
            splitChance = this.splittChance;
            splitRequirement = this.splitRequirement;
            sight = this.sight;
            size = this.size;
        }
        obstacleTolerance = this.obstacleTolerance;
        if (obstacleTolerance > sight) {
            obstacleTolerance = sight;
        }
        int carnivore = random.nextInt(10);

        if (carnivore < 4) {
            carnivore = this.diet;
        } else {
            carnivore = random.nextInt(4);
        }
        int strategy = random.nextInt(10);
        if (strategy < 2) {
            strategy = this.strategy;
        } else {
            strategy = random.nextInt(3);
        }
        int[] pr;
        if (random.nextInt(2) == 1) {
            List<Integer> makePriorities = new ArrayList<>();
            do {
                Integer temp = random.nextInt(5);
                if (!makePriorities.contains(temp)) {
                    makePriorities.add(temp);
                }
            } while (makePriorities.size() < 5);
            pr = makePriorities.stream().mapToInt(Number::intValue).toArray();
        } else {
            pr = this.priorities;
        }

        int flockingTolerance = random.nextInt(100);
        if (flockingTolerance < 2) {
            flockingTolerance = this.flockingTolerance;
        } else {
            flockingTolerance += this.flockingTolerance + random.nextInt(10);
            if (flockingTolerance > sight) {
                flockingTolerance = sight;
            }
        }
        //Add to the environment.
        //Cell(IDGen idGen, int threatTolerance, int obstacleTolerance, int sight, double size, int carnivore, int strategy, int[] priorities)
        //temp.brain = this.brain;
        //temp.brain.evolveBrain();
        //temp.biggerBrain.evolveBrain();
        //temp.biggerBrain.evolveBrainDown();

        return new Cell(idGen, threatTolerance, obstacleTolerance, sight, size, carnivore, strategy, pr, splitChance, splitRequirement, 0, flockingTolerance);
    }

    /**
     * When a Cell consumes it grows. This grows the cell in size and gives the cell energy
     * allowing the cell to survive longer.
     *
     * @param growthFactor int
     */
    public void grow(double growthFactor) {
        this.score++;
        //this.size += growthFactor; //The cell grows in size.
        this.size += 10;
        //this.body.growBody(this.size); //might break everything.. Slows everything down.
        this.energy += growthFactor; //the cell gains more energy
        //this.color = this.color - this.energy * 1000 - this.size * 10; //For changing color based off of energy and size.
    }
/*
    public boolean doNext() {

        //for each object
        Examination closestThreat = analyzeThreatsComplex();
        Examination nullCheck = null;
        if (closestThreat == nullCheck) {
            //no need to run.
            return false;
        }
        this.state.eating = false;
        ;
        //this.state = "Thinking";
        Cell eating = null;
        Food eatenFood = null;
        float[] conclusion;
        try {

           conclusion = this.brain.think(this.brain.inputs(closestThreat.theirDirection().x, closestThreat.theirDirection().x, (float) closestThreat.theirSize, (float) this.size, closestThreat.theirDiet,
                               this.diet, this.energy, facts.distance(this,closestThreat)));
            //conclusion = this.biggerBrain.deepLearn(closestThreat.theirDirection().x, closestThreat.theirDirection().x, (float) closestThreat.theirSize, (float) this.size, closestThreat.theirDiet,
            //        this.diet, this.energy, facts.distance(this,closestThreat));

        } catch (Exception e) {
            System.out.println(" Their Brain broke!" + e.toString());
            return false;
        }
        //left
        //right
        //up
        //down
        //up left
        //up right
        //down left
        //down right
        //do nothing
        int top = -5;
        float highest = -90000;
        for (int x = 0; x < 3; x++) {
            if (highest < conclusion[x]) {
                highest = conclusion[x];
                top = x;
            }

        }

        Coord comparePrev = this.getCenter();

        switch (top) {
            case 0: {
                //left
                Movement temp = new Movement(-1, 0, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 1: {
                //right
                Movement temp = new Movement(1, 0, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 2: {
                //up
                Movement temp = new Movement(0, 1, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 3: {
                //down
                Movement temp = new Movement(0, -1, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 4: {
                //up left
                Movement temp = new Movement(-1, 1, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 5: {
                //up right
                Movement temp = new Movement(1, 1, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 6: {
                //down left
                Movement temp = new Movement(-1, -1, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;
            }
            case 7: {
                //down right
                Movement temp = new Movement(1, -1, this.size);
                this.move(temp);
                this.burnCalories(temp);
                
                //return true;
                if (this.getCenter().x == comparePrev.x) {

                    if (this.getCenter().y == comparePrev.y) {
                        System.out.println("DIDN'T MOVE, x = " + temp.xSpeed + ", y = " + temp.ySpeed);
                    }

                }
                break;

            }
            case 8: {//do nothing

                
                //return false;
                break;

               

            }
        }
        int newDistance = facts.distance(this,closestThreat.theirDirection());
        int oldDistance = comparePrev.distance(closestThreat.theirDirection());
        Examination cell = closestThreat;

        //Cell cell
        if (cell.theirDiet < this.diet && cell.theirSize > this.size) {
            if (newDistance < oldDistance) {
                this.score--;
            }
            if (newDistance > oldDistance) {
                this.score++;
            }
        }
        if (this.diet == 0 && cell.theirSize < this.size) {
            if (newDistance > oldDistance) {
                this.score--;
            }
            if (newDistance < oldDistance) {
                this.score++;
            }
        }
        if (cell.theirDiet == this.diet) {
            if (newDistance > oldDistance) {
                this.score--;
            }
            if (newDistance < oldDistance && newDistance > 5) {
                this.score++;
            }
        }
        if (cell.theirDiet > this.diet && this.size > cell.theirSize) {
            if (newDistance > oldDistance) {
                this.score--;
            }
            if (newDistance < oldDistance) {
                this.score++;
            }
        }

        for (Cell cell1 : this.CellBeingEaten) {
            eating = cell1;
            break;
        }
        if (eating != null) {
            grow(eating.size);
            this.score += eating.score;
            this.CellBeingEaten.remove(eating);
            this.foodDirection.remove(eating.getCenter);
            this.state.eating = false;
            ;
            //System.out.println("Ate a cell");
            return true;
        }
        for (Food food : this.FoodBeingEaten) {
            eatenFood = food;
            break;
        }
        if (eatenFood != null) {
            grow(eatenFood.getSize());
            this.FoodBeingEaten.remove(eatenFood);
            this.foodDirection.remove(eatenFood.getCenter());
            //System.out.println("Ate some food");
            this.state.eating = false;
            ;
            return true;
        }
        return false;
    }
    
 */

    /**
     * Contains the Pathfinding logic of the Cell.
     * Eventually this will be the A.I. magic happens. A.I. will learn to choose order of purpose
     * Sight is 20 units from any body part (outside of the body? if not inside, it's possible some cells might form inside a cell and act as parasites).
     */
    public void pathFind() {
        //Analyze environment and determine course of action, can only do 1 at a time.
        //1. search for threats
        //2. search for food
        //3. Analyze Other objects for chance at food or death?

        //run away
/*
        //randomly assign order and whichever lives so many generations will be included in next so many generations as majority combination for evolution.
        if (this.priorities != null) {
            obstacleAvoidance();
            //if (!obstacleAvoidance()) {
            for (Integer todo : this.priorities) {
                if (todo == 0) {
                    if (flight()) {
                        break;
                    } else {
                        //searching();
                    }
                } else if (todo == 1) {
                    if (fight()) {
                        break;
                    } else {
                        //searching();
                    }
                } else if (todo == 2) {
                    if (eatingFood()) {
                        break;
                    } else {
                        //searching();
                    }
                } else if (todo == 3) {
                    if (reproduce()) {
                        break;
                    } else {
                        //searching();
                    }
                } else {
                    searching(); //might never get here.
                    break;
                }
            }
            // }
        } else {
            this.priorities = Arrays.stream(setPriorities()).mapToInt(Integer::intValue).toArray();
        }
 */
        //obstacleAvoidance();

        if (this.type != 0) {

            //thinking cell
            //if (!flight2()) {
            if (eatingFood()) {
                if (fight()) {
                    //if (!reproduce()) {
                    searching();
                    //}
                }
            }
            //}


            //doNext(); //bigger brain funciton.
        } else {
            if (!flight()) {
                if (eatingFood()) {
                    if (fight()) {
                        //if (!reproduce()) {
                        searching();
                        //}
                    }
                }
            }
        }
        //obstacleAvoidance();
        metabolism(1);
    }

    public void setThoughts(ArrayList<Examination> thoughts) {
        this.thoughts = thoughts;
    }
/*
    private boolean flight2() {

        Examination closestThreat = analyzeObjects();
        Examination nullCheck = null;
        if (closestThreat == nullCheck) {
            //no need to run.
            return false;
        }
        //System.out.print("Cell #" + this.id + " is thinking!");
        //Now think, do I run away?
        //if 1 is higher, yes
        //if 2 is higher no
        //if 3 is higher yes?
        double[] conclusion;
        try {
            conclusion = this.brain.think(closestThreat.theirSize, this.size, closestThreat.theirDiet);
        } catch (Exception e) {
            //System.out.println(" Their Brain broke!" + e.toString());
            return false;
        }
        int top = -1;
        double highest = 0;
        for (int x = 0; x < 3; x++) {
            if (highest < conclusion[x]) {
                highest = conclusion[x];
                top = x;
            }

        }
        if (top == -1) {
            //failure! I couldn't think straight.
            //System.out.println("IDK what to do!");
            return false;
        }
        if (top == 0) {
            //run away!
            Movement temp = new Movement(closestThreat.theirDirection(), this.getCenter(), false, this.size, this.strategy);
            this.move(temp);
            this.burnCalories(temp);

            //System.out.println("They are a threat! Run Away! #1");
            return true;
        } else if (top == 1) {
            //do nothing!
            //System.out.println("No threats nearby!");
            return false;
        } else {
            //run away!
            Movement temp = new Movement(closestThreat.theirDirection(), this.getCenter(), true, this.size, this.strategy);
            this.move(temp);
            this.burnCalories(temp);

            //System.out.println("They are a friend! go say hi! #3");
            return true;
        }
    }

 */

    public boolean obstacleAvoidance() {
        //avoid nearby obstacles. similar to flight, except no running away and it just doesnt move into obstacles.
        Coord closestObstacle = analyzeObstacles();
        Coord nullCheck = null;
        if (closestObstacle == null) {
            //no need to avoid an obstacle.
            return false;
        }
        if (!this.state.bumping) {
            return false;
        }

        //Away or around obstacle.
        //might be an opportunity to add a survival trait. A value can determine if which direction the cell moves?
        //this.state = "Obstacle Avoidance";
        Movement temp = new Movement(closestObstacle, this.getCenter(), this.size);
        this.move(temp);
        this.burnCalories(temp);
        //this.energy -= 1;


        return true;

    }

// --Commented out by Inspection START (11/12/2020 4:59 PM):
//    /**
//     * Old Pathfinding algorithm. Still very functional. I just wanted to control the cell a lot less and made a new on instead.
//     */
//    public void pathFindOLD() {
//        if (!flight()) {
//            if (!eatingFood()) {
//                if (!fight()) {
//                    if (!reproduce()) {
//                        searching();
//                    }
//                }
//            }
//        }
//        metabolism(1);
//    }
// --Commented out by Inspection STOP (11/12/2020 4:59 PM)

    private Coord analyzeObstacles() {

        Coord closestObstacle = null;
        boolean first = true;

        for (Coord obstacle : this.obstacleArrayList) {

            if (facts.distance(this, obstacle) <= 3) {
                if (first) {
                    closestObstacle = obstacle;
                    first = false;
                } else {
                    if (facts.distance(this, closestObstacle) <= facts.distance(this, obstacle)) {
                        closestObstacle = obstacle;
                    }
                }
            }

        }

        this.state.bumping = closestObstacle != null;

        return closestObstacle;
    }


    /**
     * Simulating time passing and energy usage by living.
     *
     * @param cost How much energy is consumed in one tick.
     */
    public void metabolism(int cost) {
        //if (cost > -1) {
        this.energy -= cost;
        this.state.hungry = this.energy < this.hungerReq;
        if (this.energy <= 0) {
            this.state.dead = true;
            //System.out.println("Cell #" + id + " Starved");
        }
        // } else {
        //System.out.println("Somehow broke the system.");
        // }
    }

    /**
     * For how much energy is lost during a movement.
     *
     * @param move Movement object
     */
    public void burnCalories(Movement move) {
        if (this.state.smol) {
            return;
        }
        if (move.energyLost < 1) {
            this.energy -= 1;
        } else {
            //this.energy -= move.energyLost;
            this.energy -= 1;
        }
    }

    /**
     * For how much energy is lost during a movement.
     *
     * @param energyLost
     */
    public void burnCalories(int energyLost) {
        if (energyLost < 1) {
            this.energy -= 1;
        } else {
            //this.energy -= move.energyLost;
            this.energy -= 1;
        }
    }

    /**
     * Where the cell chooses to eat or not. If the conditions are met it will return true to say
     * that it is focusing on eating.
     *
     * @return True if focused on eating, false if not.
     */
    public boolean eatingFood() {
        //obstacleAvoidance();
        this.state.eating = false;
        Cell eating = null;
        Food eatenFood = null;
        //Other trash = null;

        if (this.CellBeingEaten.size() == 0) {
            if (this.FoodBeingEaten.size() == 0) {
                if (this.OtherBeingEaten.size() == 0) {
                    //this.state.eating = false;;
                    return true;
                }
            }
        }
        for (Cell cell : this.CellBeingEaten) {
            grow(cell.size);
            this.score += cell.score;
            //this.CellBeingEaten.remove(cell);
            eating = cell;
            break;
        }
        if (eating != null) {
            this.CellBeingEaten.remove(eating);
            this.foodDirection.remove(eating.getCenter());
            this.state.eating = false;
            return false;
        }
        for (Food food : this.FoodBeingEaten) {
            grow(food.getSize());
            //this.CellBeingEaten.remove(food);
            eatenFood = food;
            break;
        }
        if (eatenFood != null) {
            this.FoodBeingEaten.remove(eatenFood);
            this.foodDirection.remove(eatenFood.getCenter());
            this.state.eating = false;
            return false;
        }
        /*
        for (Other other : this.OtherBeingEaten) {
            grow(other.getSize());
            //this.CellBeingEaten.remove(other);
            trash = other;
        }
        if (trash != null) {
            this.OtherBeingEaten.remove(trash);
            this.foodDirection.remove(trash.getCenter);
            this.state.eating = false;;
            return true;
        }
         */
        return true;
    }

    /**
     * Cell has no food/threats/ or potential mates in sight and is searching for food.
     * Unlike all other pathfinding choices the cell doesn't really "choose" to search.
     * Searching is a result of the cell not knowing what to do next. A default state
     * more or less.
     *
     * @return True if it is searching, false if it is not searching.
     */
    public boolean searching() {
        //obstacleAvoidance();
        if (this.state.eating) {
            return false;
        }
        if (this.lastSearch != null) {
            Random random = new Random();
            int tem = random.nextInt(500);
            if (tem <= 10) {
                //new direction
                Movement temp = new Movement(0, 0, this.size);
                this.move(temp);
                this.burnCalories(temp);
                //this.energy -= 1;
                this.lastSearch = temp;
            } else {
                //same direction
                this.move(lastSearch);
                this.burnCalories(lastSearch);
            }


        } else {
            Movement temp = new Movement(0, 0, this.size);
            this.burnCalories(temp);
            //this.energy -= 1;
            this.move(temp);
            this.lastSearch = temp;
        }

        return true;
    }

    /**
     * If a threat is within viewing distance AND within the cells Threat Tolerance,
     * then the cell will move away from the threat. This movement varies based off of it's
     * Strategy trait which affects avoidance movement (Causes wiggling wasting energy and simulating panic).
     * Move to run away from nearest threat to the safest position (furthest away from nearest threat.)
     * Initially when coding, I had decided that if the cell was threatened, it could not perform any other function.
     * After seeing the results, I found that the Cells still eat while running away, almost as if to be able to
     * continue running away from a threat and not die from hunger. After some thought I decided to leave this since
     * it is much more organic of a response and was a trait that only exhibited itself in Intelligent Cells.
     *
     * @return True if running away, false if not.
     */
    public boolean flight() {
        //obstacleAvoidance();

        Coord closestThreat = analyzeThreats();
        Coord nullCheck = null;
        if (closestThreat == null) {
            //no need to run.
            return false;
        }

        //RUN AWAY
        //this.state.eating = false;; //may cause pathfinding problems
        //opposite direction of the threat.
/*
        if (this.lastFlight != null) {
            Random random = new Random();
            int tem = random.nextInt(100);
            if (tem <= 50) {
                //new direction
                Movement temp = new Movement(closestThreat, this.getCenter(), false, this.size, this.strategy);
                this.move(temp);
                this.burnCalories(temp);
                //this.energy -= 1;
                this.lastFlight = temp;
            } else {
                //same direction
                this.move(lastFlight);
                this.burnCalories(lastFlight);
            }


        } else {
            Movement temp = new Movement(0, 0, this.size);
            this.burnCalories(temp);
            //this.energy -= 1;
            this.move(temp);
            this.lastSearch = temp;
        }
*/


        Movement temp = new Movement(closestThreat, this.getCenter(), false, this.size, this.strategy);
        this.move(temp);
        this.burnCalories(temp);


        //this.energy -= 1;
        //move(closestThreat, this.c false);


        return true;

    }

    /**
     * The Fight response is triggered when a cell is moving towards food that it can consume.
     * If the food is smaller in size, within the edible food group of the cell, AND not of
     * the same species, the cell can consume the food and will move towards it. Food is
     * defined as anything "edible" this will allow for future food sources to be added in
     * that are not other cells and/or FoodBoxes. In the future I plan to add waste (typically
     * inefficient food sources containing mostly byproduct) to be edible, as well as random
     * nutrients that only satisfy specific needs of the cell.
     * <p>
     * Eventually I plan to add a survival chance roll that will allow a cell to fight for it's
     * life if chased by a predator, or for other predators to be able to attack cells of similar
     * or greater size and survive. Currently, if a cell attacks another that is bigger in size,
     * it will die.
     *
     * @return True if Fighting, false if not.
     */
    public boolean fight() {
        // obstacleAvoidance();

        //Move to consume the nearest cell whose size is smaller than itself or nearest food source;
        Coord closestFood = analyzeFoodSources();
        Coord nullCheck = null;

        if (closestFood == null) {
            //no food sources to attack found.
            return true;
        }

        Movement temp = new Movement(closestFood, this.getCenter(), true, this.size, this.strategy);
        this.move(temp);
        this.burnCalories(temp);
        //this.energy -= 1;


        for (Cell cell : CellBeingEaten) {
            if (facts.touching(this, cell)) {
                this.state.eating = true;

                return true;
            }
        }

        for (Food food : FoodBeingEaten) {
            if (facts.touching(this, food)) {
                this.state.eating = true;
                return true;
            }
        }

        return false;
    }

    public boolean doISplit() {
        if (this.energy >= splitRequirement) {
            //System.out.println("Cell #" + this.id + " has Split!");
            if (this.state.scared) {
                //System.out.println("Cell #" + this.id + " has Split!");
                return random.nextInt(500) < this.splittChance;
            } else return random.nextInt(1000) < this.splittChance;
        }
        return false;

    }

    /*
    public NeuralNetwork getSameBrain() {
        Random random = new Random();

        NeuralNetwork newBrain = new NeuralNetwork(this.brain, random.nextInt(100000));

        newBrain.evolveBrain();
        return newBrain;
    }

     */

    public Cell split(IDGen idGen) {

        this.energy /= 2;
        this.size -= this.size / 8;

        Cell temp = this.evolve(idGen);
        temp.energy = 300;
        temp.size = this.size;
        /*
        if (this.brain != null) {
            temp.brain = this.brain;
            temp.brain = getSameBrain();
        }

         */
        int rx = +random.nextInt(3);
        int ry = +random.nextInt(3);
        if (random.nextInt(3) == 0) {
            rx *= -1;
        }
        if (random.nextInt(3) == 0) {
            ry *= -1;
        }
        temp.x = this.x + rx;
        temp.y = this.y + ry;

        return temp;

    }

// --Commented out by Inspection START (11/12/2020 4:58 PM):
//    public boolean doIGiveBirth(Cell spouse) {
//        //System.out.println("Someone checked if they could give birth");
//        for (Cell soul : this.soulMate) {
//            if (this.getCenter().touching(soul.getCenter)) {
//                //this.reproductionDirection = new ArrayList<>();
//                //this.state.young = false;
//                //System.out.println("Someone Gave Birth!");
//                return true;
//            }
//        }
//        //for (Coord coord : this.reproductionDirection) {
//        //    if (this.getCenter().touching(coord) && coord == spouse.getCenter) {
//        //this.reproductionDirection = new ArrayList<>();
//        //this.state.young = false;
//        //        System.out.println("Someone Gave Birth!");
//        //        return true;
//        //    }
//        //}
//        return false;
//    }
// --Commented out by Inspection STOP (11/12/2020 4:58 PM)

    /**
     * If a cell has a potential mate that is is young (has not mated before) it will move
     * towards the mate until touching. Once touching (carried out in Environment class)
     * It will be marked as no longer young and cannot produce anymore. I chose this
     * behavior because I plan to introduce a future behavior where a cell will analyze
     * it's mate for favorable traits. Currently a cell can only mate if the traits of the
     * spouse cell are within 4 of it's own traits. This allows for Species to develop,
     * diverge and evolve! This also allows for extinction of Species as well which is when
     * a cell has no suitable mates within it's own species and the species cannot continue.
     * I plan to introduce a counter which will count the number of unique cell species
     * and announce when a species has gone extinct or formed.
     * <p>
     * Currently buggy, I'm not entirely sure the cells are even being born!
     * * All i know currently is that parent cells disapear for some reason and then
     * * reappear later in a new location. It might not even be parent cells appearing
     * * but the children being born and the parents might be lost. I have no idea and
     * * I need to analyze it further.
     *
     * @return True if reproducing, False if not.
     */
    public boolean reproduce() {
        if (!this.state.young) {
            return false;
        }
        Coord closestMate = analyzePotentialMates();
        Coord nullCheck = null;

        if (closestMate == null) {
            //no mate found.
            return false;
        }
        Movement temp = new Movement(closestMate, this.getCenter(), true, this.size, this.strategy);
        this.move(temp);

/*
        for (Cell soul : this.soulMate) {
            if (this.getCenter().touching(soul.getCenter)) {
                //this.reproductionDirection = new ArrayList<>();
                //this.state.young = false;
                System.out.println("Someone Gave Birth!");
                this.state.givingBirth = true;
                //return true;
            }
        }
        */


        for (Coord coord : this.reproductionDirection) {
            if (this.getCenter().touching(coord)) {
                this.reproductionDirection = new ArrayList<>();
                //this.state.young = false;
                this.state.givingBirth = true;
                //System.out.println("Someone Gave Birth!");
                //return true;
            }
        }

        //this.energy -= 1;
        this.burnCalories(temp);


        return true;
    }

    /**
     * This is where the 'magic' happens for reproduction. which is why it's
     * incredibly simple. From my perspective, a cell that is born contains
     * summarized values of it's parents as well as possible mutations. This
     * allows for species to form, diverge, and evolve.
     * <p>
     * Currently buggy, I'm not entirely sure the cells are even being born!
     * All i know currently is that parent cells disapear for some reason and then
     * reappear later in a new location. It might not even be parent cells appearing
     * but the children being born and the parents might be lost. I have no idea and
     * I need to analyze it further.
     *
     * @param spouse Cell that is being mated with.
     * @param idGen  Allows for a unique identifier to be assigned to the cell.
     * @return A new cell similar in traits to it's parents.
     */
    public Cell giveBirth(Cell spouse, IDGen idGen) {
        this.energy -= 10;
        this.score++;
        this.state.young = false;
        Cell baby = summarize(this, spouse, idGen).evolve(idGen);
        int rx = +random.nextInt(3);
        int ry = +random.nextInt(3);
        if (random.nextInt(3) == 0) {
            rx *= -1;
        }
        if (random.nextInt(3) == 0) {
            ry *= -1;
        }
        baby.x = this.x + rx;
        baby.y = this.y + ry;

        return baby;
    }

    /**
     * Summarizes the traits of two cells by finding the mean of each trait (except priorities).
     * Used in reproduction.
     *
     * @param cell1 Parent Cell 1
     * @param cell2 Parent Cell 2
     * @param idGen IDGen object
     * @return A summarized Cell.
     */
    public Cell summarize(Cell cell1, Cell cell2, IDGen idGen) {
        int x = cell1.x;
        int y = cell1.y;
        int id = idGen.makeCellID();
        int threatTolerance = (cell1.threatTolerance + cell2.threatTolerance) / 2;
        int sight = (cell1.sight + cell2.sight) / 2;
        double size = (cell1.size + cell2.size) / 2;
        final int energy = 100;
        int carnivore = cell1.diet;
        int strategy = (cell1.strategy + cell2.strategy) / 2;
        int obstacleTolerance = (cell1.obstacleTolerance + cell2.obstacleTolerance) / 2;
        int splitchance = (cell1.splittChance + cell2.splittChance) / 2;
        int splitRequirment = (cell1.splitRequirement + cell2.splitRequirement) / 2;
        int hungerReq = (cell1.hungerReq + cell2.hungerReq) / 2;
        Cell temp = new Cell(x, y, id, threatTolerance, obstacleTolerance, sight, size, energy, carnivore, strategy, splitchance, splitRequirment);
        temp.hungerReq = hungerReq;
        //int color = (cell1.color + cell2.color) / 2;
        //int color = (cell1.color + cell2.color) / 2;
        return temp;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Coord analyzeThreats() {

        Coord closestThreat = null;
        boolean first = true;

        for (Coord threat : this.threatDirection) {

            if (facts.distance(this, threat) <= this.threatTolerance) {
                if (first) {
                    closestThreat = threat;
                    first = false;
                } else {
                    if (facts.distance(this, closestThreat) <= facts.distance(this, threat)) {
                        closestThreat = threat;
                    }
                }
            }

        }

        return closestThreat;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Coord analyzeThreats(Iterable<Coord> threatDirection) {

        Coord closestThreat = null;
        boolean first = true;

        for (Coord threat : threatDirection) {

            if (facts.distance(this, threat) <= this.threatTolerance) {
                if (first) {
                    closestThreat = threat;
                    first = false;
                } else {
                    if (facts.distance(this, closestThreat) <= facts.distance(this, threat)) {
                        closestThreat = threat;
                    }
                }
            }

        }

        return closestThreat;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Examination analyzeObjects() {

        Examination closestThreat = null;
        boolean first = true;
        for (Examination examination : this.thoughts) {

            if (facts.distance(this, examination) <= this.threatTolerance) {
                if (first) {
                    closestThreat = examination;
                    first = false;
                } else {
                    if (facts.distance(this, closestThreat) <= facts.distance(this, examination)) {
                        closestThreat = examination;
                    }
                }
            }

        }

        return closestThreat;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Examination analyzeObjects(SightResult result) {

        Examination closestThreat = null;
        boolean first = true;
        for (Examination examination : result.getType1()) {

            if (facts.distance(this, examination) <= this.threatTolerance) {
                if (first) {
                    closestThreat = examination;
                    first = false;
                } else {
                    if (facts.distance(this, closestThreat) <= facts.distance(this, examination)) {
                        closestThreat = examination;
                    }
                }
            }

        }

        return closestThreat;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Examination analyzeObjectsSecond(SightResult result) {

        Examination closestThreat = null;
        Examination secondClosestThreat = null;
        boolean first = true;
        for (Examination examination : result.getType1()) {

            if (facts.distance(this, examination) <= this.threatTolerance) {
                if (first) {
                    closestThreat = examination;
                    first = false;
                } else {
                    if (facts.distance(this, closestThreat) <= facts.distance(this, examination)) {
                        closestThreat = examination;
                    } else if (facts.distance(this, secondClosestThreat) <= facts.distance(this, examination)) {
                        secondClosestThreat = examination;
                    }
                }
            }

        }

        return secondClosestThreat;
    }

    /**
     * Analyze all threats in the Cell's memory and decide to move or not.
     *
     * @return returns a Coord object if an immanent, null if threats are tolerable.
     */
    public Examination analyzeObjectsThird(SightResult result) {

        Examination closestThreat = null;
        Examination secondClosestThreat = null;
        Examination thirdClosestThreat = null;

        boolean first = true;
        for (Examination examination : result.getType1()) {

            if (facts.distance(this, examination) <= this.threatTolerance) {
                if (first) {
                    closestThreat = examination;
                    first = false;
                } else {
                    if (facts.distance(this, closestThreat) <= facts.distance(this, examination)) {
                        closestThreat = examination;
                    } else if (facts.distance(this, secondClosestThreat) <= facts.distance(this, examination)) {
                        secondClosestThreat = examination;
                    } else if (facts.distance(this, thirdClosestThreat) <= facts.distance(this, examination)) {
                        thirdClosestThreat = examination;
                    }
                }
            }

        }

        return thirdClosestThreat;
    }

// --Commented out by Inspection START (11/12/2020 4:58 PM):
//    /**
//     * Old Food Analysis function. Still works with current configuration (with some modification).
//     * Only two food groups.
//     *
//     * @return Coordinate of nearest food source.
//     */
//    public Coord analyzeFoodSourcesOLD() {
//        Coord closestFood = null;
//        boolean first = true;
//
//        //carnivore? if yes, prioritize meat before Foodbox.
//        if (this.Carnivore == 1) {
//            for (Coord food : this.foodDirection) {
//                if (food.meat) {
//                    if (facts.distance(this,food) <= sight) {
//                        if (first) {
//                            closestFood = food;
//                            first = false;
//                        } else {
//                            if (facts.distance(this,closestFood) >= facts.distance(this,food)) {
//                                closestFood = food;
//                            }
//                        }
//                    }
//                }
//            }
//        }
//        if (closestFood == null) {
//            if (this.Carnivore == 2) { // FoodBoxes only!
//                for (Coord food : this.foodDirection) {
//                    if (!food.meat) {
//                        if (facts.distance(this,food) <= sight) {
//                            if (first) {
//                                closestFood = food;
//                                first = false;
//                            } else {
//                                if (facts.distance(this,closestFood) >= facts.distance(this,food)) {
//                                    closestFood = food;
//                                }
//                            }
//                        }
//                    }
//                }
//            }
//        }
//        if (closestFood == null) {
//
//            for (Coord food : this.foodDirection) {
//
//                if (facts.distance(this,food) <= sight) {
//                    if (first) {
//                        closestFood = food;
//                        first = false;
//                    } else {
//                        if (facts.distance(this,closestFood) >= facts.distance(this,food)) {
//                            closestFood = food;
//                        }
//                    }
//                }
//
//            }
//        }
//        return closestFood;
//    }
// --Commented out by Inspection STOP (11/12/2020 4:58 PM)

    /**
     * Analyze all Food Sources in the Cell's memory and if a food source is near
     * return it to the fight function for the cell to move towards it.
     * This is where the traits Herbivore, carnivore, and Omnivore come into play.
     * A cell will only eat food that fall within it's ability to consume.
     * There are two types of Omnivore because I felt that preference would be an
     * interesting characteristic to see displayed. So far this has been incredibly
     * interesting!
     * <p>
     * There might be a bug with herbivores as I think I have seen some actually eat
     * other cells. It might be something that occurs by accident due to the cell touching
     * another cell, I'm nto sure. I need to make sure that if a cell is consumed, a counter
     * is added to to allow me to check if it is consuming other cells.
     *
     * @return Food coordinate coordinate.
     */
    public Coord analyzeFoodSources() {

        Coord closestFood = null;
        boolean first = true;

        if (this.diet == 0 && !this.state.smol) { // carnivore
            for (Coord food : this.foodDirection) {
                if (food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (facts.distance(this, closestFood) >= facts.distance(this, food)) {
                                closestFood = food;
                            }
                        }
                    }
                }
            }
            return closestFood;
        }
        if (this.diet == 1) { // omnivore favoring meat
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (Coord food : this.foodDirection) {
                if (food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (facts.distance(this, closestMeat) >= facts.distance(this, food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (facts.distance(this, closestPlant) >= facts.distance(this, food)) {
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
        if (this.diet == 2) { // omnivore favoring plants
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (Coord food : this.foodDirection) {
                if (food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (facts.distance(this, closestMeat) >= facts.distance(this, food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (facts.distance(this, closestPlant) >= facts.distance(this, food)) {
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
        if (this.diet == 3) { // herbivore
            for (Coord food : this.foodDirection) {
                if (!food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (facts.distance(this, closestFood) >= facts.distance(this, food)) {
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

    public Coord analyzeFoodSources(Iterable<Coord> foodDirection) {

        Coord closestFood = null;
        boolean first = true;

        if (this.diet == 0) { // carnivore
            for (Coord food : foodDirection) {
                if (food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (facts.distance(this, closestFood) >= facts.distance(this, food)) {
                                closestFood = food;
                            }
                        }
                    }
                }
            }
            return closestFood;
        }
        if (this.diet == 1) { // omnivore favoring meat
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (Coord food : foodDirection) {
                if (food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (facts.distance(this, closestMeat) >= facts.distance(this, food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (facts.distance(this, closestPlant) >= facts.distance(this, food)) {
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
        if (this.diet == 2) { // omnivore favoring plants
            Coord closestMeat = null;
            Coord closestPlant = null;
            boolean firstPlant = true;
            boolean firstMeat = true;
            for (Coord food : foodDirection) {
                if (food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstMeat) {
                            closestMeat = food;
                            firstMeat = false;
                        } else {
                            if (facts.distance(this, closestMeat) >= facts.distance(this, food)) {
                                closestMeat = food;
                            }
                        }
                    }
                }
                if (!food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (firstPlant) {
                            closestPlant = food;
                            firstPlant = false;
                        } else {
                            if (facts.distance(this, closestPlant) >= facts.distance(this, food)) {
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
        if (this.diet == 3) { // herbivore
            for (Coord food : foodDirection) {
                if (!food.meat) {
                    if (facts.distance(this, food) <= sight) {
                        if (first) {
                            closestFood = food;
                            first = false;
                        } else {
                            if (facts.distance(this, closestFood) >= facts.distance(this, food)) {
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


// --Commented out by Inspection START (11/12/2020 4:58 PM):
//    /**
//     * Returns how many cells this cell has consumed.
//     *
//     * @return int value of how many cells this cell has consumed.
//     */
//    public int getScore() {
//        return this.score;
//    }
// --Commented out by Inspection STOP (11/12/2020 4:58 PM)

    /**
     * Analyzes nearby potential mates. A potential mate is a cell
     * that is of the same species and is considered young (has not reproduced before).
     * Returns null if no nearby potential mates exist.
     *
     * @return Coord of nearest mate. Null if none are within range.
     */
    public Coord analyzePotentialMates() {
        Coord closestMate = null;
        boolean first = true;
        for (Coord mate : this.reproductionDirection) {
            if (facts.distance(this, mate) <= sight) {
                if (first) {
                    closestMate = mate;
                    first = false;
                } else {
                    if (facts.distance(this, closestMate) >= facts.distance(this, mate)) {
                        closestMate = mate;
                    }
                }
            }

        }
        return closestMate;
    }

    public Coord analyzePotentialMates(Iterable<Coord> reproductionDirection) {
        Coord closestMate = null;
        boolean first = true;
        for (Coord mate : reproductionDirection) {
            if (facts.distance(this, mate) <= sight) {
                if (first) {
                    closestMate = mate;
                    first = false;
                } else {
                    if (facts.distance(this, closestMate) >= facts.distance(this, mate)) {
                        closestMate = mate;
                    }
                }
            }

        }
        return closestMate;
    }


    public int getX() {
        return x;
    }

    public int getY() {
        return y;
    }

    public int getID() {
        return this.id;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Cell)) return false;
        Cell cell = (Cell) o;
        return getX() == cell.getX() &&
                getY() == cell.getY();
    }

    @Override
    public int hashCode() {
        return Objects.hash(getX(), getY());
    }

    public void setThreatDirection(ArrayList<Coord> threatDirection) {
        this.threatDirection = threatDirection;
    }

    public void setFoodDirection(ArrayList<Coord> foodDirection) {
        this.foodDirection = foodDirection;
    }

    public void setObstacleDirection(ArrayList<Coord> obstacleDirection) {
        ObstacleDirection = obstacleDirection;
    }

// --Commented out by Inspection START (11/12/2020 4:58 PM):
//    public ArrayList<Coord> getReproductionDirection() {
//        return reproductionDirection;
//    }
// --Commented out by Inspection STOP (11/12/2020 4:58 PM)

    public void setOtherDirection(ArrayList<Coord> otherDirection) {
        OtherDirection = otherDirection;
    }

    public void setReproductionDirection(ArrayList<Coord> reproductionDirection) {
        this.reproductionDirection = reproductionDirection;
    }

    public Coord getCenter() {
        return new Coord(x, y);
    }

    public boolean move(Movement movement) {
        final int failed = 0;
        this.goalXSpeed = movement.xSpeed;
        this.goalYSpeed = movement.ySpeed;
        this.xSpeed += this.goalXSpeed / 3;
        this.ySpeed += this.goalYSpeed / 3;
        if (Math.abs(xSpeed) >= Math.abs(this.goalXSpeed)) {
            this.goalXSpeed = 0;
            this.xSpeed = 0;
        }
        if (Math.abs(ySpeed) >= Math.abs(this.goalYSpeed)) {
            this.goalYSpeed = 0;
            this.ySpeed = 0;
        }
        return true;
/*
        try {
            moveX(movement.xSpeed);

        } catch (Exception e) {
            System.out.println("Failed move1");
            failed++;
        }
        try {
            moveY(movement.ySpeed);
        } catch (Exception e) {
            System.out.println("Failed move2");
            failed++;
        }
        //moved somewhere
        return failed != 2; // couldn't move anywhere


 */
    }

    public void moveX(int xTranslation) {

        //this.gSpeed = xTranslation;

        if (this.x + xTranslation > Constants.WIDTH - 1) {
            this.x = (this.x + xTranslation) - (Constants.WIDTH - 1);

        } else if (this.x + xTranslation < 0) {
            this.x = (Constants.WIDTH - 1) - (this.x + xTranslation);

        } else {
            this.x += xTranslation;
        }
    }

    public void moveY(int yTranslation) {

        if (this.y + yTranslation > Constants.HEIGHT - 1) {
            this.y = (this.y + yTranslation) - (Constants.HEIGHT - 1);
        } else if (this.y + yTranslation < 0) {
            this.y = (Constants.HEIGHT - 1) - (this.y + yTranslation);
        } else {
            this.y += yTranslation;
        }
    }


    public void flocking(SightResult s) {
        //find nearby cells of same species.
        //count how many there are.

        int withinT = 0;
        int outsideT = 0;
        Coord within = null;

        if (!state.desire2Flock) {
            return;
        }

        //Coord closestMate;
        //do {
        //    within = analyzePotentialMates(s.getReproductionDirection());
        //} while (!noMoreThan2(within, s.getReproductionDirection()));

        if (this.type != 3) { //WormBody

            for (Coord cell : s.getFlockDirection()) {

                move(cell, true);

            }


            for (Coord cell : s.getFlockDirection()) {
                if (facts.distance(this, cell) > flockingTolerance) {
                    outsideT++;
                } else {
                    withinT++;
                    within = cell;
                }
            }
            if (outsideT > withinT) {
                //outside of flock!
                if (within != null) {
                    move(within, true);
                    this.state.inFlock = false;
                } else {
                    this.state.inFlock = false;
                    return;
                }

            } else {
                this.state.inFlock = true;
                this.energy += 50;
            }
        } else { //chain with other worm bodies. there must be only two directly nearby
            for (Coord cell : s.getFlockDirection()) {
                if (facts.distance(this, cell) > 10) {
                    move(cell, true);
                } else if (facts.distance(this, cell) < 5) {
                    move(cell, false);
                } else {
                    withinT++;
                }
            }
            if (withinT > 2) {
                this.state.wormBody = true;
                this.state.inFlock = true;
                this.energy += 1000;
            } else {
                this.state.wormBody = false;
                this.state.inFlock = false;
            }
            //can only be two worm bodies within a 10 pixel radius and the must be near opposite of each other.
            /*
            ArrayList<Coord> nearbyCells = new ArrayList<>();

            for (Coord cell : s.getFlockDirection()) {
                if (facts.distance(this, cell) > 10) {
                    outsideT++;
                    nearbyCells.add(cell);
                } else {
                    withinT++;
                    //nearbyCells.add(cell);
                    if (withinT > 3 || facts.distance(this, cell) < 6) {
                        move(cell, false);
                    }
                }
            }
            if (withinT < 1) {
                //outside of flock!
                this.state.wormBody = false;
                for (Coord cell : nearbyCells) {
                    move(cell, true);
                }
                /*
                if (within != null) {
                    move(within, true);
                    this.state.inFlock = false;
                } else {
                    this.state.inFlock = false;
                    return;
                }




            } else {
                this.state.wormBody = true;
                this.state.inFlock = true;
                this.energy += 2;
            }
            /*
            for (Coord cell : s.getReproductionDirection()) {
                if (facts.distance(this, cell) > 10) {
                    outsideT++;
                } else {
                    if ((facts.distance(this, cell) < 7)) {
                        //too close!
                        move(within, false);
                    }
                    withinT++;
                    within = cell;
                }
            }
            if (withinT > 2) {
                //outside of flock!
                if (within != null) {
                    move(within, false);
                    this.state.inFlock = false;
                } else {
                    this.state.inFlock = false;
                    return;
                }
            }
            if (withinT < 2) {
                //outside of flock!
                if (within != null) {
                    move(within, true);
                    this.state.inFlock = false;
                } else {
                    this.state.inFlock = false;
                    return;
                }

            } else {
                this.state.inFlock = true;
                this.energy += 100;
            }


             */
        }
    }


    public int obCheckX(Movement move) {
        return this.x + move.xSpeed;
    }

    public int obCheckY(Movement move) {
        return this.y + move.ySpeed;
    }


    public boolean allPossibleMoves(Movement move) {
        int xRight = this.x + move.xSpeed;
        int yUp = this.y + move.ySpeed;
        int xLeft = this.x - move.xSpeed;
        int yDown = this.y - move.ySpeed;
        final int xStall = 0;
        final int yStall = 0;

        //define forward as moving up and to the right since it's the norm of adding the movement.
        if (!verify(xRight, yUp)) {
            if (!verify(xRight, yStall)) {
                if (!verify(xStall, yUp)) {
                    if (!verify(xLeft, yUp)) {
                        if (!verify(xLeft, yStall)) {
                            if (!verify(xLeft, yDown)) {
                                if (!verify(xRight, yDown)) {
                                    //trapped!
                                    return verify(xStall, yDown);
                                }
                            }
                        }
                    }
                }
            }
        }

        return true;
    }

    public boolean verify(int x, int y) {

        // if an obstacle exists return false
        if (obstacleArrayList.contains(new Coord(x, y))) {
            return false;
        } else {
            moveX(x);
            moveY(y);
            return true;
        }
    }


    @Override
    public String toString() {
        return "Cell{" +
                "state=" + state +
                ", facts=" + facts +
                ", random=" + random +
                ", x=" + x +
                ", y=" + y +
                ", CellBeingEaten=" + CellBeingEaten +
                ", soulMate=" + soulMate +
                ", FoodBeingEaten=" + FoodBeingEaten +
                ", OtherBeingEaten=" + OtherBeingEaten +
                ", obstacleArrayList=" + obstacleArrayList +
                ", threatTolerance=" + threatTolerance +
                ", sight=" + sight +
                ", obstacleTolerance=" + obstacleTolerance +
                ", size=" + size +
                ", energy=" + energy +
                ", diet=" + diet +
                ", strategy=" + strategy +
                ", priorities=" + Arrays.toString(priorities) +
                ", splittChance=" + splittChance +
                ", splitRequirement=" + splitRequirement +
                ", score=" + score +
                ", type=" + type +
                ", age=" + age +
                ", constants=" + constants +
                ", speed=" + speed +
                ", closestaiObject=" + closestaiObject +
                ", justRevived=" + justRevived +
                ", movementSpeed=" + movementSpeed +
                ", prop=" + prop +
                ", hungerReq=" + hungerReq +
                ", xSpeed=" + xSpeed +
                ", ySpeed=" + ySpeed +
                ", goalXSpeed=" + goalXSpeed +
                ", goalYSpeed=" + goalYSpeed +
                ", id=" + id +
                ", threatDirection=" + threatDirection +
                ", foodDirection=" + foodDirection +
                ", ObstacleDirection=" + ObstacleDirection +
                ", OtherDirection=" + OtherDirection +
                ", reproductionDirection=" + reproductionDirection +
                ", lastSearch=" + lastSearch +
                ", lastDirection=" + lastDirection +
                ", thoughts=" + thoughts +
                ", foodEaten=" + foodEaten +
                ", flockingTolerance=" + flockingTolerance +
                '}';
    }
}
