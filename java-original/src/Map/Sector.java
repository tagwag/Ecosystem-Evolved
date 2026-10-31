package Map;

import Models.Cell;
import Models.Food;
import Enviroment.Obstacle;
import Enviroment.Coord;

import java.util.ArrayList;

public class Sector {

    ArrayList<Cell> cells = new ArrayList<>();
    ArrayList<Food> foods = new ArrayList<>();
    ArrayList<Obstacle> obstacles = new ArrayList<>();

    public void addCell(final Cell cell) {
        cells.add(cell);
    }

    public void addFood(final Food food) {
        foods.add(food);
    }

    public void addObstacle(final Obstacle obstacle) {
        obstacles.add(obstacle);
    }

    public void removeCell(final Cell cell) {
        cells.remove(cell);
    }

    public void removeFood(final Food food) {
        foods.remove(food);
    }

    public void removeObstacle(final Obstacle obstacle) {
        obstacles.remove(obstacle);
    }

    public void removeCell(final int id) {
        for (final Cell cell : cells) {
            if (cell.getID() == id) {
                this.removeCell(cell);
                return;
            }
        }
    }

    public void removeFood(final int id) {
        for (final Food food : foods) {
            if (food.id == id) {
                this.removeFood(food);
                return;
            }
        }
    }

    public void updateCell(final Cell cellUpdate) {
        final int id = cellUpdate.getID();
        for (Cell cell : cells) {
            if (cell.getID() == id) {
                cell = cellUpdate;
                return;
            }
        }
    }

    public ArrayList<Cell> getCells() {
        return this.cells;
    }

    public void setCells(final ArrayList<Cell> cells) {
        this.cells = cells;
    }

    public ArrayList<Food> getFoods() {
        return this.foods;
    }

    public void setFoods(final ArrayList<Food> foods) {
        this.foods = foods;
    }

    public ArrayList<Obstacle> getObstacles() {
        return this.obstacles;
    }

    public ArrayList<Coord> getObstacleDirections() {
        final ArrayList<Coord> directions = new ArrayList<>();
       for (final Obstacle obstacle : obstacles) {
           directions.add(obstacle.getCenter());
       }
       return directions;
    }

    public void setObstacles(final ArrayList<Obstacle> obstacles) {
        this.obstacles = obstacles;
    }
}
