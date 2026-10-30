package demo;

/** Small enough to read, real enough to fail when the demo is wired wrong. */
public final class Calc {
    private Calc() {}

    public static int add(int a, int b) {
        return a + b;
    }

    public static int divide(int a, int b) {
        if (b == 0) {
            throw new ArithmeticException("division by zero");
        }
        return a / b;
    }
}
