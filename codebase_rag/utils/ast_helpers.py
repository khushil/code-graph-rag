"""AST helper functions for tree-sitter parsing."""

from tree_sitter import Node


def get_node_text(node: Node, source_code: str) -> str:
    """Extract text content from a tree-sitter node."""
    if not node:
        return ""
    return source_code[node.start_byte:node.end_byte]


def find_nodes_by_type(node: Node, node_type: str) -> list[Node]:
    """Find all nodes of a specific type in the AST."""
    results = []
    
    def visit(n: Node) -> None:
        if n.type == node_type:
            results.append(n)
        for child in n.children:
            visit(child)
            
    visit(node)
    return results


def get_parent_of_type(node: Node, parent_type: str) -> Node | None:
    """Find the first parent node of a specific type."""
    current = node.parent
    while current:
        if current.type == parent_type:
            return current
        current = current.parent
    return None


def get_function_name(node: Node, source_code: str) -> str | None:
    """Extract function name from a function node."""
    if node.type in ["function_definition", "function_declaration", "method_definition"]:
        for child in node.children:
            if child.type == "identifier":
                return get_node_text(child, source_code)
    return None


def get_class_name(node: Node, source_code: str) -> str | None:
    """Extract class name from a class node."""
    if node.type in ["class_definition", "class_declaration"]:
        for child in node.children:
            if child.type == "identifier":
                return get_node_text(child, source_code)
    return None


def is_inside_function(node: Node) -> bool:
    """Check if a node is inside a function definition."""
    return get_parent_of_type(node, "function_definition") is not None


def is_inside_class(node: Node) -> bool:
    """Check if a node is inside a class definition."""
    return get_parent_of_type(node, "class_definition") is not None


def get_line_number(node: Node) -> int:
    """Get the line number of a node (1-indexed)."""
    return node.start_point[0] + 1


def get_column_number(node: Node) -> int:
    """Get the column number of a node (0-indexed)."""
    return node.start_point[1]