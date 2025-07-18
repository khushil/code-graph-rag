"""Linux kernel-specific pattern analyzer for C code."""

import re
from dataclasses import dataclass, field

from tree_sitter import Node


@dataclass
class SyscallInfo:
    """Information about a system call definition."""

    name: str
    number: int  # Syscall number if found
    param_count: int
    params: list[tuple[str, str]] = field(default_factory=list)  # (type, name) pairs
    location: tuple[int, int] = (0, 0)


@dataclass
class KernelModuleInfo:
    """Information about kernel module exports and dependencies."""

    exported_symbols: list[str] = field(default_factory=list)
    imported_symbols: list[str] = field(default_factory=list)
    module_params: dict[str, dict[str, str]] = field(
        default_factory=dict
    )  # name -> {type, desc, perms}
    init_function: str | None = None
    exit_function: str | None = None


@dataclass
class ConcurrencyPrimitive:
    """Information about concurrency primitives."""

    name: str
    primitive_type: str  # spinlock, mutex, semaphore, rwlock
    operations: list[tuple[str, int, str]] = field(
        default_factory=list
    )  # (op_type, line, context)
    is_static: bool = False
    is_global: bool = False


@dataclass
class IoctlInfo:
    """Information about ioctl definitions."""

    name: str
    magic: str
    number: str
    direction: str  # none, read, write, read_write
    data_type: str | None = None
    location: tuple[int, int] = (0, 0)


class CKernelAnalyzer:
    """Analyzes Linux kernel-specific patterns in C code."""

    # Kernel macro patterns
    SYSCALL_PATTERNS = [
        r"SYSCALL_DEFINE(\d+)\s*\(\s*(\w+)",
        r"COMPAT_SYSCALL_DEFINE(\d+)\s*\(\s*(\w+)",
        r"__SYSCALL_DEFINE(\d+)\s*\(\s*(\w+)",
    ]

    EXPORT_PATTERNS = [
        r"EXPORT_SYMBOL\s*\(\s*(\w+)\s*\)",
        r"EXPORT_SYMBOL_GPL\s*\(\s*(\w+)\s*\)",
        r"EXPORT_SYMBOL_NS\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)",
    ]

    MODULE_PATTERNS = {
        "init": r"(?<!_)module_init\s*\(\s*(\w+)\s*\)",
        "exit": r"(?<!_)module_exit\s*\(\s*(\w+)\s*\)",
        "param": r"module_param\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)",
        "param_desc": r'MODULE_PARM_DESC\s*\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)',
    }

    # Ioctl patterns
    IOCTL_PATTERNS = [
        (
            r"#define\s+(\w+)\s+_IO\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)",
            "none",
            3,
        ),  # _IO(magic, nr)
        (
            r"#define\s+(\w+)\s+_IOR\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)",
            "read",
            4,
        ),  # _IOR(magic, nr, type)
        (
            r"#define\s+(\w+)\s+_IOW\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)",
            "write",
            4,
        ),  # _IOW(magic, nr, type)
        (
            r"#define\s+(\w+)\s+_IOWR\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)",
            "read_write",
            4,
        ),  # _IOWR(magic, nr, type)
    ]

    LOCK_PATTERNS = {
        "spinlock": {
            "types": ["spinlock_t", "raw_spinlock_t"],
            "init": ["spin_lock_init", "raw_spin_lock_init", "DEFINE_SPINLOCK"],
            "lock": ["spin_lock", "spin_lock_irq", "spin_lock_irqsave", "spin_lock_bh"],
            "unlock": [
                "spin_unlock",
                "spin_unlock_irq",
                "spin_unlock_irqrestore",
                "spin_unlock_bh",
            ],
            "trylock": ["spin_trylock", "spin_trylock_irq", "spin_trylock_bh"],
        },
        "mutex": {
            "types": ["struct mutex", "mutex"],
            "init": ["mutex_init", "DEFINE_MUTEX"],
            "lock": ["mutex_lock", "mutex_lock_interruptible", "mutex_lock_killable"],
            "unlock": ["mutex_unlock"],
            "trylock": ["mutex_trylock"],
        },
        "semaphore": {
            "types": ["struct semaphore", "semaphore"],
            "init": ["sema_init", "DEFINE_SEMAPHORE"],
            "lock": ["down", "down_interruptible", "down_killable", "down_timeout"],
            "unlock": ["up"],
            "trylock": ["down_trylock"],
        },
        "rwlock": {
            "types": ["rwlock_t"],
            "init": ["rwlock_init", "DEFINE_RWLOCK"],
            "lock": ["read_lock", "write_lock", "read_lock_irq", "write_lock_irq"],
            "unlock": [
                "read_unlock",
                "write_unlock",
                "read_unlock_irq",
                "write_unlock_irq",
            ],
            "trylock": ["read_trylock", "write_trylock"],
        },
    }

    def __init__(self):
        self.syscalls: dict[str, SyscallInfo] = {}
        self.module_info = KernelModuleInfo()
        self.concurrency_primitives: dict[str, ConcurrencyPrimitive] = {}
        self.ioctls: dict[str, IoctlInfo] = {}
        self.kernel_relationships: list[tuple[str, str, str, str]] = []
        self.external_symbols: set[str] = set()  # Track external symbols used

    def analyze_kernel_patterns(
        self, root: Node, content: str, file_path: str
    ) -> tuple[
        dict[str, SyscallInfo],
        KernelModuleInfo,
        dict[str, ConcurrencyPrimitive],
        list[tuple[str, str, str, str]],
        dict[str, IoctlInfo],
    ]:
        """Analyze kernel-specific patterns in the code."""
        self.syscalls = {}
        self.module_info = KernelModuleInfo()
        self.concurrency_primitives = {}
        self.kernel_relationships = []
        self.content = content
        self.file_path = file_path

        # Analyze using regex patterns (for macros that may not be in AST)
        self._analyze_syscalls_regex()
        self._analyze_exports_regex()
        self._analyze_module_macros_regex()
        self._analyze_lock_macros_regex()
        self._analyze_ioctls_regex()

        # Walk AST for structured analysis
        self._walk_tree(root)
        
        # Analyze module dependencies
        self._analyze_module_dependencies()

        return (
            self.syscalls,
            self.module_info,
            self.concurrency_primitives,
            self.kernel_relationships,
            self.ioctls,
        )

    def _analyze_syscalls_regex(self) -> None:
        """Find SYSCALL_DEFINE patterns using regex."""
        for pattern in self.SYSCALL_PATTERNS:
            for match in re.finditer(pattern, self.content, re.MULTILINE):
                param_count = int(match.group(1))
                syscall_name = match.group(2)

                # Extract full syscall definition
                start_pos = match.start()
                line_num = self.content[:start_pos].count("\n") + 1

                # Extract parameters
                params = self._extract_syscall_params(start_pos, param_count)

                # Use a unique key for compat syscalls
                syscall_key = syscall_name
                if "COMPAT_" in pattern:
                    syscall_key = f"compat_{syscall_name}"

                self.syscalls[syscall_key] = SyscallInfo(
                    name=syscall_name,
                    number=-1,  # Would need syscall table to get number
                    param_count=param_count,
                    params=params,
                    location=(line_num, 0),
                )

                # Add relationship
                self.kernel_relationships.append(
                    (
                        f"sys_{syscall_name}",
                        "IMPLEMENTS_SYSCALL",
                        "syscall",
                        syscall_name,
                    )
                )

    def _analyze_exports_regex(self) -> None:
        """Find EXPORT_SYMBOL patterns using regex."""
        for pattern in self.EXPORT_PATTERNS:
            for match in re.finditer(pattern, self.content, re.MULTILINE):
                symbol_name = match.group(1)
                self.module_info.exported_symbols.append(symbol_name)

                # Add relationship
                self.kernel_relationships.append(
                    (self.file_path, "EXPORTS", "symbol", symbol_name)
                )

    def _analyze_module_macros_regex(self) -> None:
        """Find module-related macros using regex."""
        # Module init/exit
        for macro_type, pattern in self.MODULE_PATTERNS.items():
            if macro_type == "init":
                match = re.search(pattern, self.content)
                if match:
                    self.module_info.init_function = match.group(1)
                    self.kernel_relationships.append(
                        (self.file_path, "MODULE_INIT", "function", match.group(1))
                    )
            elif macro_type == "exit":
                match = re.search(pattern, self.content)
                if match:
                    self.module_info.exit_function = match.group(1)
                    self.kernel_relationships.append(
                        (self.file_path, "MODULE_EXIT", "function", match.group(1))
                    )
            elif macro_type == "param":
                for match in re.finditer(pattern, self.content):
                    param_name = match.group(1)
                    param_type = match.group(2)
                    param_perms = match.group(3)
                    self.module_info.module_params[param_name] = {
                        "type": param_type,
                        "perms": param_perms,
                        "desc": "",
                    }
            elif macro_type == "param_desc":
                for match in re.finditer(pattern, self.content):
                    param_name = match.group(1)
                    param_desc = match.group(2)
                    if param_name in self.module_info.module_params:
                        self.module_info.module_params[param_name]["desc"] = param_desc

    def _analyze_lock_macros_regex(self) -> None:
        """Find lock definition macros using regex."""
        # Look for DEFINE_* macros
        for lock_type, patterns in self.LOCK_PATTERNS.items():
            for init_macro in patterns.get("init", []):
                if init_macro.startswith("DEFINE_"):
                    # Create regex pattern for DEFINE_* macros
                    pattern = (
                        rf"(?:static\s+)?{re.escape(init_macro)}\s*\(\s*(\w+)\s*\)"
                    )
                    for match in re.finditer(pattern, self.content):
                        lock_name = match.group(1)
                        # Determine if it's static based on the match
                        is_static = match.group(0).strip().startswith("static")

                        self.concurrency_primitives[lock_name] = ConcurrencyPrimitive(
                            name=lock_name,
                            primitive_type=lock_type,
                            is_static=is_static,
                            is_global=True,
                        )

    def _analyze_ioctls_regex(self) -> None:
        """Find ioctl definitions using regex."""
        for pattern, direction, group_count in self.IOCTL_PATTERNS:
            for match in re.finditer(pattern, self.content, re.MULTILINE):
                ioctl_name = match.group(1)
                magic = match.group(2).strip()
                number = match.group(3).strip()
                data_type = None

                if group_count == 4:
                    data_type = match.group(4).strip()

                # Get line number
                start_pos = match.start()
                line_num = self.content[:start_pos].count("\n") + 1

                self.ioctls[ioctl_name] = IoctlInfo(
                    name=ioctl_name,
                    magic=magic,
                    number=number,
                    direction=direction,
                    data_type=data_type,
                    location=(line_num, 0),
                )

                # Add relationship
                self.kernel_relationships.append(
                    (self.file_path, "DEFINES_IOCTL", "ioctl", ioctl_name)
                )

    def _walk_tree(self, node: Node | None, context: str | None = None) -> None:
        """Walk the AST to find kernel patterns."""
        if node is None:
            return

        # Track function context
        if node.type == "function_definition":
            func_name = self._get_function_name(node)
            if func_name:
                context = func_name

        # Look for concurrency primitive declarations
        if node.type == "declaration":
            self._analyze_lock_declaration(node)
            # Also check for extern declarations
            self._analyze_extern_declaration(node)

        # Look for lock/unlock operations
        elif node.type == "call_expression":
            self._analyze_lock_operation(node, context)
            # Track all function calls for dependency analysis
            self._track_function_call(node)

        # Look for specific macro invocations
        elif node.type == "expression_statement":
            self._analyze_macro_call(node, context)

        # Also check macro calls that might be parsed as declarations
        # (e.g., DEFINE_SPINLOCK which looks like a declaration)
        if node.type == "declaration":
            # Check if it contains a macro call
            for child in node.children:
                if child.type == "call_expression":
                    func_node = child.child_by_field_name("function")
                    if func_node and func_node.type == "identifier":
                        macro_name = func_node.text.decode("utf-8")
                        if macro_name.startswith("DEFINE_"):
                            # Handle as macro call
                            self._analyze_macro_call_node(child, context)

        # Recurse
        for child in node.children:
            self._walk_tree(child, context)

    def _analyze_lock_declaration(self, node: Node) -> None:
        """Analyze declarations for concurrency primitives."""
        # Get type from declaration - handle both type_identifier and struct_specifier
        type_text = ""
        type_parts = []

        for child in node.children:
            if child.type in ["primitive_type", "type_identifier", "struct_specifier"]:
                part_text = self.content[child.start_byte : child.end_byte]
                type_parts.append(part_text)

        # Combine all type parts
        type_text = " ".join(type_parts)

        # Check if it's a lock type
        lock_type = None
        for ltype, info in self.LOCK_PATTERNS.items():
            for lock_type_pattern in info["types"]:
                # Check for exact match (for simple types like spinlock_t)
                if lock_type_pattern == type_text:
                    lock_type = ltype
                    break
                # Check for pattern in text (for struct types)
                if lock_type_pattern in type_text:
                    lock_type = ltype
                    break
            if lock_type:
                break

        if not lock_type:
            return

        # Extract variable name
        for child in node.named_children:
            if child.type in ["init_declarator", "declarator", "identifier"]:
                var_name = self._extract_variable_name(child)
                if var_name:
                    # Check if it's static/global
                    is_static = self._has_storage_class(node, "static")
                    is_global = node.parent and node.parent.type == "translation_unit"

                    self.concurrency_primitives[var_name] = ConcurrencyPrimitive(
                        name=var_name,
                        primitive_type=lock_type,
                        is_static=is_static,
                        is_global=is_global,
                    )

    def _analyze_lock_operation(self, node: Node, context: str | None) -> None:
        """Analyze function calls for lock operations."""
        func_node = node.child_by_field_name("function")
        if not func_node or func_node.type != "identifier":
            return

        func_name = func_node.text.decode("utf-8")
        line_num = node.start_point[0] + 1

        # Check if it's a lock operation
        for lock_type, patterns in self.LOCK_PATTERNS.items():
            op_type = None
            if func_name in patterns.get("init", []):
                op_type = "init"
            elif func_name in patterns.get("lock", []):
                op_type = "lock"
            elif func_name in patterns.get("unlock", []):
                op_type = "unlock"
            elif func_name in patterns.get("trylock", []):
                op_type = "trylock"

            if op_type:
                # Try to find the lock variable
                args = node.child_by_field_name("arguments")
                if args and args.named_children:
                    first_arg = args.named_children[0]
                    lock_var = self._get_identifier_text(first_arg)

                    if lock_var:
                        # Track the operation
                        if lock_var in self.concurrency_primitives:
                            self.concurrency_primitives[lock_var].operations.append(
                                (op_type, line_num, context or "global")
                            )

                        # Add relationships for lock/unlock pairs
                        if op_type == "lock" and context:
                            self.kernel_relationships.append(
                                (context, "LOCKS", lock_type, lock_var)
                            )
                        elif op_type == "unlock" and context:
                            self.kernel_relationships.append(
                                (context, "UNLOCKS", lock_type, lock_var)
                            )
                        elif op_type == "trylock" and context:
                            self.kernel_relationships.append(
                                (context, "TRIES_LOCK", lock_type, lock_var)
                            )
                break

    def _analyze_macro_call(self, node: Node, context: str | None) -> None:
        """Analyze macro calls in expression statements."""
        # Check for DEFINE_* macros for static initialization
        expr = node.children[0] if node.children else None
        if expr and expr.type == "call_expression":
            self._analyze_macro_call_node(expr, context)

    def _analyze_macro_call_node(self, expr: Node, context: str | None) -> None:
        """Analyze a specific macro call node."""
        func_node = expr.child_by_field_name("function")
        if func_node and func_node.type == "identifier":
            macro_name = func_node.text.decode("utf-8")

            # Check if it's a lock definition macro
            for lock_type, patterns in self.LOCK_PATTERNS.items():
                if macro_name in patterns.get("init", []):
                    # Extract the lock name from arguments
                    args = expr.child_by_field_name("arguments")
                    if args and args.named_children:
                        lock_name_node = args.named_children[0]
                        if lock_name_node.type == "identifier":
                            lock_name = lock_name_node.text.decode("utf-8")

                            self.concurrency_primitives[lock_name] = (
                                ConcurrencyPrimitive(
                                    name=lock_name,
                                    primitive_type=lock_type,
                                    is_static=True,  # DEFINE_* macros create static vars
                                    is_global=True,
                                )
                            )
                    break

    def _get_function_name(self, func_node: Node) -> str | None:
        """Extract function name from function_definition."""
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

    def _extract_variable_name(self, declarator: Node) -> str | None:
        """Extract variable name from various declarator types."""
        if declarator.type == "identifier":
            return declarator.text.decode("utf-8")

        # Navigate through declarator tree
        for child in declarator.named_children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
            result = self._extract_variable_name(child)
            if result:
                return result

        return None

    def _has_storage_class(self, declaration: Node, storage_class: str) -> bool:
        """Check if declaration has specific storage class."""
        for child in declaration.children:
            if child.type == "storage_class_specifier" and self.content[child.start_byte : child.end_byte] == storage_class:
                return True
        return False

    def _extract_syscall_params(
        self, start_pos: int, param_count: int
    ) -> list[tuple[str, str]]:
        """Extract syscall parameters from SYSCALL_DEFINE macro."""
        if param_count == 0:
            return []

        params = []

        # Find the opening parenthesis after the syscall name
        paren_start = self.content.find("(", start_pos)
        if paren_start == -1:
            return params

        # Find matching closing parenthesis, handling nested parentheses
        paren_count = 1
        pos = paren_start + 1
        paren_end = -1

        while pos < len(self.content) and paren_count > 0:
            if self.content[pos] == "(":
                paren_count += 1
            elif self.content[pos] == ")":
                paren_count -= 1
                if paren_count == 0:
                    paren_end = pos
                    break
            pos += 1

        if paren_end == -1:
            return params

        # Extract parameter string and split by commas
        param_str = self.content[paren_start + 1 : paren_end]

        # Skip the syscall name which is the first "parameter"
        parts = []
        current_part = ""
        paren_level = 0

        for char in param_str:
            if char == "," and paren_level == 0:
                parts.append(current_part.strip())
                current_part = ""
            else:
                if char == "(":
                    paren_level += 1
                elif char == ")":
                    paren_level -= 1
                current_part += char

        if current_part.strip():
            parts.append(current_part.strip())

        # Skip the first part (syscall name) and process type-name pairs
        parts = parts[1:]  # Skip syscall name

        # Group parts into (type, name) pairs
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                param_type = parts[i].strip()
                param_name = parts[i + 1].strip()
                params.append((param_type, param_name))

        return params

    def _get_identifier_text(self, node: Node) -> str | None:
        """Get identifier text from various node types."""
        if node.type == "identifier":
            return node.text.decode("utf-8")

        # Handle address-of expressions
        if node.type == "unary_expression":
            operator = node.child_by_field_name("operator")
            if operator and operator.text == b"&":
                argument = node.child_by_field_name("argument")
                if argument:
                    return self._get_identifier_text(argument)

        # Handle pointer_expression (newer tree-sitter)
        if node.type == "pointer_expression" and len(node.children) >= 2 and node.children[0].text == b"&":
            # pointer_expression is &something
            operand = node.children[1]
            return self._get_identifier_text(operand)

        # Handle field expressions (e.g., d->lock)
        if node.type == "field_expression":
            # For lock tracking, we want the field name (e.g., "lock" from d->lock)
            field = node.child_by_field_name("field")
            if field:
                return field.text.decode("utf-8")

        return None
    
    def _analyze_extern_declaration(self, node: Node) -> None:
        """Analyze extern declarations to track external symbols."""
        # Check if it has extern storage class
        has_extern = False
        for child in node.children:
            if child.type == "storage_class_specifier" and self.content[child.start_byte : child.end_byte] == "extern":
                has_extern = True
                break
        
        if not has_extern:
            return
        
        # Extract the symbol name
        declarator = None
        for child in node.named_children:
            if child.type in ["init_declarator", "declarator", "identifier"]:
                declarator = child
                break
        
        if declarator:
            symbol_name = self._extract_variable_name(declarator)
            if symbol_name:
                self.external_symbols.add(symbol_name)
    
    def _track_function_call(self, node: Node) -> None:
        """Track function calls that might be external symbols."""
        func_node = node.child_by_field_name("function")
        if func_node and func_node.type == "identifier":
            func_name = func_node.text.decode("utf-8")
            # Common kernel functions that indicate dependencies
            kernel_funcs = {
                "printk", "kmalloc", "kfree", "register_chrdev", "unregister_chrdev",
                "device_create", "device_destroy", "class_create", "class_destroy",
                "request_irq", "free_irq", "ioremap", "iounmap", "pci_register_driver",
                "pci_unregister_driver", "platform_driver_register", "platform_driver_unregister"
            }
            # Don't track common C library functions
            stdlib_funcs = {
                "memcpy", "memset", "strcpy", "strcmp", "strlen", "sprintf", "snprintf",
                "malloc", "free", "printf", "fprintf", "fopen", "fclose"
            }
            if func_name not in stdlib_funcs and func_name not in self.module_info.exported_symbols:
                # Could be an external dependency
                self.external_symbols.add(func_name)
    
    def _analyze_module_dependencies(self) -> None:
        """Analyze module dependencies based on external symbols."""
        # For each external symbol that's not in our exports, create a MODULE_DEPENDS edge
        for symbol in self.external_symbols:
            if symbol not in self.module_info.exported_symbols:
                # Check if it's a known kernel API
                kernel_apis = {
                    "printk": "kernel/printk",
                    "kmalloc": "mm/slab",
                    "kfree": "mm/slab", 
                    "register_chrdev": "fs/char_dev",
                    "device_create": "drivers/base/core",
                    "class_create": "drivers/base/class",
                    "request_irq": "kernel/irq/manage",
                    "ioremap": "arch/*/mm/ioremap",
                    "pci_register_driver": "drivers/pci/pci-driver",
                    "platform_driver_register": "drivers/base/platform"
                }
                
                if symbol in kernel_apis:
                    # Known kernel API
                    self.kernel_relationships.append(
                        (self.file_path, "MODULE_DEPENDS", "kernel_api", kernel_apis[symbol])
                    )
                else:
                    # Unknown external symbol - might be from another module
                    self.kernel_relationships.append(
                        (self.file_path, "MODULE_DEPENDS", "symbol", symbol)
                    )
