// Rust test example with various test patterns

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_positive_numbers() {
        let calc = Calculator::new();
        assert_eq!(calc.add(2, 2), 4);
        assert_eq!(calc.add(10, 5), 15);
    }

    #[test]
    fn test_subtract() {
        let calc = Calculator::new();
        assert_eq!(calc.subtract(10, 5), 5);
        assert_eq!(calc.subtract(0, 5), -5);
    }

    #[test]
    #[should_panic(expected = "attempt to divide by zero")]
    fn test_divide_by_zero() {
        let calc = Calculator::new();
        calc.divide(10, 0);
    }

    #[test]
    #[ignore]
    fn test_expensive_operation() {
        // This test is ignored by default
        let calc = Calculator::new();
        let result = calc.factorial(20);
        assert!(result > 0);
    }
}

#[cfg(test)]
mod integration_tests {
    use super::*;

    #[test]
    fn test_calculator_chain_operations() {
        let mut calc = Calculator::new();
        calc.set_value(10);
        calc.add_to_value(5);
        calc.multiply_value(2);
        assert_eq!(calc.get_value(), 30);
    }
}

// Test function outside of module
#[test]
fn standalone_test_function() {
    assert!(true);
}
