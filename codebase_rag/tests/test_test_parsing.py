from pathlib import Path

import pytest

from codebase_rag.parser_loader import load_parsers
from codebase_rag.parsers.bdd_parser import BDDParser
from codebase_rag.parsers.test_detector import TestDetector
from codebase_rag.parsers.test_parser import TestParser


class TestTestParsing:
    """Test the test parsing functionality."""

    @pytest.fixture
    def parsers_and_queries(self):
        """Load parsers and queries."""
        parsers, queries = load_parsers()
        return parsers, queries

    def test_test_detection(self):
        """Test detection of test files."""
        detector = TestDetector()

        # Python test files
        assert detector.is_test_file("test_example.py", "python")
        assert detector.is_test_file("example_test.py", "python")
        assert detector.is_test_file("tests/test_module.py", "python")
        assert not detector.is_test_file("example.py", "python")

        # JavaScript test files
        assert detector.is_test_file("example.test.js", "javascript")
        assert detector.is_test_file("example.spec.js", "javascript")
        assert detector.is_test_file("__tests__/example.js", "javascript")
        assert not detector.is_test_file("example.js", "javascript")

        # C test files
        assert detector.is_test_file("test_example.c", "c")
        assert detector.is_test_file("example_test.c", "c")
        assert not detector.is_test_file("example.c", "c")

    def test_framework_detection(self):
        """Test detection of test frameworks."""
        detector = TestDetector()

        # Pytest detection
        pytest_code = """
import pytest

def test_example():
    assert True

@pytest.mark.skip
def test_skipped():
    pass
"""
        framework = detector.detect_framework(pytest_code, "python", "test_file.py")
        assert framework is not None
        assert framework.framework == "pytest"

        # Jest detection
        jest_code = """
describe('Example', () => {
    it('should work', () => {
        expect(true).toBe(true);
    });
});
"""
        framework = detector.detect_framework(jest_code, "javascript", "test.js")
        assert framework is not None
        assert framework.framework == "jest"

    def test_python_test_parsing(self, parsers_and_queries):
        """Test parsing Python test files."""
        parsers, queries = parsers_and_queries
        test_parser = TestParser(parsers["python"], queries["python"], "python")

        # Read test file
        test_file = Path(__file__).parent / "fixtures" / "test_python_example.py"
        content = test_file.read_text()

        nodes, relationships = test_parser.parse_test_file(str(test_file), content)

        # Check nodes
        node_types = {}
        for node in nodes:
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1

        assert "test_suite" in node_types  # TestCalculatorUnittest
        assert "test_function" in node_types  # test_add_positive_numbers, etc.
        assert "test_case" in node_types  # Methods in TestCalculatorUnittest

        # Check test names
        test_names = [n.name for n in nodes if n.node_type == "test_function"]
        assert "test_add_positive_numbers" in test_names
        assert "test_add_negative_numbers" in test_names

        # Check relationships
        rel_types = set(r[1] for r in relationships)
        assert "CONTAINS_TEST" in rel_types
        assert "ASSERTS" in rel_types

    def test_javascript_test_parsing(self, parsers_and_queries):
        """Test parsing JavaScript test files."""
        parsers, queries = parsers_and_queries
        test_parser = TestParser(parsers["javascript"], queries["javascript"], "javascript")

        # Read test file
        test_file = Path(__file__).parent / "fixtures" / "test_javascript.test.js"
        content = test_file.read_text()

        nodes, relationships = test_parser.parse_test_file(str(test_file), content)

        # Check nodes
        suite_names = [n.name for n in nodes if n.node_type == "test_suite"]
        assert "Math Functions" in suite_names
        assert "StringUtils" in suite_names
        assert "fibonacci" in suite_names  # Nested suite

        test_names = [n.name for n in nodes if n.node_type == "test_case"]
        assert "should return 0 for n=0" in test_names
        assert "should capitalize first letter" in test_names

    def test_bdd_parsing(self):
        """Test parsing BDD feature files."""
        parser = BDDParser()

        # Read feature file
        feature_file = Path(__file__).parent / "fixtures" / "calculator.feature"
        content = feature_file.read_text()

        feature = parser.parse_feature_file(str(feature_file), content)

        # Check feature
        assert feature.name == "Calculator Operations"
        assert len(feature.scenarios) == 4

        # Check scenarios
        scenario_names = [s.name for s in feature.scenarios]
        assert "Addition of two numbers" in scenario_names
        assert "Division by zero" in scenario_names

        # Check scenario with outline
        outline = next(s for s in feature.scenarios if s.name == "Multiplication operations")
        assert outline.examples is not None
        assert len(outline.examples) == 3

        # Check tags
        addition_scenario = next(s for s in feature.scenarios if s.name == "Addition of two numbers")
        assert "@arithmetic" in addition_scenario.tags
        assert "@basic" in addition_scenario.tags

        # Check steps
        assert len(addition_scenario.steps) == 4
        step_texts = [s.text for s in addition_scenario.steps]
        assert "I have entered 50 into the calculator" in step_texts
        assert "the result should be 120 on the screen" in step_texts

    def test_c_test_parsing(self, parsers_and_queries):
        """Test parsing C test files with Unity framework."""
        parsers, queries = parsers_and_queries
        test_parser = TestParser(parsers["c"], queries["c"], "c")

        # Read test file
        test_file = Path(__file__).parent / "fixtures" / "test_c_unity.c"
        content = test_file.read_text()

        nodes, relationships = test_parser.parse_test_file(str(test_file), content)

        # Check test functions
        test_funcs = [n for n in nodes if n.node_type == "test_function"]
        assert len(test_funcs) > 0

        test_names = [f.name for f in test_funcs]
        assert "test_factorial_base_cases" in test_names
        assert "test_is_prime_small_numbers" in test_names
        assert "test_string_reverse" in test_names

        # Check assertions
        assertions = [(r[0], r[3]) for r in relationships if r[1] == "ASSERTS"]
        assert len(assertions) > 0

    def test_bdd_step_matching(self):
        """Test matching BDD steps to implementations."""
        parser = BDDParser()

        # Sample step definitions
        step_defs = [
            (r"I have entered (\d+) into the calculator", "enter_number", "given"),
            (r"I press (\w+)", "press_operation", "when"),
            (r"the result should be (\d+) on the screen", "check_result", "then"),
        ]

        # Create a step
        from codebase_rag.parsers.bdd_parser import BDDStep
        step = BDDStep(
            keyword="Given",
            text="I have entered 50 into the calculator",
            line_number=1
        )

        # Match step to definition
        matched = parser.match_step_to_definition(step, step_defs)
        assert matched == "enter_number"
