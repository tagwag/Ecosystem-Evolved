package Request;

public class InteractionRequest {

    final int type; //1 == eating a cell, 2 == eating food, 3 == reproducing, 4 == splitting
    private final int x;
    private final int y;


    public InteractionRequest(final int type, final int x, final int y) {
        this.type = type;
        this.x = x;
        this.y = y;
    }

    public int getType() {
        return this.type;
    }

    public int getX() {
        return this.x;
    }

    public int getY() {
        return this.y;
    }
}
