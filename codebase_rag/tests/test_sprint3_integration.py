"""Integration tests for Sprint 3: Testing Framework Integration."""

import tempfile
from pathlib import Path

import pytest
from tree_sitter import Parser

from codebase_rag.graph_updater import GraphUpdater
from codebase_rag.language_config import get_language_config
from codebase_rag.parsers.test_detector import TestDetector


class MockIngestor:
    """Mock ingestor for testing."""

    def __init__(self):
        self.nodes = {}
        self.relationships = []
        self.batched_nodes = []
        self.batched_relationships = []

    def ensure_node(self, label, properties):
        key = f"{label}:{properties.get('qualified_name', properties.get('name', properties.get('id', '')))}"
        self.nodes[key] = {"label": label, "properties": properties}

    def ensure_node_batch(self, label, properties):
        self.batched_nodes.append({"label": label, "properties": properties})

    def ensure_relationship_batch(self, source, rel_type, target, properties=None):
        self.batched_relationships.append(
            {
                "source": source,
                "rel_type": rel_type,
                "target": target,
                "properties": properties or {},
            }
        )

    def flush_all(self):
        pass


class TestSprint3Integration:
    """Test the complete Sprint 3 implementation."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)

        # Create mock ingestor
        self.ingestor = MockIngestor()

        # Set up parsers
        self.parsers = {}
        self.queries = {}

        # Initialize for Python
        try:
            import tree_sitter_python
            from tree_sitter import Language

            # Create Language object from the Python grammar
            PY_LANGUAGE = Language(tree_sitter_python.language())
            parser = Parser(PY_LANGUAGE)
            self.parsers["python"] = parser

            lang_config = get_language_config(".py")
            self.queries["python"] = {
                "functions": PY_LANGUAGE.query(
                    " ".join(
                        f"({nt}) @function" for nt in lang_config.function_node_types
                    )
                ),
                "classes": PY_LANGUAGE.query(
                    " ".join(f"({nt}) @class" for nt in lang_config.class_node_types)
                ),
                "calls": PY_LANGUAGE.query(
                    " ".join(f"({nt}) @call" for nt in lang_config.call_node_types)
                )
                if lang_config.call_node_types
                else None,
                "config": lang_config,
            }
        except ImportError:
            pytest.skip("tree-sitter-python not available")

    def test_test_detection_and_parsing(self):
        """Test that test files are detected and parsed correctly."""
        # Create a test file
        test_file = self.repo_path / "test_calculator.py"
        test_file.write_text("""
import pytest

class TestCalculator:
    def test_add(self):
        from calculator import add
        assert add(2, 3) == 5

    def test_subtract(self):
        from calculator import subtract
        assert subtract(5, 3) == 2

def test_multiply():
    from calculator import multiply
    result = multiply(3, 4)
    assert result == 12
""")

        # Create the actual code file
        code_file = self.repo_path / "calculator.py"
        code_file.write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""")

        # Create graph updater
        updater = GraphUpdater(
            self.ingestor, self.repo_path, self.parsers, self.queries
        )

        # Run the analysis
        updater.run()

        # Verify test nodes were created
        test_nodes = [
            n
            for n in self.ingestor.batched_nodes
            if n["label"] in ["TestSuite", "TestCase", "TestFunction"]
        ]
        assert len(test_nodes) > 0

        # Verify test suite was found
        test_suites = [
            n
            for n in test_nodes
            if n["label"] == "TestSuite" and n["properties"]["name"] == "TestCalculator"
        ]
        assert len(test_suites) == 1

        # Verify test cases were found
        test_cases = [n for n in test_nodes if n["label"] == "TestCase"]
        assert len(test_cases) >= 2
        test_names = [tc["properties"]["name"] for tc in test_cases]
        assert "test_add" in test_names
        assert "test_subtract" in test_names

        # Verify standalone test function was found
        test_functions = [
            n
            for n in test_nodes
            if n["label"] == "TestFunction"
            and n["properties"]["name"] == "test_multiply"
        ]
        assert len(test_functions) == 1

        # Verify TESTS relationships were created
        test_relationships = [
            r for r in self.ingestor.batched_relationships if r["rel_type"] == "TESTS"
        ]
        assert len(test_relationships) > 0

        # Verify coverage metrics were calculated
        module_nodes = [
            n for n in self.ingestor.nodes.values() if n["label"] == "Module"
        ]
        if module_nodes:
            # Check that at least one module has coverage metrics
            modules_with_coverage = [
                m for m in module_nodes if "test_coverage_percentage" in m["properties"]
            ]
            assert len(modules_with_coverage) > 0

    def test_bdd_parsing(self):
        """Test BDD feature file parsing."""
        # Create a feature file
        feature_file = self.repo_path / "calculator.feature"
        feature_file.write_text("""
Feature: Calculator Operations
  As a user
  I want to perform basic arithmetic operations
  So that I can calculate values

  Scenario: Add two numbers
    Given I have entered 50 into the calculator
    And I have entered 70 into the calculator
    When I press add
    Then the result should be 120

  Scenario: Subtract two numbers
    Given I have entered 100 into the calculator
    And I have entered 25 into the calculator
    When I press subtract
    Then the result should be 75
""")

        # Create graph updater
        updater = GraphUpdater(
            self.ingestor, self.repo_path, self.parsers, self.queries
        )

        # Run the analysis
        updater.run()

        # Verify BDD nodes were created
        bdd_nodes = [
            n
            for n in self.ingestor.batched_nodes
            if n["label"] in ["BDDFeature", "BDDScenario", "BDDStep"]
        ]
        assert len(bdd_nodes) > 0

        # Verify feature was parsed
        features = [n for n in bdd_nodes if n["label"] == "BDDFeature"]
        assert len(features) == 1
        assert features[0]["properties"]["name"] == "Calculator Operations"

        # Verify scenarios were parsed
        scenarios = [n for n in bdd_nodes if n["label"] == "BDDScenario"]
        assert len(scenarios) == 2
        scenario_names = [s["properties"]["name"] for s in scenarios]
        assert "Add two numbers" in scenario_names
        assert "Subtract two numbers" in scenario_names

        # Verify steps were parsed
        steps = [n for n in bdd_nodes if n["label"] == "BDDStep"]
        assert len(steps) >= 8  # At least 4 steps per scenario

    def test_multi_language_test_parsing(self):
        """Test parsing tests in multiple languages."""
        # Create JavaScript test file
        js_test_file = self.repo_path / "calculator.test.js"
        js_test_file.write_text("""
describe('Calculator', () => {
  describe('add function', () => {
    it('should add two positive numbers', () => {
      expect(add(2, 3)).toBe(5);
    });

    it('should handle negative numbers', () => {
      expect(add(-1, 1)).toBe(0);
    });
  });

  test('multiply function works', () => {
    expect(multiply(3, 4)).toBe(12);
  });
});
""")

        # Create Java test file
        java_test_file = self.repo_path / "CalculatorTest.java"
        java_test_file.write_text("""
import org.junit.Test;
import static org.junit.Assert.*;

public class CalculatorTest {
    @Test
    public void testAddition() {
        Calculator calc = new Calculator();
        assertEquals(5, calc.add(2, 3));
    }

    @Test
    public void testSubtraction() {
        Calculator calc = new Calculator();
        assertEquals(2, calc.subtract(5, 3));
    }
}
""")

        # Create Go test file
        go_test_file = self.repo_path / "calculator_test.go"
        go_test_file.write_text("""
package calculator

import "testing"

func TestAdd(t *testing.T) {
    result := Add(2, 3)
    if result != 5 {
        t.Errorf("Add(2, 3) = %d; want 5", result)
    }
}

func BenchmarkAdd(b *testing.B) {
    for i := 0; i < b.N; i++ {
        Add(2, 3)
    }
}

func ExampleAdd() {
    fmt.Println(Add(2, 3))
    // Output: 5
}
""")

        # Test framework detection
        detector = TestDetector()

        # JavaScript
        assert detector.is_test_file(str(js_test_file), "javascript")
        js_content = js_test_file.read_text()
        js_framework = detector.detect_framework(
            js_content, "javascript", str(js_test_file)
        )
        assert js_framework is not None
        assert js_framework.framework in ["jest", "mocha"]

        # Java
        assert detector.is_test_file(str(java_test_file), "java")
        java_content = java_test_file.read_text()
        java_framework = detector.detect_framework(
            java_content, "java", str(java_test_file)
        )
        assert java_framework is not None
        assert java_framework.framework == "junit"

        # Go
        assert detector.is_test_file(str(go_test_file), "go")
        go_content = go_test_file.read_text()
        go_framework = detector.detect_framework(go_content, "go", str(go_test_file))
        assert go_framework is not None
        assert go_framework.framework == "testing"

    def test_test_code_linking(self):
        """Test that tests are correctly linked to the code they test."""
        # Create a Python module with functions
        module_file = self.repo_path / "math_utils.py"
        module_file.write_text("""
def calculate_average(numbers):
    '''Calculate the average of a list of numbers.'''
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

def find_median(numbers):
    '''Find the median of a list of numbers.'''
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    if n == 0:
        return None
    if n % 2 == 0:
        return (sorted_nums[n//2 - 1] + sorted_nums[n//2]) / 2
    return sorted_nums[n//2]

class Statistics:
    def __init__(self):
        self.data = []

    def add_value(self, value):
        self.data.append(value)

    def get_mean(self):
        return calculate_average(self.data)
""")

        # Create corresponding test file
        test_file = self.repo_path / "test_math_utils.py"
        test_file.write_text("""
import pytest
from math_utils import calculate_average, find_median, Statistics

def test_calculate_average():
    assert calculate_average([1, 2, 3, 4, 5]) == 3
    assert calculate_average([]) == 0
    assert calculate_average([10]) == 10

def test_find_median():
    assert find_median([1, 2, 3, 4, 5]) == 3
    assert find_median([1, 2, 3, 4]) == 2.5
    assert find_median([]) is None

class TestStatistics:
    def test_add_value(self):
        stats = Statistics()
        stats.add_value(10)
        assert len(stats.data) == 1
        assert stats.data[0] == 10

    def test_get_mean(self):
        stats = Statistics()
        stats.add_value(10)
        stats.add_value(20)
        assert stats.get_mean() == 15
""")

        # Create graph updater
        updater = GraphUpdater(
            self.ingestor, self.repo_path, self.parsers, self.queries
        )

        # Run the analysis
        updater.run()

        # Check that TESTS relationships were created
        test_relationships = [
            r for r in self.ingestor.batched_relationships if r["rel_type"] == "TESTS"
        ]
        assert len(test_relationships) > 0

        # Check specific relationships
        # test_calculate_average should link to calculate_average
        calc_avg_tests = [
            r
            for r in test_relationships
            if "test_calculate_average" in str(r["source"])
            and "calculate_average" in str(r["target"])
        ]
        assert len(calc_avg_tests) >= 1

        # TestStatistics should link to Statistics class
        stats_tests = [
            r
            for r in test_relationships
            if "TestStatistics" in str(r["source"]) and "Statistics" in str(r["target"])
        ]
        assert len(stats_tests) >= 1

        # Check COVERED_BY relationships
        covered_by_relationships = [
            r
            for r in self.ingestor.batched_relationships
            if r["rel_type"] == "COVERED_BY"
        ]
        assert len(covered_by_relationships) > 0

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)
