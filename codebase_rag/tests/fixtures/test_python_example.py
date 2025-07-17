import unittest

import pytest


# Example production code to test
def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

class Calculator:
    """Simple calculator class."""

    def __init__(self):
        self.history = []

    def calculate(self, operation, a, b):
        if operation == "add":
            result = a + b
        elif operation == "multiply":
            result = a * b
        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.history.append((operation, a, b, result))
        return result


# Pytest style tests
def test_add_positive_numbers():
    """Test addition of positive numbers."""
    assert add(2, 3) == 5
    assert add(10, 20) == 30

def test_add_negative_numbers():
    """Test addition with negative numbers."""
    assert add(-1, 1) == 0
    assert add(-5, -3) == -8

@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 6),
    (0, 5, 0),
    (-2, 3, -6),
])
def test_multiply_parametrized(a, b, expected):
    """Test multiplication with various inputs."""
    assert multiply(a, b) == expected

@pytest.fixture
def calculator():
    """Fixture to create a calculator instance."""
    return Calculator()

def test_calculator_add(calculator):
    """Test calculator addition."""
    result = calculator.calculate("add", 5, 3)
    assert result == 8
    assert len(calculator.history) == 1


# Unittest style tests
class TestCalculatorUnittest(unittest.TestCase):
    """Test calculator using unittest framework."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = Calculator()

    def test_calculate_addition(self):
        """Test addition operation."""
        result = self.calculator.calculate("add", 10, 5)
        self.assertEqual(result, 15)
        self.assertEqual(len(self.calculator.history), 1)

    def test_calculate_multiplication(self):
        """Test multiplication operation."""
        result = self.calculator.calculate("multiply", 4, 7)
        self.assertEqual(result, 28)

    def test_invalid_operation(self):
        """Test invalid operation raises error."""
        with self.assertRaises(ValueError):
            self.calculator.calculate("divide", 10, 2)

    def tearDown(self):
        """Clean up after tests."""
        self.calculator = None


if __name__ == "__main__":
    unittest.main()
