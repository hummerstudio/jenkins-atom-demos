package demo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class CalcTest {

    @Test
    void adds() {
        assertEquals(5, Calc.add(2, 3));
    }

    @Test
    void divides() {
        assertEquals(3, Calc.divide(9, 3));
    }

    @Test
    void refusesToDivideByZero() {
        assertThrows(ArithmeticException.class, () -> Calc.divide(1, 0));
    }
}
