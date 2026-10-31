package Service;

import Enviroment.Coord;
import Enviroment.Obstacle;
import Models.Cell;
import Models.Facts;
import Models.Food;
import Models.Mental.Examination;
import Request.SightRequest;
import Result.SightResult;

import java.util.ArrayList;

public class SightService {

    private final ArrayList<Coord> threatDirection = new ArrayList<Coord>();
    private final ArrayList<Coord> foodDirection = new ArrayList<Coord>();
    private final ArrayList<Coord> ObstacleDirection = new ArrayList<Coord>();
    private final ArrayList<Coord> OtherDirection = new ArrayList<Coord>();
    private final ArrayList<Coord> reproductionDirection = new ArrayList<Coord>();
    private final ArrayList<Coord> flockingDirection = new ArrayList<Coord>();
    private final ArrayList<Coord> obstacles = new ArrayList<Coord>();
    public final Facts facts = new Facts();
    private final ArrayList<Examination> type1 = new ArrayList<>();

    /**
     * Determines what the requesting Cell can see.
     *
     * @param sightRequest
     * @return
     */
    public SightResult searchEnvironment(final SightRequest sightRequest) {

        Cell mainCell = sightRequest.getTheCell();
        //SightResult result = new SightResult(true,this.CellList,this.FoodList,this.ObstacleList,this.OtherList);

        int x = 0;

        for (final Cell cell : sightRequest.getTheEnvironment().getCellList()) {
            //determine distance
            if (this.facts.distance(mainCell, cell) <= mainCell.sight) {
                //it's within viewing distance
                if (mainCell.type == 0) {
                    //is it a threat?

                    if (mainCell.size < cell.size && this.notGeneticallySimilar(mainCell, cell)) {
                        //Threat detected!
                        threatDirection.add(cell.getCenter());
                    } else if (mainCell.size > cell.size && this.notGeneticallySimilar(mainCell, cell)) {
                        //Food detected!
                        final Coord meat = cell.getCenter();
                        meat.meat = true;
                        //if (notGeneticallySimilar(this.mainCell, cell)) {
                        foodDirection.add(meat);
                        //} else {
                        //    this.ObstacleDirection.add(cell.getCenter());
                        //}
                    } else {
                        //if equal size, then it is an obstacle.
                        final Coord obst = cell.getCenter();
                        obst.meat = true;
                        if (!this.notGeneticallySimilar(mainCell, cell)) {
                            flockingDirection.add(cell.getCenter());
                            if (cell.state.young) {
                                this.reproductionDirection.add(obst);
                            }
                        } else{
                            ObstacleDirection.add(obst);
                        }
                    }
                } else {
                    //it can think.
                    type1.add(new Examination(cell.size, cell.diet, cell.x, cell.y));
                }
                x++;
            }
        }
        int y = 0;
        for (final Food food : sightRequest.getTheEnvironment().getFoodList()) {
            //determine distance
            if (mainCell.type == 0) {

                if (this.facts.distance(mainCell, food) <= mainCell.sight) {
                    //it's within viewing distance
                    foodDirection.add(food.getCenter());
                    y++;
                }
            } else {
                //it can think.
                type1.add(new Examination(food.getSize(), 4, food.x, food.y));
            }

        }


        //solution is divide the map into sectors and only compute specific regions.

        int z = 0;
        //final ArrayList<Sector> withinRange = sightRequest.getTheSectorMap().getSector(mainCell.getCenter(), mainCell.sight);
/*
        for (Sector sector : withinRange) {
            //    this.ObstacleDirection.addAll(sector.getObstacleDirections());
            for (Cell cell : sector.getCells()) {

                if (this.mainCell.body.distanceFromSelf(cell.getCenter()) <= this.mainCell.sight) {
                    //it's within viewing distance

                    //is it a threat?

                    if (this.mainCell.size < cell.size && notGeneticallySimilar(mainCell, cell)) {
                        //Threat detected!
                        this.threatDirection.add(cell.getCenter());
                    } else if (this.mainCell.size > cell.size && notGeneticallySimilar(this.mainCell, cell)) {
                        //Food detected!
                        Coord meat = cell.getCenter();
                        meat.meat = true;
                        //if (notGeneticallySimilar(this.mainCell, cell)) {
                        this.foodDirection.add(meat);
                        //System.out.println("meat found at " + meat.x + "," + meat.y);
                        //System.out.println("Meat found");
                        //} else {
                        //    this.ObstacleDirection.add(cell.getCenter());
                        //}
                    } else {
                        //if equal size, then it is an obstacle.
                        Coord obst = cell.getCenter();
                        obst.meat = true;
                        if (!notGeneticallySimilar(mainCell, cell) && cell.state.young) {
                            reproductionDirection.add(obst);
                        } else {
                            this.ObstacleDirection.add(obst);
                        }
                    }


                }
            }

            for (Food food : sector.getFoods()) {
                //determine distance
                if (this.mainCell.body.distanceFromSelf(food.getCenter()) <= this.mainCell.sight) {
                    //it's within viewing distance
                    //System.out.println("food found at " + food.getCenter().x + "," + food.getCenter().y);
                    this.foodDirection.add(food.getCenter());
                }

            }


        }
*/
        //get all obstacles within range.
        //for (Sector sector: withinRange) {
        //    this.ObstacleDirection.addAll(sector.getObstacleDirections());
        //}
        try {
            for (final Obstacle obstacle : sightRequest.getTheSectorMap().getObstaclesFromSector(mainCell.getCenter())) {
                obstacles.add(obstacle.getCenter());
                ObstacleDirection.add(obstacle.getCenter());
                z++;
            }
        } catch (final Exception e) {
            //tripped when terrain is modified.
        }

        /*
        for (Obstacle obstacle : sightRequest.getTheEnvironment().getObstacleList()) {
            if (this.mainCell.body.distanceFromSelf(obstacle.getCenter()) <= this.mainCell.sight) {
                //it's within viewing distance
                this.foodDirection.add(obstacle.getCenter());
            }
        }
        This just takes way too much processing power to compute.

         */

        SightResult result;
        if (x == 0 && y == 0 && z == 0) {
            //saw nothing new
            result = new SightResult(false, threatDirection, foodDirection, ObstacleDirection, OtherDirection, reproductionDirection, obstacles, type1, flockingDirection);
        } else {
            result = new SightResult(true, threatDirection, foodDirection, ObstacleDirection, OtherDirection, reproductionDirection, obstacles, type1, flockingDirection);
        }
        return result;
    }


    public boolean notGeneticallySimilar(final Cell mainCell, final Cell secondaryCell) {
        final boolean similar = true;
        final int howClose = 15;
        if (mainCell.threatTolerance - secondaryCell.threatTolerance <= howClose && secondaryCell.threatTolerance - mainCell.threatTolerance <= howClose) {
            if (mainCell.sight - secondaryCell.sight <= howClose && secondaryCell.sight - mainCell.sight <= howClose) {
                if (mainCell.diet == secondaryCell.diet) {
                    return false;
                }
            }
        }

        return similar;
    }

}
