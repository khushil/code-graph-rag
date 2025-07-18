"""Advanced pointer analysis for C code."""

from dataclasses import dataclass, field

from tree_sitter import Node


@dataclass
class PointerInfo:
    """Information about a pointer variable or parameter."""

    name: str
    base_type: str
    indirection_level: int  # Number of * (e.g., int** has level 2)
    is_const: bool = False
    is_function_pointer: bool = False
    points_to: str | None = None  # Variable it points to
    location: tuple[int, int] = (0, 0)  # Line, column
    initialized_to_null: bool = False  # Track NULL initialization


@dataclass
class FunctionPointerInfo:
    """Information about a function pointer."""

    name: str
    return_type: str
    param_types: list[str]
    assigned_functions: list[str] = field(
        default_factory=list
    )  # Functions assigned to this pointer
    invocation_sites: list[tuple[int, str]] = field(
        default_factory=list
    )  # (line, context)


class CPointerAnalyzer:
    """Analyzes pointer relationships and function pointers in C code."""

    def __init__(self):
        self.pointers: dict[str, PointerInfo] = {}
        self.function_pointers: dict[str, FunctionPointerInfo] = {}
        self.pointer_relationships: list[
            tuple[str, str, str, str]
        ] = []  # (source, rel_type, target_type, target)

    def analyze_pointers(
        self, root: Node, content: str
    ) -> tuple[dict[str, PointerInfo], list[tuple[str, str, str, str]]]:
        """Analyze all pointer-related constructs in the AST."""
        self.pointers = {}
        self.function_pointers = {}
        self.pointer_relationships = []
        self.content = content
        self.pending_aliases = []  # Track aliases to resolve later

        # Walk the AST
        self._walk_tree(root)

        # Second pass: resolve pointer aliases
        self._resolve_pointer_aliases()

        return self.pointers, self.pointer_relationships

    def _walk_tree(self, node: Node, context: str | None = None) -> None:
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

        # Check for pointer dereference
        elif node.type == "pointer_expression":
            self._analyze_pointer_expression(node, context)

        # Check for pointer arithmetic
        elif node.type == "binary_expression":
            self._analyze_pointer_arithmetic(node, context)

        # Check for cast expressions
        elif node.type == "cast_expression":
            self._analyze_cast_expression(node, context)

        # Track context (current function)
        if node.type == "function_definition":
            func_name = self._get_function_name(node)
            if func_name:
                context = func_name

        # Recurse to children
        for child in node.children:
            self._walk_tree(child, context)

    def _analyze_declaration(self, node: Node, context: str | None) -> None:
        """Analyze a declaration for pointer variables."""
        # First check if there's a declarator directly under declaration
        # This handles cases like: int (*fp)(int, int);
        declarator_found = False
        for child in node.children:
            if child.type == "function_declarator":
                declarator_found = True
                # This is a function pointer declaration
                fp_info = self._extract_function_pointer_info(child)
                if fp_info:
                    self.function_pointers[fp_info.name] = fp_info

                    # Also create a pointer info entry
                    pointer_info = PointerInfo(
                        name=fp_info.name,
                        base_type="function",
                        indirection_level=1,
                        is_function_pointer=True,
                        location=(child.start_point[0] + 1, child.start_point[1]),
                    )
                    self.pointers[pointer_info.name] = pointer_info
                break
            if child.type in ["pointer_declarator", "parenthesized_declarator"]:
                declarator_found = True
                # Regular pointer
                pointer_info = self._extract_pointer_info(child)
                if pointer_info:
                    self.pointers[pointer_info.name] = pointer_info
                break
            if child.type == "array_declarator":
                declarator_found = True
                # Could be array of pointers or pointer to array
                pointer_info = self._extract_pointer_info(child)
                if pointer_info:
                    self.pointers[pointer_info.name] = pointer_info
                break

        # If no direct declarator, look in named children
        if not declarator_found:
            for child in node.named_children:
                if child.type == "init_declarator":
                    declarator = child.child_by_field_name("declarator")
                    value = child.child_by_field_name("value")

                    # Handle array declarators too
                    if not declarator:
                        # Check direct children for array_declarator
                        for subchild in child.children:
                            if subchild.type == "array_declarator":
                                declarator = subchild
                                break

                    if declarator:
                        # Check for function pointer first
                        if self._is_function_pointer(declarator):
                            fp_info = self._extract_function_pointer_info(declarator)
                            if fp_info:
                                self.function_pointers[fp_info.name] = fp_info

                                # Also create a pointer info entry
                                pointer_info = PointerInfo(
                                    name=fp_info.name,
                                    base_type="function",
                                    indirection_level=1,
                                    is_function_pointer=True,
                                    location=(
                                        declarator.start_point[0] + 1,
                                        declarator.start_point[1],
                                    ),
                                )
                                self.pointers[pointer_info.name] = pointer_info

                                # Check for initial assignment
                                if value and value.type == "identifier":
                                    func_name = value.text.decode("utf-8")
                                    fp_info.assigned_functions.append(func_name)
                                    self.pointer_relationships.append(
                                        (
                                            fp_info.name,
                                            "ASSIGNS_FP",
                                            "function",
                                            func_name,
                                        )
                                    )
                        else:
                            # Regular pointer
                            pointer_info = self._extract_pointer_info(declarator)
                            if pointer_info:
                                self.pointers[pointer_info.name] = pointer_info

                                # Check if it's initialized with address-of
                                if value and value.type == "pointer_expression":
                                    # pointer_expression is &something
                                    if (
                                        len(value.children) >= 2
                                        and value.children[0].text == b"&"
                                    ):
                                        operand = value.children[1]
                                        if operand.type == "identifier":
                                            target_name = operand.text.decode("utf-8")
                                            pointer_info.points_to = target_name
                                            self.pointer_relationships.append(
                                                (
                                                    pointer_info.name,
                                                    "POINTS_TO",
                                                    "variable",
                                                    target_name,
                                                )
                                            )
                                # Check for NULL initialization
                                elif value and value.type == "null":
                                    pointer_info.initialized_to_null = True
                                # Check if initialized with another pointer
                                elif value and value.type == "identifier":
                                    rhs_name = value.text.decode("utf-8")
                                    # Track for later resolution
                                    self.pending_aliases.append(
                                        (pointer_info.name, rhs_name)
                                    )
                                # Check for numeric 0 initialization
                                elif value and value.type == "number_literal":
                                    if value.text == b"0":
                                        pointer_info.initialized_to_null = True
                                # Check for cast expressions like (void *)0
                                elif value and value.type == "cast_expression":
                                    argument = value.child_by_field_name("value")
                                    if (
                                        argument
                                        and argument.type == "number_literal"
                                        and argument.text == b"0"
                                    ):
                                        pointer_info.initialized_to_null = True
                                elif value and value.type == "unary_expression":
                                    # Handle old-style unary_expression for compatibility
                                    operator = value.child_by_field_name("operator")
                                    if operator and operator.text == b"&":
                                        operand = value.child_by_field_name("argument")
                                        if operand and operand.type == "identifier":
                                            target_name = operand.text.decode("utf-8")
                                            pointer_info.points_to = target_name
                                            self.pointer_relationships.append(
                                                (
                                                    pointer_info.name,
                                                    "POINTS_TO",
                                                    "variable",
                                                    target_name,
                                                )
                                            )

                elif child.type == "declarator":
                    # Handle simple declarations without initialization
                    if self._is_function_pointer(child):
                        fp_info = self._extract_function_pointer_info(child)
                        if fp_info:
                            self.function_pointers[fp_info.name] = fp_info

                            # Also create a pointer info entry
                            pointer_info = PointerInfo(
                                name=fp_info.name,
                                base_type="function",
                                indirection_level=1,
                                is_function_pointer=True,
                                location=(
                                    child.start_point[0] + 1,
                                    child.start_point[1],
                                ),
                            )
                            self.pointers[pointer_info.name] = pointer_info
                    else:
                        pointer_info = self._extract_pointer_info(child)
                        if pointer_info:
                            self.pointers[pointer_info.name] = pointer_info

    def _analyze_assignment(self, node: Node, context: str | None) -> None:
        """Analyze pointer assignments."""
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if not left or not right:
            return

        # Get the left-hand side identifier
        lhs_name = self._get_identifier_name(left)

        # Check if it's a function pointer assignment
        if (
            lhs_name
            and lhs_name in self.function_pointers
            and right.type == "identifier"
        ):
            func_name = right.text.decode("utf-8")
            self.function_pointers[lhs_name].assigned_functions.append(func_name)
            self.pointer_relationships.append(
                (lhs_name, "ASSIGNS_FP", "function", func_name)
            )
            return
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
            if lhs_name in self.pointers:
                # Track for later resolution
                self.pending_aliases.append((lhs_name, rhs_name))

        # Check cast expressions in assignments
        elif right.type == "cast_expression":
            self._analyze_cast_expression(right, context)
            # Get the value being cast
            value_node = right.child_by_field_name("value")
            if value_node and value_node.type == "identifier":
                rhs_name = value_node.text.decode("utf-8")
                if lhs_name in self.pointers and rhs_name in self.pointers:
                    # Track aliasing through cast
                    self.pending_aliases.append((lhs_name, rhs_name))

    def _analyze_pointer_call(self, node: Node, context: str | None) -> None:
        """Analyze function calls through function pointers."""
        function_node = node.child_by_field_name("function")
        if not function_node:
            return

        # Track invocation
        line = node.start_point[0] + 1
        invoked_fp = None

        # Handle (*fp)() pattern
        if function_node.type == "parenthesized_expression":
            inner = (
                function_node.children[1] if len(function_node.children) > 1 else None
            )
            if inner and inner.type == "unary_expression":
                operator = inner.child_by_field_name("operator")
                if operator and operator.text == b"*":
                    operand = inner.child_by_field_name("argument")
                    if operand:
                        fp_name = self._get_identifier_name(operand)
                        if fp_name and fp_name in self.function_pointers:
                            invoked_fp = fp_name

        # Handle direct fp() pattern
        elif function_node.type == "identifier":
            fp_name = function_node.text.decode("utf-8")
            if fp_name in self.function_pointers:
                invoked_fp = fp_name

        # Handle array access pattern like ops[0]()
        elif function_node.type == "subscript_expression":
            argument = function_node.child_by_field_name("argument")
            if argument:
                arr_name = self._get_identifier_name(argument)
                # For now, treat array of function pointers as single entity
                if arr_name and arr_name in self.function_pointers:
                    invoked_fp = arr_name

        # Record invocation
        if invoked_fp:
            # Check if already recorded on this line
            existing_sites = self.function_pointers[invoked_fp].invocation_sites
            site = (line, context or "global")
            if site not in existing_sites:
                self.function_pointers[invoked_fp].invocation_sites.append(site)

            # Add INVOKES_FP relationships for all assigned functions
            for func in self.function_pointers[invoked_fp].assigned_functions:
                self.pointer_relationships.append(
                    (invoked_fp, "INVOKES_FP", "function", func)
                )

    def _analyze_unary_expression(self, node: Node, context: str | None) -> None:
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
                # Add DEREFERENCES relationship
                line = node.start_point[0] + 1
                self.pointer_relationships.append(
                    (ptr_name, "DEREFERENCES", "pointer", f"line {line}")
                )

    def _analyze_pointer_expression(self, node: Node, context: str | None) -> None:
        """Analyze pointer expressions (dereferences)."""
        # pointer_expression is *pointer
        if len(node.children) >= 2 and node.children[0].text == b"*":
            operand = node.children[1]
            ptr_name = self._get_identifier_name(operand)
            if ptr_name and ptr_name in self.pointers:
                # Add DEREFERENCES relationship
                line = node.start_point[0] + 1
                self.pointer_relationships.append(
                    (ptr_name, "DEREFERENCES", "pointer", f"line {line}")
                )

    def _analyze_cast_expression(self, node: Node, context: str | None) -> None:
        """Analyze cast expressions involving pointers."""
        type_node = node.child_by_field_name("type")
        value_node = node.child_by_field_name("value")

        if not type_node or not value_node:
            return

        # Check if casting involves pointers
        type_text = self.content[type_node.start_byte : type_node.end_byte]
        if "*" in type_text:
            # Get the identifier being cast
            source_name = self._get_identifier_name(value_node)
            if source_name and source_name in self.pointers:
                # Track the cast operation
                line = node.start_point[0] + 1
                self.pointer_relationships.append(
                    (source_name, "CAST_TO", "type", f"{type_text} at line {line}")
                )

    def _analyze_pointer_arithmetic(self, node: Node, context: str | None) -> None:
        """Analyze pointer arithmetic operations."""
        operator = node.child_by_field_name("operator")
        if not operator:
            return

        op_text = operator.text.decode("utf-8")
        if op_text in ["+", "-", "+=", "-="]:
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")  # noqa: F841

            if left:
                ptr_name = self._get_identifier_name(left)
                if ptr_name and ptr_name in self.pointers:
                    # Mark pointer as using arithmetic
                    if "uses_arithmetic" not in self.pointers[ptr_name].__dict__:
                        # Add uses_arithmetic as a dynamic property
                        self.pointers[ptr_name].uses_arithmetic = True

                    # Track arithmetic operation details
                    line = node.start_point[0] + 1
                    self.pointer_relationships.append(
                        (
                            ptr_name,
                            "USES_ARITHMETIC",
                            "operation",
                            f"{op_text} at line {line}",
                        )
                    )

    def _extract_pointer_info(self, declarator: Node) -> PointerInfo | None:
        """Extract pointer information from a declarator."""
        indirection_level = 0
        current = declarator
        is_array_pointer = False

        # Count pointer levels
        while current and current.type == "pointer_declarator":
            indirection_level += 1
            current = current.child_by_field_name("declarator")

        # Check for parenthesized declarator (e.g., int (*pa)[10])
        if current and current.type == "parenthesized_declarator":
            # Look inside parentheses
            for child in current.children:
                if child.type == "pointer_declarator":
                    indirection_level += 1
                    # Check if followed by array declarator
                    parent = declarator.parent
                    if parent and parent.type == "array_declarator":
                        is_array_pointer = True
                    current = child.child_by_field_name("declarator")
                    break

        # Check for array declarator at current level
        if current and current.type == "array_declarator":
            # Look for pointer inside array declarator
            for child in current.children:
                if child.type == "parenthesized_declarator":
                    for subchild in child.children:
                        if subchild.type == "pointer_declarator":
                            indirection_level += 1
                            current = subchild.child_by_field_name("declarator")
                            is_array_pointer = True
                            break
                elif child.type == "pointer_declarator":
                    indirection_level += 1
                    current = child.child_by_field_name("declarator")
                    is_array_pointer = True
                    break
            else:
                # No pointer inside, just array
                current = current.child_by_field_name("declarator")

        # Also handle if the entire declarator is an array_declarator
        if declarator.type == "array_declarator":
            # Same logic as above
            for child in declarator.children:
                if child.type == "parenthesized_declarator":
                    for subchild in child.children:
                        if subchild.type == "pointer_declarator":
                            indirection_level += 1
                            current = subchild.child_by_field_name("declarator")
                            is_array_pointer = True
                            break
                elif child.type == "pointer_declarator":
                    indirection_level += 1
                    current = child.child_by_field_name("declarator")
                    is_array_pointer = True
                    break

        if indirection_level == 0:
            return None

        # Get the identifier
        identifier = self._get_deepest_identifier(current or declarator)
        if not identifier:
            return None

        name = identifier.text.decode("utf-8")

        # Get base type (simplified - would need parent declaration for full type)
        base_type = "array" if is_array_pointer else "unknown"

        # Check for const qualifier
        is_const = self._has_const_qualifier(declarator)

        return PointerInfo(
            name=name,
            base_type=base_type,
            indirection_level=indirection_level,
            is_const=is_const,
            location=(declarator.start_point[0] + 1, declarator.start_point[1]),
        )

    def _is_function_pointer(self, declarator: Node) -> bool:
        """Check if a declarator is a function pointer."""
        current = declarator

        # Navigate through pointer declarators
        while current and current.type == "pointer_declarator":
            current = current.child_by_field_name("declarator")

        # Check if we end up with a function declarator
        return current is not None and current.type == "function_declarator"

    def _extract_function_pointer_info(
        self, declarator: Node
    ) -> FunctionPointerInfo | None:
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
                        param_types=param_types,
                    )

        return None

    def _get_function_name(self, func_node: Node) -> str | None:
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

    def _get_identifier_name(self, node: Node) -> str | None:
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

    def _get_deepest_identifier(self, node: Node) -> Node | None:
        """Find the deepest identifier in a declarator tree."""
        if node.type == "identifier":
            return node

        for child in node.named_children:
            result = self._get_deepest_identifier(child)
            if result:
                return result

        return None

    def _get_parameter_type(self, param_node: Node) -> str | None:
        """Extract parameter type from parameter_declaration."""
        type_parts = []
        for child in param_node.children:
            if child.type in ["primitive_type", "type_identifier"]:
                type_parts.append(self.content[child.start_byte : child.end_byte])
            elif child.type == "pointer_declarator":
                type_parts.append("*")

        return " ".join(type_parts) if type_parts else None

    def _has_const_qualifier(self, node: Node) -> bool:
        """Check if a node has const qualifier in its declaration."""
        # Walk up the tree to find the declaration
        current = node
        while current and current.type not in ["declaration", "parameter_declaration"]:
            current = current.parent

        if not current:
            return False

        # Check for type_qualifier nodes with const
        for child in current.children:
            if (
                child.type == "type_qualifier"
                and self.content[child.start_byte : child.end_byte] == "const"
            ):
                return True

        return False

    def _resolve_pointer_aliases(self) -> None:
        """Resolve pointer aliases in a second pass."""
        # Keep resolving until no more changes
        changed = True
        max_iterations = 10  # Prevent infinite loops
        iterations = 0

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1

            for lhs_name, rhs_name in self.pending_aliases:
                if lhs_name not in self.pointers:
                    continue

                # Direct aliasing: p2 = p1
                if (
                    rhs_name in self.pointers
                    and self.pointers[rhs_name].points_to
                    and self.pointers[lhs_name].points_to
                    != self.pointers[rhs_name].points_to
                ):
                    self.pointers[lhs_name].points_to = self.pointers[
                        rhs_name
                    ].points_to
                    self.pointer_relationships.append(
                        (
                            lhs_name,
                            "POINTS_TO",
                            "variable",
                            self.pointers[rhs_name].points_to,
                        )
                    )
                    changed = True
