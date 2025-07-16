"""Enhanced dependency analysis for tracking module relationships and detecting issues."""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
from tree_sitter import Node
from loguru import logger


@dataclass
class Export:
    """Represents an exported symbol from a module."""
    symbol: str  # Name of the exported symbol
    export_type: str  # "function", "class", "variable", "default", "namespace"
    line_number: int
    is_default: bool = False
    is_reexport: bool = False
    source_module: Optional[str] = None  # For re-exports


@dataclass 
class Import:
    """Represents an imported symbol in a module."""
    symbol: str  # Name of the imported symbol (or "*" for import all)
    source_module: str  # Module path being imported from
    import_type: str  # "named", "default", "namespace", "side_effect"
    line_number: int
    alias: Optional[str] = None  # If imported with alias (import X as Y)
    is_type_only: bool = False  # TypeScript type imports


@dataclass
class DependencyInfo:
    """Complete dependency information for a module."""
    module_path: str
    exports: List[Export]
    imports: List[Import]
    dependencies: Set[str]  # Set of all modules this module depends on
    dependents: Set[str]  # Set of all modules that depend on this module


class DependencyAnalyzer:
    """Analyzes module dependencies, exports, and imports."""
    
    def __init__(self, parser, queries: Dict, language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self._source_lines: List[str] = []
        
    def analyze_file(self, file_path: str, content: str, module_qn: str) -> Tuple[List[Export], List[Import]]:
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
    
    def _analyze_python(self, root_node: Node, module_qn: str) -> Tuple[List[Export], List[Import]]:
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
    
    def _process_python_import(self, node: Node) -> List[Import]:
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
    
    def _process_python_import_from(self, node: Node) -> List[Import]:
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
    
    def _find_python_all_exports(self, root_node: Node) -> List[Export]:
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
    
    def _analyze_javascript(self, root_node: Node, module_qn: str) -> Tuple[List[Export], List[Import]]:
        """Analyze JavaScript/TypeScript imports and exports."""
        exports = []
        imports = []
        
        # ES6 imports and exports
        import_export_query = """
        [
            (import_statement) @import
            (export_statement) @export
        ]
        """
        
        # CommonJS patterns
        commonjs_query = """
        [
            (call_expression
                function: (identifier) @func
                arguments: (arguments (string) @module)
            ) @require
            (assignment_expression
                left: (member_expression
                    object: (identifier) @obj
                    property: (property_identifier) @prop
                )
                right: (_) @value
            ) @exports_assign
        ]
        """
        
        # TODO: Implement JavaScript/TypeScript dependency analysis
        logger.info("JavaScript/TypeScript dependency analysis not yet implemented")
        
        return exports, imports
    
    def _analyze_c(self, root_node: Node, module_qn: str) -> Tuple[List[Export], List[Import]]:
        """Analyze C includes and header exports."""
        exports = []
        imports = []
        
        # C includes
        include_query = """
        (preproc_include
            path: (_) @path
        ) @include
        """
        
        # Function declarations (in headers)
        declaration_query = """
        (declaration
            declarator: (function_declarator) @func_decl
        ) @declaration
        """
        
        # TODO: Implement C dependency analysis
        logger.info("C dependency analysis not yet implemented")
        
        return exports, imports
    
    def detect_circular_dependencies(self, module_deps: Dict[str, Set[str]]) -> List[List[str]]:
        """Detect circular dependencies in the module graph."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(module: str, path: List[str]) -> None:
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