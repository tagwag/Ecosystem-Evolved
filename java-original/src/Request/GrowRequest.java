package Request;

import Models.Cell;
import Models.Food;

public class GrowRequest {

    public Cell predator;
    public Cell prey;
    public final Food food;

    public GrowRequest(final Cell predator, final Cell prey, final Food food) {
        this.predator = predator;
        this.prey = prey;
        this.food = food;
    }

    public Cell getPredator() {
        return this.predator;
    }

    public void setPredator(final Cell predator) {
        this.predator = predator;
    }

    public Cell getPrey() {
        return this.prey;
    }

    public void setPrey(final Cell prey) {
        this.prey = prey;
    }
}
