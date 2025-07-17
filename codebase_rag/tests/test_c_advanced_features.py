from pathlib import Path

import pytest

from codebase_rag.parser_loader import load_parsers
from codebase_rag.parsers.c_kernel_analyzer import CKernelAnalyzer
from codebase_rag.parsers.c_parser import CParser
from codebase_rag.parsers.c_pointer_analyzer import CPointerAnalyzer


class TestCAdvancedFeatures:
    """Test advanced C parsing features including pointers and kernel patterns."""

    @pytest.fixture
    def parsers_and_queries(self):
        """Load parsers and queries."""
        parsers, queries = load_parsers()
        return parsers, queries

    def test_pointer_analysis(self, parsers_and_queries):
        """Test pointer analysis functionality."""
        parsers, queries = parsers_and_queries
        parser = parsers["c"]

        code = """
        int value = 42;
        int *ptr = &value;
        int **ptr_ptr = &ptr;

        void update_value(int *p) {
            *p = 100;
        }

        int main() {
            update_value(&value);
            update_value(ptr);
            return 0;
        }
        """

        tree = parser.parse(bytes(code, "utf8"))
        analyzer = CPointerAnalyzer()
        pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)

        # Check pointer detection
        assert "ptr" in pointers
        assert pointers["ptr"].indirection_level == 1
        assert pointers["ptr"].points_to == "value"

        assert "ptr_ptr" in pointers
        assert pointers["ptr_ptr"].indirection_level == 2
        assert pointers["ptr_ptr"].points_to == "ptr"

        # Check POINTS_TO relationships
        points_to_rels = [(r[0], r[3]) for r in relationships if r[1] == "POINTS_TO"]
        assert ("ptr", "value") in points_to_rels
        assert ("ptr_ptr", "ptr") in points_to_rels

    def test_function_pointer_analysis(self, parsers_and_queries):
        """Test function pointer detection and analysis."""
        parsers, queries = parsers_and_queries
        parser = parsers["c"]

        code = """
        typedef int (*operation_t)(int, int);

        int add(int a, int b) { return a + b; }
        int multiply(int a, int b) { return a * b; }

        int main() {
            operation_t op = add;
            int result = op(5, 3);

            op = multiply;
            result = (*op)(10, 2);

            return 0;
        }
        """

        tree = parser.parse(bytes(code, "utf8"))
        analyzer = CPointerAnalyzer()
        pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)

        # Check function pointer detection
        assert "op" in analyzer.function_pointers
        fp = analyzer.function_pointers["op"]
        assert "add" in fp.assigned_functions
        assert "multiply" in fp.assigned_functions

        # Check relationships
        assigns_fp = [(r[0], r[3]) for r in relationships if r[1] == "ASSIGNS_FP"]
        assert ("op", "add") in assigns_fp
        assert ("op", "multiply") in assigns_fp

        invokes_fp = [(r[0], r[3]) for r in relationships if r[1] == "INVOKES_FP"]
        assert len(invokes_fp) > 0  # Should have invocations

    def test_kernel_syscall_detection(self, parsers_and_queries):
        """Test detection of kernel syscall patterns."""
        parsers, queries = parsers_and_queries

        code = """
        #include <linux/syscalls.h>

        SYSCALL_DEFINE2(example_syscall, int, arg1, char __user *, arg2)
        {
            // Syscall implementation
            return 0;
        }

        SYSCALL_DEFINE0(simple_syscall)
        {
            return 42;
        }
        """

        analyzer = CKernelAnalyzer()
        syscalls, _, _, relationships = analyzer.analyze_kernel_patterns(None, code, "test.c")

        # Check syscall detection
        assert "example_syscall" in syscalls
        assert syscalls["example_syscall"].param_count == 2

        assert "simple_syscall" in syscalls
        assert syscalls["simple_syscall"].param_count == 0

        # Check relationships
        impl_syscall = [(r[0], r[3]) for r in relationships if r[1] == "IMPLEMENTS_SYSCALL"]
        assert ("sys_example_syscall", "example_syscall") in impl_syscall
        assert ("sys_simple_syscall", "simple_syscall") in impl_syscall

    def test_kernel_module_patterns(self, parsers_and_queries):
        """Test detection of kernel module patterns."""
        parsers, queries = parsers_and_queries

        code = """
        #include <linux/module.h>
        #include <linux/init.h>

        static int debug = 0;
        module_param(debug, int, 0644);
        MODULE_PARM_DESC(debug, "Enable debug messages");

        static int __init my_module_init(void)
        {
            return 0;
        }

        static void __exit my_module_exit(void)
        {
            // Cleanup
        }

        module_init(my_module_init);
        module_exit(my_module_exit);

        EXPORT_SYMBOL(some_function);
        EXPORT_SYMBOL_GPL(another_function);

        MODULE_LICENSE("GPL");
        MODULE_AUTHOR("Test Author");
        """

        analyzer = CKernelAnalyzer()
        _, module_info, _, relationships = analyzer.analyze_kernel_patterns(None, code, "test.c")

        # Check module info
        assert module_info.init_function == "my_module_init"
        assert module_info.exit_function == "my_module_exit"
        assert "some_function" in module_info.exported_symbols
        assert "another_function" in module_info.exported_symbols
        assert "debug" in module_info.module_params

        # Check relationships
        exports = [(r[3]) for r in relationships if r[1] == "EXPORTS"]
        assert "some_function" in exports
        assert "another_function" in exports

    def test_concurrency_primitive_detection(self, parsers_and_queries):
        """Test detection of kernel concurrency primitives."""
        parsers, queries = parsers_and_queries
        parser = parsers["c"]

        code = """
        #include <linux/spinlock.h>
        #include <linux/mutex.h>

        static DEFINE_SPINLOCK(my_lock);
        static DEFINE_MUTEX(my_mutex);

        struct data {
            spinlock_t lock;
            int value;
        };

        void update_data(struct data *d, int val) {
            spin_lock(&d->lock);
            d->value = val;
            spin_unlock(&d->lock);
        }

        void critical_section(void) {
            mutex_lock(&my_mutex);
            // Critical code
            mutex_unlock(&my_mutex);
        }
        """

        tree = parser.parse(bytes(code, "utf8"))
        analyzer = CKernelAnalyzer()
        _, _, primitives, relationships = analyzer.analyze_kernel_patterns(tree.root_node, code, "test.c")

        # Check primitive detection
        assert "my_lock" in primitives
        assert primitives["my_lock"].primitive_type == "spinlock"
        assert primitives["my_lock"].is_static

        assert "my_mutex" in primitives
        assert primitives["my_mutex"].primitive_type == "mutex"

        # Check lock/unlock relationships
        locks = [(r[0], r[3]) for r in relationships if r[1] == "LOCKS"]
        unlocks = [(r[0], r[3]) for r in relationships if r[1] == "UNLOCKS"]

        assert ("critical_section", "my_mutex") in locks
        assert ("critical_section", "my_mutex") in unlocks

    def test_full_c_parser_integration(self, parsers_and_queries):
        """Test full C parser with all advanced features."""
        parsers, queries = parsers_and_queries
        c_parser = CParser(parsers["c"], queries["c"])

        # Test with pointer_test.c
        test_file = Path("codebase_rag/tests/fixtures/c_samples/pointer_test.c")
        content = test_file.read_text()

        nodes, relationships = c_parser.parse_file(str(test_file), content)

        # Check for various node types
        node_types = {}
        for node in nodes:
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1

        assert "function" in node_types
        assert "function_pointer" in node_types
        assert "global_var" in node_types
        assert "typedef" in node_types
        assert "struct" in node_types

        # Check for pointer relationships
        rel_types = set(r[1] for r in relationships)
        assert "POINTS_TO" in rel_types
        assert "ASSIGNS_FP" in rel_types
        assert "TYPE_OF" in rel_types
