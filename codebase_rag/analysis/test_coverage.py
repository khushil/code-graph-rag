"""Test coverage analysis and test-code linking."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TestCodeLink:
    """Represents a link between a test and the code it tests."""

    test_name: str
    test_type: str  # test_case, test_function, bdd_scenario
    tested_function: str
    tested_type: str  # function, class, method
    confidence: float  # 0.0 to 1.0
    reason: str  # Why we think this test tests this code


class TestCodeAnalyzer:
    """Analyzes relationships between tests and the code they test."""

    # Patterns for extracting what a test is testing
    TEST_NAME_PATTERNS = [
        # test_function_name -> function_name
        (r"test_([a-z_]+)", r"\1"),
        # testFunctionName -> functionName (camelCase)
        (r"test([A-Z]\w+)", lambda m: m.group(1)[0].lower() + m.group(1)[1:]),
        # TestClassName -> ClassName
        (r"Test([A-Z]\w+)", r"\1"),
        # function_name_test -> function_name
        (r"([a-z_]+)_test", r"\1"),
        # FunctionNameTest -> FunctionName
        (r"([A-Z]\w+)Test", r"\1"),
    ]

    # Common test naming conventions by language
    LANGUAGE_CONVENTIONS = {
        "python": {
            "test_prefix": ["test_", "Test"],
            "module_suffix": ["_test.py", "_tests.py", "test_*.py"],
            "import_patterns": [
                r"from\s+(\S+)\s+import\s+(\w+)",
                r"import\s+(\S+)",
            ],
        },
        "javascript": {
            "test_prefix": ["test", "it should", "should"],
            "module_suffix": [".test.js", ".spec.js"],
            "import_patterns": [
                r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
                r"const\s+.*=\s*require\s*\(['\"]([^'\"]+)['\"]\)",
            ],
        },
        "java": {
            "test_prefix": ["test", "Test"],
            "class_suffix": ["Test", "Tests", "TestCase"],
            "import_patterns": [
                r"import\s+([\w.]+)",
            ],
        },
        "go": {
            "test_prefix": ["Test", "Benchmark", "Example"],
            "module_suffix": ["_test.go"],
            "import_patterns": [
                r"import\s+\"([^\"]+)\"",
                r"import\s+\(\s*[^)]*\"([^\"]+)\"",
            ],
        },
    }

    def __init__(self):
        self.links: list[TestCodeLink] = []
        self.coverage_stats: dict[str, Any] = {}

    def analyze_test_code_relationships(
        self,
        test_nodes: list[Any],
        code_nodes: list[Any],
        test_content: str,
        language: str,
    ) -> list[tuple[str, str, str, str]]:
        """Analyze relationships between test nodes and code nodes.

        Returns list of (test_name, rel_type, target_type, target_name) tuples.
        """
        relationships = []

        # Extract imports from test file
        imports = self._extract_imports(test_content, language)

        # Create a map of code nodes by name for quick lookup
        code_map = self._build_code_map(code_nodes)

        for test_node in test_nodes:
            if test_node.node_type not in [
                "test_case",
                "test_function",
                "bdd_scenario",
            ]:
                continue

            # Try different strategies to find what this test is testing
            tested_items = []

            # Strategy 1: Name-based matching
            name_matches = self._match_by_name(test_node.name, code_map, language)
            tested_items.extend(name_matches)

            # Strategy 2: Import-based matching
            if imports:
                import_matches = self._match_by_imports(test_node, imports, code_map)
                tested_items.extend(import_matches)

            # Strategy 3: Content-based matching (look for function calls in test)
            if hasattr(test_node, "content") or test_content:
                content_matches = self._match_by_content(
                    test_node, test_content, code_map
                )
                tested_items.extend(content_matches)

            # Create relationships for the best matches
            best_matches = self._select_best_matches(tested_items)
            for match in best_matches:
                relationships.append(
                    (test_node.name, "TESTS", match.tested_type, match.tested_function)
                )
                self.links.append(match)

        return relationships

    def _extract_imports(self, content: str, language: str) -> list[str]:
        """Extract import statements from test file."""
        imports = []
        patterns = self.LANGUAGE_CONVENTIONS.get(language, {}).get(
            "import_patterns", []
        )

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                # Get the imported module/package
                if match.groups():
                    imports.append(match.group(1))

        return imports

    def _build_code_map(self, code_nodes: list[Any]) -> dict[str, Any]:
        """Build a map of code nodes by name for quick lookup."""
        code_map = {}

        for node in code_nodes:
            if hasattr(node, "name") and node.name:
                # Store by exact name
                code_map[node.name] = node

                # Also store by lowercase for case-insensitive matching
                code_map[node.name.lower()] = node

                # For methods, also store by method name alone
                if (
                    hasattr(node, "node_type")
                    and node.node_type == "method"
                    and "." in node.name
                ):
                    method_name = node.name.split(".")[-1]
                    code_map[method_name] = node
                    code_map[method_name.lower()] = node

        return code_map

    def _match_by_name(
        self, test_name: str, code_map: dict[str, Any], language: str
    ) -> list[TestCodeLink]:
        """Match test to code based on naming conventions."""
        matches = []

        # Try each naming pattern
        for pattern, replacement in self.TEST_NAME_PATTERNS:
            match = re.match(pattern, test_name)
            if match:
                if callable(replacement):
                    potential_name = replacement(match)
                else:
                    potential_name = re.sub(pattern, replacement, test_name)

                # Look for exact match
                if potential_name in code_map:
                    matches.append(
                        TestCodeLink(
                            test_name=test_name,
                            test_type="test_function",
                            tested_function=code_map[potential_name].name,
                            tested_type=getattr(
                                code_map[potential_name], "node_type", "function"
                            ),
                            confidence=0.9,
                            reason=f"Name pattern match: {pattern}",
                        )
                    )

                # Look for case-insensitive match
                elif potential_name.lower() in code_map:
                    matches.append(
                        TestCodeLink(
                            test_name=test_name,
                            test_type="test_function",
                            tested_function=code_map[potential_name.lower()].name,
                            tested_type=getattr(
                                code_map[potential_name.lower()],
                                "node_type",
                                "function",
                            ),
                            confidence=0.8,
                            reason=f"Case-insensitive name pattern match: {pattern}",
                        )
                    )

        # If no pattern matched, try fuzzy matching
        if not matches:
            # Remove common test prefixes/suffixes and try again
            cleaned_name = test_name
            for prefix in ["test_", "Test", "test"]:
                if cleaned_name.startswith(prefix):
                    cleaned_name = cleaned_name[len(prefix) :]
                    break

            for suffix in ["_test", "Test", "_spec"]:
                if cleaned_name.endswith(suffix):
                    cleaned_name = cleaned_name[: -len(suffix)]
                    break

            if cleaned_name in code_map:
                matches.append(
                    TestCodeLink(
                        test_name=test_name,
                        test_type="test_function",
                        tested_function=code_map[cleaned_name].name,
                        tested_type=getattr(
                            code_map[cleaned_name], "node_type", "function"
                        ),
                        confidence=0.7,
                        reason="Fuzzy name match after removing test affixes",
                    )
                )

        return matches

    def _match_by_imports(
        self, test_node: Any, imports: list[str], code_map: dict[str, Any]
    ) -> list[TestCodeLink]:
        """Match test to code based on import statements."""
        matches = []

        # This is a simplified version - in reality, we'd need to resolve
        # module paths to actual functions/classes
        for imp in imports:
            # Check if any code node's file path matches the import
            for code_node in code_map.values():
                if (
                    hasattr(code_node, "file_path")
                    and imp.replace(".", "/") in code_node.file_path
                ):
                    matches.append(
                        TestCodeLink(
                            test_name=test_node.name,
                            test_type=test_node.node_type,
                            tested_function=code_node.name,
                            tested_type=getattr(code_node, "node_type", "function"),
                            confidence=0.6,
                            reason=f"Import path match: {imp}",
                        )
                    )

        return matches

    def _match_by_content(
        self, test_node: Any, test_content: str, code_map: dict[str, Any]
    ) -> list[TestCodeLink]:
        """Match test to code by analyzing test content for function calls."""
        matches = []

        # Extract the test's content if possible
        test_code = ""
        if hasattr(test_node, "start_line") and hasattr(test_node, "end_line"):
            lines = test_content.split("\n")
            start = max(0, test_node.start_line - 1)
            end = min(len(lines), test_node.end_line)
            test_code = "\n".join(lines[start:end])

        if not test_code:
            return matches

        # Look for function calls in the test code
        # Simple pattern: function_name( or ClassName( or object.method(
        call_pattern = r"\b(\w+)\s*\("
        method_pattern = r"\b(\w+)\.(\w+)\s*\("

        # Find function calls
        for match in re.finditer(call_pattern, test_code):
            func_name = match.group(1)
            if func_name in code_map:
                matches.append(
                    TestCodeLink(
                        test_name=test_node.name,
                        test_type=test_node.node_type,
                        tested_function=code_map[func_name].name,
                        tested_type=getattr(
                            code_map[func_name], "node_type", "function"
                        ),
                        confidence=0.5,
                        reason=f"Function call found in test: {func_name}(",
                    )
                )

        # Find method calls
        for match in re.finditer(method_pattern, test_code):
            obj_name = match.group(1)
            method_name = match.group(2)

            # Check for method in code map
            if method_name in code_map:
                matches.append(
                    TestCodeLink(
                        test_name=test_node.name,
                        test_type=test_node.node_type,
                        tested_function=code_map[method_name].name,
                        tested_type="method",
                        confidence=0.5,
                        reason=f"Method call found in test: {obj_name}.{method_name}(",
                    )
                )

        return matches

    def _select_best_matches(self, matches: list[TestCodeLink]) -> list[TestCodeLink]:
        """Select the best matches from all found matches."""
        if not matches:
            return []

        # Sort by confidence
        matches.sort(key=lambda x: x.confidence, reverse=True)

        # Take the highest confidence match(es)
        best_confidence = matches[0].confidence
        best_matches = [m for m in matches if m.confidence >= best_confidence - 0.1]

        # Deduplicate by tested function
        seen = set()
        unique_matches = []
        for match in best_matches:
            if match.tested_function not in seen:
                seen.add(match.tested_function)
                unique_matches.append(match)

        return unique_matches

    def calculate_coverage_metrics(
        self, test_nodes: list[Any], code_nodes: list[Any]
    ) -> dict[str, Any]:
        """Calculate test coverage metrics."""
        # Count testable code nodes (functions, methods, classes)
        testable_nodes = [
            n
            for n in code_nodes
            if hasattr(n, "node_type")
            and n.node_type in ["function", "method", "class"]
        ]

        # Count tested nodes (those with TESTS relationships)
        tested_nodes = set()
        for link in self.links:
            tested_nodes.add(link.tested_function)

        # Calculate metrics
        total_testable = len(testable_nodes)
        total_tested = len(tested_nodes)
        coverage_percentage = (
            (total_tested / total_testable * 100) if total_testable > 0 else 0
        )

        # Group by node type
        coverage_by_type = {}
        for node_type in ["function", "method", "class"]:
            type_nodes = [n for n in testable_nodes if n.node_type == node_type]
            type_tested = [n for n in type_nodes if n.name in tested_nodes]
            coverage_by_type[node_type] = {
                "total": len(type_nodes),
                "tested": len(type_tested),
                "percentage": (len(type_tested) / len(type_nodes) * 100)
                if type_nodes
                else 0,
            }

        # Find untested code
        untested_nodes = [n for n in testable_nodes if n.name not in tested_nodes]

        self.coverage_stats = {
            "total_testable": total_testable,
            "total_tested": total_tested,
            "coverage_percentage": coverage_percentage,
            "coverage_by_type": coverage_by_type,
            "untested_nodes": untested_nodes,
            "test_count": len(test_nodes),
            "links_found": len(self.links),
        }

        return self.coverage_stats
