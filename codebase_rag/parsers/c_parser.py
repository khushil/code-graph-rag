"""C language parser with enhanced features for kernel code analysis."""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from tree_sitter import Node, Parser

from .c_kernel_analyzer import CKernelAnalyzer
from .c_pointer_analyzer import CPointerAnalyzer


@dataclass
class CNode:
    """Represents a parsed C language node."""

    node_type: str  # function, struct, enum, typedef, macro, global_var
    name: str
    file_path: str
    start_line: int
    end_line: int
    properties: dict[str, Any] = field(default_factory=dict)
    relationships: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (rel_type, target_type, target_name)


class CParser:
    """Enhanced C parser with support for kernel-specific features."""

    def __init__(self, parser: Parser, queries: dict[str, Any]):
        self.parser = parser
        self.queries = queries
        self.nodes: list[CNode] = []
        self.relationships: list[
            tuple[str, str, str, str]
        ] = []  # (source, rel_type, target_type, target)

    def parse_file(
        self, file_path: str, content: str
    ) -> tuple[list[CNode], list[tuple[str, str, str, str]]]:
        """Parse a C file and extract nodes and relationships."""
        self.nodes = []
        self.relationships = []
        self.current_file = file_path

        # Parse the content
        tree = self.parser.parse(bytes(content, "utf8"))
        if tree.root_node.has_error:
            logger.warning(f"Parse errors in {file_path}")

        # Extract various node types
        self._extract_functions(tree.root_node, content)
        self._extract_structs_unions_enums(tree.root_node, content)
        self._extract_typedefs(tree.root_node, content)
        self._extract_preprocessor_directives(tree.root_node, content)
        self._extract_global_variables(tree.root_node, content)
        self._extract_function_calls(tree.root_node, content)

        # Perform pointer analysis
        pointer_analyzer = CPointerAnalyzer()
        pointer_info, pointer_relationships = pointer_analyzer.analyze_pointers(
            tree.root_node, content
        )

        # Add pointer relationships
        self.relationships.extend(pointer_relationships)

        # Add regular pointer nodes
        for ptr_name, ptr_info in pointer_info.items():
            if not ptr_info.is_function_pointer:
                self.nodes.append(
                    CNode(
                        node_type="pointer",
                        name=ptr_name,
                        file_path=file_path,
                        start_line=ptr_info.location[0],
                        end_line=ptr_info.location[0],
                        properties={
                            "base_type": ptr_info.base_type,
                            "indirection_level": ptr_info.indirection_level,
                            "points_to": ptr_info.points_to,
                            "is_const": ptr_info.is_const,
                            "uses_arithmetic": getattr(
                                ptr_info, "uses_arithmetic", False
                            ),
                            "initialized_to_null": ptr_info.initialized_to_null,
                        },
                    )
                )

        # Add function pointer nodes
        for fp_name, fp_info in pointer_analyzer.function_pointers.items():
            # Get location from pointer_info if available
            location = (0, 0)
            if fp_name in pointer_info:
                location = pointer_info[fp_name].location

            self.nodes.append(
                CNode(
                    node_type="function_pointer",
                    name=fp_name,
                    file_path=file_path,
                    start_line=location[0],
                    end_line=location[0],
                    properties={
                        "return_type": fp_info.return_type,
                        "param_types": fp_info.param_types,
                        "assigned_functions": fp_info.assigned_functions,
                        "invocation_count": len(fp_info.invocation_sites),
                    },
                )
            )

        # Perform kernel-specific analysis
        kernel_analyzer = CKernelAnalyzer()
        syscalls, module_info, concurrency_primitives, kernel_relationships = (
            kernel_analyzer.analyze_kernel_patterns(tree.root_node, content, file_path)
        )

        # Add syscall nodes
        for syscall_name, syscall_info in syscalls.items():
            self.nodes.append(
                CNode(
                    node_type="syscall",
                    name=syscall_name,
                    file_path=file_path,
                    start_line=syscall_info.location[0],
                    end_line=syscall_info.location[0],
                    properties={
                        "param_count": syscall_info.param_count,
                        "params": syscall_info.params,
                    },
                )
            )

        # Add concurrency primitive nodes
        for lock_name, lock_info in concurrency_primitives.items():
            self.nodes.append(
                CNode(
                    node_type="concurrency_primitive",
                    name=lock_name,
                    file_path=file_path,
                    start_line=0,
                    end_line=0,
                    properties={
                        "primitive_type": lock_info.primitive_type,
                        "is_static": lock_info.is_static,
                        "is_global": lock_info.is_global,
                        "operations": lock_info.operations,
                    },
                )
            )

        # Add kernel relationships
        self.relationships.extend(kernel_relationships)

        # Add module info as properties of the file
        if module_info.exported_symbols or module_info.init_function:
            self.nodes.append(
                CNode(
                    node_type="kernel_module",
                    name=file_path.split("/")[-1].replace(".c", ""),
                    file_path=file_path,
                    start_line=0,
                    end_line=0,
                    properties={
                        "exported_symbols": module_info.exported_symbols,
                        "init_function": module_info.init_function,
                        "exit_function": module_info.exit_function,
                        "module_params": list(module_info.module_params.keys()),
                    },
                )
            )

        return self.nodes, self.relationships

    def _extract_functions(self, root: Node, content: str) -> None:
        """Extract function definitions."""
        query = self.queries["functions"]
        captures = query.captures(root)

        for node in captures.get("function", []):
            if node.type == "function_definition":
                name = self._get_function_name(node)
                if name:
                    # Extract return type
                    return_type = self._get_return_type(node, content)
                    # Extract parameters
                    params = self._get_function_parameters(node, content)

                    c_node = CNode(
                        node_type="function",
                        name=name,
                        file_path=self.current_file,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        properties={
                            "return_type": return_type,
                            "parameters": params,
                            "is_static": self._is_static_function(node, content),
                            "is_inline": self._is_inline_function(node, content),
                        },
                    )
                    self.nodes.append(c_node)

    def _extract_structs_unions_enums(self, root: Node, content: str) -> None:
        """Extract struct, union, and enum definitions."""
        query = self.queries[
            "classes"
        ]  # Reusing classes query for C structs/unions/enums
        captures = query.captures(root)

        for node in captures.get("class", []):
            if node.type == "struct_specifier":
                self._extract_struct(node, content)
            elif node.type == "union_specifier":
                self._extract_union(node, content)
            elif node.type == "enum_specifier":
                self._extract_enum(node, content)

    def _extract_struct(self, node: Node, content: str) -> None:
        """Extract struct definition."""
        # Only extract structs with bodies (not forward declarations)
        body = node.child_by_field_name("body")
        if not body:
            return

        name = self._get_type_name(node)
        if name:
            # Extract fields
            fields = self._get_struct_fields(node, content)

            c_node = CNode(
                node_type="struct",
                name=name,
                file_path=self.current_file,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                properties={
                    "fields": fields,
                    "is_anonymous": name.startswith("_anon_"),
                },
            )
            self.nodes.append(c_node)

    def _extract_typedefs(self, root: Node, content: str) -> None:
        """Extract typedef declarations."""
        # Find all typedef declarations
        cursor = root.walk()

        def visit_node(cursor) -> None:
            node = cursor.node
            if node.type == "type_definition":
                name = None
                base_type = None

                # Get the declarator (the new type name)
                declarator = node.child_by_field_name("declarator")
                if declarator:
                    name = self._get_identifier_text(declarator, content)

                # Get the type being aliased
                type_node = node.child_by_field_name("type")
                if type_node:
                    base_type = content[
                        type_node.start_byte : type_node.end_byte
                    ].strip()

                if name:
                    c_node = CNode(
                        node_type="typedef",
                        name=name,
                        file_path=self.current_file,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        properties={
                            "base_type": base_type,
                        },
                    )
                    self.nodes.append(c_node)

                    # Add TYPE_OF relationship
                    if base_type:
                        self.relationships.append((name, "TYPE_OF", "type", base_type))

            # Recurse
            if cursor.goto_first_child():
                visit_node(cursor)
                while cursor.goto_next_sibling():
                    visit_node(cursor)
                cursor.goto_parent()

        visit_node(cursor)

    def _extract_preprocessor_directives(self, root: Node, content: str) -> None:
        """Extract preprocessor directives like #define and #include."""
        cursor = root.walk()

        def visit_node(cursor) -> None:
            node = cursor.node

            if node.type in ["preproc_def", "preproc_function_def"]:
                # Extract macro definition
                # For both types, the identifier is the second child
                name = None
                for child in node.children:
                    if child.type == "identifier":
                        name = child.text.decode("utf-8")
                        break

                if name:
                    # Get macro value
                    value = ""
                    # Find the preproc_arg node which contains the value
                    for child in node.children:
                        if child.type == "preproc_arg":
                            value = content[child.start_byte : child.end_byte].strip()
                            break

                    # Check if it's a function-like macro
                    parameters = self._get_macro_parameters(node, content)

                    c_node = CNode(
                        node_type="macro",
                        name=name,
                        file_path=self.current_file,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        properties={
                            "value": value,
                            "is_function_like": parameters is not None,
                            "parameters": parameters or [],
                        },
                    )
                    self.nodes.append(c_node)

            elif node.type == "preproc_include":
                # Extract include directive
                path_node = node.child_by_field_name("path")
                if path_node:
                    include_path = content[
                        path_node.start_byte : path_node.end_byte
                    ].strip()
                    # Remove quotes or angle brackets
                    include_path = include_path.strip('"<>')

                    # Add INCLUDES relationship
                    self.relationships.append(
                        (self.current_file, "INCLUDES", "file", include_path)
                    )

            elif node.type in {"preproc_ifdef", "preproc_ifndef"}:
                # Extract conditional compilation
                name_node = node.child_by_field_name("name")
                if name_node:
                    macro_name = content[name_node.start_byte : name_node.end_byte]
                    # Add relationship to track macro usage
                    self.relationships.append(
                        (self.current_file, "USES_MACRO", "macro", macro_name)
                    )

            # Recurse
            if cursor.goto_first_child():
                visit_node(cursor)
                while cursor.goto_next_sibling():
                    visit_node(cursor)
                cursor.goto_parent()

        visit_node(cursor)

    def _extract_global_variables(self, root: Node, content: str) -> None:
        """Extract global variable declarations."""
        cursor = root.walk()

        def visit_node(cursor, in_function: bool = False) -> None:
            node = cursor.node

            # Track if we're inside a function
            if node.type == "function_definition":
                in_function = True

            # Look for declarations at the top level (not inside functions)
            if (
                node.type == "declaration"
                and not in_function
                and node.parent.type == "translation_unit"
            ):
                # Extract variable name and type
                declarator = self._find_declarator(node)
                if declarator:
                    # Skip function pointers - they're handled separately
                    if self._is_function_pointer_declarator(declarator):
                        return

                    name = self._get_identifier_text(declarator, content)
                    var_type = self._get_variable_type(node, content)

                    if name and not self._is_function_declaration(node):
                        c_node = CNode(
                            node_type="global_var",
                            name=name,
                            file_path=self.current_file,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            properties={
                                "type": var_type,
                                "is_static": self._is_static_declaration(node, content),
                                "is_extern": self._is_extern_declaration(node, content),
                                "is_const": self._is_const_declaration(node, content),
                            },
                        )
                        self.nodes.append(c_node)

            # Recurse
            if cursor.goto_first_child():
                visit_node(cursor, in_function)
                while cursor.goto_next_sibling():
                    visit_node(cursor, in_function)
                cursor.goto_parent()

        visit_node(cursor)

    def _extract_function_calls(self, root: Node, content: str) -> None:
        """Extract function calls to establish CALLS relationships."""
        if not self.queries.get("calls"):
            return

        query = self.queries["calls"]
        captures = query.captures(root)

        # Find which function contains each call
        for node in captures.get("call", []):
            if node.type == "call_expression":
                # Get the function being called
                function_node = node.child_by_field_name("function")
                if function_node and function_node.type == "identifier":
                    called_function = content[
                        function_node.start_byte : function_node.end_byte
                    ]

                    # Find the containing function
                    containing_function = self._find_containing_function(node, content)
                    if containing_function:
                        self.relationships.append(
                            (containing_function, "CALLS", "function", called_function)
                        )

    # Helper methods
    def _get_function_name(self, node: Node) -> str | None:
        """Extract function name from function_definition node."""
        declarator = node.child_by_field_name("declarator")
        if not declarator:
            return None

        # Handle pointer declarators
        while declarator.type == "pointer_declarator":
            declarator = declarator.child_by_field_name("declarator")

        if declarator.type == "function_declarator":
            name_node = declarator.child_by_field_name("declarator")
            if name_node and name_node.type == "identifier":
                return name_node.text.decode("utf-8")

        return None

    def _get_type_name(self, node: Node) -> str | None:
        """Extract name from struct/union/enum specifier."""
        # Try to get the tag name
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode("utf-8")

        # For anonymous types, generate a unique name
        return f"_anon_{node.type}_{node.start_point[0]}_{node.start_point[1]}"

    def _get_identifier_text(self, node: Node, content: str) -> str | None:
        """Extract identifier text from various node types."""
        if node.type in ["identifier", "type_identifier", "field_identifier"]:
            return node.text.decode("utf-8")

        # For declarators, find the identifier
        if node.type in [
            "declarator",
            "init_declarator",
            "array_declarator",
            "pointer_declarator",
            "function_declarator",
            "parenthesized_declarator",
        ]:
            cursor = node.walk()

            def find_identifier(cursor) -> str | None:
                if cursor.node.type in [
                    "identifier",
                    "field_identifier",
                    "type_identifier",
                ]:
                    return cursor.node.text.decode("utf-8")

                if cursor.goto_first_child():
                    result = find_identifier(cursor)
                    if result:
                        return result
                    while cursor.goto_next_sibling():
                        result = find_identifier(cursor)
                        if result:
                            return result
                    cursor.goto_parent()
                return None

            return find_identifier(cursor)

        return None

    def _get_return_type(self, func_node: Node, content: str) -> str:
        """Extract return type from function definition."""
        # Get all text before the declarator
        declarator = func_node.child_by_field_name("declarator")
        if declarator:
            type_text = content[func_node.start_byte : declarator.start_byte].strip()
            # Remove storage class specifiers
            for spec in ["static", "inline", "extern"]:
                type_text = type_text.replace(spec, "").strip()
            return type_text if type_text else "void"
        return "void"

    def _get_function_parameters(
        self, func_node: Node, content: str
    ) -> list[dict[str, str]]:
        """Extract function parameters."""
        params = []
        declarator = func_node.child_by_field_name("declarator")

        if not declarator:
            return params

        # Navigate to function_declarator
        while declarator.type == "pointer_declarator":
            declarator = declarator.child_by_field_name("declarator")

        if declarator.type == "function_declarator":
            param_list = declarator.child_by_field_name("parameters")
            if param_list:
                for child in param_list.named_children:
                    if child.type == "parameter_declaration":
                        param_type = ""
                        param_name = ""

                        # Get parameter type - extract everything except the identifier
                        declarator_node = child.child_by_field_name("declarator")
                        if declarator_node:
                            # Get parameter name first
                            param_name = (
                                self._get_identifier_text(declarator_node, content)
                                or ""
                            )

                            # For the type, we need everything from the start of the parameter
                            # to just before the identifier
                            param_text = content[
                                child.start_byte : child.end_byte
                            ].strip()

                            # If we have a name, remove it from the end to get the type
                            if param_name and param_name in param_text:
                                # Find the last occurrence of the name and extract everything before it
                                name_pos = param_text.rfind(param_name)
                                param_type = param_text[:name_pos].strip()
                            else:
                                # No name, the whole thing is the type
                                param_type = param_text
                        else:
                            # No declarator, get the whole parameter as type
                            param_type = content[
                                child.start_byte : child.end_byte
                            ].strip()

                        params.append({"type": param_type, "name": param_name})

        return params

    def _get_struct_fields(
        self, struct_node: Node, content: str
    ) -> list[dict[str, str]]:
        """Extract fields from struct definition."""
        fields = []
        body = struct_node.child_by_field_name("body")

        if body:
            for child in body.named_children:
                if child.type == "field_declaration":
                    field_type = ""
                    field_names = []

                    # Get field type
                    type_node = child.child_by_field_name("type")
                    if type_node:
                        field_type = content[
                            type_node.start_byte : type_node.end_byte
                        ].strip()

                    # Get field names (can be multiple in one declaration)
                    # Look for the declarator field
                    declarator = child.child_by_field_name("declarator")
                    if declarator:
                        # Handle array declarators and other complex declarators
                        if declarator.type == "array_declarator":
                            # The identifier is inside the array_declarator
                            name = self._get_identifier_text(declarator, content)
                        elif declarator.type == "pointer_declarator":
                            # Navigate through pointer declarators
                            name = self._get_identifier_text(declarator, content)
                        else:
                            # Direct identifier
                            name = self._get_identifier_text(declarator, content)

                        if name:
                            field_names.append(name)
                    else:
                        # Fall back to looking for field identifiers directly
                        for node in child.named_children:
                            if node.type == "field_identifier":
                                field_names.append(node.text.decode("utf-8"))

                    for name in field_names:
                        fields.append({"type": field_type, "name": name})

        return fields

    def _is_static_function(self, func_node: Node, content: str) -> bool:
        """Check if function is declared static."""
        # Check storage class specifiers before the return type
        for child in func_node.children:
            if (
                child.type == "storage_class_specifier"
                and content[child.start_byte : child.end_byte] == "static"
            ):
                return True
        return False

    def _is_inline_function(self, func_node: Node, content: str) -> bool:
        """Check if function is declared inline."""
        for child in func_node.children:
            if (
                child.type == "storage_class_specifier"
                and content[child.start_byte : child.end_byte] == "inline"
            ):
                return True
        return False

    def _find_containing_function(self, node: Node, content: str) -> str | None:
        """Find the function that contains this node."""
        current = node.parent
        while current:
            if current.type == "function_definition":
                return self._get_function_name(current)
            current = current.parent
        return None

    def _get_macro_parameters(self, macro_node: Node, content: str) -> list[str] | None:
        """Extract parameters from function-like macro."""
        params = []

        # Check if there's a parameter list
        for child in macro_node.children:
            if child.type == "preproc_params":
                # Extract parameter names
                for param in child.named_children:
                    if param.type == "identifier":
                        params.append(param.text.decode("utf-8"))
                return params

        return None

    def _find_declarator(self, declaration_node: Node) -> Node | None:
        """Find the declarator in a declaration."""
        for child in declaration_node.named_children:
            if child.type in ["init_declarator", "declarator", "identifier"]:
                return child
        return None

    def _get_variable_type(self, declaration_node: Node, content: str) -> str:
        """Extract variable type from declaration."""
        # Get the type specifier
        type_parts = []
        for child in declaration_node.children:
            if (
                child.type
                in [
                    "primitive_type",
                    "type_identifier",
                    "struct_specifier",
                    "union_specifier",
                    "enum_specifier",
                ]
                or child.type == "type_qualifier"
            ):
                type_parts.append(content[child.start_byte : child.end_byte])

        return " ".join(type_parts)

    def _is_function_declaration(self, node: Node) -> bool:
        """Check if declaration is a function declaration (not definition)."""
        for child in node.named_children:
            if child.type in ["init_declarator", "declarator"]:
                # Check if it contains a function_declarator
                cursor = child.walk()

                def has_function_declarator(cursor) -> bool:
                    if cursor.node.type == "function_declarator":
                        return True
                    if cursor.goto_first_child():
                        if has_function_declarator(cursor):
                            return True
                        while cursor.goto_next_sibling():
                            if has_function_declarator(cursor):
                                return True
                        cursor.goto_parent()
                    return False

                return has_function_declarator(cursor)
        return False

    def _is_function_pointer_declarator(self, declarator: Node) -> bool:
        """Check if a declarator is a function pointer."""
        current = declarator

        # Navigate through pointer declarators
        while current and current.type == "pointer_declarator":
            current = current.child_by_field_name("declarator")

        # Check if we end up with a function declarator
        if current and current.type == "function_declarator":
            return True

        # Also check for parenthesized declarators containing function declarators
        if current and current.type == "parenthesized_declarator":
            for child in current.children:
                if child.type == "pointer_declarator":
                    inner = child.child_by_field_name("declarator")
                    while inner and inner.type == "pointer_declarator":
                        inner = inner.child_by_field_name("declarator")
                    if inner and inner.type == "function_declarator":
                        return True

        return False

    def _is_static_declaration(self, node: Node, content: str) -> bool:
        """Check if declaration has static storage class."""
        for child in node.children:
            if (
                child.type == "storage_class_specifier"
                and content[child.start_byte : child.end_byte] == "static"
            ):
                return True
        return False

    def _is_extern_declaration(self, node: Node, content: str) -> bool:
        """Check if declaration has extern storage class."""
        for child in node.children:
            if (
                child.type == "storage_class_specifier"
                and content[child.start_byte : child.end_byte] == "extern"
            ):
                return True
        return False

    def _is_const_declaration(self, node: Node, content: str) -> bool:
        """Check if declaration has const qualifier."""
        for child in node.children:
            if (
                child.type == "type_qualifier"
                and content[child.start_byte : child.end_byte] == "const"
            ):
                return True
        return False

    def _extract_union(self, node: Node, content: str) -> None:
        """Extract union definition."""
        name = self._get_type_name(node)
        if name:
            # Similar to struct extraction
            fields = self._get_struct_fields(node, content)  # Same structure as struct

            c_node = CNode(
                node_type="union",
                name=name,
                file_path=self.current_file,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                properties={
                    "fields": fields,
                    "is_anonymous": name.startswith("_anon_"),
                },
            )
            self.nodes.append(c_node)

    def _extract_enum(self, node: Node, content: str) -> None:
        """Extract enum definition."""
        name = self._get_type_name(node)
        if name:
            # Extract enum values
            values = []
            body = node.child_by_field_name("body")

            if body:
                for child in body.named_children:
                    if child.type == "enumerator":
                        enum_name = child.child_by_field_name("name")
                        if enum_name:
                            value_name = enum_name.text.decode("utf-8")
                            # Check if it has an explicit value
                            value_node = child.child_by_field_name("value")
                            value = None
                            if value_node:
                                value = content[
                                    value_node.start_byte : value_node.end_byte
                                ].strip()

                            values.append({"name": value_name, "value": value})

            c_node = CNode(
                node_type="enum",
                name=name,
                file_path=self.current_file,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                properties={
                    "values": values,
                    "is_anonymous": name.startswith("_anon_"),
                },
            )
            self.nodes.append(c_node)
