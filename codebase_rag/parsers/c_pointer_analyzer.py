"""Advanced pointer analysis for C code."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from tree_sitter import Node
from loguru import logger


@dataclass
class PointerInfo:
    """Information about a pointer variable or parameter."""
    name: str
    base_type: str
    indirection_level: int  # Number of * (e.g., int** has level 2)
    is_const: bool = False
    is_function_pointer: bool = False
    points_to: Optional[str] = None  # Variable it points to
    location: Tuple[int, int] = (0, 0)  # Line, column


@dataclass
class FunctionPointerInfo:
    """Information about a function pointer."""
    name: str
    return_type: str
    param_types: List[str]
    assigned_functions: List[str] = field(default_factory=list)  # Functions assigned to this pointer
    invocation_sites: List[Tuple[int, str]] = field(default_factory=list)  # (line, context)


class CPointerAnalyzer:
    """Analyzes pointer relationships and function pointers in C code."""
    
    def __init__(self):
        self.pointers: Dict[str, PointerInfo] = {}
        self.function_pointers: Dict[str, FunctionPointerInfo] = {}
        self.pointer_relationships: List[Tuple[str, str, str, str]] = []  # (source, rel_type, target_type, target)
        
    def analyze_pointers(self, root: Node, content: str) -> Tuple[Dict[str, PointerInfo], List[Tuple[str, str, str, str]]]:
        """Analyze all pointer-related constructs in the AST."""
        self.pointers = {}
        self.function_pointers = {}
        self.pointer_relationships = []
        self.content = content
        
        # Walk the AST
        self._walk_tree(root)
        
        return self.pointers, self.pointer_relationships
        
    def _walk_tree(self, node: Node, context: Optional[str] = None) -> None:
        """Recursively walk the AST to find pointer-related constructs."""
        # Check for pointer declarations
        if node.type == "declaration":
            self._analyze_declaration(node, context)
            
        # Check for pointer assignments
        elif node.type == "assignment_expression":
            self._analyze_assignment(node, context)
            
        # Check for function calls through pointers
        elif node.type == "call_expression":
            self._analyze_pointer_call(node, context)
            
        # Check for address-of operations
        elif node.type == "unary_expression":
            self._analyze_unary_expression(node, context)
            
        # Check for pointer arithmetic
        elif node.type == "binary_expression":
            self._analyze_pointer_arithmetic(node, context)
            
        # Track context (current function)
        if node.type == "function_definition":
            func_name = self._get_function_name(node)
            if func_name:
                context = func_name
                
        # Recurse to children
        for child in node.children:
            self._walk_tree(child, context)
            
    def _analyze_declaration(self, node: Node, context: Optional[str]) -> None:
        """Analyze a declaration for pointer variables."""
        for child in node.named_children:
            if child.type == "init_declarator":
                declarator = child.child_by_field_name("declarator")
                value = child.child_by_field_name("value")
                
                if declarator:
                    pointer_info = self._extract_pointer_info(declarator)
                    if pointer_info:
                        self.pointers[pointer_info.name] = pointer_info
                        
                        # Check if it's initialized with address-of
                        if value and value.type == "unary_expression":
                            operator = value.child_by_field_name("operator")
                            if operator and operator.text == b"&":
                                operand = value.child_by_field_name("argument")
                                if operand and operand.type == "identifier":
                                    target_name = operand.text.decode("utf-8")
                                    pointer_info.points_to = target_name
                                    self.pointer_relationships.append(
                                        (pointer_info.name, "POINTS_TO", "variable", target_name)
                                    )
                                    
                        # Check for function pointer
                        if self._is_function_pointer(declarator):
                            fp_info = self._extract_function_pointer_info(declarator)
                            if fp_info:
                                self.function_pointers[fp_info.name] = fp_info
                                pointer_info.is_function_pointer = True
                                
            elif child.type == "declarator":
                # Handle simple declarations without initialization
                pointer_info = self._extract_pointer_info(child)
                if pointer_info:
                    self.pointers[pointer_info.name] = pointer_info
                    
                    if self._is_function_pointer(child):
                        fp_info = self._extract_function_pointer_info(child)
                        if fp_info:
                            self.function_pointers[fp_info.name] = fp_info
                            pointer_info.is_function_pointer = True
                            
    def _analyze_assignment(self, node: Node, context: Optional[str]) -> None:
        """Analyze pointer assignments."""
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        
        if not left or not right:
            return
            
        # Get the left-hand side identifier
        lhs_name = self._get_identifier_name(left)
        if not lhs_name:
            return
            
        # Check if assigning address-of
        if right.type == "unary_expression":
            operator = right.child_by_field_name("operator")
            if operator and operator.text == b"&":
                operand = right.child_by_field_name("argument")
                if operand:
                    target_name = self._get_identifier_name(operand)
                    if target_name and lhs_name in self.pointers:
                        self.pointers[lhs_name].points_to = target_name
                        self.pointer_relationships.append(
                            (lhs_name, "POINTS_TO", "variable", target_name)
                        )
                        
        # Check if assigning function to function pointer
        elif right.type == "identifier" and lhs_name in self.function_pointers:
            func_name = right.text.decode("utf-8")
            self.function_pointers[lhs_name].assigned_functions.append(func_name)
            self.pointer_relationships.append(
                (lhs_name, "ASSIGNS_FP", "function", func_name)
            )
            
        # Check pointer-to-pointer assignment
        elif right.type == "identifier":
            rhs_name = right.text.decode("utf-8")
            if lhs_name in self.pointers and rhs_name in self.pointers:
                # Pointer aliasing
                if self.pointers[rhs_name].points_to:
                    self.pointers[lhs_name].points_to = self.pointers[rhs_name].points_to
                    self.pointer_relationships.append(
                        (lhs_name, "POINTS_TO", "variable", self.pointers[rhs_name].points_to)
                    )
                    
    def _analyze_pointer_call(self, node: Node, context: Optional[str]) -> None:
        """Analyze function calls through function pointers."""
        function_node = node.child_by_field_name("function")
        if not function_node:
            return
            
        # Handle (*fp)() pattern
        if function_node.type == "parenthesized_expression":
            inner = function_node.children[1] if len(function_node.children) > 1 else None
            if inner and inner.type == "unary_expression":
                operator = inner.child_by_field_name("operator")
                if operator and operator.text == b"*":
                    operand = inner.child_by_field_name("argument")
                    if operand:
                        fp_name = self._get_identifier_name(operand)
                        if fp_name and fp_name in self.function_pointers:
                            line = node.start_point[0] + 1
                            self.function_pointers[fp_name].invocation_sites.append((line, context or "global"))
                            # Add INVOKES_FP relationships for all assigned functions
                            for func in self.function_pointers[fp_name].assigned_functions:
                                self.pointer_relationships.append(
                                    (fp_name, "INVOKES_FP", "function", func)
                                )
                                
        # Handle direct fp() pattern
        elif function_node.type == "identifier":
            fp_name = function_node.text.decode("utf-8")
            if fp_name in self.function_pointers:
                line = node.start_point[0] + 1
                self.function_pointers[fp_name].invocation_sites.append((line, context or "global"))
                for func in self.function_pointers[fp_name].assigned_functions:
                    self.pointer_relationships.append(
                        (fp_name, "INVOKES_FP", "function", func)
                    )
                    
    def _analyze_unary_expression(self, node: Node, context: Optional[str]) -> None:
        """Analyze unary expressions for pointer operations."""
        operator = node.child_by_field_name("operator")
        argument = node.child_by_field_name("argument")
        
        if not operator or not argument:
            return
            
        op_text = operator.text.decode("utf-8")
        
        # Track dereference operations
        if op_text == "*":
            ptr_name = self._get_identifier_name(argument)
            if ptr_name and ptr_name in self.pointers:
                # Could add DEREFERENCES relationship if needed
                pass
                
    def _analyze_pointer_arithmetic(self, node: Node, context: Optional[str]) -> None:
        """Analyze pointer arithmetic operations."""
        operator = node.child_by_field_name("operator")
        if not operator:
            return
            
        op_text = operator.text.decode("utf-8")
        if op_text in ["+", "-", "+=", "-="]:
            left = node.child_by_field_name("left")
            if left:
                ptr_name = self._get_identifier_name(left)
                if ptr_name and ptr_name in self.pointers:
                    # Track that this pointer is used in arithmetic
                    # Could add properties or relationships for this
                    pass
                    
    def _extract_pointer_info(self, declarator: Node) -> Optional[PointerInfo]:
        """Extract pointer information from a declarator."""
        indirection_level = 0
        current = declarator
        
        # Count pointer levels
        while current and current.type == "pointer_declarator":
            indirection_level += 1
            current = current.child_by_field_name("declarator")
            
        if indirection_level == 0:
            return None
            
        # Get the identifier
        identifier = self._get_deepest_identifier(declarator)
        if not identifier:
            return None
            
        name = identifier.text.decode("utf-8")
        
        # Get base type (simplified - would need parent declaration for full type)
        base_type = "unknown"
        
        return PointerInfo(
            name=name,
            base_type=base_type,
            indirection_level=indirection_level,
            location=(declarator.start_point[0] + 1, declarator.start_point[1])
        )
        
    def _is_function_pointer(self, declarator: Node) -> bool:
        """Check if a declarator is a function pointer."""
        current = declarator
        
        # Navigate through pointer declarators
        while current and current.type == "pointer_declarator":
            current = current.child_by_field_name("declarator")
            
        # Check if we end up with a function declarator
        return current is not None and current.type == "function_declarator"
        
    def _extract_function_pointer_info(self, declarator: Node) -> Optional[FunctionPointerInfo]:
        """Extract function pointer information."""
        # Navigate to the function declarator
        current = declarator
        while current and current.type == "pointer_declarator":
            current = current.child_by_field_name("declarator")
            
        if not current or current.type != "function_declarator":
            return None
            
        # Get the name
        name_node = current.child_by_field_name("declarator")
        if name_node and name_node.type == "parenthesized_declarator":
            # Handle (*name) pattern
            inner = None
            for child in name_node.children:
                if child.type == "pointer_declarator":
                    inner = child
                    break
            if inner:
                identifier = self._get_deepest_identifier(inner)
                if identifier:
                    name = identifier.text.decode("utf-8")
                    
                    # Extract parameter types (simplified)
                    params_node = current.child_by_field_name("parameters")
                    param_types = []
                    if params_node:
                        for param in params_node.named_children:
                            if param.type == "parameter_declaration":
                                param_type = self._get_parameter_type(param)
                                if param_type:
                                    param_types.append(param_type)
                                    
                    return FunctionPointerInfo(
                        name=name,
                        return_type="unknown",  # Would need parent context
                        param_types=param_types
                    )
                    
        return None
        
    def _get_function_name(self, func_node: Node) -> Optional[str]:
        """Get function name from function_definition node."""
        declarator = func_node.child_by_field_name("declarator")
        if not declarator:
            return None
            
        while declarator.type == "pointer_declarator":
            declarator = declarator.child_by_field_name("declarator")
            
        if declarator.type == "function_declarator":
            name_node = declarator.child_by_field_name("declarator")
            if name_node and name_node.type == "identifier":
                return name_node.text.decode("utf-8")
                
        return None
        
    def _get_identifier_name(self, node: Node) -> Optional[str]:
        """Get identifier name from various node types."""
        if node.type == "identifier":
            return node.text.decode("utf-8")
            
        # Handle field expressions like ptr->field
        if node.type == "field_expression":
            field = node.child_by_field_name("field")
            if field:
                return field.text.decode("utf-8")
                
        # Handle subscript expressions like arr[i]
        if node.type == "subscript_expression":
            argument = node.child_by_field_name("argument")
            if argument and argument.type == "identifier":
                return argument.text.decode("utf-8")
                
        return None
        
    def _get_deepest_identifier(self, node: Node) -> Optional[Node]:
        """Find the deepest identifier in a declarator tree."""
        if node.type == "identifier":
            return node
            
        for child in node.named_children:
            result = self._get_deepest_identifier(child)
            if result:
                return result
                
        return None
        
    def _get_parameter_type(self, param_node: Node) -> Optional[str]:
        """Extract parameter type from parameter_declaration."""
        type_parts = []
        for child in param_node.children:
            if child.type in ["primitive_type", "type_identifier"]:
                type_parts.append(self.content[child.start_byte:child.end_byte])
            elif child.type == "pointer_declarator":
                type_parts.append("*")
                
        return " ".join(type_parts) if type_parts else None