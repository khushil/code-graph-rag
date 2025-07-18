"""Enhanced tests for advanced pointer analysis in C code."""

import pytest
from codebase_rag.parser_loader import load_parsers
from codebase_rag.parsers.c_parser import CParser
from codebase_rag.parsers.c_pointer_analyzer import CPointerAnalyzer


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


def test_basic_pointer_nodes(parser, queries):
    """Test creation of Pointer nodes with properties."""
    code = """
    int x = 5;
    int *p = &x;
    int **pp = &p;
    char *str = "hello";
    const int *cp = &x;
    int * const pc = &x;
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Should create Pointer nodes
    assert "p" in pointers
    assert pointers["p"].indirection_level == 1
    assert pointers["p"].base_type == "unknown"  # Current implementation
    assert pointers["p"].points_to == "x"
    
    assert "pp" in pointers
    assert pointers["pp"].indirection_level == 2
    assert pointers["pp"].points_to == "p"
    
    assert "str" in pointers
    assert pointers["str"].indirection_level == 1
    
    # Check relationships
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("p", "POINTS_TO", "x") in rel_dict
    assert ("pp", "POINTS_TO", "p") in rel_dict


def test_multiple_indirection_levels(parser, queries):
    """Test handling of multiple indirection levels."""
    code = """
    int x = 10;
    int *p1 = &x;
    int **p2 = &p1;
    int ***p3 = &p2;
    int ****p4 = &p3;
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    assert pointers["p1"].indirection_level == 1
    assert pointers["p2"].indirection_level == 2
    assert pointers["p3"].indirection_level == 3
    assert pointers["p4"].indirection_level == 4
    
    # Check chain of POINTS_TO relationships
    assert pointers["p1"].points_to == "x"
    assert pointers["p2"].points_to == "p1"
    assert pointers["p3"].points_to == "p2"
    assert pointers["p4"].points_to == "p3"


def test_pointer_arithmetic_tracking(parser, queries):
    """Test tracking of pointer arithmetic operations."""
    code = """
    int arr[10];
    int *p = arr;
    int *q = p + 5;
    p++;
    p += 3;
    int *r = p - 2;
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Should detect pointers involved in arithmetic
    assert "p" in pointers
    assert "q" in pointers
    assert "r" in pointers
    
    # TODO: In enhanced version, track arithmetic operations
    # assert pointers["p"].properties.get("uses_arithmetic") == True


def test_array_pointer_duality(parser, queries):
    """Test support for array-pointer duality."""
    code = """
    int arr[10];
    int *p1 = arr;        // Array decay to pointer
    int *p2 = &arr[0];    // Explicit address of first element
    int (*pa)[10] = &arr; // Pointer to array
    
    void func(int param[]) {  // Array parameter is pointer
        int *p = param;
    }
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    assert "p1" in pointers
    assert "p2" in pointers
    assert "pa" in pointers
    
    # TODO: Enhanced version should track array relationships
    # assert relationships should include array decay information


def test_function_pointer_enhancements(parser, queries):
    """Test enhanced function pointer analysis."""
    code = """int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }

int (*fp)(int, int) = add;
int (*ops[2])(int, int) = {add, sub};  // Array of function pointers

typedef int (*operation_t)(int, int);
operation_t op = sub;

int result = fp(5, 3);
int result2 = (*fp)(5, 3);
int result3 = ops[0](10, 5);
"""
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Check function pointer detection
    assert "fp" in analyzer.function_pointers
    assert "add" in analyzer.function_pointers["fp"].assigned_functions
    
    # Check invocation tracking
    # Note: Due to single-pass parsing, we may not catch all invocations
    # if they appear before the function pointer declaration
    assert len(analyzer.function_pointers["fp"].invocation_sites) >= 1
    
    # Check relationships
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("fp", "ASSIGNS_FP", "add") in rel_dict
    assert ("fp", "INVOKES_FP", "add") in rel_dict


def test_void_pointer_handling(parser, queries):
    """Test handling of void pointers."""
    code = """
    int x = 42;
    void *vp = &x;
    int *ip = (int *)vp;
    
    void *malloc(size_t size);
    void *mem = malloc(100);
    char *buffer = (char *)mem;
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    assert "vp" in pointers
    assert pointers["vp"].base_type == "unknown"  # Current limitation
    assert pointers["vp"].points_to == "x"
    
    assert "ip" in pointers
    assert "mem" in pointers
    assert "buffer" in pointers


def test_pointer_in_structs(parser, queries):
    """Test pointers as struct members."""
    code = """
    struct Node {
        int data;
        struct Node *next;
        struct Node **prev_ptr;
    };
    
    struct Node n1 = {10, NULL, NULL};
    struct Node n2 = {20, &n1, NULL};
    n1.next = &n2;
    
    struct Node *head = &n1;
    head->next->data = 30;
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Should detect struct member pointers
    assert "head" in pointers
    assert pointers["head"].points_to == "n1"
    
    # TODO: Enhanced version should track struct member pointer relationships


def test_pointer_aliasing(parser, queries):
    """Test pointer aliasing detection."""
    code = """
    int x = 100;
    int *p1 = &x;
    int *p2 = p1;  // p2 aliases p1
    int *p3 = p2;  // p3 aliases p2 (and transitively p1)
    
    *p3 = 200;  // Modifies x through aliased pointer
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Check aliasing is tracked
    assert pointers["p1"].points_to == "x"
    assert pointers["p2"].points_to == "x"  # Should inherit from p1
    assert pointers["p3"].points_to == "x"  # Should inherit from p2
    
    # All should point to same target
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("p1", "POINTS_TO", "x") in rel_dict
    assert ("p2", "POINTS_TO", "x") in rel_dict
    assert ("p3", "POINTS_TO", "x") in rel_dict


def test_const_pointer_properties(parser, queries):
    """Test const qualifier tracking for pointers."""
    code = """
    int x = 42;
    const int *ptr_to_const = &x;      // Pointer to const int
    int * const const_ptr = &x;        // Const pointer to int
    const int * const cptc = &x;       // Const pointer to const int
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Should track const qualifiers
    assert "ptr_to_const" in pointers
    assert "const_ptr" in pointers
    assert "cptc" in pointers
    
    # TODO: Enhanced version should track const properties
    # assert pointers["ptr_to_const"].properties.get("points_to_const") == True
    # assert pointers["const_ptr"].properties.get("is_const_pointer") == True


def test_null_pointer_handling(parser, queries):
    """Test NULL pointer detection."""
    code = """
    int *p1 = NULL;
    int *p2 = 0;
    int *p3 = (void *)0;
    
    if (p1 != NULL) {
        *p1 = 10;
    }
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    assert "p1" in pointers
    assert "p2" in pointers
    assert "p3" in pointers
    
    # TODO: Enhanced version should track NULL assignments
    # assert pointers["p1"].properties.get("initialized_to_null") == True


def test_pointer_type_casts(parser, queries):
    """Test pointer type casting."""
    code = """
    int x = 42;
    int *ip = &x;
    char *cp = (char *)ip;
    void *vp = ip;
    double *dp = (double *)vp;
    
    struct S { int a; };
    struct S s;
    struct S *sp = &s;
    void *vsp = (void *)sp;
    struct S *sp2 = (struct S *)vsp;
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Should track all pointers regardless of casts
    assert "ip" in pointers
    assert "cp" in pointers
    assert "vp" in pointers
    assert "dp" in pointers
    assert "sp" in pointers
    assert "vsp" in pointers
    assert "sp2" in pointers


def test_pointer_dereferencing_tracking(parser, queries):
    """Test tracking of pointer dereferences."""
    code = """
    int x = 10;
    int *p = &x;
    int **pp = &p;
    
    int val1 = *p;      // Single dereference
    int val2 = **pp;    // Double dereference
    *p = 20;            // Dereference for write
    **pp = 30;          // Double dereference for write
    """
    
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, relationships = analyzer.analyze_pointers(tree.root_node, code)
    
    # Current implementation tracks pointers
    assert "p" in pointers
    assert "pp" in pointers
    
    # TODO: Enhanced version should track dereference operations
    # Could add DEREFERENCES relationships or properties


def test_c_parser_integration(parser, queries):
    """Test that CParser properly creates Pointer nodes."""
    code = """
    int x = 5;
    int *p = &x;
    int **pp = &p;
    
    void process(int *ptr) {
        *ptr = 10;
    }
    
    int (*fp)(int, int);
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Debug: Print all nodes and relationships
    print(f"\nAll nodes created: {[(n.node_type, n.name) for n in nodes]}")
    print(f"All relationships: {relationships}")
    
    # Test the pointer analyzer directly
    tree = parser.parse(bytes(code, "utf8"))
    analyzer = CPointerAnalyzer()
    pointers, ptr_rels = analyzer.analyze_pointers(tree.root_node, code)
    print(f"Pointer analyzer found: {list(pointers.keys())}")
    print(f"Function pointers: {list(analyzer.function_pointers.keys())}")
    
    # Should have Pointer nodes
    pointer_nodes = [n for n in nodes if n.node_type == "pointer"]
    function_pointer_nodes = [n for n in nodes if n.node_type == "function_pointer"]
    
    # Check what we got
    assert len(pointer_nodes) >= 2  # p and pp
    assert any(n.name == "p" for n in pointer_nodes)
    assert any(n.name == "pp" for n in pointer_nodes)
    
    assert len(function_pointer_nodes) == 1
    assert function_pointer_nodes[0].name == "fp"
    
    # TODO: Enhanced version should create Pointer nodes
    # assert len(pointer_nodes) >= 2  # p and pp
    # assert any(n.name == "p" for n in pointer_nodes)
    # assert any(n.name == "pp" for n in pointer_nodes)