"""Data flow analysis for tracking variable flows and modifications (REQ-DF-1, REQ-DF-2)."""

from dataclasses import dataclass
from typing import Any

from loguru import logger
from tree_sitter import Node


@dataclass
class VariableNode:
    """Represents a variable in the code (REQ-DF-1)."""
    name: str
    qualified_name: str
    var_type: str  # local, global, parameter, field
    declared_at: int  # line number
    scope: str  # function/class qualified name
    is_mutable: bool = True
    initial_value: str | None = None
    language: str = "python"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for graph storage."""
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "var_type": self.var_type,
            "declared_at": self.declared_at,
            "scope": self.scope,
            "is_mutable": self.is_mutable,
            "initial_value": self.initial_value or "",
            "language": self.language,
        }


@dataclass
class FlowEdge:
    """Represents data flow between variables/functions (REQ-DF-2)."""
    source: str  # qualified name
    target: str  # qualified name
    flow_type: str  # "assigns", "reads", "modifies", "passes_to", "returns_from"
    line_number: int
    confidence: float = 1.0  # For uncertain flows

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for graph storage."""
        return {
            "flow_type": self.flow_type,
            "line_number": self.line_number,
            "confidence": self.confidence,
        }


class DataFlowAnalyzer:
    """Analyzes data flow in code to track variable usage and modifications."""

    def __init__(self, parser, queries: dict[str, Any], language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self.variables: dict[str, VariableNode] = {}
        self.flows: list[FlowEdge] = []
        self._current_scope = ""
        self._source_lines: list[str] = []

    def analyze_file(self, file_path: str, content: str, module_qn: str) -> tuple[list[VariableNode], list[FlowEdge]]:
        """Analyze data flow in a file."""
        self.variables.clear()
        self.flows.clear()
        self._source_lines = content.split("\n")

        # Parse the file
        tree = self.parser.parse(content.encode("utf-8"))
        root_node = tree.root_node

        # Analyze based on language
        if self.language == "python":
            self._analyze_python(root_node, module_qn)
        elif self.language == "javascript" or self.language == "typescript":
            self._analyze_javascript(root_node, module_qn)
        elif self.language == "c":
            self._analyze_c(root_node, module_qn)
        else:
            logger.warning(f"Data flow analysis not implemented for {self.language}")

        return list(self.variables.values()), self.flows

    def _analyze_python(self, root_node: Node, module_qn: str) -> None:
        """Analyze Python data flow."""
        # Find all assignments
        if "assignments" in self.queries:
            query = self.queries["assignments"]
            captures = query.captures(root_node)

            # Process all assignment nodes
            assignment_nodes = captures.get("assignment", [])
            for node in assignment_nodes:
                self._process_python_assignment(node, module_qn)

        # Find all function definitions to track parameters
        if "functions" in self.queries:
            query = self.queries["functions"]
            captures = query.captures(root_node)

            function_nodes = captures.get("function", [])
            for node in function_nodes:
                self._process_python_function(node, module_qn)

        # Find all class definitions to track fields
        if "classes" in self.queries:
            query = self.queries["classes"]
            captures = query.captures(root_node)

            class_nodes = captures.get("class", [])
            for node in class_nodes:
                self._process_python_class(node, module_qn)

    def _process_python_assignment(self, node: Node, module_qn: str) -> None:
        """Process Python assignment statement."""
        # Get left side (target)
        left_node = node.child_by_field_name("left")
        right_node = node.child_by_field_name("right")

        if not left_node:
            return

        # Extract variable name
        var_name = self._get_node_text(left_node)
        line_number = left_node.start_point[0] + 1

        # Determine scope
        scope = self._find_enclosing_scope(node, module_qn)

        # Create variable node
        var_qn = f"{scope}.{var_name}"
        var_type = "local" if scope != module_qn else "global"

        if var_name not in self.variables:
            initial_value = self._get_node_text(right_node) if right_node else None
            var_node = VariableNode(
                name=var_name,
                qualified_name=var_qn,
                var_type=var_type,
                declared_at=line_number,
                scope=scope,
                initial_value=initial_value,
                language="python"
            )
            self.variables[var_qn] = var_node

        # Analyze right side for data flow
        if right_node:
            self._analyze_expression_flow(right_node, var_qn, "assigns", line_number)

    def _process_python_function(self, node: Node, module_qn: str) -> None:
        """Process Python function definition for parameters."""
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")

        if not name_node:
            return

        func_name = self._get_node_text(name_node)
        func_qn = f"{module_qn}.{func_name}"

        # Process parameters
        if params_node:
            for child in params_node.children:
                if child.type in ["identifier", "typed_parameter"]:
                    param_name = self._extract_parameter_name(child)
                    if param_name:
                        param_qn = f"{func_qn}.{param_name}"
                        param_node = VariableNode(
                            name=param_name,
                            qualified_name=param_qn,
                            var_type="parameter",
                            declared_at=child.start_point[0] + 1,
                            scope=func_qn,
                            language="python"
                        )
                        self.variables[param_qn] = param_node

        # Analyze function body
        body_node = node.child_by_field_name("body")
        if body_node:
            self._analyze_block_flow(body_node, module_qn, func_qn)

    def _process_python_class(self, node: Node, module_qn: str) -> None:
        """Process Python class definition for fields."""
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")

        if not name_node:
            return

        class_name = self._get_node_text(name_node)
        class_qn = f"{module_qn}.{class_name}"

        # Look for field assignments in __init__ or class body
        if body_node:
            for child in body_node.children:
                if child.type == "function_definition":
                    func_name_node = child.child_by_field_name("name")
                    if func_name_node and self._get_node_text(func_name_node) == "__init__":
                        # Analyze __init__ for self.field assignments
                        self._analyze_init_method(child, class_qn)
                elif child.type == "expression_statement":
                    # Class-level field assignments
                    self._process_class_field(child, class_qn)

    def _analyze_init_method(self, node: Node, class_qn: str) -> None:
        """Analyze __init__ method for instance variable declarations."""
        body_node = node.child_by_field_name("body")
        if not body_node:
            return

        for child in body_node.children:
            if child.type == "expression_statement":
                expr = child.children[0] if child.children else None
                if expr and expr.type == "assignment":
                    left = expr.child_by_field_name("left")
                    if left and left.type == "attribute":
                        obj = left.child_by_field_name("object")
                        attr = left.child_by_field_name("attribute")

                        if obj and attr and self._get_node_text(obj) == "self":
                            field_name = self._get_node_text(attr)
                            field_qn = f"{class_qn}.{field_name}"

                            field_node = VariableNode(
                                name=field_name,
                                qualified_name=field_qn,
                                var_type="field",
                                declared_at=left.start_point[0] + 1,
                                scope=class_qn,
                                language="python"
                            )
                            self.variables[field_qn] = field_node

                            # Analyze right side for flow
                            right = expr.child_by_field_name("right")
                            if right:
                                self._analyze_expression_flow(
                                    right, field_qn, "assigns",
                                    left.start_point[0] + 1
                                )

    def _analyze_expression_flow(self, expr_node: Node, target_var: str, flow_type: str, line_number: int) -> None:
        """Analyze an expression for data flow relationships."""
        if expr_node.type == "identifier":
            # Direct variable reference
            var_name = self._get_node_text(expr_node)
            source_var = self._resolve_variable(var_name)
            if source_var:
                flow = FlowEdge(
                    source=source_var,
                    target=target_var,
                    flow_type=flow_type,
                    line_number=line_number
                )
                self.flows.append(flow)

        elif expr_node.type == "call":
            # Function call
            func_node = expr_node.child_by_field_name("function")
            if func_node:
                func_name = self._get_node_text(func_node)
                # Track flow from function return
                flow = FlowEdge(
                    source=f"return_of_{func_name}",
                    target=target_var,
                    flow_type="returns_from",
                    line_number=line_number
                )
                self.flows.append(flow)

            # Analyze arguments for flows
            args_node = expr_node.child_by_field_name("arguments")
            if args_node:
                for arg in args_node.children:
                    if arg.type not in ["(", ")", ","]:
                        self._analyze_expression_flow(arg, f"param_of_{func_name}", "passes_to", line_number)

        elif expr_node.type == "binary_operator":
            # Binary operations
            left = expr_node.child_by_field_name("left")
            right = expr_node.child_by_field_name("right")

            if left:
                self._analyze_expression_flow(left, target_var, "reads", line_number)
            if right:
                self._analyze_expression_flow(right, target_var, "reads", line_number)

        elif expr_node.type == "attribute":
            # Attribute access (e.g., obj.field)
            obj = expr_node.child_by_field_name("object")
            attr = expr_node.child_by_field_name("attribute")

            if obj and attr:
                obj_name = self._get_node_text(obj)
                attr_name = self._get_node_text(attr)
                # Try to resolve the field
                field_var = self._resolve_field(obj_name, attr_name)
                if field_var:
                    flow = FlowEdge(
                        source=field_var,
                        target=target_var,
                        flow_type=flow_type,
                        line_number=line_number
                    )
                    self.flows.append(flow)

    def _analyze_javascript(self, root_node: Node, module_qn: str) -> None:
        """Analyze JavaScript/TypeScript data flow."""
        # Variable declarations (let, const, var)
        # TODO: Implement var_query when JavaScript analysis is added
        # var_query = """
        # [
        #     (variable_declaration) @vardecl
        #     (lexical_declaration) @lexdecl
        # ]
        # """

        # Function declarations and expressions
        # TODO: Implement func_query when JavaScript analysis is added
        # func_query = """
        # [
        #     (function_declaration) @function
        #     (arrow_function) @arrow
        #     (function_expression) @funcexpr
        # ]
        # """

        # TODO: Implement JavaScript-specific analysis
        logger.info("JavaScript data flow analysis not yet implemented")

    def _analyze_c(self, root_node: Node, module_qn: str) -> None:
        """Analyze C data flow including pointer operations."""
        # Global variables
        # TODO: Implement global_query when C analysis is added
        # global_query = """
        # (translation_unit
        #     (declaration
        #         declarator: [
        #             (identifier) @var_name
        #             (pointer_declarator
        #                 declarator: (identifier) @var_name)
        #             (array_declarator
        #                 declarator: (identifier) @var_name)
        #         ]
        #     ) @global_var
        # )
        # """

        # Local variables in functions
        # TODO: Implement local_query when C analysis is added
        # local_query = """
        # (function_definition
        #     body: (compound_statement
        #         (declaration
        #             declarator: [
        #                 (identifier) @var_name
        #                 (pointer_declarator
        #                     declarator: (identifier) @var_name)
        #                 (array_declarator
        #                     declarator: (identifier) @var_name)
        #             ]
        #         ) @local_var
        #     )
        # )
        # """

        # Assignments including pointer operations
        # TODO: Implement assign_query when C analysis is added
        # assign_query = """
        # [
        #     (assignment_expression
        #         left: (_) @lhs
        #         right: (_) @rhs
        #     ) @assignment
        #     (update_expression
        #         argument: (_) @var
        #     ) @update
        # ]
        # """

        # TODO: Implement C-specific analysis with pointer tracking
        logger.info("C data flow analysis not yet implemented")

    def _analyze_block_flow(self, block_node: Node, module_qn: str, scope: str) -> None:
        """Analyze flow within a code block."""
        # Save the current scope
        prev_scope = self._current_scope
        self._current_scope = scope

        for child in block_node.children:
            if child.type == "expression_statement":
                expr = child.children[0] if child.children else None
                if expr and expr.type == "assignment":
                    self._process_python_assignment(expr, module_qn)
            elif child.type in ["if_statement", "while_statement", "for_statement"]:
                # Recursively analyze control flow blocks
                for subchild in child.children:
                    if subchild.type in ["block", "compound_statement"]:
                        self._analyze_block_flow(subchild, module_qn, scope)

        # Restore the previous scope
        self._current_scope = prev_scope

    def _find_enclosing_scope(self, node: Node, default_scope: str) -> str:
        """Find the enclosing function or class scope."""
        current = node.parent
        while current:
            if current.type == "function_definition":
                name_node = current.child_by_field_name("name")
                if name_node:
                    return f"{default_scope}.{self._get_node_text(name_node)}"
            elif current.type == "class_definition":
                name_node = current.child_by_field_name("name")
                if name_node:
                    return f"{default_scope}.{self._get_node_text(name_node)}"
            current = current.parent
        return default_scope

    def _resolve_variable(self, var_name: str) -> str | None:
        """Resolve a variable name to its qualified name."""
        # Check current scope first
        if self._current_scope:
            local_qn = f"{self._current_scope}.{var_name}"
            if local_qn in self.variables:
                return local_qn

        # Check module scope
        for qn, var in self.variables.items():
            if var.name == var_name and (var.var_type == "global" or var.scope == self._current_scope):
                return qn

        return None

    def _resolve_field(self, obj_name: str, field_name: str) -> str | None:
        """Resolve object.field to qualified field name."""
        # This is simplified - real implementation would need type inference
        if obj_name == "self" and self._current_scope:
            # Extract class from method scope
            parts = self._current_scope.split(".")
            if len(parts) >= 2:
                class_qn = ".".join(parts[:-1])
                field_qn = f"{class_qn}.{field_name}"
                if field_qn in self.variables:
                    return field_qn
        return None

    def _extract_parameter_name(self, param_node: Node) -> str | None:
        """Extract parameter name from various parameter node types."""
        if param_node.type == "identifier":
            return self._get_node_text(param_node)
        elif param_node.type == "typed_parameter":
            # Handle type annotations
            for child in param_node.children:
                if child.type == "identifier":
                    return self._get_node_text(child)
        return None

    def _process_class_field(self, node: Node, class_qn: str) -> None:
        """Process class-level field assignment."""
        if node.children and node.children[0].type == "assignment":
            assign = node.children[0]
            left = assign.child_by_field_name("left")
            right = assign.child_by_field_name("right")

            if left and left.type == "identifier":
                field_name = self._get_node_text(left)
                field_qn = f"{class_qn}.{field_name}"

                field_node = VariableNode(
                    name=field_name,
                    qualified_name=field_qn,
                    var_type="field",
                    declared_at=left.start_point[0] + 1,
                    scope=class_qn,
                    is_mutable=True,
                    initial_value=self._get_node_text(right) if right else None,
                    language="python"
                )
                self.variables[field_qn] = field_node

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
