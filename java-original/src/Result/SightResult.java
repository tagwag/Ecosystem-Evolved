package Result;

import Enviroment.Coord;
import Models.Mental.Examination;

import java.util.ArrayList;

/**
 *
 */
public class SightResult {

    private boolean success;
    private ArrayList<Coord> threatDirection = new ArrayList<>();
    private ArrayList<Coord> foodDirection = new ArrayList<>();
    private ArrayList<Coord> ObstacleDirection = new ArrayList<>();
    private ArrayList<Coord> OtherDirection = new ArrayList<>();
    private ArrayList<Coord> reproductionDirection = new ArrayList<>();
    private ArrayList<Coord> flockDirection = new ArrayList<>();
    private ArrayList<Coord> obstacles = new ArrayList<>();
    private ArrayList<Examination> type1 = new ArrayList<>();

    /**
     * Contains the results of a Cell's attempt to see objects in the surrounding Environment.
     *
     * @param success               boolean
     * @param threatDirection       int
     * @param foodDirection         ArrayList
     * @param obstacleDirection     ArrayList
     * @param otherDirection        ArrayList
     * @param reproductionDirection ArrayList
     */
    public SightResult(final boolean success, final ArrayList<Coord> threatDirection, final ArrayList<Coord> foodDirection, final ArrayList<Coord> obstacleDirection, final ArrayList<Coord> otherDirection,
                       final ArrayList<Coord> reproductionDirection, final ArrayList<Coord> obstacles, final ArrayList<Examination> type1, final ArrayList<Coord> flockDirection) {
        //it saw something.
        //didn't see anything.
        this.success = success;
        this.threatDirection = threatDirection;
        this.foodDirection = foodDirection;
        ObstacleDirection = obstacleDirection;
        OtherDirection = otherDirection;
        this.reproductionDirection = reproductionDirection;
        this.obstacles = obstacles;
        this.type1 = type1;
        this.flockDirection = flockDirection;
    }

    public SightResult() {
    }

    public boolean isSuccess() {
        return this.success;
    }

    public void setSuccess(final boolean success) {
        this.success = success;
    }

    public ArrayList<Coord> getThreatDirection() {
        return this.threatDirection;
    }

    public ArrayList<Coord> getFoodDirection() {
        return this.foodDirection;
    }

    public ArrayList<Coord> getObstacleDirection() {
        return this.ObstacleDirection;
    }

    public ArrayList<Coord> getOtherDirection() {
        return this.OtherDirection;
    }

    public ArrayList<Coord> getReproductionDirection() {
        return this.reproductionDirection;
    }

    public ArrayList<Coord> getObstacles() {
        return this.obstacles;
    }

    public ArrayList<Examination> getType1() {
        return this.type1;
    }

    public void addToThreats(final Coord coord) {
        threatDirection.add(coord);
    }

    public void addToFood(final Coord coord) {
        foodDirection.add(coord);
    }

    public void addToReproduction(final Coord coord) {
        reproductionDirection.add(coord);
    }

    public void addToObstacles(final Coord coord) {
        reproductionDirection.add(coord);
    }

    public void addToExaminations(final Examination examination) {
        type1.add(examination);
    }
    public void addToFlock(final Coord coord) {
        flockDirection.add(coord);
    }

    public Iterable<Coord> getFlockDirection() {
        return this.flockDirection;
    }
}
