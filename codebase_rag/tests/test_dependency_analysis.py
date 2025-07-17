"""Test dependency analysis functionality."""


import pytest

from codebase_rag.analysis.dependencies import DependencyAnalyzer
from codebase_rag.parser_loader import load_parsers


class TestDependencyAnalysis:
    """Test dependency analysis for various languages."""

    @pytest.fixture(scope="class")
    def parsers_and_queries(self):
        """Load parsers and queries once for all tests."""
        parsers, queries = load_parsers()
        return parsers, queries

    def test_python_imports(self, parsers_and_queries):
        """Test Python import detection."""
        parsers, queries = parsers_and_queries

        python_code = '''
import os
import sys
from pathlib import Path
from typing import List, Dict as DictType
from ..utils import helper
from . import local_module
import package.submodule as sub
'''

        analyzer = DependencyAnalyzer(parsers["python"], queries["python"], "python")
        exports, imports = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check imports
        assert len(imports) > 0

        # Check specific imports
        import_sources = {imp.source_module for imp in imports}
        assert "os" in import_sources
        assert "sys" in import_sources
        assert "pathlib" in import_sources
        assert "typing" in import_sources
        assert "..utils" in import_sources  # Relative import
        assert "." in import_sources  # Current package import
        assert "package.submodule" in import_sources

        # Check import types
        typing_imports = [imp for imp in imports if imp.source_module == "typing"]
        assert len(typing_imports) == 2  # List and Dict
        assert any(imp.symbol == "List" for imp in typing_imports)
        assert any(imp.symbol == "Dict" and imp.alias == "DictType" for imp in typing_imports)

    def test_python_exports(self, parsers_and_queries):
        """Test Python export detection."""
        parsers, queries = parsers_and_queries

        python_code = '''
__all__ = ["public_function", "PublicClass"]

def public_function():
    pass

def _private_function():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass

# Global variable
CONFIG = {"debug": True}
'''

        analyzer = DependencyAnalyzer(parsers["python"], queries["python"], "python")
        exports, imports = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check exports
        export_symbols = {exp.symbol for exp in exports}

        # Should include top-level functions and classes
        assert "public_function" in export_symbols
        assert "PublicClass" in export_symbols
        assert "_private_function" in export_symbols  # Even private ones are technically exportable
        assert "_PrivateClass" in export_symbols

        # Check export types
        func_exports = [exp for exp in exports if exp.export_type == "function"]
        class_exports = [exp for exp in exports if exp.export_type == "class"]

        assert len(func_exports) == 2
        assert len(class_exports) == 2

        # Check __all__ re-exports
        reexports = [exp for exp in exports if exp.is_reexport]
        assert len(reexports) == 2
        assert all(exp.symbol in ["public_function", "PublicClass"] for exp in reexports)

    def test_circular_dependency_detection(self, parsers_and_queries):
        """Test circular dependency detection."""
        parsers, queries = parsers_and_queries

        # Create a mock dependency graph with cycles
        module_deps = {
            "module_a": {"module_b", "module_c"},
            "module_b": {"module_c", "module_d"},
            "module_c": {"module_a"},  # Creates cycle: a -> c -> a
            "module_d": {"module_e"},
            "module_e": {"module_d"},  # Creates cycle: d -> e -> d
            "module_f": {"module_g"},
            "module_g": {"module_h"},
            "module_h": {"module_f"},  # Creates cycle: f -> g -> h -> f
        }

        analyzer = DependencyAnalyzer(None, {}, "")
        cycles = analyzer.detect_circular_dependencies(module_deps)

        # Should find 3 cycles
        assert len(cycles) == 3

        # Verify specific cycles exist (order may vary)
        cycle_sets = [set(cycle[:-1]) for cycle in cycles]  # Remove duplicate last element

        # The a->c->a cycle might be detected as a->b->c->a or a->c->a
        assert any({"module_a", "module_c"}.issubset(s) for s in cycle_sets)
        assert {"module_d", "module_e"} in cycle_sets
        assert {"module_f", "module_g", "module_h"} in cycle_sets

    def test_python_relative_imports(self, parsers_and_queries):
        """Test Python relative import handling."""
        parsers, queries = parsers_and_queries

        python_code = '''
from . import sibling
from .. import parent
from ...package import cousin
from ..utils.helpers import utility_func
'''

        analyzer = DependencyAnalyzer(parsers["python"], queries["python"], "python")
        exports, imports = analyzer.analyze_file("test.py", python_code, "package.subpackage.module")

        # Check relative imports
        relative_imports = [imp for imp in imports if imp.source_module.startswith(".")]
        assert len(relative_imports) == 4

        # Check different relative levels
        import_modules = {imp.source_module for imp in imports}
        assert "." in import_modules  # Same package
        assert ".." in import_modules  # Parent package
        assert "...package" in import_modules  # Grandparent package with module
        assert "..utils.helpers" in import_modules  # Parent package subdirectory

    def test_python_star_imports(self, parsers_and_queries):
        """Test Python star import handling."""
        parsers, queries = parsers_and_queries

        python_code = '''
from module import *
from package.submodule import *
'''

        analyzer = DependencyAnalyzer(parsers["python"], queries["python"], "python")
        exports, imports = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check star imports
        star_imports = [imp for imp in imports if imp.symbol == "*"]
        assert len(star_imports) == 2

        # Star imports should be marked as namespace type
        assert all(imp.import_type == "namespace" for imp in star_imports)

    def test_javascript_placeholder(self, parsers_and_queries):
        """Test JavaScript dependency analysis placeholder."""
        parsers, queries = parsers_and_queries

        if "javascript" not in parsers:
            pytest.skip("JavaScript parser not available")

        js_code = '''
import React from 'react';
import { Component } from 'react';
import * as utils from './utils';
const fs = require('fs');
export default class MyComponent extends Component {}
export const helper = () => {};
'''

        analyzer = DependencyAnalyzer(parsers["javascript"], queries["javascript"], "javascript")
        exports, imports = analyzer.analyze_file("test.js", js_code, "test_module")

        # For now, just verify it doesn't crash
        assert isinstance(exports, list)
        assert isinstance(imports, list)
