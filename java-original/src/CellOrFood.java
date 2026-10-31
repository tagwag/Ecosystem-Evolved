import Constants.Constants;
import Enviroment.Coord;
import Enviroment.Environment;
import Models.Body.Bacillus;
import Models.Cell;
import Models.Food;
import Models.Squid.Squid;
import Models.Squid.SquidLeg;
import Models.Squid.Tentacle;
import Models.Worm.Worm;
import Models.Worm.wormBody;
import Technical.IDGen;

import javax.swing.*;
import java.awt.*;
import java.awt.event.KeyEvent;
import java.awt.event.KeyListener;
import java.awt.image.BufferStrategy;
import java.awt.image.BufferedImage;
import java.awt.image.DataBufferInt;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Random;


public class CellOrFood extends Canvas implements Runnable {
    public static final int SCALE = 1;
    public static final String NAME = "Cell or Food";
    private static final long serialVersionUID = 1L;
    public final int WIDTH = Constants.WIDTH;
    public final int HEIGHT = Constants.HEIGHT;
    /*
        void paint(Graphics g) {...Graphics2D g2d = (Graphics2D) g;
            AffineTransform at1 = new AffineTransform();
            at1.translate(300 - 25, 400 - 20);
            at1.rotate(Math.PI / 180 * 30, 25, 20);
            g2d.drawImage(image, at1, null);...}
    */
    public final Image foodboxImage = new Constants().getFoodBox();
    public final Image wormBodyImage = new Constants().getWormbodyImage();
    public final Image wormHeadImage = new Constants().getWormHeadImage();
    public final Image wormTailImage = new Constants().getWormTailImage();
    public final Image squidLegImage = new Constants().getSquidLegImage();
    public final Image squidHeadImage = new Constants().getSquidHeadImage();
    public final Image squidGrabberImage = new Constants().getSquidGrabberImage();
    public final Image cellImage = new Constants().getCell();
    public final Image smolFoodboxImage = new Constants().getSmolFoodBoxImage();
    public final Image herbCarnImage = new Constants().getHerbCarn();
    public final Image herbImage = new Constants().getHerb();
    public final Image carnHerbImage = new Constants().getCarnHerb();
    public final Image carnImage = new Constants().getCarn();
    public final Image smolCellImage = new Constants().smolCellImage();
    public final Image BacillusImage = new Constants().getWormbodyImage();
    //private static final double FEATURE_SIZE = 24;
    private final JFrame frame;
    private final int time4 = 0;
    private final BufferedImage image = new BufferedImage(Constants.WIDTH, Constants.HEIGHT, BufferedImage.TYPE_INT_RGB);
    private final int[] cleanPixels = ((DataBufferInt) this.image.getRaster().getDataBuffer()).getData();
    private final int blinkCounter = 0;
    //private final MultiLayerNetwork network = NetworkUtil.getNetwork();
    public Constants constants = new Constants();
    //public static final int HEIGHT = 200;
    public boolean printer;
    public Random random = new Random();
    public boolean running;
    public int tickCount;
    public boolean[][] paint = new boolean[this.WIDTH][this.HEIGHT];
    public ArrayList<Coord> foodPainter = new ArrayList<>();
    public boolean score;
    //public GameState state = game.getGameState();
    public double epsilon = 0.9;
    public int ticks;
    public java.net.URL fb = getClass().getResource("images/FoodBox.png");
    int lives = 500;
    private int[] pixels = ((DataBufferInt) this.image.getRaster().getDataBuffer()).getData();
    private boolean completed;
    private Environment world;
    private IDGen idGen = new IDGen();
    private boolean cellState;
    private boolean foodVis;
    private BufferedImage test;
    //private ArrayList<CellImage> cellImages = new ArrayList<>();
    private int generations;
    private boolean fastForward;
    private int minCellCount = 2;
    private boolean aiOn;
    private boolean up;
    private boolean down;
    private boolean left;
    private boolean right;
    final KeyListener listener = new KeyListener() {
        @Override
        public void keyPressed(final KeyEvent event) {
            switch (event.getKeyCode()) {
                case KeyEvent.VK_SPACE:
                    //forcedEvolution();
                    CellOrFood.this.printCellState();
                    break;
                case KeyEvent.VK_DOWN:
                    CellOrFood.this.hideFood();
                    break;
                case KeyEvent.VK_RIGHT:
                    CellOrFood.this.moveTerrainUP();
                    break;
                case KeyEvent.VK_W:
                    CellOrFood.this.moveWormUP();
                    break;
                case KeyEvent.VK_A:
                    CellOrFood.this.moveWormLEFT();
                    break;
                case KeyEvent.VK_S:
                    CellOrFood.this.moveWormDOWN();
                    break;
                case KeyEvent.VK_D:
                    CellOrFood.this.moveWormRIGHT();
                    break;

            }
        }

        @Override
        public void keyReleased(final KeyEvent event) {
            //printEventInfo("Key Released", event);
        }

        @Override
        public void keyTyped(final KeyEvent event) {
            //printEventInfo("Key Typed", event);
        }
    };

    public CellOrFood() {


        this.setMinimumSize(new Dimension(this.WIDTH * CellOrFood.SCALE, this.HEIGHT * CellOrFood.SCALE));
        this.setMaximumSize(new Dimension(this.WIDTH * CellOrFood.SCALE, this.HEIGHT * CellOrFood.SCALE));
        this.setPreferredSize(new Dimension(this.WIDTH * CellOrFood.SCALE, this.HEIGHT * CellOrFood.SCALE));

        this.frame = new JFrame(CellOrFood.NAME);
        // frame.getContentPane().add(panel);
        //addKeyListener(this);
        //final JButton button2 = new JButton("Fast\nForward");


        //final JSlider b = new JSlider(0, 1000, 120);
        //b.setMajorTickSpacing(50);
        //b.setMinorTickSpacing(5);
        //b.setBounds(Constants.WIDTH / 2, Constants.HEIGHT - 50, 100, 10);

/*
        final JButton button = new JButton("Cell\nstate");
        final JButton button3 = new JButton("Terrain Up");
        final JButton button4 = new JButton("Terrain Down");
        final JButton button5 = new JButton("Terrain On/Off");
        final JButton button6 = new JButton("Kill All");
        final JButton button7 = new JButton("Start Over");

        button2.setBounds(0, 0, 103, 20);
        button.setBounds(103, 0, 103, 20);
        button4.setBounds(206, 0, 103, 20);
        button5.setBounds(309, 0, 103, 20);
        button3.setBounds(412, 0, 103, 20);
        button6.setBounds(515, 0, 103, 20);
        button7.setBounds(618, 0, 103, 20);

        button.setFont(new Font("Arial", Font.PLAIN, 10));
        button2.setFont(new Font("Arial", Font.PLAIN, 10));
        button3.setFont(new Font("Arial", Font.PLAIN, 10));
        button4.setFont(new Font("Arial", Font.PLAIN, 10));
        button5.setFont(new Font("Arial", Font.PLAIN, 10));
        button6.setFont(new Font("Arial", Font.PLAIN, 10));
        button7.setFont(new Font("Arial", Font.PLAIN, 10));

        final JButton Spawn = new JButton("Spawn");
        final JTextField textfield2 = new JTextField("", 10);
        textfield2.setFont(new Font("Arial", Font.PLAIN, 10));
        Spawn.setFont(new Font("Arial", Font.PLAIN, 10));

        textfield2.setBounds(0, 500, 80, 20);
        Spawn.setBounds(70, 500, 90, 20);

        final JButton feed = new JButton("Feed");
        final JTextField textfield1 = new JTextField("", 10);
        textfield1.setFont(new Font("Arial", Font.PLAIN, 10));
        feed.setFont(new Font("Arial", Font.PLAIN, 10));

        textfield1.setBounds(0, 520, 80, 20);
        feed.setBounds(70, 520, 90, 20);

        final JButton fV = new JButton("Food Value");
        final JTextField fVt = new JTextField("", 10);
        fVt.setFont(new Font("Arial", Font.PLAIN, 10));
        fV.setFont(new Font("Arial", Font.PLAIN, 8));

        fVt.setBounds(0, 480, 80, 20);
        fV.setBounds(70, 480, 90, 20);

        final JButton wipe = new JButton("Min Cell Count");
        final JTextField wiper = new JTextField("", 10);
        wiper.setFont(new Font("Arial", Font.PLAIN, 10));
        wipe.setFont(new Font("Arial", Font.PLAIN, 8));

        wiper.setBounds(0, 460, 80, 20);
        wipe.setBounds(70, 460, 90, 20);

        final JButton score_based = new JButton("Score Based");
        final JButton energy_based = new JButton("Energy Based");
        score_based.setFont(new Font("Arial", Font.PLAIN, 9));
        energy_based.setFont(new Font("Arial", Font.PLAIN, 9));
        score_based.setBounds(0, 440, 87, 20);
        energy_based.setBounds(72, 440, 87, 20);


        final JButton up = new JButton("up");
        up.setBounds(1920 - 80, 440, 80, 20);
        final JButton down = new JButton("down");
        down.setBounds(1920 - 80, 460, 80, 20);
        final JButton left = new JButton("left");
        left.setBounds(1920 - 80, 480, 80, 20);
        final JButton right = new JButton("right");
        right.setBounds(1920 - 80, 500, 80, 20);


        this.frame.add(button2);
        this.frame.add(button);
        this.frame.add(button3);
        this.frame.add(button4);
        this.frame.add(button5);
        this.frame.add(button6);
        this.frame.add(button7);
        this.frame.add(textfield1);
        this.frame.add(feed);
        this.frame.add(textfield2);
        this.frame.add(Spawn);
        this.frame.add(fV);
        this.frame.add(fVt);
        this.frame.add(wipe);
        this.frame.add(wiper);
        this.frame.add(score_based);
        this.frame.add(energy_based);
        this.frame.add(up);
        this.frame.add(down);
        this.frame.add(left);
        this.frame.add(right);


 */

        this.frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
        this.frame.setLayout(new BorderLayout());


        this.frame.add(this, BorderLayout.CENTER);
        this.frame.pack();

        //frame.addKeyListener(listener); //for User interaction!
        this.frame.setEnabled(true);

        this.frame.pack();
        this.frame.setResizable(true);
        this.frame.setLocationRelativeTo(null);
        this.frame.pack();

        this.setVisible(true);
        /*
        button2.addActionListener(arg0 -> this.fastForward());
        button.addActionListener(arg0 -> this.printCellState());
        button4.addActionListener(arg0 -> this.moveTerrainDOWN());
        button3.addActionListener(arg0 -> this.moveTerrainUP());
        button5.addActionListener(arg0 -> this.toggleTerrain());
        button6.addActionListener(arg0 -> this.killAll());
        button7.addActionListener(arg0 -> this.StartOver());

        up.addActionListener(arg0 -> this.moveWormUP());
        down.addActionListener(arg0 -> this.moveWormDOWN());
        left.addActionListener(arg0 -> this.moveWormLEFT());
        right.addActionListener(arg0 -> this.moveWormRIGHT());

        score_based.addActionListener(arg0 -> score = true);

        energy_based.addActionListener(arg0 -> score = false);


        Spawn.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(final ActionEvent arg0) {
                final String temp = textfield2.getText();
                final int temp1 = Integer.parseInt(temp);
                try {
                    CellOrFood.this.spawn(temp1);
                } catch (final Exception e) {
                    textfield2.setText("Invalid");
                }
            }
        });
        feed.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(final ActionEvent arg0) {
                final String temp = textfield1.getText();
                final int temp1 = Integer.parseInt(temp);
                try {
                    CellOrFood.this.feed(temp1);
                } catch (final Exception e) {
                    textfield1.setText("Invalid");
                }
            }
        });

        fV.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(final ActionEvent arg0) {
                final String temp = fVt.getText();
                final int temp1 = Integer.parseInt(temp);
                try {
                    CellOrFood.this.foodWeight(temp1);
                } catch (final Exception e) {
                    textfield1.setText("Invalid");
                }
            }
        });

        wipe.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(final ActionEvent arg0) {
                final String temp = wiper.getText();
                final int temp1 = Integer.parseInt(temp);
                try {
                    CellOrFood.this.minCellCount = temp1;
                } catch (final Exception e) {
                    wiper.setText("Invalid");
                }
            }
        });

         */
        this.frame.addKeyListener(this.listener);
        this.frame.setVisible(true);
        //setDefaultCloseOperation(EXIT_ON_CLOSE);

    }

    public static void main(final String[] args) {

        final CellOrFood scene = new CellOrFood();

        scene.world = new Environment(scene.idGen);
        scene.start();

    }

    private void moveWormRIGHT() {
        System.out.println("RIGHT");

        this.right = !this.right;
        if (this.left) {
            this.left = false;
        }
    }

    private void moveWormDOWN() {
        System.out.println("DOWN");
        this.down = !this.down;
        if (this.up) {
            this.up = false;
        }
    }

    private void moveWormLEFT() {
        System.out.println("LEFT");

        this.left = !this.left;
        if (this.right) {
            this.right = false;
        }
    }

    private void moveWormUP() {
        System.out.println("UP");

        this.up = !this.up;
        if (this.down) {
            this.down = false;
        }
    }

/*
        if (this.world.getCellList().size() <= 50 && this.world.firstGen) {
            this.generations++;
            System.out.println("Generation #" + generations + " has started!");
            this.world.nextGen();
            this.world.evolveFirstGen(this.idGen);
        }

 */

    public void spawn(int i) {
        if (i > 1000) {
            i = 1000;
        }
        if (world.CellList.size() < 1000) {
            for (int x = 0; x < i; x++) {
                world.addCell(new Cell(idGen, this.random.nextInt(20), 2,
                        this.random.nextInt(100), this.random.nextInt(100), this.random.nextInt(4),
                        this.random.nextInt(3), Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(),
                        this.random.nextInt(10), this.random.nextInt(1000), 0, this.random.nextInt(100)));
                world.addCell(new Cell(this.idGen, true, this.random.nextInt(20), 2,
                        this.random.nextInt(100), this.random.nextInt(500), this.random.nextInt(4), this.random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), this.random.nextInt(10),
                        this.random.nextInt(1000), 0, this.random.nextInt(100)));
            }
        }
        if (world.bacillusArrayList.size() < 1000) {
            for (int x = 0; x < 1000; x++) {
                world.addBacillus(new Bacillus());
            }
        }

    }

    public void feed(int i) {
        if (i > 2000) {
            i = 2000;
        }
        for (int x = 0; x < i; x++) {
            world.addFood(new Food(idGen));
        }

    }

    public void StartOver() {
        frame.dispose();
        stop();
        CellOrFood.main(new String[0]);
    }

    public void moveTerrainUP() {
        //System.out.println("Terrain Moved UP");
        world.changeTerrain(4);
    }

    public void moveTerrainDOWN() {
        //System.out.println("Terrain Moved DOWN");
        world.changeTerrain(-4);
    }

    public void toggleTerrain() {
        if (!world.terrainON) {
            world.toggleterrain();
        } else {
            world.toggleterrain();
            pixels = ((DataBufferInt) this.image.getRaster().getDataBuffer()).getData();
        }
    }

    public void killAll() {
        world.killAll();
    }

    private void setUp() {
        if (!completed) {
            //cleanPixels.fill(3,4);
            for (int x = 0; x < this.cleanPixels.length; x++) {
                this.cleanPixels[x] = Color.BLACK.getRGB();
            }
            completed = true;
            for (int j = 0; j < Constants.cellSpawnAmount; j++) {
                final Cell temp = new Cell(idGen, this.random.nextInt(20), 2,
                        this.random.nextInt(100), this.random.nextInt(500), this.random.nextInt(4), this.random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), this.random.nextInt(10),
                        this.random.nextInt(1000), 0, this.random.nextInt(100));
                temp.x = this.random.nextInt(Constants.WIDTH);
                temp.y = this.random.nextInt(Constants.HEIGHT);
                world.addCell(temp);
                final Cell temp2 = new Cell(this.idGen, true, this.random.nextInt(20), 2,
                        this.random.nextInt(100), this.random.nextInt(500), this.random.nextInt(4), this.random.nextInt(3),
                        Arrays.stream(new Cell().setPriorities()).mapToInt(Integer::intValue).toArray(), this.random.nextInt(10),
                        this.random.nextInt(1000), 0, this.random.nextInt(100));
                temp2.x = this.random.nextInt(Constants.WIDTH);
                temp2.y = this.random.nextInt(Constants.HEIGHT);
                world.addCell(temp2);

            }

            if (world.bacillusArrayList.size() < 10000) {
                for (int x = 0; x < 10000; x++) {
                    world.addBacillus(new Bacillus());
                }
            }

            for (int x = 0; x < Constants.wormSpawnAmount; x++) {
                world.addWorm(new Worm(20 - this.random.nextInt(15), idGen));
            }

            for (int x = 0; x < Constants.squidSpawnAmount; x++) {
                //world.addSquid(new Squid(random.nextInt(5) + 2, 7, this.idGen));
            }
            for (int j = 0; j < Constants.foodBoxSpawnAmount; j++) {
                world.addFood(new Food(idGen));
                world.addFood(new Food(this.idGen, true));
            }
            long startTime = System.currentTimeMillis();


        }
    }

    public synchronized void start() {
        this.running = true;
        new Thread(this).start();
    }

    public synchronized void stop() {
        this.running = false;
    }

    public void run() {
        this.setUp();
        long lastTime = System.nanoTime();
        final double nsPerTick = 1000000000D / 60D;

        //int ticks = 0;

        final long lastTimer = System.currentTimeMillis();
        double delta = 0;
        int lastX = 0;
        int lastY = 0;
        int stillCounter = 0;
        int gameCounter = 0;
        this.ticks = 0;
        while (this.running) {
            final long now = System.nanoTime();
            delta += (now - lastTime) / nsPerTick;
            lastTime = now;
            boolean shouldRender = true;


            //if (this.aiOn) {
                /*
                if (world.isAIDead()) {
                    gameCounter++;
                    System.out.println("Game #" + gameCounter + " score: " + world.aiScore);
                    world.aiScore = 0;
                    //saveNetwork(network);
                }

                if (lastX == world.ai.x) {
                    if (lastY == world.ai.y) {
                        stillCounter++;
                        world.aiScore--;
                        if (stillCounter == 50) {
                            //System.out.println("Stuck! Killing");
                            this.killAll();
                            stillCounter = 0;
                        }
                    } else {
                        stillCounter = 0;
                    }
                } else {
                    stillCounter = 0;
                }

                //lastPosition = this.world.ai.getCenter();
                lastX = world.ai.x;
                lastY = world.ai.y;
            }

                 */
            while (delta >= 1) {
                this.ticks++;
                try {
                    this.tick();
                } catch (final Exception e) {
                    System.out.println("Tick failed " + e);
                }
                delta -= 1;
                shouldRender = true;
            }
            /*
            try {
                Thread.sleep(1); // half a second?
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            */
            if (shouldRender) {
                this.render();
            }
/*
            if (System.currentTimeMillis() - lastTimer > 1000) {
                lastTimer += 1000;
                if (ticks < 10) {
                    System.out.println("Cancer has formed, purging. Cell count: " + this.world.CellList.size() + " Generation #" + this.generations);
                    try {
                        Thread.sleep(100000);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                        StartOver();
                    }
                    StartOver();
                }
                //System.out.println(ticks + "ticks");
                ticks = 0;
            }

 */
        }
    }

    public int getPosition(final int x, final int y) {
        int sum = y * this.WIDTH;
        sum += x;
        return sum;
    }

    public void foodWeight(final int i) {
        try {
            for (final Food food : world.getFoodList()) {
                food.updateValue(i);
            }
        } catch (final Exception e) {
            //something happened
        }
    }

    public void ChangeMinCellCount(final int i) {

        try {
            minCellCount = i;
        } catch (final Exception e) {
            //something happened
        }

    }

    /**
     * Calculates the newly refreshed screen as well as the next.
     */
    public void tick() {
        this.tickCount++;
        try {

            //this.world.player.move(0, 1);

            if (this.up) {
                world.player.tentacles.get(0).moveGrabber(0, 1);
            }
            if (this.down) {
                world.player.tentacles.get(0).moveGrabber(0, -1);
            }
            if (this.left) {
                world.player.tentacles.get(0).moveGrabber(-1, 0);
            }
            if (this.right) {
                world.player.tentacles.get(0).moveGrabber(1, 0);
            }


            //if (!this.fastForward) {
//
            //}


            //paint obstacles only once unless they are changed.
            if (world.obstacles.enabled) {
                if (world.obstacles.changed) {

                    int f = 0;
                    for (int y = 0; y < Constants.HEIGHT; y++) {

                        for (int x = 0; x < Constants.WIDTH; x++) {

                            if (world.obstacles.location[x][y]) {
                                this.pixels[f] = Color.WHITE.getRGB();
                                //this.paint[x][y] = true; // dont paint over obstacles
                            } else {
                                this.pixels[f] = Color.BLACK.getRGB();
                            }
                            f++;
                        }

                    }
                    world.obstacles.changed = false;
                }
            } else {
                for (int x = 0; x < this.pixels.length; x++) {
                    this.pixels[x] = Color.BLACK.getRGB();
                }
                //pixels = cleanPixels;
            }
/*
            int f = 0;
            for (int y = 0; y < HEIGHT; y++) {

                for (int x = 0; x < WIDTH; x++) {

                    if (!paint[x][y]) {
                        pixels[f] = Color.BLACK.getRGB();
                    }
                    f++;
                }

            }
*/

        } catch (final Exception e) {
            System.out.println("CellOrFood.java" + e);
        }


        //if (tickCount % 300 == 0)

        try {
            world.updateIDGEN(idGen);
            //this.world.update();
            world.passTime();
            idGen = world.getIDGen();
        } catch (final Exception e) {
            System.out.println("Failed passing time " + e);
        }

        if (world.getCellList().size() <= minCellCount) {
            generations++;
            System.out.println("Generation #" + this.generations + " has started!");
            world.nextGen();
            world.evolve(idGen, score);
        }


        if (world.getFoodList().size() < 300) {
            for (int j = world.getFoodList().size(); j < this.random.nextInt(200); j++) {
                world.addFood(new Food(idGen));
                world.addFood(new Food(idGen, true));
            }
        }
        //System.out.println(ticks);
        if (world.getCellList().size() >= 3000) {
            this.StartOver();
        }

        /*
        if (this.world.getCellList().size() < this.minCellCount) {
            this.generations++;
            System.out.println("Generation #" + generations + " has started!");
            this.world.nextGen();
            this.world.evolve(this.idGen, this.score);
        }

         */

    }

    public void setScore() {
        score = !this.score;
    }

    public void render() {
        final BufferStrategy bs = this.getBufferStrategy();
        if (bs == null) {
            this.createBufferStrategy(3);
            return;
        }

        final Graphics g = bs.getDrawGraphics();
        final Dimension screenSize = Toolkit.getDefaultToolkit().getScreenSize();
        final int frameWidth = this.frame.getWidth();
        final int frameHeight = this.frame.getHeight();

        int scalarX;
        int scalarY;
        scalarX = 1;
        scalarY = 1;

        g.setColor(Color.BLACK);
        g.fillRect(0, 0, this.getWidth(), this.getHeight());
        g.drawImage(Constants.getBackgroundImage(), 0, 0, Constants.WIDTH * scalarX, Constants.HEIGHT * scalarY, null);
        g.drawImage(this.image, 0, 0, this.getWidth() * scalarX, this.getHeight() * scalarY, null);

        if (false) {
            try {
                for (Tentacle tent : this.world.player.tentacles) {
                    for (SquidLeg leg : tent.segment) {
                        if (!leg.grabber) {
                            g.drawImage(squidLegImage, leg.x - 1, leg.y - 3, constants.Cell_SIZE, constants.Cell_SIZE, null);
                        } else {
                            g.drawImage(squidGrabberImage, leg.x - 1, leg.y - 3, constants.Cell_SIZE + 5, constants.Cell_SIZE + 5, null);
                        }
                    }
                }
                g.drawImage(squidHeadImage, this.world.player.head.x - 1, this.world.player.head.y - 3, constants.Cell_SIZE + 5, constants.Cell_SIZE + 5, null);
            } catch (Exception e) {
                System.out.println("Error Rendering Player: " + e.toString());
            }
        }

        try {
            for (final Squid squid : world.squidArrayList) {
                for (final Tentacle tent : squid.tentacles) {
                    for (final SquidLeg leg : tent.segment) {
                        if (!leg.grabber) {
                            g.drawImage(squidLegImage, leg.x - 1, leg.y - 3, Constants.Cell_SIZE - 2, Constants.Cell_SIZE - 2, null);
                        } else {
                            g.drawImage(squidGrabberImage, leg.x - 1, leg.y - 3, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                        }
                    }
                }
                g.drawImage(squidHeadImage, squid.head.x - 1, squid.head.y - 3, Constants.Cell_SIZE + 3, Constants.Cell_SIZE + 3, null);
            }
        } catch (final Exception e) {

            System.out.println("Error Rendering Squid: " + e.getMessage());
        }

        try {
            for (final Worm worm : world.wormList) {
                if (!worm.state.dead) {

                    for (final wormBody body : worm.wormBodies) {
                        if (body.age < 100) {
                            g.drawImage(wormTailImage, body.x - 1, body.y - 3, Constants.Cell_SIZE - 2, Constants.Cell_SIZE - 2, null);
                        } else {
                            g.drawImage(wormBodyImage, body.x - 1, body.y - 3, Constants.Cell_SIZE - 2, Constants.Cell_SIZE - 2, null);
                        }
                    }
                    g.drawImage(wormHeadImage, worm.head.x - 1, worm.head.y - 3, Constants.Cell_SIZE - 1, Constants.Cell_SIZE - 1, null);

                }
            }
        } catch (final Exception e) {
            System.out.println("Error Rendering Worm: " + e.toString());
        }


        try {
            for (final Food food : world.getFoodList()) {
                if (!food.isEaten()) {
                    if (food.state.smol) {
                        g.drawImage(smolFoodboxImage, food.x - 1, food.y - 3, Constants.smol_FOOD_SIZE, Constants.smol_FOOD_SIZE, null);
                    } else {
                        g.drawImage(foodboxImage, food.x * scalarX - 1, food.y * scalarY - 3, Constants.FOOD_SIZE * scalarX, Constants.FOOD_SIZE * scalarY, null);
                    }
                }
            }
        } catch (final Exception e) {
            //error occurs when new foodboxs are added mid thread
        }
        try {
            for (final Cell cell : world.getCellList()) {

                if ((cell.size / Constants.sizeThreshold) > 1) {
                    scalarX = (int) (cell.size / 300);
                }
                if (cell.age > 1 && cell.speed < 25) {
                    final Graphics d = bs.getDrawGraphics();
                    if (cell.type == 3) {
                        g.drawImage(wormBodyImage, cell.x - 4, cell.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                    } else if (cell.state.smol) {
                        g.drawImage(smolCellImage, cell.x - 4, cell.y - 6, Constants.smol_Cell_SIZE, Constants.smol_Cell_SIZE, null);
                    } else if (cell.type == 1) {
                        g.drawImage(cellImage, cell.x - 4, cell.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                    } else if (cell.diet == 0) {
                        g.drawImage(carnImage, cell.x - 4, cell.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                    } else if (cell.diet == 1) {
                        g.drawImage(carnHerbImage, cell.x - 4, cell.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                    } else if (cell.diet == 2) {
                        g.drawImage(herbCarnImage, cell.x - 4, cell.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                    } else if (cell.diet == 3) {
                        g.drawImage(herbImage, cell.x - 4, cell.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                    }
                }
                if (this.cellState) {
                    System.out.println("Cell #" + cell.getID() + " Sight: " + cell.sight + " Size: " + cell.size + " Energy: " + cell.energy + " Split Requirement: " + cell.splitRequirement + " Speed: " + cell.movementSpeed + " Location: ( " + cell.x + ", " + cell.y + ")");
                }
            }
        } catch (final Exception e) {
            //error occurs when new cells are added mid thread
        }

        try {
            for (final Bacillus bacillus : world.getBacillusList()) {

                final Graphics d = bs.getDrawGraphics();
                g.drawImage(wormBodyImage, bacillus.x - 4, bacillus.y - 6, Constants.Cell_SIZE, Constants.Cell_SIZE, null);
                //System.out.println("Rendered Baccilus at " + bacillus.x + " " + bacillus.y);

            }
        } catch (final Exception e) {
            //error occurs when new cells are added mid thread
            System.out.println("Cannot render Bacillus");
        }


        g.dispose();
        bs.show();
    }













    /*
    @Override
    public void actionPerformed(ActionEvent e) {
        if (running) {
            if (this.world.ai.isFoodEaten()) {
                // Increase player length
                this.world.cellScore++;

                // Set food on a new position
                //setFoodPosition();
            } else {
                //final Position headPosition = snakePosition[0];
                //inGame = !headPosition.isOutsideTheGameBounds();
                //final Position headPosition = new Position(new Coord(this.world.ai.x,this.world.ai.y));
                if (this.world.isAIDead()) { // We only need to check for body part collision if we are still in the game
                    //checkIfPlayerHeadIsCollidingWithOtherBodyParts(headPosition);
                    this.lives--;
                }
            }
        }


        if (!inGame) {
            LOG.debug("Game is over :(");
        }



        repaint();
    }
    */

    public void printTrue() {
        printer = !printer;
    }

    public void printCellState() {
        cellState = !cellState;
    }

    public void hideFood() {
        foodVis = !foodVis;
    }

    private void forcedEvolution() {
        world.nextGen();
        world.evolve(idGen, this.score);
    }

    public void fastForward() {
        fastForward = !fastForward;
    }
}

