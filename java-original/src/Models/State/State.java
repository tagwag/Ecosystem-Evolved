package Models.State;

/**
 * For each state of being a cell or Foodbox can have.
 */
public class State {

    public boolean eating; //State of being.
    public boolean hungry; //State of being.
    public boolean young; //State of being.
    public boolean dead; //State of being.
    public boolean scared;
    public boolean attacking;
    public boolean fat;
    public boolean givingBirth;
    public boolean inFlock;
    public boolean bumping;
    public boolean moving;
    public boolean wormBody;
    public boolean desire2Flock;

    public boolean edible;
    public boolean eaten;
    public final boolean smol;

    public State(final Boolean cell) {

        if (cell) {

            this.eating = false;
            this.hungry = false;
            this.young = true;
            this.dead = false;
            this.scared = false;
            this.attacking = false;
            this.fat = false;
            this.givingBirth = false;
            this.inFlock = false;
            this.bumping = false;
            this.smol = false;
            this.moving = false;
            this.wormBody = false;
            this.desire2Flock = false;

        } else {

            this.edible = false;
            this.eaten = false;
            this.smol = false;

        }

    }

    public State(final Boolean cell, final boolean smol) {

        if (cell) {

            this.eating = false;
            this.hungry = false;
            this.young = true;
            this.dead = false;
            this.scared = false;
            this.attacking = false;
            this.fat = false;
            this.givingBirth = false;
            this.inFlock = false;
            this.bumping = false;
            this.smol = smol;

        } else {

            this.edible = false;
            this.eaten = false;
            this.smol = smol;

        }

    }

}
