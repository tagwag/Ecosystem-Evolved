package Models.Mental;

import Enviroment.Coord;

import java.util.ArrayList;

/**
 * All Cells have Knowledge of their surroundings. It is a version of short term memory.
 */
public class Knowledge {

    private final ArrayList<Coord> threatDirection = new ArrayList<>(); // contains nearby potential threats.
    private final ArrayList<Coord> foodDirection = new ArrayList<>(); // contains nearby potential food.
    private final ArrayList<Coord> ObstacleDirection = new ArrayList<>();
    private final ArrayList<Coord> OtherDirection = new ArrayList<>();
    private final ArrayList<Coord> reproductionDirection = new ArrayList<>(); //contains nearby potential mates.
    private final ArrayList<Examination> thoughts = new ArrayList<>();

}
