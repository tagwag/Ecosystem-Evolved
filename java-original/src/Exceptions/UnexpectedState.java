package Exceptions;

public class UnexpectedState extends Exception {

    public UnexpectedState() {
        super("Object found to be in unexpected state!");
    }
}
