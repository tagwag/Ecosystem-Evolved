package Enviroment;

public class Vector2D {
    public float f4x;
    public float f5y;

    public Vector2D(float a, float b) {
        this.f4x = a;
        this.f5y = b;
    }

    public Vector2D(Vector2D v) {
        this.f4x = v.f4x;
        this.f5y = v.f5y;
    }

    public void set(float a, float b) {
        this.f4x = a;
        this.f5y = b;
    }

    public float value() {
        return (float) Math.sqrt((double) ((this.f4x * this.f4x) + (this.f5y * this.f5y)));
    }

    public void add(Vector2D v) {
        this.f4x += v.f4x;
        this.f5y += v.f5y;
    }

    public Vector2D getAdd(Vector2D v) { // use this for movement
        return new Vector2D(this.f4x + v.f4x, this.f5y + v.f5y);
    }

    public void sub(Vector2D v) {
        this.f4x -= v.f4x;
        this.f5y -= v.f5y;
    }

    public Vector2D getSub(Vector2D v) {
        return new Vector2D(this.f4x - v.f4x, this.f5y - v.f5y);
    }

    public void scalarMul(float d) { // use this for acceleration
        this.f4x *= d;
        this.f5y *= d;
    }

    public Vector2D getScalarMul(float d) {
        return new Vector2D(this.f4x * d, this.f5y * d);
    }

    public Vector2D getUnit() {
        float d = value();
        return new Vector2D(this.f4x / d, this.f5y / d);
    }

    public void setUnit() {
        float d = value();
        this.f4x /= d;
        this.f5y /= d;
    }

    public float dotProduct(Vector2D v) {
        return (this.f4x * v.f4x) + (this.f5y * v.f5y);
    }

    public Vector2D getNormal() {
        return new Vector2D(this.f5y, -this.f4x);
    }

    @Override
    public String toString() {
        return "Vector2D{" +
                "x=" + f4x +
                ", y=" + f5y +
                '}';
    }
}
