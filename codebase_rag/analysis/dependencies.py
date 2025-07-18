"""Enhanced dependency analysis for tracking module relationships and detecting issues."""

from dataclasses import dataclass
from typing import Any

from loguru import logger
from tree_sitter import Node


@dataclass
class Export:
    """Represents an exported symbol from a module."""
    symbol: str  # Name of the exported symbol
    export_type: str  # "function", "class", "variable", "default", "namespace"
    line_number: int
    is_default: bool = False
    is_reexport: bool = False
    source_module: str | None = None  # For re-exports


@dataclass
class Import:
    """Represents an imported symbol in a module."""
    symbol: str  # Name of the imported symbol (or "*" for import all)
    source_module: str  # Module path being imported from
    import_type: str  # "named", "default", "namespace", "side_effect"
    line_number: int
    alias: str | None = None  # If imported with alias (import X as Y)
    is_type_only: bool = False  # TypeScript type imports


@dataclass
class DependencyInfo:
    """Complete dependency information for a module."""
    module_path: str
    exports: list[Export]
    imports: list[Import]
    dependencies: set[str]  # Set of all modules this module depends on
    dependents: set[str]  # Set of all modules that depend on this module


class DependencyAnalyzer:
    """Analyzes module dependencies, exports, and imports."""

    def __init__(self, parser, queries: dict, language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self._source_lines: list[str] = []

    def analyze_file(self, file_path: str, content: str, module_qn: str) -> tuple[list[Export], list[Import]]:
        """Analyze dependencies in a file."""
        self._source_lines = content.split("\n")

        # Parse the file
        tree = self.parser.parse(content.encode("utf-8"))
        root_node = tree.root_node

        exports = []
        imports = []

        # Analyze based on language
        if self.language == "python":
            exports, imports = self._analyze_python(root_node, module_qn)
        elif self.language in ["javascript", "typescript"]:
            exports, imports = self._analyze_javascript(root_node, module_qn)
        elif self.language == "c":
            exports, imports = self._analyze_c(root_node, module_qn)
        else:
            logger.warning(f"Dependency analysis not implemented for {self.language}")

        return exports, imports

    def _analyze_python(self, root_node: Node, module_qn: str) -> tuple[list[Export], list[Import]]:
        """Analyze Python imports and exports."""
        exports = []
        imports = []

        # Find all imports
        import_query = """
        [
            (import_statement) @import
            (import_from_statement) @import_from
        ]
        """

        if self.language == "python" and self.parser:
            try:
                query = self.parser.language.query(import_query)
                captures = query.captures(root_node)

                # Process import statements
                for node in captures.get("import", []):
                    imports.extend(self._process_python_import(node))

                # Process import_from statements
                for node in captures.get("import_from", []):
                    imports.extend(self._process_python_import_from(node))
            except Exception as e:
                logger.error(f"Error parsing Python imports: {e}")

        # Find exports (functions, classes at module level)
        if "functions" in self.queries:
            func_captures = self.queries["functions"].captures(root_node)
            for node in func_captures.get("function", []):
                # Check if it's a top-level function
                if self._is_top_level(node):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        export = Export(
                            symbol=self._get_node_text(name_node),
                            export_type="function",
                            line_number=node.start_point[0] + 1
                        )
                        exports.append(export)

        if "classes" in self.queries:
            class_captures = self.queries["classes"].captures(root_node)
            for node in class_captures.get("class", []):
                # Check if it's a top-level class
                if self._is_top_level(node):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        export = Export(
                            symbol=self._get_node_text(name_node),
                            export_type="class",
                            line_number=node.start_point[0] + 1
                        )
                        exports.append(export)

        # Check for __all__ exports
        all_exports = self._find_python_all_exports(root_node)
        exports.extend(all_exports)

        return exports, imports

    def _process_python_import(self, node: Node) -> list[Import]:
        """Process Python import statement."""
        imports = []

        # import module1, module2 as alias
        for child in node.children:
            if child.type == "dotted_name" or child.type == "aliased_import":
                if child.type == "aliased_import":
                    # import module as alias
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if name_node:
                        module_name = self._get_node_text(name_node)
                        alias = self._get_node_text(alias_node) if alias_node else None
                        imports.append(Import(
                            symbol=module_name.split(".")[-1],
                            source_module=module_name,
                            import_type="namespace",
                            line_number=node.start_point[0] + 1,
                            alias=alias
                        ))
                else:
                    # import module
                    module_name = self._get_node_text(child)
                    imports.append(Import(
                        symbol=module_name.split(".")[-1],
                        source_module=module_name,
                        import_type="namespace",
                        line_number=node.start_point[0] + 1
                    ))

        return imports

    def _process_python_import_from(self, node: Node) -> list[Import]:
        """Process Python from...import statement."""
        imports = []

        # from module import name1, name2 as alias
        module_node = node.child_by_field_name("module_name")
        module_name = ""

        # Check for relative imports first
        level = 0
        for child in node.children:
            if child.type == "relative_import":
                # Count dots in import_prefix
                for subchild in child.children:
                    if subchild.type == "import_prefix":
                        level = subchild.text.decode().count(".")
                    elif subchild.type == "dotted_name":
                        module_name = self._get_node_text(subchild)
                break

        if level > 0:
            # Relative import
            module_name = "." * level + module_name
        elif module_node:
            # Absolute import
            module_name = self._get_node_text(module_node)
        else:
            # Might be "from . import X" with no module
            if not module_name:
                # Check if it's a bare relative import
                for child in node.children:
                    if child.type == "relative_import":
                        for subchild in child.children:
                            if subchild.type == "import_prefix":
                                module_name = subchild.text.decode()

        # Find imported names - they come after "import" keyword
        found_import = False
        for child in node.children:
            if child.type == "import":
                found_import = True
                continue

            if found_import and child.type in ["dotted_name", "identifier"]:
                imports.append(Import(
                    symbol=self._get_node_text(child),
                    source_module=module_name,
                    import_type="named",
                    line_number=node.start_point[0] + 1
                ))
            elif found_import and child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    imports.append(Import(
                        symbol=self._get_node_text(name_node),
                        source_module=module_name,
                        import_type="named",
                        line_number=node.start_point[0] + 1,
                        alias=self._get_node_text(alias_node) if alias_node else None
                    ))
            elif found_import and child.type == "wildcard_import":
                imports.append(Import(
                    symbol="*",
                    source_module=module_name,
                    import_type="namespace",
                    line_number=node.start_point[0] + 1
                ))

        return imports

    def _find_python_all_exports(self, root_node: Node) -> list[Export]:
        """Find __all__ exports in Python."""
        exports = []

        # Look for __all__ = [...]
        assignment_query = """
        (assignment
            left: (identifier) @name
            right: (list) @value
        ) @assignment
        """

        try:
            query = self.parser.language.query(assignment_query)
            captures = query.captures(root_node)

            for node in captures.get("name", []):
                if self._get_node_text(node) == "__all__":
                        # Found __all__, get the list
                        parent = node.parent
                        if parent and parent.type == "assignment":
                            right = parent.child_by_field_name("right")
                            if right and right.type == "list":
                                # Extract string literals from list
                                for child in right.children:
                                    if child.type == "string":
                                        # Remove quotes
                                        symbol = self._get_node_text(child).strip("\"'")
                                        exports.append(Export(
                                            symbol=symbol,
                                            export_type="variable",
                                            line_number=node.start_point[0] + 1,
                                            is_reexport=True
                                        ))
        except Exception as e:
            logger.error(f"Error finding __all__ exports: {e}")

        return exports

    def _analyze_javascript(self, root_node: Node, module_qn: str) -> tuple[list[Export], list[Import]]:
        """Analyze JavaScript/TypeScript imports and exports."""
        exports = []
        imports = []

        # ES6 imports and exports
        # TODO: Implement import_export_query when JavaScript analysis is added
        # import_export_query = """
        # [
        #     (import_statement) @import
        #     (export_statement) @export
        # ]
        # """

        # CommonJS patterns
        # TODO: Implement commonjs_query when JavaScript analysis is added
        # commonjs_query = """
        # [
        #     (call_expression
        #         function: (identifier) @func
        #         arguments: (arguments (string) @module)
        #     ) @require
        #     (assignment_expression
        #         left: (member_expression
        #             object: (identifier) @obj
        #             property: (property_identifier) @prop
        #         )
        #         right: (_) @value
        #     ) @exports_assign
        # ]
        # """

        # TODO: Implement JavaScript/TypeScript dependency analysis
        logger.info("JavaScript/TypeScript dependency analysis not yet implemented")

        return exports, imports

    def _analyze_c(self, root_node: Node, module_qn: str) -> tuple[list[Export], list[Import]]:
        """Analyze C includes and header exports."""
        exports = []
        imports = []

        # C includes
        # TODO: Implement include_query when C analysis is added
        # include_query = """
        # (preproc_include
        #     path: (_) @path
        # ) @include
        # """

        # Function declarations (in headers)
        # TODO: Implement declaration_query when C analysis is added
        # declaration_query = """
        # (declaration
        #     declarator: (function_declarator) @func_decl
        # ) @declaration
        # """

        # TODO: Implement C dependency analysis
        logger.info("C dependency analysis not yet implemented")

        return exports, imports

    def detect_circular_dependencies(self, module_deps: dict[str, set[str]]) -> list[list[str]]:
        """Detect circular dependencies in the module graph."""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(module: str, path: list[str]) -> None:
            visited.add(module)
            rec_stack.add(module)
            path.append(module)

            for dep in module_deps.get(module, set()):
                if dep not in visited:
                    dfs(dep, path.copy())
                elif dep in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(module)

        for module in module_deps:
            if module not in visited:
                dfs(module, [])

        # Remove duplicate cycles
        unique_cycles = []
        for cycle in cycles:
            # Normalize cycle to start with smallest element
            min_idx = cycle.index(min(cycle))
            normalized = cycle[min_idx:] + cycle[:min_idx]
            if normalized not in unique_cycles:
                unique_cycles.append(normalized)

        return unique_cycles

    def _is_top_level(self, node: Node) -> bool:
        """Check if a node is at the top level of the module."""
        parent = node.parent
        while parent:
            if parent.type in ["function_definition", "class_definition"]:
                return False
            parent = parent.parent
        return True

    def _get_node_text(self, node: Node) -> str:
        """Get text content of a node."""
        start_line = node.start_point[0]
        start_col = node.start_point[1]
        end_line = node.end_point[0]
        end_col = node.end_point[1]

        if start_line == end_line:
            return self._source_lines[start_line][start_col:end_col]
        else:
            # Multi-line node
            lines = []
            lines.append(self._source_lines[start_line][start_col:])
            for i in range(start_line + 1, end_line):
                lines.append(self._source_lines[i])
            lines.append(self._source_lines[end_line][:end_col])
            return "\n".join(lines)
    
    def build_dependency_graph(
        self, module_info: dict[str, DependencyInfo]
    ) -> tuple[list[dict], list[dict]]:
        """Build graph nodes and relationships for module dependencies."""
        nodes = []
        relationships = []
        
        # Create Export nodes for each module's exports
        for module_path, info in module_info.items():
            for export in info.exports:
                export_node = {
                    "label": "Export",
                    "properties": {
                        "symbol": export.symbol,
                        "module": module_path,
                        "export_type": export.export_type,
                        "line_number": export.line_number,
                        "is_default": export.is_default,
                        "is_reexport": export.is_reexport,
                        "qualified_name": f"{module_path}.{export.symbol}",
                    },
                }
                nodes.append(export_node)
                
                # Create EXPORTS relationship from Module to Export
                exports_rel = {
                    "start_label": "Module",
                    "start_key": "qualified_name",
                    "start_value": module_path,
                    "rel_type": "EXPORTS",
                    "end_label": "Export",
                    "end_key": "qualified_name",
                    "end_value": f"{module_path}.{export.symbol}",
                    "properties": {
                        "export_type": export.export_type,
                        "line_number": export.line_number,
                    },
                }
                relationships.append(exports_rel)
        
        # Create REQUIRES relationships based on imports
        for module_path, info in module_info.items():
            for imp in info.imports:
                # Try to find the exported symbol in the source module
                source_info = module_info.get(imp.source_module)
                if source_info:
                    # Check if the imported symbol is exported
                    matching_export = None
                    for export in source_info.exports:
                        if export.symbol == imp.symbol or imp.symbol == "*":
                            matching_export = export
                            break
                    
                    if matching_export or imp.symbol == "*":
                        # Create REQUIRES relationship
                        requires_rel = {
                            "start_label": "Module",
                            "start_key": "qualified_name", 
                            "start_value": module_path,
                            "rel_type": "REQUIRES",
                            "end_label": "Module",
                            "end_key": "qualified_name",
                            "end_value": imp.source_module,
                            "properties": {
                                "symbol": imp.symbol,
                                "import_type": imp.import_type,
                                "line_number": imp.line_number,
                                "alias": imp.alias,
                            },
                        }
                        relationships.append(requires_rel)
                        
                        # If specific symbol, create IMPORTS relationship to Export
                        if imp.symbol != "*" and matching_export:
                            imports_rel = {
                                "start_label": "Module",
                                "start_key": "qualified_name",
                                "start_value": module_path,
                                "rel_type": "IMPORTS",
                                "end_label": "Export",
                                "end_key": "qualified_name",
                                "end_value": f"{imp.source_module}.{imp.symbol}",
                                "properties": {
                                    "alias": imp.alias,
                                    "line_number": imp.line_number,
                                },
                            }
                            relationships.append(imports_rel)
        
        return nodes, relationships
    
    def generate_dependency_report(
        self, module_info: dict[str, DependencyInfo]
    ) -> dict[str, Any]:
        """Generate a comprehensive dependency report."""
        report = {
            "total_modules": len(module_info),
            "total_exports": sum(len(info.exports) for info in module_info.values()),
            "total_imports": sum(len(info.imports) for info in module_info.values()),
            "circular_dependencies": [],
            "most_depended_on": [],
            "most_dependencies": [],
            "unused_exports": [],
        }
        
        # Build dependency graph for analysis
        module_deps = {
            module: info.dependencies for module, info in module_info.items()
        }
        
        # Detect circular dependencies
        cycles = self.detect_circular_dependencies(module_deps)
        report["circular_dependencies"] = cycles
        
        # Find most depended on modules
        dependency_counts = {}
        for info in module_info.values():
            for dep in info.dependencies:
                dependency_counts[dep] = dependency_counts.get(dep, 0) + 1
        
        most_depended = sorted(
            dependency_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
        report["most_depended_on"] = [
            {"module": mod, "dependent_count": count} for mod, count in most_depended
        ]
        
        # Find modules with most dependencies
        most_deps = sorted(
            [(mod, len(info.dependencies)) for mod, info in module_info.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        report["most_dependencies"] = [
            {"module": mod, "dependency_count": count} for mod, count in most_deps
        ]
        
        # Find potentially unused exports
        all_imports = set()
        for info in module_info.values():
            for imp in info.imports:
                if imp.symbol != "*":
                    all_imports.add(f"{imp.source_module}.{imp.symbol}")
        
        unused = []
        for module, info in module_info.items():
            for export in info.exports:
                qualified_name = f"{module}.{export.symbol}"
                if qualified_name not in all_imports and not export.is_default:
                    unused.append({
                        "module": module,
                        "symbol": export.symbol,
                        "type": export.export_type,
                        "line": export.line_number,
                    })
        
        report["unused_exports"] = unused[:20]  # Limit to top 20
        
        return report
