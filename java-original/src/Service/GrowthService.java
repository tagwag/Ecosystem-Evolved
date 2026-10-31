package Service;

import Models.Cell;
import Request.GrowRequest;
import Result.GrowResult;

public class GrowthService {


    public GrowResult DoIGrow(final GrowRequest gr) {

        //eating food or eating a Cell?
        if (gr.prey == null) {
            //food
            return new GrowResult(gr.food.getSize(),true,null,gr.predator,gr.food, true);
        } else {
            //a Cell

            final Cell predator = gr.getPredator();
            final Cell prey = gr.getPrey();

            //tie?
            if (prey.size == predator.size) {
                return new GrowResult(0, false, prey, predator, null, false);
            }
            //win
            if (prey.size < predator.size) {
                predator.grow(prey.size);
                return new GrowResult(predator.size, true, prey, predator, null, false);
            } else {

                //lose
                prey.grow(predator.size);
                return new GrowResult(prey.size, false, predator, prey, null, false);

            }
        }
    }

}
