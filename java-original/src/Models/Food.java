package Models;

import Enviroment.Coord;
import Models.State.State;
import Constants.Constants;
import Technical.IDGen;

import java.util.Objects;
import java.util.Random;

/**
 * Classified as the Block a 2x2 pattern
 */
public class Food {
    //food is classified as a group of inactive cells. Typically the 2x2 pattern

    public int x;
    public int y;
    public int id;
    public State state = new State(false);
    private int size;


    public Food(final IDGen idGen) {
        final Random random = new Random();

        //x = random.nextInt(680) + 20;
        //y = random.nextInt(500) + 20;
        this.size = new Constants().foodValue;
        this.x = random.nextInt(new Constants().WIDTH);
        this.y = random.nextInt(new Constants().HEIGHT);
        id = idGen.makeFoodID();
    }

    public Food(final IDGen idGen, final boolean smol) {
            final Random random = new Random();

            //x = random.nextInt(680) + 20;
            //y = random.nextInt(500) + 20;
        this.size = new Constants().foodValue;
        this.x = random.nextInt(new Constants().WIDTH);
        this.y = random.nextInt(new Constants().HEIGHT);
        id = idGen.makeFoodID();
        state = new State(false,true);
        }


    public Food(final int x, final int y) {
        this.x = x;
        this.y = y;
    }

    public Food() {
    }//default constructor

    public int getSize() {
        return this.size;
    }

    public void setSize(final int size) {
        this.size = size;
    }

    public int getX() {
        return this.x;
    }

    public void setX(final int x) {
        this.x = x;
    }

    public int getY() {
        return this.y;
    }

    public void setY(final int y) {
        this.y = y;
    }

    public int getId() {
        return this.id;
    }

    public boolean isEaten() {
        return state.eaten;
    }

    public boolean isEdible() {
        return state.edible;
    }

    public void wasAte() {

        state.eaten = true;

    }

    public void rotten() {

        state.edible = false;

    }

    /**
     * Makes a family at the coordinates (starting at center, offset by int x and int y).
     *
     * @return Family of cells. a Models.Cell array
     */
    public void makeFood() {
        final Random random = new Random();
        final int x = random.nextInt(680) + 20;
        final int y = random.nextInt(500) + 20;
    }

    @Override
    public int hashCode() {
        return Objects.hash(this.getSize(), this.getX(), this.getY());
    }

    /**
     * Makes a family at the coordinates (starting at center, offset by int x and int y).
     *
     * @return Family of cells. a Models.Cell array
     */
    public void makeFoodCenter() {
        final Random random = new Random();
        final int x = 140 + random.nextInt(10);
        final int y = 140 + random.nextInt(10);
    }

    public void updateValue(final int i) {
        size = i;
    }

    public Coord getCenter() {
        return new Coord(this.x, this.y);
    }

}
