package Request;

import Enviroment.Environment;
import Map.SectorMap;
import Models.Cell;
import Models.Squid.Squid;
import Models.Squid.Tentacle;
import Models.Worm.Worm;

/**
 *
 */
public class SightRequest {

    private Cell theCell;
    private Worm theWorm;
    private Environment theEnvironment;
    private SectorMap theSectorMap;

    private int x;
    private int y;
    private int viewingDistance;
    private Squid theSquid;
    private Tentacle theTentacle;

    /**
     * A Cell's request to see.
     *
     * @param theCell
     * @param theEnvironment
     */
    public SightRequest(final Cell theCell, final Environment theEnvironment, final SectorMap sectorMap) {
        this.theCell = theCell;
        this.theEnvironment = theEnvironment;
        theSectorMap = sectorMap;
    }

    /**
     * A Cell's request to see.
     *
     * @param x
     * @param y
     * @param viewingDistance
     */
    public SightRequest(final int x, final int y, final int viewingDistance) {
        this.x = x;
        this.y = y;
        this.viewingDistance = viewingDistance;
    }

    public SightRequest(final int x, final int y, final int viewingDistance, final Cell cell) {
        this.x = x;
        this.y = y;
        this.viewingDistance = viewingDistance;
        theCell = cell;
    }

    public SightRequest(final int x, final int y, final int viewingDistance, final Worm worm) {
        this.x = x;
        this.y = y;
        this.viewingDistance = viewingDistance;
        theWorm = worm;
    }

    public SightRequest(final int x, final int y, final int viewingDistance, final Squid Squid) {
        this.x = x;
        this.y = y;
        this.viewingDistance = viewingDistance;
        theSquid = Squid;
    }

    public SightRequest(final int x, final int y, final int viewingDistance, final Tentacle tentacle) {
        this.x = x;
        this.y = y;
        this.viewingDistance = viewingDistance;
        theTentacle = tentacle;
    }

    public int getX() {
        return this.x;
    }

    public int getY() {
        return this.y;
    }

    public int getViewingDistance() {
        return this.viewingDistance;
    }

    public Cell getTheCell() {
        return this.theCell;
    }

    public Environment getTheEnvironment() {
        return this.theEnvironment;
    }

    public SectorMap getTheSectorMap() {
        return this.theSectorMap;
    }

    public Worm getTheWorm() {
        return this.theWorm;
    }

    public Squid getTheSquid() {
        return this.theSquid;
    }

    public Tentacle getTheTentacle() {
        return this.theTentacle;
    }
}
