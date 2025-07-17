"""Inheritance analysis for object-oriented code structures."""

from dataclasses import dataclass

from loguru import logger
from tree_sitter import Node


@dataclass
class InheritanceInfo:
    """Represents inheritance relationship information."""

    child_class: str  # Fully qualified name of child class
    parent_class: str  # Fully qualified name or unresolved name of parent class
    inheritance_type: str  # "extends", "implements", "mixin", "metaclass"
    line_number: int
    is_resolved: bool = True  # Whether parent class was resolved to FQN
    confidence: float = 1.0  # Confidence in the relationship


@dataclass
class MethodOverride:
    """Represents a method override relationship."""

    child_method: str  # Fully qualified name of overriding method
    parent_method: str  # Fully qualified name of overridden method
    override_type: str  # "override", "abstract_implementation", "super_call"
    line_number: int
    has_super_call: bool = False
    is_abstract: bool = False


@dataclass
class ClassInfo:
    """Complete class information including inheritance."""

    qualified_name: str
    name: str
    module: str
    line_number: int
    is_abstract: bool = False
    is_interface: bool = False
    is_mixin: bool = False
    metaclass: str | None = None
    decorators: list[str] = None
    methods: list[str] = None
    attributes: list[str] = None


class InheritanceAnalyzer:
    """Analyzes class inheritance relationships and method overrides."""

    def __init__(self, parser, queries: dict, language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self._source_lines: list[str] = []
        self._module_imports: dict[str, str] = {}  # Maps imported names to modules

    def analyze_file(
        self, file_path: str, content: str, module_qn: str
    ) -> tuple[list[InheritanceInfo], list[MethodOverride], list[ClassInfo]]:
        """Analyze inheritance relationships in a file."""
        self._source_lines = content.split("\n")

        # Parse the file
        tree = self.parser.parse(content.encode("utf-8"))
        root_node = tree.root_node

        inheritance_info = []
        method_overrides = []
        class_info = []

        # First pass: collect imports for name resolution
        self._collect_imports(root_node, module_qn)

        # Analyze based on language
        if self.language == "python":
            inheritance_info, method_overrides, class_info = (
                self._analyze_python_inheritance(root_node, module_qn)
            )
        elif self.language in ["javascript", "typescript"]:
            inheritance_info, method_overrides, class_info = (
                self._analyze_javascript_inheritance(root_node, module_qn)
            )
        elif self.language == "java":
            inheritance_info, method_overrides, class_info = (
                self._analyze_java_inheritance(root_node, module_qn)
            )
        elif self.language == "cpp":
            inheritance_info, method_overrides, class_info = (
                self._analyze_cpp_inheritance(root_node, module_qn)
            )
        else:
            logger.warning(f"Inheritance analysis not implemented for {self.language}")

        return inheritance_info, method_overrides, class_info

    def _collect_imports(self, root_node: Node, module_qn: str) -> None:
        """Collect import statements for name resolution."""
        self._module_imports.clear()

        if self.language == "python":
            import_query = """
            [
                (import_statement) @import
                (import_from_statement) @import_from
            ]
            """

            try:
                query = self.parser.language.query(import_query)
                captures = query.captures(root_node)

                # Process imports
                for node in captures.get("import", []):
                    self._process_python_import_for_resolution(node)

                for node in captures.get("import_from", []):
                    self._process_python_from_import_for_resolution(node)

            except Exception as e:
                logger.error(f"Error collecting imports: {e}")

    def _process_python_import_for_resolution(self, node: Node) -> None:
        """Process Python import statement for name resolution."""
        # import module1, module2 as alias
        for child in node.children:
            if child.type == "dotted_name":
                module_name = self._get_node_text(child)
                # For import X.Y.Z, we can reference Z directly
                parts = module_name.split(".")
                if parts:
                    self._module_imports[parts[-1]] = module_name
                # Also store the full module name
                self._module_imports[module_name] = module_name
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node and alias_node:
                    module_name = self._get_node_text(name_node)
                    alias = self._get_node_text(alias_node)
                    self._module_imports[alias] = module_name

    def _process_python_from_import_for_resolution(self, node: Node) -> None:
        """Process Python from...import statement for name resolution."""
        module_node = node.child_by_field_name("module_name")
        if not module_node:
            return

        module_name = self._get_node_text(module_node)

        # Find imported names
        found_import = False
        for child in node.children:
            if child.type == "import":
                found_import = True
                continue

            if found_import and child.type in ["dotted_name", "identifier"]:
                imported_name = self._get_node_text(child)
                self._module_imports[imported_name] = f"{module_name}.{imported_name}"
            elif found_import and child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    imported_name = self._get_node_text(name_node)
                    alias = (
                        self._get_node_text(alias_node) if alias_node else imported_name
                    )
                    self._module_imports[alias] = f"{module_name}.{imported_name}"

    def _analyze_python_inheritance(
        self, root_node: Node, module_qn: str
    ) -> tuple[list[InheritanceInfo], list[MethodOverride], list[ClassInfo]]:
        """Analyze Python class inheritance."""
        inheritance_info = []
        method_overrides = []
        class_info = []

        # Find all class definitions
        if "classes" in self.queries:
            class_captures = self.queries["classes"].captures(root_node)

            # Handle both old and new capture formats
            class_nodes = []
            if isinstance(class_captures, dict):
                class_nodes = class_captures.get("class", [])
            else:
                # Old format: list of (node, capture_name) tuples
                class_nodes = [node for node, name in class_captures if name == "class"]

            for class_node in class_nodes:
                class_name_node = class_node.child_by_field_name("name")
                if not class_name_node:
                    continue

                class_name = self._get_node_text(class_name_node)
                class_qn = f"{module_qn}.{class_name}"

                # Extract class information
                info = ClassInfo(
                    qualified_name=class_qn,
                    name=class_name,
                    module=module_qn,
                    line_number=class_node.start_point[0] + 1,
                    decorators=self._extract_decorators(class_node),
                    methods=[],
                    attributes=[],
                )

                # Check decorators for abstract/mixin patterns
                for decorator in info.decorators:
                    if "abstract" in decorator.lower() or "ABC" in decorator:
                        info.is_abstract = True
                    if "mixin" in decorator.lower():
                        info.is_mixin = True

                # Check class name for mixin pattern
                if class_name.endswith("Mixin") or class_name.endswith("MixIn"):
                    info.is_mixin = True

                # Extract base classes
                superclasses_node = class_node.child_by_field_name("superclasses")
                if superclasses_node:
                    bases = self._extract_python_base_classes(
                        superclasses_node, class_qn, module_qn
                    )
                    inheritance_info.extend(bases)

                    # Check for metaclass
                    for base in bases:
                        if base.inheritance_type == "metaclass":
                            info.metaclass = base.parent_class

                    # Check if inherits from ABC
                    for base in bases:
                        if "ABC" in base.parent_class or base.parent_class == "abc.ABC":
                            info.is_abstract = True

                # Extract methods and check for overrides
                body_node = class_node.child_by_field_name("body")
                if body_node:
                    methods, overrides = self._extract_python_methods(
                        body_node, class_qn, inheritance_info
                    )
                    info.methods = [m["name"] for m in methods]
                    method_overrides.extend(overrides)

                    # Extract attributes
                    info.attributes = self._extract_python_attributes(body_node)

                class_info.append(info)

        return inheritance_info, method_overrides, class_info

    def _extract_python_base_classes(
        self, superclasses_node: Node, class_qn: str, module_qn: str
    ) -> list[InheritanceInfo]:
        """Extract base classes from Python class definition."""
        bases = []

        # The superclasses node is an argument_list itself in tree-sitter-python
        for child in superclasses_node.children:
            if child.type == "identifier":
                base_name = self._get_node_text(child)
                resolved_name = self._resolve_class_name(base_name, module_qn)

                # Check if it's resolved
                is_resolved = resolved_name != base_name

                inheritance = InheritanceInfo(
                    child_class=class_qn,
                    parent_class=resolved_name,
                    inheritance_type="extends",
                    line_number=child.start_point[0] + 1,
                    is_resolved=is_resolved,
                )
                bases.append(inheritance)

            elif child.type == "attribute":
                # Handle Module.Class notation
                base_name = self._get_node_text(child)
                resolved_name = self._resolve_class_name(base_name, module_qn)

                # Check if it's resolved: either the name changed OR it's a qualified name with imported module
                is_resolved = resolved_name != base_name
                if not is_resolved and "." in base_name:
                    # Check if the module part is imported
                    module_part = base_name.split(".", 1)[0]
                    is_resolved = module_part in self._module_imports

                inheritance = InheritanceInfo(
                    child_class=class_qn,
                    parent_class=resolved_name,
                    inheritance_type="extends",
                    line_number=child.start_point[0] + 1,
                    is_resolved=is_resolved,
                )
                bases.append(inheritance)

            elif child.type == "keyword_argument":
                # Check for metaclass
                name = child.child_by_field_name("name")
                value = child.child_by_field_name("value")
                if name and value and self._get_node_text(name) == "metaclass":
                    metaclass_name = self._get_node_text(value)
                    resolved_name = self._resolve_class_name(metaclass_name, module_qn)

                    inheritance = InheritanceInfo(
                        child_class=class_qn,
                        parent_class=resolved_name,
                        inheritance_type="metaclass",
                        line_number=value.start_point[0] + 1,
                        is_resolved=resolved_name != metaclass_name,
                    )
                    bases.append(inheritance)

        return bases

    def _extract_python_methods(
        self, body_node: Node, class_qn: str, inheritance_info: list[InheritanceInfo]
    ) -> tuple[list[dict], list[MethodOverride]]:
        """Extract methods from Python class body and identify overrides."""
        methods = []
        overrides = []

        for child in body_node.children:
            if child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    method_name = self._get_node_text(name_node)
                    method_qn = f"{class_qn}.{method_name}"

                    # Extract method info
                    method_info = {
                        "name": method_name,
                        "qualified_name": method_qn,
                        "line_number": child.start_point[0] + 1,
                        "decorators": self._extract_decorators(child),
                        "has_super_call": self._has_super_call(child),
                        "is_abstract": False,
                    }

                    # Check if abstract
                    for decorator in method_info["decorators"]:
                        if "abstractmethod" in decorator or "abstract" in decorator:
                            method_info["is_abstract"] = True

                    # Check for overrides
                    # For each parent class, check if this could be an override
                    for inheritance in inheritance_info:
                        if inheritance.child_class == class_qn:
                            parent_method_qn = (
                                f"{inheritance.parent_class}.{method_name}"
                            )

                            override = MethodOverride(
                                child_method=method_qn,
                                parent_method=parent_method_qn,
                                override_type="override",
                                line_number=method_info["line_number"],
                                has_super_call=method_info["has_super_call"],
                                is_abstract=method_info["is_abstract"],
                            )

                            # Adjust confidence based on method name
                            if method_name in [
                                "__init__",
                                "__str__",
                                "__repr__",
                                "__eq__",
                            ]:
                                override.override_type = "override"
                            elif method_info["is_abstract"]:
                                override.override_type = "abstract_implementation"

                            overrides.append(override)

                    methods.append(method_info)

        return methods, overrides

    def _extract_python_attributes(self, body_node: Node) -> list[str]:
        """Extract class attributes from Python class body."""
        attributes = []

        def search_assignments(node: Node) -> None:
            """Recursively search for self.attribute assignments."""
            if node.type == "assignment":
                left = node.child_by_field_name("left")
                if left and left.type == "attribute":
                    obj = left.child_by_field_name("object")
                    attr = left.child_by_field_name("attribute")
                    if obj and attr and self._get_node_text(obj) == "self":
                        attributes.append(self._get_node_text(attr))

            # Recurse into children
            for child in node.children:
                search_assignments(child)

        # Search the entire class body recursively
        search_assignments(body_node)

        return list(set(attributes))  # Remove duplicates

    def _analyze_javascript_inheritance(
        self, root_node: Node, module_qn: str
    ) -> tuple[list[InheritanceInfo], list[MethodOverride], list[ClassInfo]]:
        """Analyze JavaScript/TypeScript class inheritance."""
        inheritance_info = []
        method_overrides = []
        class_info = []

        # ES6 class syntax
        class_query = """
        (class_declaration
            name: (identifier) @class_name
            (class_heritage
                (identifier) @parent_class
            )?
            body: (class_body) @body
        ) @class
        """

        try:
            query = self.parser.language.query(class_query)
            captures = query.captures(root_node)

            # Process each class
            # Group captures by class node
            classes = {}
            parent_classes = {}

            # Handle both old and new capture formats
            capture_list = []
            if isinstance(captures, dict):
                for capture_name, nodes in captures.items():
                    for node in nodes:
                        capture_list.append((node, capture_name))
            else:
                # Old format: list of (node, capture_name) tuples
                capture_list = captures

            for node, capture_name in capture_list:
                if capture_name == "class":
                    classes[node] = {"node": node}
                elif capture_name == "class_name":
                    # Find the class_declaration parent
                    parent = node.parent
                    while parent and parent.type != "class_declaration":
                        parent = parent.parent
                    if parent and parent in classes:
                        classes[parent]["name"] = self._get_node_text(node)
                elif capture_name == "parent_class":
                    # Find the class_declaration ancestor
                    parent = node.parent
                    while parent and parent.type != "class_declaration":
                        parent = parent.parent
                    if parent:
                        if parent not in parent_classes:
                            parent_classes[parent] = []
                        parent_classes[parent].append(self._get_node_text(node))
                elif capture_name == "body":
                    parent = node.parent
                    if parent in classes:
                        classes[parent]["body"] = node

            for class_node, class_data in classes.items():
                if "name" not in class_data:
                    continue

                class_name = class_data["name"]
                class_qn = f"{module_qn}.{class_name}"

                info = ClassInfo(
                    qualified_name=class_qn,
                    name=class_name,
                    module=module_qn,
                    line_number=class_data["node"].start_point[0] + 1,
                    methods=[],
                    attributes=[],
                )

                # Extract inheritance
                if class_node in parent_classes:
                    for parent_name in parent_classes[class_node]:
                        inheritance = InheritanceInfo(
                            child_class=class_qn,
                            parent_class=parent_name,
                            inheritance_type="extends",
                            line_number=class_node.start_point[0] + 1,
                            is_resolved=False,
                        )
                        inheritance_info.append(inheritance)

                # TODO: Extract methods and check for overrides

                class_info.append(info)

        except Exception as e:
            logger.error(f"Error analyzing JavaScript inheritance: {e}")

        return inheritance_info, method_overrides, class_info

    def _analyze_java_inheritance(
        self, root_node: Node, module_qn: str
    ) -> tuple[list[InheritanceInfo], list[MethodOverride], list[ClassInfo]]:
        """Analyze Java class inheritance."""
        # TODO: Implement Java inheritance analysis
        return [], [], []

    def _analyze_cpp_inheritance(
        self, root_node: Node, module_qn: str
    ) -> tuple[list[InheritanceInfo], list[MethodOverride], list[ClassInfo]]:
        """Analyze C++ class inheritance."""
        # TODO: Implement C++ inheritance analysis
        return [], [], []

    def _resolve_class_name(self, name: str, module_qn: str) -> str:
        """Resolve a class name to its fully qualified name."""
        # Check if it's already qualified (contains dots)
        if "." in name:
            # Check if the module part is an imported module
            parts = name.split(".", 1)
            if parts[0] in self._module_imports:
                # Resolve the module part to its full name
                full_module = self._module_imports[parts[0]]
                # Return the full path with the class name
                return f"{full_module}.{parts[1]}"
            return name

        # Check imports
        if name in self._module_imports:
            return self._module_imports[name]

        # Check common built-ins
        builtins = {
            "object": "builtins.object",
            "type": "builtins.type",
            "Exception": "builtins.Exception",
            "ABC": "abc.ABC",
            "dict": "builtins.dict",
            "list": "builtins.list",
            "str": "builtins.str",
            "int": "builtins.int",
            "float": "builtins.float",
            "bool": "builtins.bool",
        }

        if name in builtins:
            return builtins[name]

        # Assume it's in the same module
        return f"{module_qn}.{name}"

    def _is_override_candidate(self, method_name: str) -> bool:
        """Check if a method name suggests it might be an override."""
        # Common override patterns
        override_patterns = [
            "__init__",
            "__str__",
            "__repr__",
            "__eq__",
            "__hash__",
            "__lt__",
            "__gt__",
            "__le__",
            "__ge__",
            "__ne__",
            "__getitem__",
            "__setitem__",
            "__delitem__",
            "__len__",
            "__iter__",
            "__next__",
            "__contains__",
            "__enter__",
            "__exit__",
            "__call__",
            "setUp",
            "tearDown",
            "test_",  # Unit test methods
            "render",
            "update",
            "draw",  # Common game/UI methods
            "save",
            "load",
            "validate",  # Common data methods
            "process",
            "handle",
            "execute",  # Common handler methods
        ]

        # Check exact matches
        if method_name in override_patterns:
            return True

        # Check prefixes
        for pattern in override_patterns:
            if method_name.startswith(pattern):
                return True

        return False

    def _has_super_call(self, method_node: Node) -> bool:
        """Check if a method contains a super() call."""
        # Simple text search for super() - could be improved with proper AST traversal
        method_text = self._get_node_text(method_node)
        return "super()" in method_text or "super()." in method_text

    def _extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators from a function or class node."""
        decorators = []

        # For tree-sitter, decorators are children of the parent node
        parent = node.parent
        if parent:
            for i, child in enumerate(parent.children):
                if child == node:
                    # Look at previous siblings
                    for j in range(i - 1, -1, -1):
                        sibling = parent.children[j]
                        if sibling.type == "decorator":
                            decorator_text = self._get_node_text(sibling).strip("@")
                            decorators.insert(
                                0, decorator_text
                            )  # Insert at beginning to maintain order
                        elif sibling.type not in ["comment", "newline"]:
                            # Stop when we hit something that's not a decorator
                            break
                    break

        return decorators

    def _get_node_text(self, node: Node) -> str:
        """Get text content of a node."""
        start_line = node.start_point[0]
        start_col = node.start_point[1]
        end_line = node.end_point[0]
        end_col = node.end_point[1]

        if start_line == end_line:
            return self._source_lines[start_line][start_col:end_col]
        # Multi-line node
        lines = []
        lines.append(self._source_lines[start_line][start_col:])
        for i in range(start_line + 1, end_line):
            lines.append(self._source_lines[i])
        lines.append(self._source_lines[end_line][:end_col])
        return "\n".join(lines)
