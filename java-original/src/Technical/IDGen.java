package Technical;

import java.util.ArrayList;

public class IDGen {

    public ArrayList<Integer> cellIDList = new ArrayList<Integer>();
    public ArrayList<Integer> foodIDList = new ArrayList<Integer>();
    public ArrayList<Integer> obstacleIDList = new ArrayList<Integer>();
    public ArrayList<Integer> otherIDList = new ArrayList<Integer>();

    private int lastCellID;
    private int lastFoodID;
    private int lastObstacleID;
    private int lastOtherID;

    public int makeCellID() {
        final int theID = lastCellID;
        lastCellID++;
        cellIDList.add(theID);

        return theID;
    }


    public boolean removeCellID(final int toRemove) {

        return cellIDList.remove(new Integer(toRemove));

    }


    public int makeFoodID() {

        final int theID = lastFoodID;
        lastFoodID++;
        foodIDList.add(theID);

        return theID;

    }


    public boolean removeFoodID(final int toRemove) {

        return foodIDList.remove(new Integer(toRemove));

    }


    public int makeObstacleID() {
        final int theID = lastObstacleID;
        lastObstacleID++;

        obstacleIDList.add(theID);


        return theID;
    }


    public boolean removeObstacleID(final int toRemove) {


        return obstacleIDList.remove(new Integer(toRemove));


    }

    public int makeOtherID() {

        final int theID = lastOtherID;
        lastOtherID++;
        otherIDList.add(theID);

        return theID;
    }


    public ArrayList<Integer> getCellIDList() {
        return this.cellIDList;

    }


    public void setCellIDList(final ArrayList<Integer> cellIDList) {
        this.cellIDList = cellIDList;
    }

    public ArrayList<Integer> getFoodIDList() {
        return this.foodIDList;
    }

    public void setFoodIDList(final ArrayList<Integer> foodIDList) {
        this.foodIDList = foodIDList;
    }

    public ArrayList<Integer> getObstacleIDList() {
        return this.obstacleIDList;
    }

    public void setObstacleIDList(final ArrayList<Integer> obstacleIDList) {
        this.obstacleIDList = obstacleIDList;
    }


    public ArrayList<Integer> getOtherIDList() {


        return this.otherIDList;
    }


    public void setOtherIDList(final ArrayList<Integer> otherIDList) {


        this.otherIDList = otherIDList;
    }

    public int getLastCellID() {
        return this.lastCellID;
    }

    public void setLastCellID(final int lastCellID) {
        this.lastCellID = lastCellID;
    }

    public int getLastFoodID() {
        return this.lastFoodID;
    }

    public void setLastFoodID(final int lastFoodID) {
        this.lastFoodID = lastFoodID;
    }

    public int getLastObstacleID() {
        return this.lastObstacleID;
    }

    public void setLastObstacleID(final int lastObstacleID) {
        this.lastObstacleID = lastObstacleID;
    }

    public int getLastOtherID() {
        return this.lastOtherID;
    }

    public void setLastOtherID(final int lastOtherID) {
        this.lastOtherID = lastOtherID;
    }
}
