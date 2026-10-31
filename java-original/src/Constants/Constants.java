package Constants;

import javax.imageio.ImageIO;
import javax.swing.*;
import java.awt.*;
import java.io.IOException;

public final class Constants {


    public static final int WIDTH = 1920;
    public static final int HEIGHT = 1080;
    //public static final int WIDTH = 300;
    //public static final int HEIGHT = 300;
    //public static final int WIDTH = 720;
    //public static final int HEIGHT = 540;

    public static final int Cell_SIZE = 5;
    public static final int smol_Cell_SIZE = 2;
    public static final int FOOD_SIZE = 4;
    public static final int smol_FOOD_SIZE = 1;
    public static final int sizeThreshold = 400;
    public static final int foodValue = 150;
    public static final int squidSpawnAmount = 10;
    public static final int wormSpawnAmount = 20;
    public static final int cellSpawnAmount = 500;
    public static final int foodBoxSpawnAmount = 1000;


    public Constants() {
    }

    public static Image getFoodImage() {
        return new ImageIcon("resources/images/FoodBox.png").getImage();
    }

    public static Image getCellImage() {
        return new ImageIcon("resources/images/Cell.png").getImage();
    }

    public static Image getSmolCellImage() {
        return new ImageIcon("resources/images/smolCell.png").getImage();
    }

    public static Image getSmolFoodImage() {
        return new ImageIcon("resources/images/smolFruit.png").getImage();
    }

    public static Image getCellCarnImage() {
        return new ImageIcon("resources/images/CellCarn.png").getImage();
    }

    public static Image getCellHerbImage() {
        return new ImageIcon("resources/images/Herb.png").getImage();
    }

    public static Image getCellCarnHerbImage() {
        return new ImageIcon("resources/images/CellCarnHerb.png").getImage();
    }

    public static Image getCellHerbCarnImage() {
        return new ImageIcon("resources/images/HerbCarn.png").getImage();
    }

    public static Image getCellTwo() {
        return new ImageIcon("resources/images/newCell.png").getImage();
    }

    public static Image getHeliozoa() {
        return new ImageIcon("resources/images/Heliozoa.png").getImage();
    }

    public static Image getSpiderCell() {
        return new ImageIcon("resources/images/SpiderCell.png").getImage();
    }

    public static Image getSpiralCell() {
        return new ImageIcon("resources/images/SpiralCell.png").getImage();
    }

    public static Image getTargetImage() {
        return new ImageIcon("resources/images/target.png").getImage();
    }

    public static Image getBackgroundImage() {
        return new ImageIcon("resources/images/Background.png").getImage();
    }

    public static Image getFlockImage() {
        return new ImageIcon("resources/images/flockId.png").getImage();
    }

    public static Image getWormBody() {
        return new ImageIcon("resources/images/WormBody.png").getImage();
    }

    public static Image getWormHead() {
        return new ImageIcon("resources/images/wormHead.png").getImage();
    }

    public static Image getWormTail() {
        return new ImageIcon("resources/images/wormTail.png").getImage();
    }

    public static Image getSquidLeg() {
        return new ImageIcon("resources/images/squidLeg.png").getImage();
    }

    public static Image getSquidHead() {
        return new ImageIcon("resources/images/squidHead.png").getImage();
    }

    public static Image getGrabber() {
        return new ImageIcon("resources/images/Grabber.png").getImage();
    }

    public Image getFoodBox() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/FoodBox.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getWormbodyImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/WormBody.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getWormHeadImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/wormHead.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getCell() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/Cell.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getSmolFoodBoxImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/smolFruit.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getHerbCarn() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/herbcarn.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getHerb() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/herb.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getCarnHerb() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/CellCarnHerb.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }


    public Image getCarn() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/CellCarn.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getWormTailImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/wormTail.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image smolCellImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/smolCell.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getSquidLegImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/squidLeg.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getSquidHeadImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/squidHead.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public Image getSquidGrabberImage() {
        try {
            return ImageIO.read(getClass().getResourceAsStream("/images/Grabber.png"));
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }
}
