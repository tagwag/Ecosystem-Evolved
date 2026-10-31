package Result;

import Models.Cell;
import Models.Food;

public class GrowResult {
    private double growthFactor;
    private boolean success;
    private String result;
    public boolean nothingHappened;

    public GrowResult(final double growthFactor, boolean success, final Cell dead, final Cell alive, final Food eaten, final boolean ateFood) {
        Cell alive1;
        if (ateFood) {
            this.growthFactor = growthFactor;
            alive1 = alive;
            success = true;
        }
        Cell dead1;
        if (success) {
            dead1 = dead;
            alive1 = alive;
            this.success = true;
            //this.result = "Models.Cell " + alive.getID() + " has grown by " + growthFactor + "!";
            //System.out.println(this.result);
        } else {

            if (growthFactor == 0) {
                //tie!
                this.success = false;
                //this.result = "Nothing happened.";
                //System.out.println(this.result);

            } else {

                dead1 = dead;
                alive1 = alive;
                this.success = false;
                result = "Models.Cell " + dead.getID() + " was too small! It lost and was eaten.";
                //System.out.println(this.result);
                //System.out.println("Models.Cell " + alive.getID() + " has grown by " + growthFactor + "!");

            }
        }
    }


    public double getGrowthFactor() {
        return this.growthFactor;
    }

    public void setGrowthFactor(final int growthFactor) {
        this.growthFactor = growthFactor;
    }

    public boolean isSuccess() {
        return this.success;
    }

    public void setSuccess(final boolean success) {
        this.success = success;
    }

    public String getResult() {
        return this.result;
    }

    public void setResult(final String result) {
        this.result = result;
    }
}
