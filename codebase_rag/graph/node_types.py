"""Node type definitions for the knowledge graph."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Variable:
    """Represents a variable in the code."""
    name: str
    qualified_name: str
    type_hint: str | None = None
    line_number: int = 0
    scope: str = ""
    is_parameter: bool = False
    is_global: bool = False
    is_mutable: bool = True
    initial_value: str | None = None


@dataclass
class DataFlow:
    """Represents data flow between code elements."""
    source: str
    target: str
    flow_type: str
    line_number: int
    is_tainted: bool = False
    taint_source: str | None = None


@dataclass
class Vulnerability:
    """Represents a security vulnerability."""
    type: str
    severity: str
    description: str
    file_path: str
    line_number: int
    cwe_id: str | None = None
    confidence: float = 0.0


@dataclass
class TestCoverage:
    """Represents test coverage information."""
    target_function: str
    test_function: str
    coverage_type: str  # UNIT, INTEGRATION, E2E
    assertions: list[str]
    line_coverage: float = 0.0