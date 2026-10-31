package Models.Mental;

import Enviroment.Vector2D;
import com.sun.javafx.geom.Vec2d;
import org.lwjgl.Sys;

import java.util.Stack;

public class Pathfinding {

    //turnRight(degrees) == 1
    //turnLeft(degrees) == 2
    //velocity(int accelerationChange) == 3
    //does not store it's location, or if it needs to, it is only stored for use by rendering,
    // and does not contribute to any other pert of the behavior
    public int velocity = 0; //CAN BE NEGATIVE
    public double direction = 0; //radians not sure I should store this, but it might be needed.
    //create a list/stack of the pathfinding algorithm that uses the functions below
    //add complexity for when an obstacle is found in it's path like food, junk/wall
    public Stack<Vector2D> searchPath = new Stack<>();
    public Stack<Vector2D> bumpPath = new Stack<>();
    public Stack<Vector2D> currentPathStack = new Stack<>();
    public Vector2D currentPath = new Vector2D(0,0);

    public int timepass = 0; // max 5
    // completed the obstacle algorithm

    public static Stack<Vector2D> generateAlgorithm(){
        Stack<Vector2D> movementVectors = new Stack<>();
        //first generate the length of the algorithm
        //generate the algorithm
        //scan the stack for 3 and then generate in a double in radians
        int max = 2;
        int min = 1;
        int range = max - min + 1;
        int negative = -1;

        // generate random numbers within 1 to 10
        for (int i = 1; i < randRange(1,1000); i++) {
            Vector2D current = new Vector2D(0,0);
            int rand = (int)(Math.random() * range) + min;
            if ( randRange(0,1) == 0) {
                negative = -1;
            } else {
                negative = 1;
            }

            if ( rand == 3) {
                //velocity change, determine new velocity
                /*
                int velocity = randRange(0,3);
                newPath.push('V' + new Integer(velocity).toString());
                //current.scalarMul(velocity);
                movementVectors.push(current);
                System.out.println("Vector value: " + current.value());

                 */
                //continue path for 5 tics?
                //System.out.println("Go straight");
                movementVectors.push(current);
            } else if (rand == 1) {

                //turn right, determine how many degrees
                //for now lets just set the the change to be 10 degrees

                //newPath.push('R' + "10");
                //int velocity = randRange(0,3);
                //newPath.push('V' + new Integer(velocity).toString());
                //current.scalarMul(velocity);
                //movementVectors.push(current);
                //System.out.println("Vector value: " + current.value());

                //add to x velocity

                float newXvec = current.f4x + (negative * randRange(0,3));

                if ( newXvec <= 3 && newXvec >= -3 ) {
                    current.f4x = newXvec;
                } //TODO: possibly make it so that any addition resulting in mor or less than +-3 just loops back around.
                System.out.println(current.toString());
                movementVectors.push(current);

            }
            else {
                float newYvec = current.f5y + (negative * randRange(0,3));

                if ( newYvec <= 3 && newYvec >= -3 ) {
                    current.f5y = newYvec;
                }
                //add to y velocity
                System.out.println(current.toString());
                movementVectors.push(current);

                //turn left, determine how many degrees
                //for now lets just set the the change to be 10 degrees
                //newPath.push('L' + "10");
            }
            //newPath.push(new Integer(randRange(min,range)).toString());
            // Output is different everytime this code is executed
        }
        return movementVectors;
    }

    public static int randRange(int low, int high) {
        int range = high - low + 1;
        return (int)(Math.random() * range) + low;
    }

    public Pathfinding() {
        this.searchPath = generateAlgorithm();
        this.bumpPath = generateAlgorithm();
    }

    public Vector2D detPath() {

        if (timepass == 30) {
            //next step in path
            try {
                if (this.currentPathStack.size() == 0) {
                    this.currentPathStack = (Stack<Vector2D>) this.searchPath.clone();
                    //this.currentPathStack = this.searchPath;
                    this.currentPath = this.currentPathStack.pop();

                } else {
                    this.currentPath = this.currentPathStack.pop();
                    //current bug, the referenace stack and search path will pop off at the same time.
                }
            } catch (Exception e) {
                System.out.println("Pathfinding STACK ERROR");
                System.out.println("currentPathStack Size = " + this.currentPathStack.size());
            }


        } else {
            timepass++;
        }


        return this.currentPath;
    }



    public static void main(String args[]) {
        Stack<Vector2D> temp = generateAlgorithm();
        /*
        for (int i = 0; i < temp.capacity() - 1; i++) {

            if (!temp.empty()) {
                String itr = temp.pop();
                if (itr.equals("3")) {
                    System.out.println("Found a 3");
                }
                System.out.println(itr);
            }

        }

         */


    }

}
