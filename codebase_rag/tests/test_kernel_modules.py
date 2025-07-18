"""Tests for kernel module pattern detection and analysis."""

import pytest

from codebase_rag.parser_loader import load_parsers
from codebase_rag.parsers.c_parser import CParser


@pytest.fixture
def parser_and_queries():
    """Create a C parser and queries."""
    parsers, queries = load_parsers()
    return parsers["c"], queries["c"]


@pytest.fixture
def parser(parser_and_queries):
    """Get just the parser."""
    return parser_and_queries[0]


@pytest.fixture
def queries(parser_and_queries):
    """Get just the queries."""
    return parser_and_queries[1]


def test_module_init_exit(parser, queries):  # noqa: ARG001
    """Test detection of module init and exit functions."""
    code = """
    #include <linux/module.h>
    #include <linux/kernel.h>
    #include <linux/init.h>
    
    static int __init my_module_init(void)
    {
        printk(KERN_INFO "Module loaded\\n");
        return 0;
    }
    
    static void __exit my_module_exit(void)
    {
        printk(KERN_INFO "Module unloaded\\n");
    }
    
    module_init(my_module_init);
    module_exit(my_module_exit);
    
    MODULE_LICENSE("GPL");
    MODULE_AUTHOR("Test Author");
    MODULE_DESCRIPTION("Test module");
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_module.c", code)
    
    # Should have kernel_module node
    module_nodes = [n for n in nodes if n.node_type == "kernel_module"]
    assert len(module_nodes) == 1
    
    module_node = module_nodes[0]
    assert module_node.name == "test_module"
    assert module_node.properties["init_function"] == "my_module_init"
    assert module_node.properties["exit_function"] == "my_module_exit"
    
    # Check relationships
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("test_module.c", "MODULE_INIT", "my_module_init") in rel_dict
    assert ("test_module.c", "MODULE_EXIT", "my_module_exit") in rel_dict


def test_export_symbol(parser, queries):  # noqa: ARG001
    """Test detection of exported symbols."""
    code = """
    #include <linux/module.h>
    
    int my_exported_function(int x)
    {
        return x * 2;
    }
    EXPORT_SYMBOL(my_exported_function);
    
    void my_gpl_function(void)
    {
        // GPL only function
    }
    EXPORT_SYMBOL_GPL(my_gpl_function);
    
    static int internal_function(void)
    {
        return 42;
    }
    
    module_init(init_func);
    module_exit(exit_func);
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_exports.c", code)
    
    # Check module node
    module_nodes = [n for n in nodes if n.node_type == "kernel_module"]
    assert len(module_nodes) == 1
    
    module_node = module_nodes[0]
    exported = module_node.properties["exported_symbols"]
    assert "my_exported_function" in exported
    assert "my_gpl_function" in exported
    assert "internal_function" not in exported  # Not exported
    
    # Check relationships
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("test_exports.c", "EXPORTS", "my_exported_function") in rel_dict
    assert ("test_exports.c", "EXPORTS", "my_gpl_function") in rel_dict


def test_module_parameters(parser, queries):  # noqa: ARG001
    """Test detection of module parameters."""
    code = """
    #include <linux/module.h>
    #include <linux/moduleparam.h>
    
    static int debug_level = 0;
    module_param(debug_level, int, 0644);
    MODULE_PARM_DESC(debug_level, "Debug level (0-3)");
    
    static char *device_name = "mydevice";
    module_param(device_name, charp, 0444);
    MODULE_PARM_DESC(device_name, "Device name string");
    
    static bool enable_feature = true;
    module_param(enable_feature, bool, 0644);
    
    module_init(init_func);
    module_exit(exit_func);
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_params.c", code)
    
    # Check module node
    module_nodes = [n for n in nodes if n.node_type == "kernel_module"]
    assert len(module_nodes) == 1
    
    module_node = module_nodes[0]
    params = module_node.properties["module_params"]
    
    # Should have all three parameters
    assert "debug_level" in params
    assert "device_name" in params
    assert "enable_feature" in params


def test_module_dependencies(parser, queries):  # noqa: ARG001
    """Test detection of module dependencies through symbol usage."""
    code = """
    #include <linux/module.h>
    
    // External function from another module
    extern int external_function(void);
    
    // Our exported function that uses external
    int my_function(void)
    {
        return external_function() + 1;
    }
    EXPORT_SYMBOL(my_function);
    
    // Using kernel symbols
    static int init_func(void)
    {
        printk(KERN_INFO "Module init\\n");
        register_chrdev(0, "mydev", &fops);
        return 0;
    }
    
    module_init(init_func);
    module_exit(exit_func);
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_deps.c", code)
    
    # Check that external function is detected
    function_nodes = [n for n in nodes if n.node_type == "function"]
    my_func = next((n for n in function_nodes if n.name == "my_function"), None)
    assert my_func is not None
    
    # Check CALLS relationships
    calls_rels = [r for r in relationships if r[1] == "CALLS"]
    assert any(r[0] == "my_function" and r[3] == "external_function" for r in calls_rels)
    assert any(r[0] == "init_func" and r[3] == "printk" for r in calls_rels)
    assert any(r[0] == "init_func" and r[3] == "register_chrdev" for r in calls_rels)
    
    # Check MODULE_DEPENDS relationships
    depends_rels = [r for r in relationships if r[1] == "MODULE_DEPENDS"]
    assert len(depends_rels) >= 3  # external_function, printk, register_chrdev
    
    # Check specific dependencies
    assert any(r[0] == "test_deps.c" and r[3] == "external_function" for r in depends_rels)
    assert any(r[0] == "test_deps.c" and r[3] == "kernel/printk" for r in depends_rels)
    assert any(r[0] == "test_deps.c" and r[3] == "fs/char_dev" for r in depends_rels)


def test_module_namespace_export(parser, queries):  # noqa: ARG001
    """Test detection of namespace exports."""
    code = """
    #include <linux/module.h>
    
    void namespaced_function(void)
    {
        // Function in a namespace
    }
    EXPORT_SYMBOL_NS(namespaced_function, MY_NAMESPACE);
    
    static int init_func(void)
    {
        return 0;
    }
    
    module_init(init_func);
    module_exit(exit_func);
    MODULE_IMPORT_NS(OTHER_NAMESPACE);
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_namespace.c", code)
    
    # Check module node
    module_nodes = [n for n in nodes if n.node_type == "kernel_module"]
    assert len(module_nodes) == 1
    
    module_node = module_nodes[0]
    exported = module_node.properties["exported_symbols"]
    assert "namespaced_function" in exported
    
    # Check export relationship
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("test_namespace.c", "EXPORTS", "namespaced_function") in rel_dict


def test_module_multiple_inits(parser, queries):  # noqa: ARG001
    """Test handling of modules with conditional init functions."""
    code = """
    #include <linux/module.h>
    
    #ifdef CONFIG_FEATURE_A
    static int __init feature_a_init(void)
    {
        return 0;
    }
    module_init(feature_a_init);
    #else
    static int __init default_init(void)
    {
        return 0;
    }
    module_init(default_init);
    #endif
    
    module_exit(cleanup_func);
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_conditional.c", code)
    
    # Should detect the first module_init it encounters
    module_nodes = [n for n in nodes if n.node_type == "kernel_module"]
    assert len(module_nodes) == 1
    
    module_node = module_nodes[0]
    # Should find one of the init functions
    init_func = module_node.properties["init_function"]
    assert init_func in ["feature_a_init", "default_init"]


def test_module_without_init(parser, queries):  # noqa: ARG001
    """Test handling of modules that only export symbols without init/exit."""
    code = """
    #include <linux/module.h>
    
    int utility_function_1(int x)
    {
        return x + 1;
    }
    EXPORT_SYMBOL(utility_function_1);
    
    int utility_function_2(int x)
    {
        return x * 2;
    }
    EXPORT_SYMBOL(utility_function_2);
    
    MODULE_LICENSE("GPL");
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test_utility.c", code)
    
    # Should still create module node due to exports
    module_nodes = [n for n in nodes if n.node_type == "kernel_module"]
    assert len(module_nodes) == 1
    
    module_node = module_nodes[0]
    assert module_node.properties["init_function"] is None
    assert module_node.properties["exit_function"] is None
    assert len(module_node.properties["exported_symbols"]) == 2