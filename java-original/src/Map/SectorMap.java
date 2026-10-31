package Map;

import Models.Cell;
import Models.Food;
import Enviroment.Obstacle;
import Enviroment.Coord;

import java.util.ArrayList;

/**
 *
 */
public class SectorMap {
    //contains 144 Sector Objects

    //Sector Dimensions are: 60x45 units.

    public Sector[][] sectors = new Sector[12][12];

    //possible optimization is to make a map that contains cell ids and their sector location and to update that instead.


    public SectorMap() {

        for (int y = 0; y < 12; y++) {
            for (int x = 0; x < 12; x++) {
                sectors[x][y] = new Sector();
            }
        }

    }

    public void clearOrganics() {
        for (final Sector[] sectorArray : this.sectors) {
            for (final Sector sector : sectorArray) {
                sector.cells = new ArrayList<>();
                sector.foods = new ArrayList<>();
            }
        }
    }

    public ArrayList getSector(final Coord position, final int viewDistance) {

        final ArrayList<Sector> result = new ArrayList<>();
        final int xPos = position.getX();
        final int yPos = position.getY();
        final int bottomleftrow = this.getRow(yPos - viewDistance);
        final int bottomleftcolumn = this.getColumn(xPos - viewDistance);
        final int toprightrow = this.getRow(yPos + viewDistance);
        final int toprightcolumn = this.getColumn(xPos + viewDistance);

        for (int y = bottomleftrow; y < toprightrow; y++) {
            for (int x = bottomleftcolumn; x < toprightcolumn; x++) {
                result.add(sectors[x][y]);
            }
        }

        return result;
    }

    public void addCell2Map(final Cell cell) {

        final Coord position = cell.getCenter();
        int row;
        int column;
        final int xPos = position.getX();
        final int yPos = position.getY();
        int pos;
        int neg;


        sectors[this.getColumn(xPos)][this.getRow(yPos)].addCell(cell);
    }

    public void addFood2Map(final Food food) {

        final Coord position = food.getCenter();
        int row;
        int column;
        final int xPos = position.getX();
        final int yPos = position.getY();
        int pos;
        int neg;


        sectors[this.getColumn(xPos)][this.getRow(yPos)].addFood(food);
    }

    public void addObstacle2Map(final Obstacle obstacle) {

        final Coord position = obstacle.getCenter();
        int row;
        int column;
        final int xPos = position.getX();
        final int yPos = position.getY();
        int pos;
        int neg;

        sectors[this.getColumn(xPos)][this.getRow(yPos)].addObstacle(obstacle);
    }

    public void removeCellFromMap(final Cell cell) {

        final Coord position = cell.getCenter();
        int row;
        int column;
        final int xPos = position.getX();
        final int yPos = position.getY();
        int pos;
        int neg;

        sectors[this.getColumn(xPos)][this.getRow(yPos)].removeCell(cell);
    }

    public void removeFoodFromMap(final Food food) {

        final Coord position = food.getCenter();
        int row;
        int column;
        final int xPos = position.getX();
        final int yPos = position.getY();
        int pos;
        int neg;

        sectors[this.getColumn(xPos)][this.getRow(yPos)].removeFood(food);
    }

    public void updateCellOnMap(final Cell cell) {

        final Coord position = cell.getCenter();
        int row;
        int column;
        final int xPos = position.getX();
        final int yPos = position.getY();
        int pos;
        int neg;

        sectors[this.getColumn(xPos)][this.getRow(yPos)].updateCell(cell);
    }

    public Sector[][] getSectors() {
        return this.sectors;
    }

    public void setSectors(final Sector[][] sectors) {
        this.sectors = sectors;
    }

    public int getColumn(final int pos) {
        int number = 0;
        int multiple = 1;
        while (!(pos <= 60 * multiple) && number < 11) {
            number++;
            multiple++;
        }
        return number--;
    }

    public int getRow(final int pos) {
        int number = 0;
        int multiple = 1;
        while (!(pos <= 45 * multiple) && number < 11) {
            number++;
            multiple++;
        }
        return number--;
    }

    public Iterable<Obstacle> getObstaclesFromSector(final Coord pos) {

        final int xPos = pos.getX();
        final int yPos = pos.getY();

        return sectors[this.getColumn(xPos)][this.getRow(yPos)].obstacles;
    }
}
