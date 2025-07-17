"""Unified test parser for multiple languages and frameworks."""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from tree_sitter import Node, Parser

from .bdd_parser import BDDFeature, BDDParser
from .test_detector import TestDetector, TestFrameworkInfo


@dataclass
class TestNode:
    """Represents a test-related node in the graph."""
    node_type: str  # test_suite, test_case, test_function, assertion, bdd_feature, bdd_scenario
    name: str
    file_path: str
    start_line: int
    end_line: int
    properties: dict[str, Any] = field(default_factory=dict)
    relationships: list[tuple[str, str, str]] = field(default_factory=list)  # (rel_type, target_type, target_name)


class TestParser:
    """Parse test files and extract test-related nodes and relationships."""

    def __init__(self, parser: Parser, queries: dict[str, Any], language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self.test_detector = TestDetector()
        self.bdd_parser = BDDParser()
        self.nodes: list[TestNode] = []
        self.relationships: list[tuple[str, str, str, str]] = []  # (source, rel_type, target_type, target)

    def parse_test_file(self, file_path: str, content: str) -> tuple[list[TestNode], list[tuple[str, str, str, str]]]:
        """Parse a test file and extract test nodes and relationships."""
        self.nodes = []
        self.relationships = []
        self.current_file = file_path

        # Detect test framework
        framework_info = self.test_detector.detect_framework(content, self.language, file_path)
        if not framework_info:
            logger.warning(f"Could not detect test framework for {file_path}")
            return self.nodes, self.relationships

        # Parse based on framework
        if framework_info.framework in ["pytest", "unittest"]:
            self._parse_python_tests(content, framework_info)
        elif framework_info.framework in ["jest", "mocha", "jasmine"]:
            self._parse_javascript_tests(content, framework_info)
        elif framework_info.framework in ["junit", "testng"]:
            self._parse_java_tests(content, framework_info)
        elif framework_info.framework in ["unity", "check", "cmocka"]:
            self._parse_c_tests(content, framework_info)
        elif framework_info.framework == "cargo":
            self._parse_rust_tests(content, framework_info)
        elif framework_info.framework in ["testing", "ginkgo"]:
            self._parse_go_tests(content, framework_info)

        # Extract assertions
        assertions = self.test_detector.extract_assertions(content, framework_info)
        self._create_assertion_relationships(assertions)

        return self.nodes, self.relationships

    def parse_bdd_file(self, file_path: str, content: str) -> tuple[list[TestNode], list[tuple[str, str, str, str]]]:
        """Parse a BDD feature file."""
        self.nodes = []
        self.relationships = []

        feature = self.bdd_parser.parse_feature_file(file_path, content)

        # Create feature node
        feature_node = TestNode(
            node_type="bdd_feature",
            name=feature.name,
            file_path=file_path,
            start_line=feature.line_number,
            end_line=len(content.split('\n')),
            properties={
                "description": feature.description,
                "tags": feature.tags,
            }
        )
        self.nodes.append(feature_node)

        # Create scenario nodes
        for scenario in feature.scenarios:
            scenario_node = TestNode(
                node_type="bdd_scenario",
                name=scenario.name,
                file_path=file_path,
                start_line=scenario.line_number,
                end_line=scenario.line_number,  # Would need to calculate
                properties={
                    "tags": scenario.tags,
                    "step_count": len(scenario.steps),
                    "has_examples": scenario.examples is not None,
                }
            )
            self.nodes.append(scenario_node)

            # Feature contains scenario
            self.relationships.append(
                (feature.name, "CONTAINS_SCENARIO", "bdd_scenario", scenario.name)
            )

            # Create step relationships
            for step in scenario.steps:
                self.relationships.append(
                    (scenario.name, "HAS_STEP", "bdd_step", f"{step.keyword} {step.text}")
                )

        return self.nodes, self.relationships

    def link_bdd_to_code(self, step_definitions: list[tuple[str, str, str]],
                         feature: BDDFeature) -> list[tuple[str, str, str, str]]:
        """Link BDD steps to their code implementations."""
        links = []

        for scenario in feature.scenarios:
            for step in scenario.steps:
                function_name = self.bdd_parser.match_step_to_definition(step, step_definitions)
                if function_name:
                    links.append(
                        (f"{step.keyword} {step.text}", "IMPLEMENTS_STEP", "function", function_name)
                    )

        return links

    def _parse_python_tests(self, content: str, framework_info: TestFrameworkInfo) -> None:
        """Parse Python test files (pytest/unittest)."""
        tree = self.parser.parse(bytes(content, "utf8"))

        # Find test classes
        class_query = self.queries.get("classes")
        if class_query:
            class_captures = class_query.captures(tree.root_node)
            for class_node in class_captures.get("class", []):
                class_name = self._get_node_name(class_node)
                if class_name and (class_name.startswith("Test") or "Test" in class_name):
                    test_suite = TestNode(
                        node_type="test_suite",
                        name=class_name,
                        file_path=self.current_file,
                        start_line=class_node.start_point[0] + 1,
                        end_line=class_node.end_point[0] + 1,
                        properties={
                            "framework": framework_info.framework,
                        }
                    )
                    self.nodes.append(test_suite)

                    # Find test methods in the class
                    self._extract_test_methods(class_node, class_name, framework_info)

        # Find standalone test functions
        function_query = self.queries.get("functions")
        if function_query:
            function_captures = function_query.captures(tree.root_node)
            for func_node in function_captures.get("function", []):
                func_name = self._get_node_name(func_node)
                if func_name and func_name.startswith("test_"):
                    test_func = TestNode(
                        node_type="test_function",
                        name=func_name,
                        file_path=self.current_file,
                        start_line=func_node.start_point[0] + 1,
                        end_line=func_node.end_point[0] + 1,
                        properties={
                            "framework": framework_info.framework,
                        }
                    )
                    self.nodes.append(test_func)

    def _parse_javascript_tests(self, content: str, framework_info: TestFrameworkInfo) -> None:
        """Parse JavaScript test files (Jest/Mocha)."""
        tree = self.parser.parse(bytes(content, "utf8"))

        # Find describe blocks and test/it calls
        self._walk_js_test_tree(tree.root_node, content, framework_info)

    def _parse_c_tests(self, content: str, framework_info: TestFrameworkInfo) -> None:
        """Parse C test files."""
        tree = self.parser.parse(bytes(content, "utf8"))

        # Find test functions
        function_query = self.queries.get("functions")
        if function_query:
            function_captures = function_query.captures(tree.root_node)
            for func_node in function_captures.get("function", []):
                func_name = self._get_node_name(func_node)
                if func_name and ("test_" in func_name or "Test" in func_name):
                    test_func = TestNode(
                        node_type="test_function",
                        name=func_name,
                        file_path=self.current_file,
                        start_line=func_node.start_point[0] + 1,
                        end_line=func_node.end_point[0] + 1,
                        properties={
                            "framework": framework_info.framework,
                        }
                    )
                    self.nodes.append(test_func)

    def _extract_test_methods(self, class_node: Node, class_name: str, framework_info: TestFrameworkInfo) -> None:
        """Extract test methods from a test class."""
        # Walk through class body to find methods
        for child in class_node.named_children:
            if child.type == "block" or child.type == "body":
                for method in child.named_children:
                    if method.type in ["function_definition", "method_definition"]:
                        method_name = self._get_node_name(method)
                        if method_name and method_name.startswith("test"):
                            test_case = TestNode(
                                node_type="test_case",
                                name=method_name,
                                file_path=self.current_file,
                                start_line=method.start_point[0] + 1,
                                end_line=method.end_point[0] + 1,
                                properties={
                                    "framework": framework_info.framework,
                                    "parent_suite": class_name,
                                }
                            )
                            self.nodes.append(test_case)

                            # Create relationship
                            self.relationships.append(
                                (class_name, "CONTAINS_TEST", "test_case", method_name)
                            )

    def _walk_js_test_tree(self, node: Node, content: str, framework_info: TestFrameworkInfo, parent_suite: str | None = None) -> None:
        """Walk JavaScript AST to find test constructs."""
        if node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            if function_node and function_node.type == "identifier":
                func_name = function_node.text.decode("utf-8")

                # Check for describe blocks
                if func_name == "describe":
                    args = node.child_by_field_name("arguments")
                    if args and args.named_children:
                        # Get suite name from first argument
                        name_arg = args.named_children[0]
                        if name_arg.type == "string":
                            suite_name = name_arg.text.decode("utf-8").strip('"\'')

                            test_suite = TestNode(
                                node_type="test_suite",
                                name=suite_name,
                                file_path=self.current_file,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                properties={
                                    "framework": framework_info.framework,
                                }
                            )
                            self.nodes.append(test_suite)

                            if parent_suite:
                                self.relationships.append(
                                    (parent_suite, "CONTAINS_SUITE", "test_suite", suite_name)
                                )

                            # Process callback for nested tests
                            if len(args.named_children) > 1:
                                callback = args.named_children[1]
                                self._walk_js_test_tree(callback, content, framework_info, suite_name)

                # Check for test/it blocks
                elif func_name in ["test", "it"]:
                    args = node.child_by_field_name("arguments")
                    if args and args.named_children:
                        # Get test name from first argument
                        name_arg = args.named_children[0]
                        if name_arg.type == "string":
                            test_name = name_arg.text.decode("utf-8").strip('"\'')

                            test_case = TestNode(
                                node_type="test_case",
                                name=test_name,
                                file_path=self.current_file,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                properties={
                                    "framework": framework_info.framework,
                                }
                            )
                            self.nodes.append(test_case)

                            if parent_suite:
                                self.relationships.append(
                                    (parent_suite, "CONTAINS_TEST", "test_case", test_name)
                                )

        # Recurse to children
        for child in node.named_children:
            self._walk_js_test_tree(child, content, framework_info, parent_suite)

    def _create_assertion_relationships(self, assertions: list[tuple[int, str]]) -> None:
        """Create relationships for assertions to their containing tests."""
        # Find which test each assertion belongs to
        for line_num, assertion_text in assertions:
            # Find the test that contains this line
            for node in self.nodes:
                if node.node_type in ["test_case", "test_function"]:
                    if node.start_line <= line_num <= node.end_line:
                        self.relationships.append(
                            (node.name, "ASSERTS", "assertion", assertion_text[:50])  # Truncate long assertions
                        )
                        break

    def _get_node_name(self, node: Node) -> str | None:
        """Extract name from various node types."""
        # Try standard name field first
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode("utf-8")

        # For C functions, the name is in the declarator
        if self.language == "c" and node.type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            if declarator:
                # For function_declarator, the first child is usually the identifier
                if declarator.type == "function_declarator":
                    ident = declarator.child(0)
                    if ident and ident.type == "identifier":
                        return ident.text.decode("utf-8")
                elif declarator.type == "pointer_declarator":
                    # Handle function pointers
                    func_decl = declarator.child_by_field_name("declarator")
                    if func_decl and func_decl.type == "function_declarator":
                        ident = func_decl.child(0)
                        if ident and ident.type == "identifier":
                            return ident.text.decode("utf-8")

        # For some languages, the identifier might be elsewhere
        for child in node.named_children:
            if child.type == "identifier":
                return child.text.decode("utf-8")

        return None

    def _parse_java_tests(self, content: str, framework_info: TestFrameworkInfo) -> None:
        """Parse Java test files (JUnit/TestNG)."""
        self.parser.parse(bytes(content, "utf8"))

        # Similar to Python but look for @Test annotations
        # This would need Java-specific parsing logic
        pass

    def _parse_rust_tests(self, content: str, framework_info: TestFrameworkInfo) -> None:
        """Parse Rust test files."""
        # Look for #[test] attributes
        pass

    def _parse_go_tests(self, content: str, framework_info: TestFrameworkInfo) -> None:
        """Parse Go test files."""
        # Look for Test* functions
        pass
