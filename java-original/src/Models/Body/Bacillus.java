package Models.Body;

import Constants.Constants;
import Models.Mental.Pathfinding;

import java.util.Random;

public class Bacillus {

    public final Random random = new Random();
    public Pathfinding pathfinding = new Pathfinding();
    //eventually the object should NOT know where it is.
    public int x; // Center position coordinate.
    public int y; // Center position coordinate.

    public Bacillus() {
        this.x = random.nextInt(Constants.WIDTH); //defines a random location for the cell to appear.
        this.y = random.nextInt(Constants.HEIGHT); //defines a random location for the cell to appear.
    }

}
