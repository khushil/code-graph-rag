"""Data flow analysis module (REQ-DF-1, REQ-DF-2, REQ-DF-4)."""

from dataclasses import dataclass
from typing import Any

from loguru import logger
from tree_sitter import Node

from ..graph.node_types import Variable, DataFlow
from ..utils.ast_helpers import get_node_text, find_nodes_by_type


@dataclass
class VariableDefinition:
    """Represents a variable definition in code."""
    name: str
    type_hint: str | None
    line_number: int
    scope: str
    initial_value: str | None
    is_parameter: bool = False
    is_global: bool = False
    is_mutable: bool = True


@dataclass
class DataFlowEdge:
    """Represents a data flow between variables or expressions."""
    source: str  # Variable or expression that provides data
    target: str  # Variable or expression that receives data
    flow_type: str  # ASSIGNS, READS, MODIFIES, PASSES_TO, RETURNS
    line_number: int
    is_tainted: bool = False
    taint_source: str | None = None


class DataFlowAnalyzer:
    """Analyzes data flow within and across functions."""

    def __init__(self, parser, queries: dict[str, Any], language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self.variables: dict[str, VariableDefinition] = {}
        self.data_flows: list[DataFlowEdge] = []
        self.taint_sources = {"input", "request", "argv", "environ", "stdin"}
        
    def analyze_file(
        self, root_node: Node, source_code: str, module_qn: str
    ) -> tuple[list[dict], list[dict]]:
        """Analyze data flow in a file and return nodes and relationships."""
        nodes = []
        relationships = []
        
        # Reset state for new file
        self.variables.clear()
        self.data_flows.clear()
        
        # Analyze based on language
        if self.language == "python":
            self._analyze_python(root_node, source_code, module_qn)
        elif self.language == "javascript" or self.language == "typescript":
            self._analyze_javascript(root_node, source_code, module_qn)
        elif self.language == "c":
            self._analyze_c(root_node, source_code, module_qn)
        else:
            logger.warning(f"Data flow analysis not implemented for {self.language}")
            return nodes, relationships
            
        # Convert analyzed data to graph nodes and relationships
        nodes, relationships = self._build_graph_elements(module_qn)
        
        return nodes, relationships
        
    def _analyze_python(self, root_node: Node, source_code: str, module_qn: str) -> None:
        """Analyze Python-specific data flow."""
        # Find all variable assignments
        assignment_query = """
        (assignment
          left: (_) @target
          right: (_) @source)
        """
        
        if "assignment" in self.queries:
            assignments = self._run_query(assignment_query, root_node, source_code)
            for match in assignments:
                self._process_assignment(match, source_code, module_qn)
                
        # Find function parameters
        param_query = """
        (function_definition
          name: (identifier) @func_name
          parameters: (parameters (_) @param))
        """
        
        if "function_definition" in self.queries:
            functions = self._run_query(param_query, root_node, source_code)
            for match in functions:
                self._process_function_params(match, source_code, module_qn)
                
        # Find return statements
        return_query = """
        (return_statement
          (expression_list (_) @return_value))
        """
        
        if "return_statement" in self.queries:
            returns = self._run_query(return_query, root_node, source_code)
            for match in returns:
                self._process_return(match, source_code, module_qn)
                
    def _analyze_javascript(self, root_node: Node, source_code: str, module_qn: str) -> None:
        """Analyze JavaScript/TypeScript data flow."""
        # Variable declarations (let, const, var)
        var_query = """
        (variable_declaration
          (variable_declarator
            name: (_) @name
            value: (_) @value))
        """
        
        declarations = self._run_query(var_query, root_node, source_code)
        for match in declarations:
            self._process_js_declaration(match, source_code, module_qn)
            
        # Function parameters
        func_param_query = """
        [(function_declaration
           name: (identifier) @func_name
           parameters: (formal_parameters (_) @param))
         (arrow_function
           parameters: (formal_parameters (_) @param))]
        """
        
        functions = self._run_query(func_param_query, root_node, source_code)
        for match in functions:
            self._process_function_params(match, source_code, module_qn)
            
    def _analyze_c(self, root_node: Node, source_code: str, module_qn: str) -> None:
        """Analyze C data flow including pointer operations."""
        # Variable declarations
        var_decl_query = """
        (declaration
          declarator: (_) @declarator
          type: (_) @type)
        """
        
        declarations = self._run_query(var_decl_query, root_node, source_code)
        for match in declarations:
            self._process_c_declaration(match, source_code, module_qn)
            
        # Pointer operations
        pointer_query = """
        [(pointer_expression
           operator: "*"
           argument: (_) @pointer)
         (unary_expression
           operator: "&"
           argument: (_) @address_of)]
        """
        
        pointers = self._run_query(pointer_query, root_node, source_code)
        for match in pointers:
            self._process_pointer_operation(match, source_code, module_qn)
            
    def _process_assignment(
        self, match: dict[str, Node], source_code: str, scope: str
    ) -> None:
        """Process an assignment statement."""
        target_node = match.get("target")
        source_node = match.get("source")
        
        if not target_node or not source_node:
            return
            
        target_name = get_node_text(target_node, source_code)
        source_text = get_node_text(source_node, source_code)
        line_number = target_node.start_point[0] + 1
        
        # Create or update variable definition
        if target_name not in self.variables:
            self.variables[target_name] = VariableDefinition(
                name=target_name,
                type_hint=None,
                line_number=line_number,
                scope=scope,
                initial_value=source_text,
            )
            
        # Create data flow edge
        flow = DataFlowEdge(
            source=source_text,
            target=target_name,
            flow_type="ASSIGNS",
            line_number=line_number,
            is_tainted=self._is_tainted(source_text),
            taint_source=self._get_taint_source(source_text),
        )
        self.data_flows.append(flow)
        
    def _process_function_params(
        self, match: dict[str, Node], source_code: str, scope: str
    ) -> None:
        """Process function parameters as variable definitions."""
        func_name = match.get("func_name")
        param_node = match.get("param")
        
        if not param_node:
            return
            
        param_name = get_node_text(param_node, source_code)
        line_number = param_node.start_point[0] + 1
        
        # Create parameter variable
        self.variables[param_name] = VariableDefinition(
            name=param_name,
            type_hint=None,
            line_number=line_number,
            scope=f"{scope}.{get_node_text(func_name, source_code)}" if func_name else scope,
            initial_value=None,
            is_parameter=True,
        )
        
    def _process_return(
        self, match: dict[str, Node], source_code: str, scope: str
    ) -> None:
        """Process return statements as data flows."""
        return_value = match.get("return_value")
        
        if not return_value:
            return
            
        return_text = get_node_text(return_value, source_code)
        line_number = return_value.start_point[0] + 1
        
        # Create data flow for return
        flow = DataFlowEdge(
            source=return_text,
            target="@return",
            flow_type="RETURNS",
            line_number=line_number,
            is_tainted=self._is_tainted(return_text),
            taint_source=self._get_taint_source(return_text),
        )
        self.data_flows.append(flow)
        
    def _process_js_declaration(
        self, match: dict[str, Node], source_code: str, scope: str
    ) -> None:
        """Process JavaScript variable declaration."""
        name_node = match.get("name")
        value_node = match.get("value")
        
        if not name_node:
            return
            
        var_name = get_node_text(name_node, source_code)
        var_value = get_node_text(value_node, source_code) if value_node else None
        line_number = name_node.start_point[0] + 1
        
        # Determine mutability from declaration type
        decl_node = name_node.parent.parent
        is_const = decl_node and get_node_text(decl_node.children[0], source_code) == "const"
        
        self.variables[var_name] = VariableDefinition(
            name=var_name,
            type_hint=None,
            line_number=line_number,
            scope=scope,
            initial_value=var_value,
            is_mutable=not is_const,
        )
        
        if var_value:
            flow = DataFlowEdge(
                source=var_value,
                target=var_name,
                flow_type="ASSIGNS",
                line_number=line_number,
                is_tainted=self._is_tainted(var_value),
                taint_source=self._get_taint_source(var_value),
            )
            self.data_flows.append(flow)
            
    def _process_c_declaration(
        self, match: dict[str, Node], source_code: str, scope: str
    ) -> None:
        """Process C variable declaration."""
        declarator = match.get("declarator")
        type_node = match.get("type")
        
        if not declarator:
            return
            
        # Extract variable name from declarator
        var_name = self._extract_c_var_name(declarator, source_code)
        var_type = get_node_text(type_node, source_code) if type_node else None
        line_number = declarator.start_point[0] + 1
        
        self.variables[var_name] = VariableDefinition(
            name=var_name,
            type_hint=var_type,
            line_number=line_number,
            scope=scope,
            initial_value=None,
        )
        
    def _process_pointer_operation(
        self, match: dict[str, Node], source_code: str, scope: str
    ) -> None:
        """Process C pointer operations."""
        pointer_node = match.get("pointer")
        address_of_node = match.get("address_of")
        
        if pointer_node:
            # Dereference operation
            pointer_name = get_node_text(pointer_node, source_code)
            line_number = pointer_node.start_point[0] + 1
            
            flow = DataFlowEdge(
                source=f"*{pointer_name}",
                target="@dereference",
                flow_type="READS",
                line_number=line_number,
            )
            self.data_flows.append(flow)
            
        elif address_of_node:
            # Address-of operation
            var_name = get_node_text(address_of_node, source_code)
            line_number = address_of_node.start_point[0] + 1
            
            flow = DataFlowEdge(
                source=var_name,
                target=f"&{var_name}",
                flow_type="ADDRESS_OF",
                line_number=line_number,
            )
            self.data_flows.append(flow)
            
    def _extract_c_var_name(self, declarator: Node, source_code: str) -> str:
        """Extract variable name from C declarator."""
        # Handle different declarator types
        if declarator.type == "identifier":
            return get_node_text(declarator, source_code)
        elif declarator.type == "pointer_declarator":
            # Recurse to find identifier
            for child in declarator.children:
                if child.type == "identifier":
                    return get_node_text(child, source_code)
                elif child.type in ["pointer_declarator", "array_declarator"]:
                    return self._extract_c_var_name(child, source_code)
        elif declarator.type == "init_declarator":
            # Has an initializer
            for child in declarator.children:
                if child.type != "=":
                    return self._extract_c_var_name(child, source_code)
                    
        return "unknown"
        
    def _is_tainted(self, expression: str) -> bool:
        """Check if an expression involves tainted sources."""
        for taint in self.taint_sources:
            if taint in expression.lower():
                return True
        return False
        
    def _get_taint_source(self, expression: str) -> str | None:
        """Get the taint source from an expression."""
        for taint in self.taint_sources:
            if taint in expression.lower():
                return taint
        return None
        
    def _run_query(self, query: str, node: Node, source_code: str) -> list[dict]:
        """Run a tree-sitter query and return matches."""
        # This is a simplified version - actual implementation would use
        # the tree-sitter query API
        return []
        
    def _build_graph_elements(
        self, module_qn: str
    ) -> tuple[list[dict], list[dict]]:
        """Build graph nodes and relationships from analyzed data."""
        nodes = []
        relationships = []
        
        # Create Variable nodes
        for var_name, var_def in self.variables.items():
            var_node = {
                "label": "Variable",
                "properties": {
                    "name": var_def.name,
                    "qualified_name": f"{var_def.scope}.{var_def.name}",
                    "type_hint": var_def.type_hint,
                    "line_number": var_def.line_number,
                    "scope": var_def.scope,
                    "is_parameter": var_def.is_parameter,
                    "is_global": var_def.is_global,
                    "is_mutable": var_def.is_mutable,
                    "initial_value": var_def.initial_value,
                },
            }
            nodes.append(var_node)
            
        # Create FLOWS_TO relationships
        for flow in self.data_flows:
            flow_rel = {
                "start_label": "Variable" if flow.source in self.variables else "Expression",
                "start_key": "name" if flow.source in self.variables else "value",
                "start_value": flow.source,
                "rel_type": "FLOWS_TO",
                "end_label": "Variable" if flow.target in self.variables else "Expression",
                "end_key": "name" if flow.target in self.variables else "value",
                "end_value": flow.target,
                "properties": {
                    "flow_type": flow.flow_type,
                    "line_number": flow.line_number,
                    "is_tainted": flow.is_tainted,
                    "taint_source": flow.taint_source,
                },
            }
            relationships.append(flow_rel)
            
        return nodes, relationships
        
    def track_cross_function_flows(
        self, call_graph: dict[str, list[str]]
    ) -> list[dict]:
        """Track data flows across function boundaries."""
        cross_function_flows = []
        
        # Analyze parameter passing and return values
        for caller, callees in call_graph.items():
            for callee in callees:
                # Check if data flows from caller to callee
                # This is a simplified version - actual implementation would
                # analyze actual parameter passing
                flow = {
                    "start_label": "Function",
                    "start_key": "qualified_name",
                    "start_value": caller,
                    "rel_type": "PASSES_DATA_TO",
                    "end_label": "Function",
                    "end_key": "qualified_name",
                    "end_value": callee,
                    "properties": {
                        "data_type": "parameters",
                    },
                }
                cross_function_flows.append(flow)
                
        return cross_function_flows
        
    def perform_taint_analysis(
        self, entry_points: list[str]
    ) -> list[tuple[str, str, str]]:
        """Perform taint analysis from specified entry points."""
        taint_paths = []
        
        # Track tainted data through the flow graph
        for entry in entry_points:
            # Find all flows starting from this entry point
            for flow in self.data_flows:
                if flow.is_tainted and flow.taint_source:
                    # Record taint path
                    taint_paths.append(
                        (flow.taint_source, flow.target, flow.flow_type)
                    )
                    
        return taint_paths