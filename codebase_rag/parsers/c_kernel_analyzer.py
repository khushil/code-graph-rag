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
    module_params: dict[str, dict[str, str]] = field(default_factory=dict)  # name -> {type, desc, perms}
    init_function: str | None = None
    exit_function: str | None = None


@dataclass
class ConcurrencyPrimitive:
    """Information about concurrency primitives."""
    name: str
    primitive_type: str  # spinlock, mutex, semaphore, rwlock
    operations: list[tuple[str, int, str]] = field(default_factory=list)  # (op_type, line, context)
    is_static: bool = False
    is_global: bool = False


class CKernelAnalyzer:
    """Analyzes Linux kernel-specific patterns in C code."""

    # Kernel macro patterns
    SYSCALL_PATTERNS = [
        r'SYSCALL_DEFINE(\d+)\s*\(\s*(\w+)',
        r'COMPAT_SYSCALL_DEFINE(\d+)\s*\(\s*(\w+)',
        r'__SYSCALL_DEFINE(\d+)\s*\(\s*(\w+)',
    ]

    EXPORT_PATTERNS = [
        r'EXPORT_SYMBOL\s*\(\s*(\w+)\s*\)',
        r'EXPORT_SYMBOL_GPL\s*\(\s*(\w+)\s*\)',
        r'EXPORT_SYMBOL_NS\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)',
    ]

    MODULE_PATTERNS = {
        'init': r'module_init\s*\(\s*(\w+)\s*\)',
        'exit': r'module_exit\s*\(\s*(\w+)\s*\)',
        'param': r'module_param\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)',
        'param_desc': r'MODULE_PARM_DESC\s*\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)',
    }

    LOCK_PATTERNS = {
        'spinlock': {
            'types': ['spinlock_t', 'raw_spinlock_t'],
            'init': ['spin_lock_init', 'raw_spin_lock_init', 'DEFINE_SPINLOCK'],
            'lock': ['spin_lock', 'spin_lock_irq', 'spin_lock_irqsave', 'spin_lock_bh'],
            'unlock': ['spin_unlock', 'spin_unlock_irq', 'spin_unlock_irqrestore', 'spin_unlock_bh'],
            'trylock': ['spin_trylock', 'spin_trylock_irq', 'spin_trylock_bh'],
        },
        'mutex': {
            'types': ['struct mutex', 'mutex'],
            'init': ['mutex_init', 'DEFINE_MUTEX'],
            'lock': ['mutex_lock', 'mutex_lock_interruptible', 'mutex_lock_killable'],
            'unlock': ['mutex_unlock'],
            'trylock': ['mutex_trylock'],
        },
        'semaphore': {
            'types': ['struct semaphore', 'semaphore'],
            'init': ['sema_init', 'DEFINE_SEMAPHORE'],
            'lock': ['down', 'down_interruptible', 'down_killable', 'down_timeout'],
            'unlock': ['up'],
            'trylock': ['down_trylock'],
        },
        'rwlock': {
            'types': ['rwlock_t'],
            'init': ['rwlock_init', 'DEFINE_RWLOCK'],
            'lock': ['read_lock', 'write_lock', 'read_lock_irq', 'write_lock_irq'],
            'unlock': ['read_unlock', 'write_unlock', 'read_unlock_irq', 'write_unlock_irq'],
            'trylock': ['read_trylock', 'write_trylock'],
        },
    }

    def __init__(self):
        self.syscalls: dict[str, SyscallInfo] = {}
        self.module_info = KernelModuleInfo()
        self.concurrency_primitives: dict[str, ConcurrencyPrimitive] = {}
        self.kernel_relationships: list[tuple[str, str, str, str]] = []

    def analyze_kernel_patterns(self, root: Node, content: str, file_path: str) -> tuple[
        dict[str, SyscallInfo],
        KernelModuleInfo,
        dict[str, ConcurrencyPrimitive],
        list[tuple[str, str, str, str]]
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

        # Walk AST for structured analysis
        self._walk_tree(root)

        return self.syscalls, self.module_info, self.concurrency_primitives, self.kernel_relationships

    def _analyze_syscalls_regex(self) -> None:
        """Find SYSCALL_DEFINE patterns using regex."""
        for pattern in self.SYSCALL_PATTERNS:
            for match in re.finditer(pattern, self.content, re.MULTILINE):
                param_count = int(match.group(1))
                syscall_name = match.group(2)

                # Extract full syscall definition
                start_pos = match.start()
                line_num = self.content[:start_pos].count('\n') + 1

                # Try to extract parameters (simplified)
                params = []
                # Would need more sophisticated parsing for full parameter extraction

                self.syscalls[syscall_name] = SyscallInfo(
                    name=syscall_name,
                    number=-1,  # Would need syscall table to get number
                    param_count=param_count,
                    params=params,
                    location=(line_num, 0)
                )

                # Add relationship
                self.kernel_relationships.append(
                    (f"sys_{syscall_name}", "IMPLEMENTS_SYSCALL", "syscall", syscall_name)
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
            if macro_type == 'init':
                match = re.search(pattern, self.content)
                if match:
                    self.module_info.init_function = match.group(1)
                    self.kernel_relationships.append(
                        (self.file_path, "MODULE_INIT", "function", match.group(1))
                    )
            elif macro_type == 'exit':
                match = re.search(pattern, self.content)
                if match:
                    self.module_info.exit_function = match.group(1)
                    self.kernel_relationships.append(
                        (self.file_path, "MODULE_EXIT", "function", match.group(1))
                    )
            elif macro_type == 'param':
                for match in re.finditer(pattern, self.content):
                    param_name = match.group(1)
                    param_type = match.group(2)
                    param_perms = match.group(3)
                    self.module_info.module_params[param_name] = {
                        'type': param_type,
                        'perms': param_perms,
                        'desc': ''
                    }
            elif macro_type == 'param_desc':
                for match in re.finditer(pattern, self.content):
                    param_name = match.group(1)
                    param_desc = match.group(2)
                    if param_name in self.module_info.module_params:
                        self.module_info.module_params[param_name]['desc'] = param_desc

    def _walk_tree(self, node: Node, context: str | None = None) -> None:
        """Walk the AST to find kernel patterns."""
        # Track function context
        if node.type == "function_definition":
            func_name = self._get_function_name(node)
            if func_name:
                context = func_name

        # Look for concurrency primitive declarations
        if node.type == "declaration":
            self._analyze_lock_declaration(node)

        # Look for lock/unlock operations
        elif node.type == "call_expression":
            self._analyze_lock_operation(node, context)

        # Look for specific macro invocations
        elif node.type == "expression_statement":
            self._analyze_macro_call(node, context)

        # Recurse
        for child in node.children:
            self._walk_tree(child, context)

    def _analyze_lock_declaration(self, node: Node) -> None:
        """Analyze declarations for concurrency primitives."""
        # Get type from declaration
        type_text = ""
        for child in node.children:
            if child.type in ["primitive_type", "type_identifier", "struct_specifier"]:
                type_text = self.content[child.start_byte:child.end_byte]
                break

        # Check if it's a lock type
        lock_type = None
        for ltype, info in self.LOCK_PATTERNS.items():
            if any(t in type_text for t in info['types']):
                lock_type = ltype
                break

        if not lock_type:
            return

        # Extract variable name
        for child in node.named_children:
            if child.type in ["init_declarator", "declarator"]:
                var_name = self._extract_variable_name(child)
                if var_name:
                    # Check if it's static/global
                    is_static = self._has_storage_class(node, "static")
                    is_global = node.parent and node.parent.type == "translation_unit"

                    self.concurrency_primitives[var_name] = ConcurrencyPrimitive(
                        name=var_name,
                        primitive_type=lock_type,
                        is_static=is_static,
                        is_global=is_global
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
            if func_name in patterns.get('init', []):
                op_type = 'init'
            elif func_name in patterns.get('lock', []):
                op_type = 'lock'
            elif func_name in patterns.get('unlock', []):
                op_type = 'unlock'
            elif func_name in patterns.get('trylock', []):
                op_type = 'trylock'

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
                        if op_type == 'lock' and context:
                            self.kernel_relationships.append(
                                (context, "LOCKS", lock_type, lock_var)
                            )
                        elif op_type == 'unlock' and context:
                            self.kernel_relationships.append(
                                (context, "UNLOCKS", lock_type, lock_var)
                            )
                break

    def _analyze_macro_call(self, node: Node, context: str | None) -> None:
        """Analyze macro calls in expression statements."""
        # Check for DEFINE_* macros for static initialization
        expr = node.children[0] if node.children else None
        if expr and expr.type == "call_expression":
            func_node = expr.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                macro_name = func_node.text.decode("utf-8")

                # Check if it's a lock definition macro
                for lock_type, patterns in self.LOCK_PATTERNS.items():
                    if macro_name in patterns.get('init', []):
                        # Extract the lock name from arguments
                        args = expr.child_by_field_name("arguments")
                        if args and args.named_children:
                            lock_name_node = args.named_children[0]
                            if lock_name_node.type == "identifier":
                                lock_name = lock_name_node.text.decode("utf-8")

                                self.concurrency_primitives[lock_name] = ConcurrencyPrimitive(
                                    name=lock_name,
                                    primitive_type=lock_type,
                                    is_static=True,  # DEFINE_* macros create static vars
                                    is_global=True
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
            if child.type == "storage_class_specifier":
                if self.content[child.start_byte:child.end_byte] == storage_class:
                    return True
        return False

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

        # Handle field expressions
        if node.type == "field_expression":
            argument = node.child_by_field_name("argument")
            if argument:
                return self._get_identifier_text(argument)

        return None
