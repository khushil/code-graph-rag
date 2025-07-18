import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import static org.junit.jupiter.api.Assertions.*;

public class TestCalculator {
    private Calculator calculator;
    
    @BeforeEach
    void setUp() {
        calculator = new Calculator();
    }
    
    @AfterEach
    void tearDown() {
        calculator = null;
    }
    
    @Test
    @DisplayName("Test addition of positive numbers")
    void testAddPositiveNumbers() {
        assertEquals(4, calculator.add(2, 2));
        assertEquals(10, calculator.add(7, 3));
    }
    
    @Test
    @DisplayName("Test subtraction")
    void testSubtraction() {
        assertEquals(5, calculator.subtract(10, 5));
        assertEquals(-2, calculator.subtract(3, 5));
    }
    
    @Test
    void testMultiplication() {
        assertEquals(20, calculator.multiply(4, 5));
        assertEquals(0, calculator.multiply(100, 0));
    }
    
    @Test
    void testDivision() {
        assertEquals(2.0, calculator.divide(10, 5), 0.001);
        assertThrows(ArithmeticException.class, () -> calculator.divide(10, 0));
    }
}

// Another test class in same file
class CalculatorIntegrationTests {
    @Test
    void testComplexOperations() {
        Calculator calc = new Calculator();
        double result = calc.add(5, 3);
        result = calc.multiply(result, 2);
        assertEquals(16, result, 0.001);
    }
}