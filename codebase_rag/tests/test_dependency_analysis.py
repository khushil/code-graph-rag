"""Tests for enhanced dependency analysis."""

from unittest.mock import MagicMock

import pytest

from codebase_rag.analysis.dependencies import (
    DependencyAnalyzer,
    DependencyInfo,
    Export,
    Import,
)


class TestDependencyAnalyzer:
    """Test the enhanced dependency analysis functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create a dependency analyzer."""
        parser = MagicMock()
        queries = {"imports": MagicMock(), "functions": MagicMock(), "classes": MagicMock()}
        return DependencyAnalyzer(parser, queries, "python")

    def test_export_dataclass(self):
        """Test Export dataclass."""
        export = Export(
            symbol="my_function",
            export_type="function",
            line_number=10,
            is_default=False,
            is_reexport=False,
            source_module=None,
        )
        
        assert export.symbol == "my_function"
        assert export.export_type == "function"
        assert export.line_number == 10
        assert not export.is_default
        assert not export.is_reexport

    def test_import_dataclass(self):
        """Test Import dataclass."""
        imp = Import(
            symbol="datetime",
            source_module="datetime",
            import_type="named",
            line_number=1,
            alias=None,
            is_type_only=False,
        )
        
        assert imp.symbol == "datetime"
        assert imp.source_module == "datetime"
        assert imp.import_type == "named"
        assert imp.line_number == 1
        assert imp.alias is None
        assert not imp.is_type_only

    def test_dependency_info_dataclass(self):
        """Test DependencyInfo dataclass."""
        exports = [Export("func1", "function", 10)]
        imports = [Import("func2", "other_module", "named", 1)]
        
        dep_info = DependencyInfo(
            module_path="my_module",
            exports=exports,
            imports=imports,
            dependencies={"other_module"},
            dependents=set(),
        )
        
        assert dep_info.module_path == "my_module"
        assert len(dep_info.exports) == 1
        assert len(dep_info.imports) == 1
        assert "other_module" in dep_info.dependencies

    def test_circular_dependency_detection(self, analyzer):
        """Test detecting circular dependencies."""
        # Create a circular dependency graph
        module_deps = {
            "module_a": {"module_b"},
            "module_b": {"module_c"},
            "module_c": {"module_a"},  # Creates cycle
            "module_d": {"module_e"},
            "module_e": set(),
        }
        
        cycles = analyzer.detect_circular_dependencies(module_deps)
        
        assert len(cycles) == 1
        cycle = cycles[0]
        assert len(cycle) == 4  # Includes the starting node twice to show the cycle
        assert cycle[0] == cycle[-1]  # Should start and end with same node
        assert set(cycle[:-1]) == {"module_a", "module_b", "module_c"}

    def test_no_circular_dependencies(self, analyzer):
        """Test when there are no circular dependencies."""
        module_deps = {
            "module_a": {"module_b", "module_c"},
            "module_b": {"module_d"},
            "module_c": {"module_d"},
            "module_d": set(),
        }
        
        cycles = analyzer.detect_circular_dependencies(module_deps)
        assert len(cycles) == 0

    def test_build_dependency_graph(self, analyzer):
        """Test building dependency graph with EXPORTS and REQUIRES edges."""
        # Create module info
        module_info = {
            "module_a": DependencyInfo(
                module_path="module_a",
                exports=[
                    Export("func_a", "function", 10),
                    Export("ClassA", "class", 20),
                ],
                imports=[
                    Import("func_b", "module_b", "named", 1),
                ],
                dependencies={"module_b"},
                dependents=set(),
            ),
            "module_b": DependencyInfo(
                module_path="module_b",
                exports=[
                    Export("func_b", "function", 5),
                ],
                imports=[],
                dependencies=set(),
                dependents={"module_a"},
            ),
        }
        
        nodes, relationships = analyzer.build_dependency_graph(module_info)
        
        # Check Export nodes
        assert len(nodes) == 3  # 2 from module_a, 1 from module_b
        export_nodes = [n for n in nodes if n["label"] == "Export"]
        assert len(export_nodes) == 3
        
        # Check EXPORTS relationships
        exports_rels = [r for r in relationships if r["rel_type"] == "EXPORTS"]
        assert len(exports_rels) == 3
        
        # Check REQUIRES relationships
        requires_rels = [r for r in relationships if r["rel_type"] == "REQUIRES"]
        assert len(requires_rels) == 1
        assert requires_rels[0]["start_value"] == "module_a"
        assert requires_rels[0]["end_value"] == "module_b"
        
        # Check IMPORTS relationships
        imports_rels = [r for r in relationships if r["rel_type"] == "IMPORTS"]
        assert len(imports_rels) == 1
        assert imports_rels[0]["end_value"] == "module_b.func_b"

    def test_generate_dependency_report(self, analyzer):
        """Test generating dependency report."""
        module_info = {
            "module_a": DependencyInfo(
                module_path="module_a",
                exports=[Export("func_a", "function", 10)],
                imports=[Import("func_b", "module_b", "named", 1)],
                dependencies={"module_b", "module_c"},
                dependents=set(),
            ),
            "module_b": DependencyInfo(
                module_path="module_b",
                exports=[Export("func_b", "function", 5)],
                imports=[],
                dependencies=set(),
                dependents={"module_a"},
            ),
            "module_c": DependencyInfo(
                module_path="module_c",
                exports=[Export("func_c", "function", 3)],  # Unused export
                imports=[],
                dependencies=set(),
                dependents={"module_a"},
            ),
        }
        
        report = analyzer.generate_dependency_report(module_info)
        
        assert report["total_modules"] == 3
        assert report["total_exports"] == 3
        assert report["total_imports"] == 1
        assert len(report["circular_dependencies"]) == 0
        
        # Check most depended on
        assert len(report["most_depended_on"]) >= 2
        most_depended = report["most_depended_on"][0]
        assert most_depended["module"] in ["module_b", "module_c"]
        assert most_depended["dependent_count"] == 1
        
        # Check modules with most dependencies
        assert len(report["most_dependencies"]) >= 1
        most_deps = report["most_dependencies"][0]
        assert most_deps["module"] == "module_a"
        assert most_deps["dependency_count"] == 2
        
        # Check unused exports
        assert len(report["unused_exports"]) == 2  # func_a is also unused (no imports)
        unused_symbols = {(u["module"], u["symbol"]) for u in report["unused_exports"]}
        assert ("module_a", "func_a") in unused_symbols
        assert ("module_c", "func_c") in unused_symbols

    def test_wildcard_imports(self, analyzer):
        """Test handling of wildcard imports (import *)."""
        module_info = {
            "module_a": DependencyInfo(
                module_path="module_a",
                exports=[],
                imports=[Import("*", "module_b", "namespace", 1)],
                dependencies={"module_b"},
                dependents=set(),
            ),
            "module_b": DependencyInfo(
                module_path="module_b",
                exports=[
                    Export("func1", "function", 5),
                    Export("func2", "function", 10),
                ],
                imports=[],
                dependencies=set(),
                dependents={"module_a"},
            ),
        }
        
        nodes, relationships = analyzer.build_dependency_graph(module_info)
        
        # Should create REQUIRES but not specific IMPORTS for wildcard
        requires_rels = [r for r in relationships if r["rel_type"] == "REQUIRES"]
        assert len(requires_rels) == 1
        assert requires_rels[0]["properties"]["symbol"] == "*"
        
        imports_rels = [r for r in relationships if r["rel_type"] == "IMPORTS"]
        assert len(imports_rels) == 0  # No specific imports for wildcard