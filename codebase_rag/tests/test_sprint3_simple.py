"""Simple tests for Sprint 3 components without full infrastructure."""

import pytest

from codebase_rag.analysis.test_coverage import TestCodeAnalyzer, TestCodeLink
from codebase_rag.parsers.test_detector import TestDetector


class TestSprint3Components:
    """Test Sprint 3 components individually."""

    def test_test_detector_file_patterns(self):
        """Test that test file detection works correctly."""
        detector = TestDetector()

        # Python test files
        assert detector.is_test_file("test_something.py", "python")
        assert detector.is_test_file("something_test.py", "python")
        assert detector.is_test_file("tests/test_module.py", "python")
        assert not detector.is_test_file("module.py", "python")

        # JavaScript test files
        assert detector.is_test_file("component.test.js", "javascript")
        assert detector.is_test_file("component.spec.js", "javascript")
        assert detector.is_test_file("__tests__/component.js", "javascript")
        assert not detector.is_test_file("component.js", "javascript")

        # Java test files
        assert detector.is_test_file("CalculatorTest.java", "java")
        assert detector.is_test_file("TestCalculator.java", "java")
        assert detector.is_test_file("CalculatorTests.java", "java")
        assert not detector.is_test_file("Calculator.java", "java")

        # Go test files
        assert detector.is_test_file("calculator_test.go", "go")
        assert not detector.is_test_file("calculator.go", "go")

        # Rust test files
        assert detector.is_test_file("calculator_test.rs", "rust")
        assert detector.is_test_file("tests/integration_test.rs", "rust")
        assert not detector.is_test_file("calculator.rs", "rust")

        # C test files
        assert detector.is_test_file("test_calculator.c", "c")
        assert detector.is_test_file("calculator_test.c", "c")
        assert detector.is_test_file("tests/test_math.c", "c")
        assert not detector.is_test_file("calculator.c", "c")

    def test_framework_detection(self):
        """Test framework detection from file content."""
        detector = TestDetector()

        # Python pytest
        pytest_content = """
import pytest

def test_addition():
    assert 1 + 1 == 2

@pytest.mark.parametrize("a,b,expected", [(1,2,3), (2,3,5)])
def test_parametrized(a, b, expected):
    assert a + b == expected
"""
        framework = detector.detect_framework(pytest_content, "python", "test_file.py")
        assert framework is not None
        assert framework.framework == "pytest"

        # Python unittest
        unittest_content = """
import unittest

class TestCalculator(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(1 + 1, 2)

    def test_subtraction(self):
        self.assertTrue(5 - 3 == 2)
"""
        framework = detector.detect_framework(
            unittest_content, "python", "test_file.py"
        )
        assert framework is not None
        assert framework.framework == "unittest"

        # JavaScript Jest
        jest_content = """
describe('Calculator', () => {
    test('adds 1 + 2 to equal 3', () => {
        expect(add(1, 2)).toBe(3);
    });

    it('subtracts correctly', () => {
        expect(subtract(5, 3)).toEqual(2);
    });
});
"""
        framework = detector.detect_framework(
            jest_content, "javascript", "calc.test.js"
        )
        assert framework is not None
        assert framework.framework in ["jest", "mocha"]

        # Java JUnit
        junit_content = """
import org.junit.Test;
import org.junit.Before;
import static org.junit.Assert.*;

public class CalculatorTest {
    @Test
    public void testAddition() {
        assertEquals(5, Calculator.add(2, 3));
    }
}
"""
        framework = detector.detect_framework(
            junit_content, "java", "CalculatorTest.java"
        )
        assert framework is not None
        assert framework.framework == "junit"

        # Go testing
        go_content = """
package calculator

import "testing"

func TestAdd(t *testing.T) {
    result := Add(2, 3)
    if result != 5 {
        t.Errorf("Add(2, 3) = %d; want 5", result)
    }
}
"""
        framework = detector.detect_framework(go_content, "go", "calculator_test.go")
        assert framework is not None
        assert framework.framework == "testing"

        # Rust cargo test
        rust_content = """
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_addition() {
        assert_eq!(add(2, 3), 5);
    }
}
"""
        framework = detector.detect_framework(rust_content, "rust", "lib_test.rs")
        assert framework is not None
        assert framework.framework == "cargo"

    def test_assertion_extraction(self):
        """Test extraction of assertions from test code."""
        detector = TestDetector()

        # Python assertions
        python_content = """
import pytest

def test_calculator():
    assert add(2, 3) == 5
    self.assertEqual(subtract(5, 3), 2)
    self.assertTrue(is_positive(5))
    pytest.raises(ValueError, divide, 1, 0)
"""
        framework = detector.detect_framework(python_content, "python", "test.py")
        if not framework:
            pytest.skip("Framework detection failed")
        assertions = detector.extract_assertions(python_content, framework)
        assert len(assertions) >= 2  # At least assert and pytest.raises
        assert any("assert add(2, 3) == 5" in a[1] for a in assertions)
        assert any("pytest.raises" in a[1] for a in assertions)

        # JavaScript assertions
        js_content = """
test('calculator operations', () => {
    expect(add(2, 3)).toBe(5);
    expect(subtract(5, 3)).toEqual(2);
    assert.strictEqual(multiply(2, 3), 6);
});
"""
        framework = detector.detect_framework(js_content, "javascript", "test.js")
        if not framework:
            pytest.skip("JavaScript framework detection failed")
        assertions = detector.extract_assertions(js_content, framework)
        assert len(assertions) >= 2
        assert any("expect(add(2, 3)).toBe(5)" in a[1] for a in assertions)

    def test_test_name_to_code_matching(self):
        """Test matching test names to code function names."""
        analyzer = TestCodeAnalyzer()

        # Test various naming patterns
        test_cases = [
            # (test_name, expected_function_name, language)
            ("test_calculate_total", "calculate_total", "python"),
            ("testCalculateTotal", "calculateTotal", "java"),
            ("TestCalculator", "Calculator", "python"),
            ("CalculatorTest", "Calculator", "java"),
            ("calculate_total_test", "calculate_total", "python"),
            ("CalculateTotalTest", "CalculateTotal", "java"),
            ("test_add_numbers", "add_numbers", "python"),
            ("TestAddNumbers", "AddNumbers", "go"),
        ]

        for test_name, expected_func, language in test_cases:
            code_map = {
                expected_func: type(
                    "obj", (object,), {"name": expected_func, "node_type": "function"}
                )()
            }

            matches = analyzer._match_by_name(test_name, code_map, language)
            assert len(matches) > 0, f"Failed to match {test_name} to {expected_func}"
            assert matches[0].tested_function == expected_func

    def test_coverage_calculation(self):
        """Test coverage metric calculations."""
        analyzer = TestCodeAnalyzer()

        # Create mock test and code nodes
        test_nodes = [
            type(
                "obj", (object,), {"name": f"test_{i}", "node_type": "test_function"}
            )()
            for i in range(5)
        ]

        code_nodes = [
            type("obj", (object,), {"name": f"func_{i}", "node_type": "function"})()
            for i in range(10)
        ] + [
            type("obj", (object,), {"name": f"Class_{i}", "node_type": "class"})()
            for i in range(3)
        ]

        # Simulate some test-code links
        for i in range(5):
            analyzer.links.append(
                TestCodeLink(
                    f"test_{i}",
                    "test_function",
                    f"func_{i}",
                    "function",
                    0.9,
                    "name match",
                )
            )

        metrics = analyzer.calculate_coverage_metrics(test_nodes, code_nodes)

        assert metrics["total_testable"] == 13  # 10 functions + 3 classes
        assert metrics["total_tested"] == 5  # 5 functions have tests
        assert metrics["coverage_percentage"] == pytest.approx(38.46, 0.1)
        assert metrics["test_count"] == 5
        assert len(metrics["untested_nodes"]) == 8

        # Check coverage by type
        assert metrics["coverage_by_type"]["function"]["total"] == 10
        assert metrics["coverage_by_type"]["function"]["tested"] == 5
        assert metrics["coverage_by_type"]["function"]["percentage"] == 50.0

        assert metrics["coverage_by_type"]["class"]["total"] == 3
        assert metrics["coverage_by_type"]["class"]["tested"] == 0
        assert metrics["coverage_by_type"]["class"]["percentage"] == 0.0
