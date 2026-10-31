package Enviroment;


import Constants.Constants;
import Exceptions.UnexpectedState;
import Map.SectorMap;
import Models.Body.Bacillus;
import Models.Cell;
import Models.Facts;
import Models.Food;
import Models.Mental.Examination;
import Models.Other;
import Models.Squid.Squid;
import Models.Squid.Tentacle;
import Models.Worm.Worm;
import Models.Worm.wormBody;
import Request.InteractionRequest;
import Request.SightRequest;
import Result.SightResult;
import Technical.IDGen;

import java.util.*;

/**
 * Contains the World Entities
 */
public class Environment {

    public static final Constants constant = new Constants();
    //private static final double FEATURE_SIZE = 24;
    private static final double FEATURE_SIZE = 50;
    public final Facts facts = new Facts();
    public final SectorMap theMap = new SectorMap();
    public final Cell[] prevLeaderboard = new Cell[10];
    public final Cell[] leaderboard = new Cell[10];
    public final Random random = new Random();
    public final Obstacle obstacles = new Obstacle(14);
    private final ArrayList<Other> OtherList = new ArrayList<>();
    private final ArrayList<Obstacle> ObstacleList;
    //private final int[][] bounds = new int[constant.WIDTH][constant.HEIGHT];
    public ArrayList<Cell> CellList = new ArrayList<>();
    public List<Cell> TopSurvivors = new ArrayList<>();
    public Iterable<Cell> suitableMates = new ArrayList<>();
    public boolean terrainON;
    //public Cell ai;
    //public Obstacle theObstacles = new Obstacle(14);
    public int aiScore;
    public boolean onlyOnce = true;
    public List<Worm> wormList = new ArrayList<>();
    public double timeCounter = 0.5;
    public double rando = 00.01;
    public boolean smallSlower1;
    public boolean smallSlower2;
    public boolean smallSlower3;
    public boolean smallSlower4;
    public boolean slower1;
    public boolean slower2;
    public List<Squid> squidArrayList;
    private ArrayList<Food> FoodList;
    private int CellListSize;
    private int deadCells;
    private IDGen idGen = new IDGen();
    public final Squid player = new Squid(20, 4, this.idGen);
    private List<Cell> toAdd;
    private List<Cell> splitResults;

    public Environment(IDGen idGen) {
        //this.seedWorld = world;
        OpenSimplexNoise noise = new OpenSimplexNoise();
        this.idGen = idGen;
        setupLeaderboard();
        //this.ai.biggerBrain = this.aiBrain;
        //this.ai.neuralNet = this.neuralNet;
        /*
        this.ai = new Cell(this.idGen, random.nextInt(20), 2,
                random.nextInt(100), random.nextInt(500), random.nextInt(4), random.nextInt(3),
                Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), random.nextInt(10),
                random.nextInt(1000), 1, 0);
                
         */
        //ai.state.dead = true;
        //this.addCell(this.ai);
        squidArrayList = new ArrayList<>();
        ObstacleList = new ArrayList<>();
        FoodList = new ArrayList<>();
        toAdd = new ArrayList<>();
        splitResults = new ArrayList<>();
    }

    /*

    public void move(int xSpeed, int ySpeed) {

            head.x += xSpeed;
            head.y += ySpeed;

            wormBody prev = null;
            boolean first = true;
            int[] prevSpeed = {0, 0};
            for (wormBody body : this.wormBodies) {

                if (first) {
                    prevSpeed = body.move(head.x, head.y, xSpeed, ySpeed);
                    first = false;
                } else {
                    //body.move(prev.x, prev.y, xSpeed, ySpeed);
                    body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                }
                prev = body;
            }

        }

     */
    public void updateWormPosition(Worm worm) {
        int tempX = worm.xSpeed;
        int tempY = worm.ySpeed;

        if (!terrainON) {
            worm.head.x += tempX;
            worm.head.y += tempY;

            wormBody prev = null;
            boolean first = true;
            int[] prevSpeed = {0, 0};
            for (wormBody body : worm.wormBodies) {

                if (first) {
                    prevSpeed = body.move(worm.head.x, worm.head.y, worm.xSpeed, worm.ySpeed);
                    first = false;
                } else {
                    //body.move(prev.x, prev.y, xSpeed, ySpeed);
                    body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                }
                prev = body;
            }
            worm.tail = prev;
        } else {
            int[] avoid = obAvoid(worm.getCenter(), new int[]{tempX, tempY});
            if (avoid != null) {
                worm.head.x += avoid[0];
                worm.head.y += avoid[1];
                wormBody prev = null;
                boolean first = true;
                int[] prevSpeed = {0, 0};
                for (wormBody body : worm.wormBodies) {

                    if (first) {
                        prevSpeed = body.move(worm.head.x, worm.head.y, worm.xSpeed, worm.ySpeed);
                        first = false;
                    } else {
                        //body.move(prev.x, prev.y, xSpeed, ySpeed);
                        body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                    }
                    prev = body;
                }
                worm.tail = prev;
            } else {
                worm.head.x += tempX;
                worm.head.y += tempY;
                wormBody prev = null;
                boolean first = true;
                int[] prevSpeed = {0, 0};
                for (wormBody body : worm.wormBodies) {

                    if (first) {
                        prevSpeed = body.move(worm.head.x, worm.head.y, worm.xSpeed, worm.ySpeed);
                        first = false;
                    } else {
                        //body.move(prev.x, prev.y, xSpeed, ySpeed);
                        body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                    }
                    prev = body;
                }
                worm.tail = prev;
            }

        }
    }

    public void updateSQuidPosition(Squid squid) {

        //squid.head.y +=1;
        //squid.move(0,1);
        /*
        int tempX = worm.xSpeed;
        int tempY = worm.ySpeed;

        if (!terrainON) {
            worm.head.x += tempX;
            worm.head.y += tempY;

            wormBody prev = null;
            boolean first = true;
            int[] prevSpeed = {0, 0};
            for (wormBody body : worm.wormBodies) {

                if (first) {
                    prevSpeed = body.move(worm.head.x, worm.head.y, worm.xSpeed, worm.ySpeed);
                    first = false;
                } else {
                    //body.move(prev.x, prev.y, xSpeed, ySpeed);
                    body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                }
                prev = body;
            }
            worm.tail = prev;
        } else {
            int[] avoid = obAvoid(worm.getCenter(), new int[]{tempX, tempY});
            if (avoid != null) {
                worm.head.x += avoid[0];
                worm.head.y += avoid[1];
                wormBody prev = null;
                boolean first = true;
                int[] prevSpeed = {0, 0};
                for (wormBody body : worm.wormBodies) {

                    if (first) {
                        prevSpeed = body.move(worm.head.x, worm.head.y, worm.xSpeed, worm.ySpeed);
                        first = false;
                    } else {
                        //body.move(prev.x, prev.y, xSpeed, ySpeed);
                        body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                    }
                    prev = body;
                }
                worm.tail = prev;
            } else {
                worm.head.x += tempX;
                worm.head.y += tempY;
                wormBody prev = null;
                boolean first = true;
                int[] prevSpeed = {0, 0};
                for (wormBody body : worm.wormBodies) {

                    if (first) {
                        prevSpeed = body.move(worm.head.x, worm.head.y, worm.xSpeed, worm.ySpeed);
                        first = false;
                    } else {
                        //body.move(prev.x, prev.y, xSpeed, ySpeed);
                        body.move(prev.x, prev.y, prevSpeed[0], prevSpeed[1]);
                    }
                    prev = body;
                }
                worm.tail = prev;
            }

        }

         */
    }

    public void updateCellPosition(Cell cell) {
        int tempX = cell.xSpeed;
        int tempY = cell.ySpeed;

        if (!terrainON) {
            cell.x += tempX;
            cell.y += tempY;
        } else {
            int[] avoid = obAvoid(cell.getCenter(), new int[]{tempX, tempY});
            if (avoid != null) {
                cell.x += avoid[0];
                cell.y += avoid[1];
            } else {
                cell.x += tempX;
                cell.y += tempY;
            }
            /*
            int verX = cell.x + tempX;
            int verY = cell.x + tempX;


            try {
                if (obstacles.location[verX + 3][verY + 3]) {
                    cell.xSpeed -= 1;
                    cell.ySpeed -= 1;
                } else if (obstacles.location[verX][verY + 3]) {
                    cell.xSpeed -= 1;
                }
                if (obstacles.location[verX + 3][verY]) {
                    cell.ySpeed -= 1;
                } else if (!obstacles.location[verX][verY]) {
                    cell.x += tempX;
                    cell.y += tempY;
                } else {
                    if (!obstacles.location[verX][cell.y]) {

                        cell.xSpeed = 0;
                        cell.ySpeed = 0;
                        // cell.x -= tempX;
                    } else if (!obstacles.location[cell.x][verY]) {
                        // cell.y -= tempY;
                        cell.xSpeed = 0;
                        cell.ySpeed = 0;
                    }
                }

            } catch (Exception e) {

            }

             */
        }
    }

    public void updateBacPosition(Bacillus bacillus) {
        Vector2D temp = bacillus.pathfinding.detPath();
        float tempX = temp.f4x;
        float tempY = temp.f5y;
        bacillus.x += tempX;
        bacillus.y += tempY;

        if (bacillus.x >= Constants.WIDTH) {
            bacillus.x -= Constants.WIDTH;
        }
        if (bacillus.y >= Constants.HEIGHT) {
            bacillus.y -= Constants.HEIGHT;
        }

        if (bacillus.x <= 0) {
            bacillus.x += Constants.WIDTH;
        }
        if (bacillus.y <= 0) {
            bacillus.y += Constants.HEIGHT;
        }

    }

    public int[] obAvoid(Coord myCenter, int[] movementCurrent) {

        //mimic threat avoidance but without running in opposite direction.
        //int moving = Math.toIntExact(Math.round(movementSpeed));
        //x movement, y movement
        //int temp = moving / 2;
        //if (temp == 0) {
        //    temp = 1;
        //}

        Coord closestObstacle = obstacles.calcNearestObstacle(myCenter);
        //if move in direction furthest away.
        //determine which is closer, x axis or y axis. and then determine positive or negative.
        if (closestObstacle != null) {
            int[] movement = {0, 0};
            if (Math.abs(myCenter.distanceX(closestObstacle)) > Math.abs(myCenter.distanceY(closestObstacle))) {
                //closer on x axis.
                //which direction?
                if (myCenter.distanceX(closestObstacle) <= 0) {
                    //move to the right
                    movement[0] = -1 - movementCurrent[0];
                } else {
                    //move to the left
                    movement[0] = 1 + movementCurrent[0];
                }
            } else {
                //closer on y axis
                if (myCenter.distanceY(closestObstacle) <= 0) {
                    //move up
                    movement[1] = -1 - movementCurrent[1];
                } else {
                    //move down
                    movement[1] = 1 + movementCurrent[1];
                }
            }
            return movement;
        }
        return null;
    }

    public Coord calcNearestObstacle(Coord myCenter) {
        return null;
    }

    public void addSmolCell() {
        this.CellList.add(new Cell(idGen, true));
    }

    public void addSmolFood() {
        this.FoodList.add(new Food(idGen, true));
    }


    public void addWorm(Worm worm) {
        this.wormList.add(worm);
    }

    /**
     * Evolution! Takes the top survivors of the previous generation and adds them to the next.
     *
     * @param idGen IDGen object
     */
    public void evolve(IDGen idGen, boolean score) {
        this.CellList = null;
        this.CellList = new ArrayList<>();
        //if (!score) {
        for (Cell cell : TopSurvivors) {
            for (int x = 0; x < 15; x++) {
                Cell temp = cell.evolve(idGen);
                temp.x = random.nextInt(Constants.WIDTH);
                temp.y = random.nextInt(Constants.HEIGHT);
                this.CellList.add(temp);
            }
        }
        this.TopSurvivors = null;
        this.TopSurvivors = new ArrayList<>();
        this.FoodList = null;
        this.FoodList = new ArrayList<>();
        for (int j = 0; j < 800; j++) {
            this.addFood(new Food(idGen));
        }
        this.deadCells = 0;
        this.CellListSize = this.CellList.size();
    }

    public void foodFall() {

        if (terrainON) {
            for (Food food : this.FoodList) {
                rando = random.nextDouble();
                if (food.state.smol) {
                    if (smallSlower1) {
                        if (smallSlower2) {
                            if (smallSlower3) {
                                if (smallSlower4) {
                                    food.y += 1;
                                    food.x += Math.sin(timeCounter) * 5 + rando;
                                    if (food.x < 0) {
                                        food.x = Constants.WIDTH + food.x;
                                    }
                                    if (food.y < 0) {
                                        food.y = Constants.HEIGHT + food.y;
                                    }
                                    if (food.x > Constants.WIDTH - 1) {
                                        food.x = Constants.WIDTH - food.x;
                                    }
                                    if (food.y >= Constants.HEIGHT - 1) {
                                        food.y = Constants.HEIGHT - food.y;
                                    }

                                    if (!obstacles.isAt(food.x, food.y + 4) || !obstacles.isAt(food.x, food.y + 3)) {
                                        food.y -= 1;
                                    }

                                    timeCounter += 0.01;
                                    System.out.println("TimeCounter: " + timeCounter);
                                    if (timeCounter >= 1) {
                                        timeCounter = -1;
                                    }
                                    smallSlower1 = false;
                                    smallSlower2 = false;
                                    smallSlower3 = false;
                                    smallSlower4 = false;
                                } else {
                                    smallSlower4 = true;
                                }
                            } else {
                                smallSlower3 = true;
                            }
                        } else {
                            smallSlower2 = true;
                        }
                    } else {
                        smallSlower1 = true;
                    }
                } else {
                    if (slower1) {
                        if (slower2) {
                            food.y += 1;
                            food.x += Math.sin(timeCounter) * 5 + rando;
                            if (food.x < 0) {
                                food.x = Constants.WIDTH + food.x;
                            }
                            if (food.y < 0) {
                                food.y = Constants.HEIGHT + food.y;
                            }
                            if (food.x > Constants.WIDTH) {
                                food.x = Constants.WIDTH - food.x;
                            }
                            if (food.y >= Constants.HEIGHT - 1) {
                                food.y = Constants.HEIGHT - food.y;
                            }
                            if (!obstacles.isAt(food.x, food.y + 4) || !obstacles.isAt(food.x, food.y + 3) ||
                                    !obstacles.isAt(food.x, food.y + 5) || !obstacles.isAt(food.x, food.y + 6)) {
                                food.y -= 1;
                            }
                            timeCounter += 0.01;
                            //System.out.println("TimeCounter: " + timeCounter);
                            if (timeCounter >= 1) {
                                timeCounter = -1;
                            }
                        } else {
                            slower2 = true;
                        }
                    } else {
                        slower1 = true;
                    }
                }
            }
        } else {
            for (Food food : this.FoodList) {
                rando = random.nextDouble();
                if (food.state.smol) {
                    if (smallSlower1) {
                        if (smallSlower2) {
                            if (smallSlower3) {
                                if (smallSlower4) {
                                    food.y += 1;
                                    food.x += Math.sin(timeCounter) * 5 + rando;
                                    if (food.x < 0) {
                                        food.x = Constants.WIDTH + food.x;
                                    }
                                    if (food.y < 0) {
                                        food.y = Constants.HEIGHT + food.y;
                                    }
                                    if (food.x > Constants.WIDTH) {
                                        food.x = Constants.WIDTH - food.x;
                                    }
                                    if (food.y >= Constants.HEIGHT - 1) {
                                        food.y = Constants.HEIGHT - food.y;
                                    }
                                    timeCounter += 0.01;
                                    //System.out.println("TimeCounter: " + timeCounter);
                                    if (timeCounter >= 1) {
                                        timeCounter = -1;
                                    }
                                    smallSlower1 = false;
                                    smallSlower2 = false;
                                    smallSlower3 = false;
                                    smallSlower4 = false;
                                } else {
                                    smallSlower4 = true;
                                }
                            } else {
                                smallSlower3 = true;
                            }
                        } else {
                            smallSlower2 = true;
                        }
                    } else {
                        smallSlower1 = true;
                    }
                } else {
                    if (slower1) {
                        if (slower2) {
                            food.y += 1;
                            food.x += Math.sin(timeCounter) * 5 + rando;
                            if (food.x < 0) {
                                food.x = Constants.WIDTH + food.x;
                            }
                            if (food.y < 0) {
                                food.y = Constants.HEIGHT + food.y;
                            }
                            if (food.x > Constants.WIDTH) {
                                food.x = Constants.WIDTH - food.x;
                            }
                            if (food.y >= Constants.HEIGHT - 1) {
                                food.y = Constants.HEIGHT - food.y;
                            }
                            timeCounter += 0.01;
                            //System.out.println("TimeCounter: " + timeCounter);
                            if (timeCounter >= 1) {
                                timeCounter = -1;
                            }
                        } else {
                            slower2 = true;
                        }
                    } else {
                        slower1 = true;
                    }
                }
            }
        }
    }

    public void updateSquidPosition(Squid squid) {
        int mean = 0;


        if (squid.lastDirectionCounter >= 10) {

            int[] directional = {0, 0, 0, 0, 0, 0, 0, 0};

            int directionTemp = -1;
            for (Tentacle tent : squid.tentacles) {
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
            squid.lastDirection = mean;
            squid.lastDirectionCounter = 0;
        } else {
            mean = squid.lastDirection;
            squid.lastDirectionCounter++;
        }

        //float sum = mean / numTent;
        //mean = Math.round(sum/numTent);
        if (mean == -1) {
            //do not move
            return;
        }
        if (mean == 0) {
            squid.move(0, 1);
        } else if (mean == 1) {
            squid.move(1, 1);
        } else if (mean == 2) {
            squid.move(1, 0);
        } else if (mean == 3) {
            squid.move(1, -1);
        } else if (mean == 4) {
            squid.move(0, -1);
        } else if (mean == 5) {
            squid.move(-1, -1);
        } else if (mean == 6) {
            squid.move(-1, 0);
        } else if (mean == 7) {
            squid.move(-1, 1);
        }


    }

    public int closestTarget(ArrayList<Coord> targets, Squid squid) {

        int value = 30;
        int positionInList = 0;
        for (int x = 0; x < targets.size(); x++) {

            if (facts.distance(targets.get(x), squid.head.getCenter()) < value) {
                value = facts.distance(targets.get(x), squid.head.getCenter());
                positionInList = x;
            }

        }

        return positionInList;
    }

    /**
     * This is my second way to pass the time in the environment besides update.
     */
    public void passTime() {

        //foodFall();

        ArrayList<Cell> cellBuffer = new ArrayList<>();
        ArrayList<Worm> wormBuffer = new ArrayList<>();
        ArrayList<Squid> squidBuffer = new ArrayList<>();

        InteractionRequest request = null;
        splitResults = new ArrayList<>();
        replenish();

        if (this.squidArrayList.size() <= 1) {
            //System.out.println("SquidList is gone");

        }
/*
        for (Squid squid : this.squidArrayList) {
            try {
                SightRequest squidRequest = squid.examineWorld();
                SightResult squidResult = searchEnvironment(squidRequest, false, true);
                //get sight, analyze nearby targets, assign out jobs.'
                int withinView = squidResult.getFoodDirection().size();
                if (withinView == 1) {

                    for (Tentacle tent : squid.tentacles) {

                        tent.target = squidResult.getFoodDirection().get(0);

                    }


                } else if (withinView > 1) { //hand out jobs.
                    //int counter = 0;
                    for (Tentacle tent : squid.tentacles) {

                        if (!tent.assignedTarget) {
                            //assign a target and increment target counter
                            //assigned target should be the closest.
                            tent.getTarget(squidResult, squid.getTargetList());
                        }

                    }

                } else {
                    //System.out.println("Squid saw nothing");
                }

                updateSquidPosition(squid);

                if (!squid.state.dead) {
                    squidBuffer.add(squid);
                }

            } catch(Exception e) {
                System.out.println("Error within Squid pathfinding: " + e.getMessage());
            }
        }

        */
        for (Squid squid : this.squidArrayList) {
            try {
                if (squid.tentacles.size() > 0) {
                    for (Tentacle tent : squid.tentacles) {
                        try {
                            if (!tent.attackTarget()) { // if not attacking a target (or retracting, get a target.)
                                try {
                                    SightRequest tentSightRequest = tent.examineWorld();
                                    if (tentSightRequest == null) {
                                        throw new NullPointerException();
                                    }
                                    tent.getTarget(searchEnvironment(tentSightRequest, false, false, true), squid.getTargetList());
                                    if (tent.target != null) {
                                        squid.addToTargets(tent.stateTarget());
                                    }
                                } catch (Exception e) {
                                    System.out.println("Error: Within Pass Time, Tent.getTarget(): " + e.toString());
                                }
                            } else if (tent.targetReached) { // if the tentacle has reached its target. we must get it's interaction request.
                                if (tent.getRequest() != null) {
                                    squid.removeFromTargets(observeTentacle(tent.getRequest(), tent));
                                } else {
                                    throw new UnexpectedState(); //should never be reached.
                                }
                            }
                        } catch (Exception e) {
                            System.out.println("Error: Tentacle " + e.toString());
                        }
                    }
                } else {
                    squid.state.dead = true;
                }
                updateSquidPosition(squid);
                if (!squid.state.dead) {
                    squidBuffer.add(squid);
                }
            } catch (Exception e) {
                System.out.println("Error: Within Pass Time, in Squid List" + e.toString());
            }
        }


         
        for (Worm worm : this.wormList) {
            try {
                try {
                    request = worm.actOnKnowledge(searchEnvironment(worm.examineWorld(), true));
                    updateWormPosition(worm);
                } catch (Exception e) {
                    System.out.println("Error: Within Pass Time, Worm Request" + e.toString());
                }
                try {
                    if (request != null) {
                        observeWorm(request, worm);
                    }
                } catch (Exception e) {
                    System.out.println("Error: Within Pass Time, Observing Worm" + e.toString());
                }

            } catch (Exception e) {
                System.out.println("Error: Within Pass Time, in Worm List" + e.toString());
            }
            if (!worm.state.dead) {
                wormBuffer.add(worm);
            }
        }
        //System.out.println("Bac list size = " + this.bacillusArrayList.size());
        for (Bacillus bacillus : this.bacillusArrayList) {
            updateBacPosition(bacillus);
        }

        try {

            for (Cell cell : this.CellList) {
                cell.prop.stepRotate();
                if (!cell.state.dead) {
                    try {
                        if (cell.type == 0 || cell.type == 3) {
                            request = cell.actOnKnowledge(searchEnvironment(cell.examineWorld()));
                            updateCellPosition(cell);
                        } else {
                            request = cell.actOnKnowledge(searchEnvironment(cell.examineWorld()));
                            //request = cell.networkAnalysis(searchEnvironment(cell.examineWorld()));
                        }
                        if (request != null) {
                            try {
                                observeCell(request, cell);
                            } catch (Exception e) {
                                System.out.println("Observe Cell" + e);
                            }
                        }
                    } catch (Exception e) {
                        System.out.println("Within pass time" + e);
                    }
                    if (cell.state.dead) {
                        if (this.deadCells == this.CellListSize - 10) {
                            this.TopSurvivors.add(cell);
                        }
                        this.deadCells++;
                    } else {
                        cell.age++;
                        cellBuffer.add(cell);
                    }
                }
                //topScore(cell);
            }
            this.wormList = wormBuffer;
            this.CellList = cellBuffer;
            this.squidArrayList = squidBuffer;
            this.CellList.addAll(this.splitResults);
            this.splitResults = new ArrayList<>();
            if (obstacles.enabled) {
                //        changed = "yes";
                ArrayList<Food> foodBuffer = new ArrayList<>(); //not required since food does nothing and can only be added or removed.
                for (Food food : this.FoodList) {
                    if (obstacles.isAt(food.x, food.y)) {
                        foodBuffer.add(food);
                    }
                }
                this.FoodList = foodBuffer;

            }

        } catch (Exception e) {
            //thrown if adding cells.
            System.out.println(e.getMessage());
            //    System.out.println(changed);
        }

    }

    public void foodWasEaten(Coord coord) {
        Iterable<Food> tempList = this.FoodList;
        //Food remover = new Food(coord.x, coord.y);
        //this.FoodList.remove(remover);

        for (Food food : tempList) {
            if (food.x == coord.x && food.y == coord.y) {
                this.FoodList.remove(food);
                break;
                // } else {
                //tempList.add(food);
                //}
            }
        }


        //this.FoodList;
    }

    public void observeCell(InteractionRequest request, Cell cell) {
        boolean foodFound = false;
        //1 == eating a cell, 2 == eating food, 3 == reproducing, 4 == splitting

        if (request.getType() == 1) {
/*
            for (Squid squid : this.squidArrayList) {
                for (Tentacle tentacle : squid.tentacles) {
                    SquidLeg food = tentacle.grabber;
                    //if (food.x == request.getX() && food.y == request.getY()) {
                    if (new Facts().touching(cell.getCenter(), food.getCenter())) {
                        if (cell.diet != 1 && tentacle.size > cell.size) {
                            //System.out.println("Tried eating a cell and died");
                            cell.state.dead = true;
                            foodFound = true;

                            break;
                        } else if (!food.state.dead) {
                            cell.grow(tentacle.score);
                            cell.size += food.size / 8;
                            //tentacle.lostASegment();
                            this.aiScore += 100;
                            foodFound = true;

                            break;
                        } else {
                            break;
                        }
                    }
                }
            }

 */
            if (!foodFound) {
                for (Worm food : this.wormList) {
                    if (food.head.x == request.getX() && food.head.y == request.getY()) {
                        if (cell.diet != 1 && food.size > cell.size) {
                            cell.state.dead = true;
                            foodFound = true;

                            break;
                        } else if (!food.state.dead) {
                            cell.grow(food.score);
                            cell.size += food.size / 8;
                            food.loseHead();
                            this.aiScore += 100;
                            foodFound = true;

                            break;
                        } else {
                            break;
                        }
                    }
                }
            }
            if (!foodFound) {
                for (Cell food : this.CellList) {
                    if (food.x == request.getX() && food.y == request.getY()) {
                        if (cell.diet != 1 && food.size > cell.size) {
                            //System.out.println("Tried eating a cell and died");
                            cell.state.dead = true;
                            foodFound = true;

                            break;
                        } else if (!food.state.dead) {
                            cell.grow(food.score);
                            cell.size += food.size / 8;
                            food.state.dead = true;
                            this.aiScore += 100;
                            foodFound = true;

                            break;
                        } else {
                            break;
                        }
                    }
                }
            }
        } else if (request.getType() == 2) {
            for (Food food : this.FoodList) {
                if (food.x == request.getX() && food.y == request.getY()) {
                    if (!food.isEaten()) {
                        cell.grow(food.getSize());
                        food.state.eaten = true;
                        this.FoodList.remove(food);
                        //System.out.println("Tried eating a FoodBox");
                        this.aiScore += 100;

                        break;
                    } else {
                        break;
                    }
                }
            }
        } else if (request.getType() == 3) {
            for (Cell mate : this.CellList) {
                if (mate.x == request.getX() && mate.y == request.getY()) {
                    if (!mate.state.dead && cell.state.young && mate.state.young) {
                        this.splitResults.add(cell.giveBirth(mate, idGen));
                        mate.state.young = false;
                        break;
                    } else {
                        break;
                    }
                }
            }
        } else if (request.getType() == 4) {
            this.splitResults.add(cell.split(this.idGen));
        }

    }

    public void observeWorm(InteractionRequest request, Worm worm) {
        boolean foodFound = false;
        if (request.getType() == 1) {
            /*
            for (Squid squid : this.squidArrayList) {
                for (Tentacle tentacle : squid.tentacles) {
                    SquidLeg food = tentacle.grabber;
                    //if (food.x == request.getX() && food.y == request.getY()) {
                    if (new Facts().touching(worm.getCenter(), food.getCenter())) {
                        if (worm.diet != 1 && tentacle.size > worm.size) {
                            //System.out.println("Tried eating a cell and died");
                            worm.state.dead = true;
                            foodFound = true;

                            break;
                        } else if (!food.state.dead) {
                            worm.grow(tentacle.score);
                            worm.size += food.size / 8;
                            //tentacle.lostASegment();
                            this.aiScore += 100;
                            foodFound = true;

                            break;
                        } else {
                            break;
                        }
                    }
                }
            }

             */
            if (!foodFound) {
                for (Worm food : this.wormList) {
                /*
                int offset = 0;
                for (wormBody bodyPart : food.wormBodies) {
                    if (bodyPart.x == request.getX() && bodyPart.y == request.getY()) {
                        if (worm.diet != 1 && food.size > worm.size) {
                            //System.out.println("Tried eating a cell and died");
                            worm.loseHead();
                            break;
                        } else if (!food.state.dead) {
                            worm.grow(food.score);
                            worm.size += food.size / 8;
                            this.wormList.add(food.splitWormOffset(idGen, offset));
                            this.aiScore += 100;
                            break;
                        } else {
                            break;
                        }
                    }
                    offset++;
                }
*/
                    if (food.head.x == request.getX() && food.head.y == request.getY()) {
                        if (worm.diet != 1 && food.size > worm.size) {
                            //System.out.println("Tried eating a cell and died");
                            worm.loseHead();
                            break;
                        } else if (!food.state.dead) {
                            worm.grow(food.score);
                            worm.size += food.size / 8;
                            food.loseHead();
                            this.aiScore += 100;
                            break;
                        } else {
                            break;
                        }
                    }
                }
            }
            if (!foodFound) {
                for (Cell food : this.CellList) {
                    if (food.x == request.getX() && food.y == request.getY()) {
                        if (worm.diet != 1 && food.size > worm.size) {
                            //System.out.println("Tried eating a cell and died");
                            worm.state.dead = true;
                            break;
                        } else if (!food.state.dead) {
                            worm.grow(food.score);
                            worm.size += food.size / 8;
                            food.state.dead = true;
                            this.aiScore += 100;
                            break;
                        } else {
                            break;
                        }
                    }
                }
            }
        } else if (request.getType() == 2) {
            for (Food food : this.FoodList) {
                if (food.x == request.getX() && food.y == request.getY()) {
                    if (!food.isEaten()) {
                        worm.grow(food.getSize());
                        food.state.eaten = true;
                        this.FoodList.remove(food);
                        //System.out.println("Tried eating a FoodBox");
                        this.aiScore += 100;

                        break;
                    } else {
                        break;
                    }
                }
            }
        }
    }

    public Coord observeTentacle(InteractionRequest request, Tentacle tent) {
        Coord requested = new Coord(request.getX(), request.getY());
        boolean foodFound = false;
        if (request.getType() == 1) {
            /*
            for (Squid squid : this.squidArrayList) {
                for (Tentacle food : squid.tentacles)
                    if (new Facts().touching(requested, food.getCenter())) {
                        if (tent.diet != 1 && food.size > tent.size) {
                            //System.out.println("Tried eating a cell and died");
                            //tent.loseHead();
                            foodFound = true;
                            break;
                        } else if (!food.state.dead) {
                            tent.grow(food.score);
                            tent.size += food.size / 8;
                            //food.lostASegment();
                            this.aiScore += 100;
                            foodFound = true;
                            break;
                        } else {
                            break;
                        }
                    }
            }

             */
            if (!foodFound) {
                for (Worm food : this.wormList) {
                    //Coord foodHead = new Coord(food.head.x, food.head.y);
                    //if (food.head.x == request.getX() && food.head.y == request.getY()) {
                    if (new Facts().touching(requested, food.getCenter())) {
                        if (tent.diet != 1 && food.size > tent.size) {
                            //System.out.println("Tried eating a cell and died");
                            //tent.loseHead();
                            foodFound = true;
                            break;
                        } else if (!food.state.dead) {
                            tent.grow(food.score);
                            tent.size += food.size / 8;
                            food.loseHead();
                            this.aiScore += 100;
                            foodFound = true;
                            break;
                        } else {
                            break;
                        }
                    }
                }
            }
            if (!foodFound) {
                for (Cell food : this.CellList) {
                    //Coord foodHead = new Coord(food.x, food.y);
                    //if (food.x == request.getX() && food.y == request.getY()) {
                    if (new Facts().touching(requested, food.getCenter())) {
                        if (tent.diet != 1 && food.size > tent.size) {
                            //System.out.println("Tried eating a cell and died");
                            tent.state.dead = true;
                            foodFound = true;
                            break;
                        } else if (!food.state.dead) {
                            tent.grow(food.score);
                            tent.size += food.size / 8;
                            food.state.dead = true;
                            this.aiScore += 100;
                            foodFound = true;
                            break;
                        } else {
                            break;
                        }
                    }
                }
            }

        } else if (request.getType() == 2) {

            for (Food food : this.FoodList) {
                //if (food.x == request.getX() && food.y == request.getY()) {
                if (new Facts().touching(requested, food.getCenter())) {
                    if (!food.isEaten()) {
                        tent.grow(food.getSize());
                        food.state.eaten = true;
                        this.FoodList.remove(food);
                        //System.out.println("Tried eating a FoodBox");
                        this.aiScore += 100;

                        break;
                    } else {
                        break;
                    }
                }
            }
        }

        Coord toRemove = tent.stateTarget();
        return toRemove;
    }

    /**
     * Determines what the requesting Cell can see.
     *
     * @param sightRequest
     * @return
     */
    public SightResult searchEnvironment(SightRequest sightRequest, boolean worm) {

        Worm requestingCell = sightRequest.getTheWorm();
        Coord reqCell = new Coord(sightRequest.getX(), sightRequest.getY());
        //SightResult result = new SightResult(true,this.CellList,this.FoodList,this.ObstacleList,this.OtherList);
        SightResult conclusion = new SightResult();
/*
        try {
            for (Squid squid : squidArrayList) {
                for (Tentacle tent : squid.tentacles) {
                    SquidLeg cell = tent.grabber;
                    if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((requestingCell.type == 0) || requestingCell.type == 3) {
                            //is it a threat?
                            if (requestingCell.size < cell.size) {
                                //Threat detected!
                                conclusion.addToThreats(cell.getCenter());
                            } else if (requestingCell.size > cell.size) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                conclusion.addToObstacles(obst);
                            }
                        }
                    }
                }
            }


        } catch (Exception e) {
            System.out.println("Within Worm SearchEnvironment, searching for squid: " + e.toString());
        }


             */
        try {
            for (Worm cell : wormList) {
                /*
                for (wormBody bodypart : cell.wormBodies) {
                    if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((requestingCell.type == 0) || requestingCell.type == 3) {
                            //is it a threat?
                            if (requestingCell.size < bodypart.size) {
                                //Threat detected!
                                conclusion.addToThreats(bodypart.getCenter());
                            } else if (requestingCell.size > bodypart.size) {
                                //Food detected!
                                Coord meat = bodypart.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = bodypart.getCenter();
                                obst.meat = true;
                                conclusion.addToObstacles(obst);
                            }
                        }
                    }
                }

                 */
                if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                    //it's within viewing distance
                    if ((requestingCell.type == 0) || requestingCell.type == 3) {
                        //is it a threat?
                        if (requestingCell.size < cell.size) {
                            //Threat detected!
                            conclusion.addToThreats(cell.getCenter());
                        } else if (requestingCell.size > cell.size) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            conclusion.addToObstacles(obst);
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Within SearchEnvironment (Cell version) " + e);
        }

        try {
            for (Cell cell : this.CellList) {
                //determine distance
                if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                    //it's within viewing distance
                    if ((requestingCell.type == 0 && requestingCell.diet != 0) || requestingCell.type == 3) {
                        //is it a threat?
                        if (requestingCell.size < cell.size) {
                            //Threat detected!
                            conclusion.addToThreats(cell.getCenter());
                        } else if (requestingCell.size > cell.size) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            try {
                                if (!notGeneticallySimilar(sightRequest.getTheWorm(), cell, true)) {
                                    conclusion.addToFlock(cell.getCenter());
                                    if (cell.state.young) {
                                        conclusion.addToReproduction(obst);
                                    }
                                } else {
                                    conclusion.addToObstacles(obst);
                                }
                            } catch (Exception e) {
                                System.out.println("Within Search Environment worm 1" + e);
                            }
                        }
                    } else if (requestingCell.diet == 0) {
                        try {
                            if (notGeneticallySimilar(requestingCell, cell, true)) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                if (!notGeneticallySimilar(sightRequest.getTheCell(), cell)) {
                                    conclusion.addToFlock(cell.getCenter());
                                    if (cell.state.young) {
                                        conclusion.addToReproduction(obst);
                                    }
                                } else {
                                    conclusion.addToObstacles(obst);
                                }
                            }
                        } catch (Exception e) {
                            System.out.println("Within Search Environment 2 " + e);
                        }
                    } else {
                        //it can think.
                        conclusion.addToExaminations(new Examination(cell.size, cell.diet, cell.x, cell.y));
                    }
                }
            }

        } catch (Exception e) {
            System.out.println("Section 1: " + e);
        }
        try {
            if (terrainON) {
                for (int j = 0; j < sightRequest.getTheCell().sight; j++) {

                    try {
                        for (int x = sightRequest.getTheCell().x - 5; x < sightRequest.getTheCell().x + 5; x++) {
                            for (int y = sightRequest.getTheCell().y - 5; y < sightRequest.getTheCell().y + 5; y++) {


                                //if (!(x < 0 && x > constant.WIDTH && x < 0 && x > constant.HEIGHT)) { //causing pathfinding problems.
                                int x4 = x;
                                int y4 = y;
                                if (x < 0) {
                                    x = Constants.WIDTH + x;
                                }
                                if (y < 0) {
                                    y = Constants.HEIGHT + y;
                                }
                                if (x == Constants.WIDTH) {
                                    x -= 1;
                                }
                                if (y == Constants.HEIGHT) {
                                    y -= 1;
                                }

                                if (x > Constants.WIDTH) {
                                    x = x - Constants.WIDTH;
                                }
                                if (y > Constants.HEIGHT) {
                                    y = y - Constants.HEIGHT;
                                }
                                //try {
                                //if (obstacles.isAt(x, y)) {
                                //    conclusion.addToObstacles(new Coord(x, y));
                                //}
                                //} catch (Exception e) {
                                //    System.out.println("Section 2" + e);
                                //}
                                //}
                                x = x4;
                                y = y4;
                            }
                        }
                        //minus x and y
                    } catch (Exception e) {
                        System.out.println("Section 3" + e);
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Section 4" + e);
        }
        try {
            int y = 0;
            for (Food food : this.FoodList) {
                //determine distance
                if (requestingCell.type == 0) {

                    if (facts.distance(food, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        conclusion.addToFood(food.getCenter());
                        y++;
                    }
                } else {
                    //it can think.
                    conclusion.addToExaminations(new Examination(food.getSize(), 4, food.x, food.y));
                }

            }
            return conclusion;
        } catch (Exception e) {
            System.out.println("Section 5" + e);
        }
        return null;
    }

    /**
     * Determines what the requesting Cell can see.
     *
     * @param sightRequest
     * @return
     */
    public SightResult searchEnvironment(SightRequest sightRequest, boolean worm, boolean squid) {

        Squid requestingCell = sightRequest.getTheSquid();
        Coord reqCell = new Coord(sightRequest.getX(), sightRequest.getY());
        //SightResult result = new SightResult(true,this.CellList,this.FoodList,this.ObstacleList,this.OtherList);
        SightResult conclusion = new SightResult();
/*
        try {
            for (Tentacle tent : requestingCell.tentacles) {
                for (Worm cell : wormList) {
                    if (facts.distance(cell, tent.grabber.getCenter()) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((requestingCell.type == 0) || requestingCell.type == 3) {
                            //is it a threat?
                            if (requestingCell.size < cell.size) {
                                //Threat detected!
                                conclusion.addToThreats(cell.getCenter());
                            } else if (requestingCell.size > cell.size) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                conclusion.addToObstacles(obst);
                            }
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Within SearchEnvironment (Cell version) " + e);
        }
*/
        try {
            for (Tentacle tent : requestingCell.tentacles) {
                for (Cell cell : this.CellList) {
                    //determine distance
                    if (facts.distance(cell, tent.grabber.getCenter()) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((requestingCell.type == 0 && requestingCell.diet != 0) || requestingCell.type == 3) {
                            //is it a threat?
                            if (requestingCell.size < cell.size) {
                                //Threat detected!
                                conclusion.addToThreats(cell.getCenter());
                            } else if (requestingCell.size > cell.size) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                try {
                                    if (!notGeneticallySimilar(sightRequest.getTheSquid(), cell, true, true)) {
                                        conclusion.addToFlock(cell.getCenter());
                                        if (cell.state.young) {
                                            conclusion.addToReproduction(obst);
                                        }
                                    } else {
                                        conclusion.addToObstacles(obst);
                                    }
                                } catch (Exception e) {
                                    System.out.println("Within Search Environment 3 " + e);
                                }
                            }
                        } else if (requestingCell.diet == 0) {
                            try {
                                if (notGeneticallySimilar(sightRequest.getTheSquid(), cell, true, true)) {
                                    //Food detected!
                                    Coord meat = cell.getCenter();
                                    meat.meat = true;
                                    conclusion.addToFood(meat);
                                } else {
                                    //if equal size, then it is an obstacle.
                                    Coord obst = cell.getCenter();
                                    obst.meat = true;
                                    if (!notGeneticallySimilar(sightRequest.getTheCell(), cell)) {
                                        conclusion.addToFlock(cell.getCenter());
                                        if (cell.state.young) {
                                            conclusion.addToReproduction(obst);
                                        }
                                    } else {
                                        conclusion.addToObstacles(obst);
                                    }
                                }
                            } catch (Exception e) {
                                System.out.println("Within Search Environment 4 " + e);
                            }
                        } else {
                            //it can think.
                            conclusion.addToExaminations(new Examination(cell.size, cell.diet, cell.x, cell.y));
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Section 1: " + e);
        }
        try {
            if (terrainON) {
                for (int j = 0; j < sightRequest.getTheCell().sight; j++) {

                    try {
                        for (int x = sightRequest.getTheCell().x - 5; x < sightRequest.getTheCell().x + 5; x++) {
                            for (int y = sightRequest.getTheCell().y - 5; y < sightRequest.getTheCell().y + 5; y++) {


                                //if (!(x < 0 && x > constant.WIDTH && x < 0 && x > constant.HEIGHT)) { //causing pathfinding problems.
                                int x4 = x;
                                int y4 = y;
                                if (x < 0) {
                                    x = Constants.WIDTH + x;
                                }
                                if (y < 0) {
                                    y = Constants.HEIGHT + y;
                                }
                                if (x == Constants.WIDTH) {
                                    x -= 1;
                                }
                                if (y == Constants.HEIGHT) {
                                    y -= 1;
                                }

                                if (x > Constants.WIDTH) {
                                    x = x - Constants.WIDTH;
                                }
                                if (y > Constants.HEIGHT) {
                                    y = y - Constants.HEIGHT;
                                }
                                //try {
                                //if (obstacles.isAt(x, y)) {
                                //    conclusion.addToObstacles(new Coord(x, y));
                                //}
                                //} catch (Exception e) {
                                //    System.out.println("Section 2" + e);
                                //}
                                //}
                                x = x4;
                                y = y4;
                            }
                        }
                        //minus x and y
                    } catch (Exception e) {
                        System.out.println("Section 3" + e);
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Section 4" + e);
        }
        try {
            int y = 0;
            for (Tentacle tent : requestingCell.tentacles) {
                for (Food food : this.FoodList) {
                    //determine distance
                    if (requestingCell.type == 0) {

                        if (facts.distance(food, tent.grabber.getCenter()) <= sightRequest.getTheSquid().sight) {
                            //it's within viewing distance
                            conclusion.addToFood(food.getCenter());
                            y++;
                        }
                    } else {
                        //it can think.
                        conclusion.addToExaminations(new Examination(food.getSize(), 4, food.x, food.y));
                    }

                }
            }
            return conclusion;
        } catch (Exception e) {
            System.out.println("Searchign for food in Searching environment" + e);
        }
        return null;
    }

    /**
     * Determines what the requesting Cell can see.
     *
     * @param sightRequest
     * @return
     */
    public SightResult searchEnvironment(SightRequest sightRequest, boolean worm, boolean squids, boolean tentacle) {

        Tentacle tent = sightRequest.getTheTentacle();
        Coord reqCell = new Coord(sightRequest.getX(), sightRequest.getY());
        //SightResult result = new SightResult(true,this.CellList,this.FoodList,this.ObstacleList,this.OtherList);
        SightResult conclusion = new SightResult();
/*
        try {
            for (Squid squid : squidArrayList) {
                for (Tentacle tentr : squid.tentacles) {
                    SquidLeg cell = tentr.grabber;
                    if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((tent.type == 0) || tent.type == 3) {
                            //is it a threat?
                            if (tent.size < cell.size) {
                                //Threat detected!
                                conclusion.addToThreats(cell.getCenter());
                            } else if (tent.size > cell.size) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                conclusion.addToObstacles(obst);
                            }
                        }
                    }
                }
            }


        } catch (Exception e) {
            System.out.println("Within Worm SearchEnvironment, searching for squid: " + e.toString());
        }
*/
        try {
            for (Worm cell : wormList) {
                if (facts.distance(cell, tent.grabber.getCenter()) <= sightRequest.getViewingDistance()) {
                    //it's within viewing distance
                    if ((tent.type == 0) || tent.type == 3) {
                        //is it a threat?
                        if (tent.size < cell.size) {
                            //Threat detected!
                            conclusion.addToThreats(cell.getCenter());
                        } else if (tent.size > cell.size) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            conclusion.addToObstacles(obst);
                        }
                    }
                }
            }

        } catch (Exception e) {
            System.out.println("Within SearchEnvironment (Cell version) " + e);
        }

        try {

            for (Cell cell : this.CellList) {
                //determine distance
                if (facts.distance(cell, tent.grabber.getCenter()) <= sightRequest.getViewingDistance()) {
                    //it's within viewing distance
                    if ((tent.type == 0 && tent.diet != 0) || tent.type == 3) {
                        //is it a threat?
                        if (tent.size < cell.size) {
                            //Threat detected!
                            conclusion.addToThreats(cell.getCenter());
                        } else if (tent.size > cell.size) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            try {
                                if (!notGeneticallySimilar(sightRequest.getTheTentacle(), cell, false, false, true)) {
                                    conclusion.addToFlock(cell.getCenter());
                                    if (cell.state.young) {
                                        conclusion.addToReproduction(obst);
                                    }
                                } else {
                                    conclusion.addToObstacles(obst);
                                }
                            } catch (Exception e) {
                                System.out.println("Within Search Environment 5 " + e);
                            }
                        }
                    } else if (tent.diet == 0) {
                        try {
                            if (notGeneticallySimilar(sightRequest.getTheTentacle(), cell, false, false, true)) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                if (!notGeneticallySimilar(sightRequest.getTheTentacle(), cell, false, false, true)) {
                                    conclusion.addToFlock(cell.getCenter());
                                    if (cell.state.young) {
                                        conclusion.addToReproduction(obst);
                                    }
                                } else {
                                    conclusion.addToObstacles(obst);
                                }
                            }
                        } catch (Exception e) {
                            System.out.println("Within Search Environment 6 " + e);
                        }
                    } else {
                        //it can think.
                        conclusion.addToExaminations(new Examination(cell.size, cell.diet, cell.x, cell.y));
                    }
                }
            }

        } catch (Exception e) {
            System.out.println("Section 1: " + e);
        }
        try {
            int y = 0;

            for (Food food : this.FoodList) {
                //determine distance
                if (tent.type == 0) {

                    if (facts.distance(food, tent.grabber.getCenter()) <= sightRequest.getTheTentacle().sight) {
                        //it's within viewing distance
                        conclusion.addToFood(food.getCenter());
                        y++;
                    }
                } else {
                    //it can think.
                    conclusion.addToExaminations(new Examination(food.getSize(), 4, food.x, food.y));
                }

            }

            return conclusion;
        } catch (Exception e) {
            System.out.println("Searchign for food in Searching environment" + e);
        }
        return null;
    }

    /**
     * Determines what the requesting Cell can see.
     *
     * @param sightRequest
     * @return
     */
    public SightResult searchEnvironment(SightRequest sightRequest) {

        Cell requestingCell = sightRequest.getTheCell();
        Coord reqCell = new Coord(sightRequest.getX(), sightRequest.getY());
        //SightResult result = new SightResult(true,this.CellList,this.FoodList,this.ObstacleList,this.OtherList);
        SightResult conclusion = new SightResult();
/*
        try {
            for (Squid squid : squidArrayList) {
                for (Tentacle tent : squid.tentacles) {
                    SquidLeg cell = tent.grabber;
                    if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((requestingCell.type == 0) || requestingCell.type == 3) {
                            //is it a threat?
                            if (requestingCell.size < cell.size) {
                                //Threat detected!
                                conclusion.addToThreats(cell.getCenter());
                            } else if (requestingCell.size > cell.size) {
                                //Food detected!
                                Coord meat = cell.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = cell.getCenter();
                                obst.meat = true;
                                conclusion.addToObstacles(obst);
                            }
                        }
                    }
                }
            }


        } catch (Exception e) {
            System.out.println("Within Worm SearchEnvironment, searching for squid: " + e.toString());
        }
*/
        try {
            for (Worm cell : wormList) {
                /*
                for (wormBody bodypart : cell.wormBodies) {
                    if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        if ((requestingCell.type == 0) || requestingCell.type == 3) {
                            //is it a threat?
                            if (requestingCell.size < bodypart.size) {
                                //Threat detected!
                                conclusion.addToThreats(bodypart.getCenter());
                            } else if (requestingCell.size > bodypart.size) {
                                //Food detected!
                                Coord meat = bodypart.getCenter();
                                meat.meat = true;
                                conclusion.addToFood(meat);
                            } else {
                                //if equal size, then it is an obstacle.
                                Coord obst = bodypart.getCenter();
                                obst.meat = true;
                                conclusion.addToObstacles(obst);
                            }
                        }
                    }
                }

                 */


                if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                    //it's within viewing distance
                    if ((requestingCell.type == 0) || requestingCell.type == 3) {
                        //is it a threat?
                        if (requestingCell.size < cell.size) {
                            //Threat detected!
                            conclusion.addToThreats(cell.getCenter());
                        } else if (requestingCell.size > cell.size) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            conclusion.addToObstacles(obst);
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Within SearchEnvironment (Cell version) " + e);
        }

        try {
            for (Cell cell : this.CellList) {
                //determine distance
                if (facts.distance(cell, reqCell) <= sightRequest.getViewingDistance()) {
                    //it's within viewing distance
                    if ((requestingCell.type == 0 && requestingCell.diet != 0) || requestingCell.type == 3) {
                        //is it a threat?
                        if (requestingCell.size < cell.size && notGeneticallySimilar(requestingCell, cell)) {
                            //Threat detected!
                            conclusion.addToThreats(cell.getCenter());
                        } else if (requestingCell.size > cell.size && notGeneticallySimilar(requestingCell, cell)) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            if (!notGeneticallySimilar(sightRequest.getTheCell(), cell)) {
                                conclusion.addToFlock(cell.getCenter());
                                if (cell.state.young) {
                                    conclusion.addToReproduction(obst);
                                }
                            } else {
                                conclusion.addToObstacles(obst);
                            }
                        }
                    } else if (requestingCell.diet == 0) {
                        if (notGeneticallySimilar(requestingCell, cell)) {
                            //Food detected!
                            Coord meat = cell.getCenter();
                            meat.meat = true;
                            conclusion.addToFood(meat);
                        } else {
                            //if equal size, then it is an obstacle.
                            Coord obst = cell.getCenter();
                            obst.meat = true;
                            if (!notGeneticallySimilar(sightRequest.getTheCell(), cell)) {
                                conclusion.addToFlock(cell.getCenter());
                                if (cell.state.young) {
                                    conclusion.addToReproduction(obst);
                                }
                            } else {
                                conclusion.addToObstacles(obst);
                            }
                        }

                    } else {
                        //it can think.
                        conclusion.addToExaminations(new Examination(cell.size, cell.diet, cell.x, cell.y));
                    }
                }
            }

        } catch (Exception e) {
            System.out.println("Section 1: " + e);
        }
        try {
            if (terrainON) {
                for (int j = 0; j < sightRequest.getTheCell().sight; j++) {

                    try {
                        for (int x = sightRequest.getTheCell().x - 5; x < sightRequest.getTheCell().x + 5; x++) {
                            for (int y = sightRequest.getTheCell().y - 5; y < sightRequest.getTheCell().y + 5; y++) {


                                //if (!(x < 0 && x > constant.WIDTH && x < 0 && x > constant.HEIGHT)) { //causing pathfinding problems.
                                int x4 = x;
                                int y4 = y;
                                if (x < 0) {
                                    x = Constants.WIDTH + x;
                                }
                                if (y < 0) {
                                    y = Constants.HEIGHT + y;
                                }
                                if (x == Constants.WIDTH) {
                                    x -= 1;
                                }
                                if (y == Constants.HEIGHT) {
                                    y -= 1;
                                }

                                if (x > Constants.WIDTH) {
                                    x = x - Constants.WIDTH;
                                }
                                if (y > Constants.HEIGHT) {
                                    y = y - Constants.HEIGHT;
                                }
                                //try {
                                //if (obstacles.isAt(x, y)) {
                                //    conclusion.addToObstacles(new Coord(x, y));
                                //}
                                //} catch (Exception e) {
                                //    System.out.println("Section 2" + e);
                                //}
                                //}
                                x = x4;
                                y = y4;
                            }
                        }
                        //minus x and y
                    } catch (Exception e) {
                        System.out.println("Section 3" + e);
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("Section 4" + e);
        }
        try {
            int y = 0;
            for (Food food : this.FoodList) {
                //determine distance
                if (requestingCell.type == 0) {

                    if (facts.distance(food, reqCell) <= sightRequest.getViewingDistance()) {
                        //it's within viewing distance
                        conclusion.addToFood(food.getCenter());
                        y++;
                    }
                } else {
                    //it can think.
                    conclusion.addToExaminations(new Examination(food.getSize(), 4, food.x, food.y));
                }

            }
            return conclusion;
        } catch (Exception e) {
            System.out.println("Section 5" + e);
        }
        return null;
    }

    public boolean notGeneticallySimilar(Cell mainCell, Cell secondaryCell) {
        final boolean similar = true;
        final int howClose = 15;
        if (mainCell == null || secondaryCell == null) {
            return true;
        }
        if (mainCell.type == 3 && secondaryCell.type == 3) {
            return false;
        }

        if (mainCell.threatTolerance - secondaryCell.threatTolerance <= howClose && secondaryCell.threatTolerance - mainCell.threatTolerance <= howClose) {
            if (mainCell.sight - secondaryCell.sight <= howClose && secondaryCell.sight - mainCell.sight <= howClose) {
                if (mainCell.diet == secondaryCell.diet) {
                    return false;
                }
            }
        }

        return similar;
    }

    public boolean notGeneticallySimilar(Worm mainCell, Cell secondaryCell, boolean worm) {
        final boolean similar = true;
        final int howClose = 15;
        if (mainCell.type == 3 && secondaryCell.type == 3) {
            return false;
        }

        if (mainCell.threatTolerance - secondaryCell.threatTolerance <= howClose && secondaryCell.threatTolerance - mainCell.threatTolerance <= howClose) {
            if (mainCell.sight - secondaryCell.sight <= howClose && secondaryCell.sight - mainCell.sight <= howClose) {
                if (mainCell.diet == secondaryCell.diet) {
                    return false;
                }
            }
        }

        return similar;
    }

    public boolean notGeneticallySimilar(Squid mainCell, Cell secondaryCell, boolean worm, boolean squid) {
        final boolean similar = true;
        final int howClose = 15;
        return true;
/*
        if (mainCell.threatTolerance - secondaryCell.threatTolerance <= howClose && secondaryCell.threatTolerance - mainCell.threatTolerance <= howClose) {
            if (mainCell.sight - secondaryCell.sight <= howClose && secondaryCell.sight - mainCell.sight <= howClose) {
                if (mainCell.diet == secondaryCell.diet) {
                    return false;
                }
            }
        }

        return similar;

 */
    }

    public boolean notGeneticallySimilar(Tentacle tent, Cell secondaryCell, boolean worm, boolean squid, boolean tentacle) {
        final boolean similar = true;
        final int howClose = 15;
        return true;
    }

    /**
    controls the number of cells
     */
    public int cellCount = 100;

    /**
     * Add a cell to the Environment.
     *
     * @param cell Cell object
     */
    public void addCell(Cell cell) {
        if (CellList.size() < cellCount) {
            boolean temper = obstacles.isAt(cell.x, cell.y);
            if (!temper) {
                this.CellList.add(cell);
                this.CellListSize++;
            }
        }
    }

    public ArrayList<Bacillus> bacillusArrayList = new ArrayList<>();

    public void addBacillus(Bacillus bacillus) {

        if (bacillusArrayList.size() < 100) {
            bacillusArrayList.add(bacillus);
        }

    }

    /**
     * Add food to the Environment.
     *
     * @param food Food Object
     */
    public void addFood(Food food) {
        if (obstacles.isAt(food.x, food.y)) {
            this.FoodList.add(food);
        }
    }

    public void nextGen() {

        this.TopSurvivors.addAll(this.CellList);
        this.CellList = null;
        this.CellList = new ArrayList<>();

    }

    public void updateIDGEN(IDGen idGen) {
        this.idGen = idGen;
    }

    public IDGen getIDGen() {
        return this.idGen;
    }

    public List<Cell> getCellList() {
        return CellList;
    }

    public List<Food> getFoodList() {
        return FoodList;
    }

    public ArrayList<Obstacle> getObstacleList() {
        return ObstacleList;
    }

    public ArrayList<Other> getOtherList() {
        return OtherList;
    }

    public void changeTerrain(double change) {
        this.obstacles.modifyHeight((int) change);
    }

    public void toggleterrain() {
        this.terrainON = !this.terrainON;
        if (this.terrainON) {
            this.obstacles.enabled = true;
            this.obstacles.changed = true;
            //this.ObstacleList = new ArrayList<>();
            //this.theMap = new SectorMap();
        } else {
            this.obstacles.enabled = false;
            //this.obstacles.
            //if (onlyOnce == true) {
                /*
                OpenSimplexNoise noise = new OpenSimplexNoise();
                this.ObstacleList = new ArrayList<>();
                this.theMap = new SectorMap();
                for (int y = 0; y < constant.HEIGHT; y++) {
                    for (int x = 0; x < constant.WIDTH; x++) {
                        double value = noise.eval(x / fSize, y / fSize, 0.0);
                        if (Math.toIntExact(Math.round(value)) == 1) {
                            //Obstacle temp = new Obstacle(new Body(new Coord(x, y)), new Coord(x, y));
                            //this.theMap.addObstacle2Map(temp);
                        }

                    }
                }

                 */
            //onlyOnce = false;
            //}
        }
    }

    public void replenish() {

        //replenishCells();
        replenishWorms();

    }

    public void replenishWorms() {
        if (this.wormList.size() < 300) {
            for (int x = this.wormList.size(); x <= 10; x++) {
                addWorm(new Worm(random.nextInt(10), idGen));
            }
        }
    }

    public void replenishCells() {
        if (this.CellList.size() < 50) {
            for (int x = this.CellList.size(); x <= 50; x++) {
                /*
                this.addCell(new Cell(this.idGen, random.nextInt(20), 2,
                        random.nextInt(100), random.nextInt(500), random.nextInt(4), random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), random.nextInt(10),
                        random.nextInt(1000), 0, random.nextInt(100)));
                this.addCell(new Cell(idGen, true, random.nextInt(20), 2,
                        random.nextInt(100), random.nextInt(500), random.nextInt(4), random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), random.nextInt(10),
                        random.nextInt(1000), 0, random.nextInt(100)));

                 */
                final Cell temp = new Cell(idGen, this.random.nextInt(20), 2,
                        this.random.nextInt(100), this.random.nextInt(500), this.random.nextInt(4), this.random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), this.random.nextInt(10),
                        this.random.nextInt(1000), 0, this.random.nextInt(100));
                temp.x = this.random.nextInt(Constants.WIDTH);
                temp.y = this.random.nextInt(Constants.HEIGHT);
                addCell(temp);
                final Cell temp2 = new Cell(this.idGen, true, this.random.nextInt(20), 2,
                        this.random.nextInt(100), this.random.nextInt(500), this.random.nextInt(4), this.random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), this.random.nextInt(10),
                        this.random.nextInt(1000), 0, this.random.nextInt(100));
                temp2.x = this.random.nextInt(Constants.WIDTH);
                temp2.y = this.random.nextInt(Constants.HEIGHT);
                addCell(temp2);
            }
        }
    }

    public void killAll() {
        for (Cell cell : this.CellList) {
            cell.state.dead = true;
        }
        for (Cell cell : this.CellList) {
            cell.state.dead = true;
        }
        replenish();
    }

    public void setupLeaderboard() {
        Random random = new Random();
        for (int x = 0; x < 10; x++) {
            leaderboard[x] = new Cell(this.idGen, random.nextInt(20), 2,
                    random.nextInt(100), random.nextInt(500), random.nextInt(4), random.nextInt(3),
                    Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), random.nextInt(10), random.nextInt(1000), 1, random.nextInt(100));
            prevLeaderboard[x] = new Cell(this.idGen, random.nextInt(20), 2,
                    random.nextInt(100), random.nextInt(500), random.nextInt(4), random.nextInt(3),
                    Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), random.nextInt(10), random.nextInt(1000), 1, random.nextInt(100));
        }

    }

    public void topScore(Cell cell) {
        //list can only be 10 long
        for (int x = 0; x < 10; x++) {
            if (cell.score > leaderboard[x].score) {
                leaderboard[x] = cell;
                break;
            }
        }
    }

    public boolean didIGetAdded() {
        for (Cell cell : this.toAdd) {
            boolean added = false;
            for (Cell living : this.CellList) {
                if (living.getID() == cell.getID()) {
                    added = true;
                }
            }
            if (!added) {
                System.out.println("Cell #" + cell.getID() + " was NOT added");
                return false;
            }
        }
        //System.out.println("All Cells added?");
        return true;
    }


    public void addSquid(Squid squid) {
        this.squidArrayList.add(squid);
    }

    public ArrayList<Bacillus> getBacillusList() {

        return this.bacillusArrayList;

    }
}
