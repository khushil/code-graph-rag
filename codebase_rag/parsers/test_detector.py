"""Test file and framework detection across multiple languages."""

import re
from dataclasses import dataclass, field


@dataclass
class TestFrameworkInfo:
    """Information about detected test framework."""

    language: str
    framework: str
    test_patterns: list[str] = field(default_factory=list)
    assertion_patterns: list[str] = field(default_factory=list)
    setup_patterns: list[str] = field(default_factory=list)
    teardown_patterns: list[str] = field(default_factory=list)


class TestDetector:
    """Detects test files and frameworks across different languages."""

    # Test file patterns by language
    TEST_FILE_PATTERNS = {
        "python": [
            r"test_.*\.py$",
            r".*_test\.py$",
            r"tests?/.*\.py$",
            r".*\.test\.py$",
        ],
        "javascript": [
            r".*\.test\.[jt]sx?$",
            r".*\.spec\.[jt]sx?$",
            r"__tests__/.*\.[jt]sx?$",
            r"test/.*\.[jt]sx?$",
        ],
        "typescript": [
            r".*\.test\.tsx?$",
            r".*\.spec\.tsx?$",
            r"__tests__/.*\.tsx?$",
            r"test/.*\.tsx?$",
        ],
        "c": [
            r"test_.*\.c$",
            r".*_test\.c$",
            r"tests?/.*\.c$",
            r"check_.*\.c$",
        ],
        "cpp": [
            r"test_.*\.cpp$",
            r".*_test\.cpp$",
            r".*Test\.cpp$",
            r"tests?/.*\.cpp$",
        ],
        "rust": [
            r".*_test\.rs$",
            r"tests?/.*\.rs$",
        ],
        "go": [
            r".*_test\.go$",
        ],
        "java": [
            r".*Test\.java$",
            r"Test.*\.java$",
            r".*Tests\.java$",
        ],
    }

    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        "python": {
            "pytest": {
                "imports": [r"import pytest", r"from pytest import"],
                "decorators": [r"@pytest\.", r"@mark\."],
                "functions": [r"def test_", r"class Test"],
                "assertions": [r"assert\s+", r"pytest\.raises"],
            },
            "unittest": {
                "imports": [r"import unittest", r"from unittest import"],
                "decorators": [r"@unittest\."],
                "functions": [r"class.*\(.*TestCase\)", r"def test_"],
                "assertions": [
                    r"self\.assert",
                    r"self\.assertEqual",
                    r"self\.assertTrue",
                ],
            },
            "behave": {
                "imports": [r"from behave import"],
                "decorators": [r"@given", r"@when", r"@then", r"@step"],
                "functions": [],
                "assertions": [],
            },
        },
        "javascript": {
            "jest": {
                "imports": [],
                "decorators": [],
                "functions": [
                    r"describe\s*\(",
                    r"test\s*\(",
                    r"it\s*\(",
                    r"beforeEach\s*\(",
                ],
                "assertions": [r"expect\s*\(", r"\.toBe", r"\.toEqual"],
            },
            "mocha": {
                "imports": [r"require\s*\(\s*['\"]mocha", r"import.*from\s+['\"]mocha"],
                "decorators": [],
                "functions": [
                    r"describe\s*\(",
                    r"it\s*\(",
                    r"before\s*\(",
                    r"after\s*\(",
                ],
                "assertions": [r"assert\.", r"expect\s*\(", r"should\."],
            },
            "jasmine": {
                "imports": [],
                "decorators": [],
                "functions": [
                    r"describe\s*\(",
                    r"it\s*\(",
                    r"beforeEach\s*\(",
                    r"afterEach\s*\(",
                ],
                "assertions": [
                    r"expect\s*\(.*\)\s*\.toBe",
                    r"expect\s*\(.*\)\s*\.toEqual",
                ],
            },
        },
        "c": {
            "unity": {
                "imports": [r"#include\s+[\"<]unity\.h[\">]"],
                "decorators": [],
                "functions": [r"void\s+test_", r"TEST_ASSERT", r"RUN_TEST"],
                "assertions": [r"TEST_ASSERT", r"TEST_FAIL", r"TEST_PASS"],
            },
            "check": {
                "imports": [r"#include\s+[\"<]check\.h[\">]"],
                "decorators": [],
                "functions": [r"START_TEST", r"END_TEST", r"Suite\s*\*"],
                "assertions": [r"ck_assert", r"fail_unless", r"fail_if"],
            },
            "cmocka": {
                "imports": [r"#include\s+[\"<]cmocka\.h[\">]"],
                "decorators": [],
                "functions": [r"static\s+void\s+test_", r"cmocka_unit_test"],
                "assertions": [r"assert_", r"will_return", r"expect_"],
            },
        },
        "rust": {
            "cargo": {
                "imports": [],
                "decorators": [r"#\[test\]", r"#\[cfg\(test\)\]"],
                "functions": [r"fn\s+test_", r"mod\s+tests"],
                "assertions": [r"assert!", r"assert_eq!", r"assert_ne!"],
            },
        },
        "go": {
            "testing": {
                "imports": [
                    r"import\s+.*\"testing\"",
                    r"\"testing\"",
                    r"import\s*\(\s*[^)]*\"testing\"",
                ],
                "decorators": [],
                "functions": [r"func\s+Test", r"func\s+Benchmark"],
                "assertions": [r"t\.Error", r"t\.Fail", r"t\.Fatal"],
            },
            "ginkgo": {
                "imports": [r"github\.com/onsi/ginkgo", r"github\.com/onsi/gomega"],
                "decorators": [],
                "functions": [r"Describe\s*\(", r"Context\s*\(", r"It\s*\("],
                "assertions": [r"Expect\s*\(", r"Eventually\s*\("],
            },
        },
        "java": {
            "junit": {
                "imports": [r"import\s+org\.junit", r"import\s+static\s+org\.junit"],
                "decorators": [r"@Test", r"@Before", r"@After", r"@BeforeClass"],
                "functions": [r"public\s+void\s+test"],
                "assertions": [r"assertEquals", r"assertTrue", r"assertThat"],
            },
            "testng": {
                "imports": [r"import\s+org\.testng"],
                "decorators": [r"@Test", r"@BeforeMethod", r"@AfterMethod"],
                "functions": [],
                "assertions": [r"Assert\.", r"assertEquals", r"assertTrue"],
            },
        },
    }

    # BDD patterns
    BDD_PATTERNS = {
        "gherkin": {
            "file_extensions": [".feature"],
            "keywords": [
                "Feature:",
                "Scenario:",
                "Given",
                "When",
                "Then",
                "And",
                "But",
            ],
        },
        "python_behave": {
            "decorators": [r"@given", r"@when", r"@then", r"@step"],
        },
        "javascript_cucumber": {
            "functions": [r"Given\s*\(", r"When\s*\(", r"Then\s*\("],
        },
        "java_cucumber": {
            "decorators": [r"@Given", r"@When", r"@Then", r"@And", r"@But"],
        },
    }

    def __init__(self):
        self.detected_frameworks: dict[str, TestFrameworkInfo] = {}

    def is_test_file(self, file_path: str, language: str) -> bool:
        """Check if a file is likely a test file based on its path and name."""
        if language not in self.TEST_FILE_PATTERNS:
            return False

        for pattern in self.TEST_FILE_PATTERNS[language]:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True

        return False

    def detect_framework(
        self, content: str, language: str, file_path: str
    ) -> TestFrameworkInfo | None:
        """Detect which test framework is being used in the file."""
        if language not in self.FRAMEWORK_PATTERNS:
            return None

        # Check each framework for the language
        for framework, patterns in self.FRAMEWORK_PATTERNS[language].items():
            score = 0

            # Check imports
            for import_pattern in patterns.get("imports", []):
                if re.search(import_pattern, content, re.MULTILINE):
                    score += 3

            # Check decorators
            for decorator_pattern in patterns.get("decorators", []):
                if re.search(decorator_pattern, content, re.MULTILINE):
                    score += 2

            # Check functions
            for function_pattern in patterns.get("functions", []):
                if re.search(function_pattern, content, re.MULTILINE):
                    score += 1

            # If we have a reasonable score, this is likely the framework
            # Lower threshold for JavaScript since it often doesn't have imports
            threshold = 2 if language == "javascript" else 3
            if score >= threshold:
                return TestFrameworkInfo(
                    language=language,
                    framework=framework,
                    test_patterns=patterns.get("functions", []),
                    assertion_patterns=patterns.get("assertions", []),
                    setup_patterns=self._get_setup_patterns(framework),
                    teardown_patterns=self._get_teardown_patterns(framework),
                )

        return None

    def is_bdd_file(self, file_path: str) -> bool:
        """Check if a file is a BDD feature file."""
        return file_path.endswith(".feature")

    def detect_bdd_framework(self, content: str, language: str) -> str | None:
        """Detect which BDD framework is being used."""
        if language == "python":
            for pattern in self.BDD_PATTERNS["python_behave"]["decorators"]:
                if re.search(pattern, content, re.MULTILINE):
                    return "behave"

        elif language in ["javascript", "typescript"]:
            for pattern in self.BDD_PATTERNS["javascript_cucumber"]["functions"]:
                if re.search(pattern, content, re.MULTILINE):
                    return "cucumber"

        elif language == "java":
            for pattern in self.BDD_PATTERNS["java_cucumber"]["decorators"]:
                if re.search(pattern, content, re.MULTILINE):
                    return "cucumber"

        return None

    def extract_test_names(
        self, content: str, framework_info: TestFrameworkInfo
    ) -> list[str]:
        """Extract test function/method names from the content."""
        test_names = []

        for pattern in framework_info.test_patterns:
            # Extract the test name from patterns like "def test_name" or "it('should...')"
            if "test_" in pattern:
                # Python/C style test functions
                matches = re.finditer(pattern + r"(\w+)", content, re.MULTILINE)
                for match in matches:
                    test_names.append(match.group(1))

            elif "describe" in pattern or "it" in pattern:
                # JavaScript style test descriptions
                matches = re.finditer(
                    pattern + r"['\"]([^'\"]+)['\"]", content, re.MULTILINE
                )
                for match in matches:
                    test_names.append(match.group(1))

        return test_names

    def extract_assertions(
        self, content: str, framework_info: TestFrameworkInfo
    ) -> list[tuple[int, str]]:
        """Extract assertions with their line numbers."""
        assertions = []

        lines = content.split("\n")
        for i, line in enumerate(lines):
            for pattern in framework_info.assertion_patterns:
                if re.search(pattern, line):
                    assertions.append((i + 1, line.strip()))
                    break

        return assertions

    def _get_setup_patterns(self, framework: str) -> list[str]:
        """Get setup method patterns for a framework."""
        setup_patterns = {
            "pytest": [
                r"def setup",
                r"def setup_method",
                r"def setup_class",
                r"@pytest\.fixture",
            ],
            "unittest": [r"def setUp", r"def setUpClass"],
            "jest": [r"beforeEach\s*\(", r"beforeAll\s*\("],
            "mocha": [r"before\s*\(", r"beforeEach\s*\("],
            "junit": [r"@Before", r"@BeforeClass", r"@BeforeEach"],
        }
        return setup_patterns.get(framework, [])

    def _get_teardown_patterns(self, framework: str) -> list[str]:
        """Get teardown method patterns for a framework."""
        teardown_patterns = {
            "pytest": [r"def teardown", r"def teardown_method", r"def teardown_class"],
            "unittest": [r"def tearDown", r"def tearDownClass"],
            "jest": [r"afterEach\s*\(", r"afterAll\s*\("],
            "mocha": [r"after\s*\(", r"afterEach\s*\("],
            "junit": [r"@After", r"@AfterClass", r"@AfterEach"],
        }
        return teardown_patterns.get(framework, [])
