import pytest
from pathlib import Path
from tree_sitter import Parser
from codebase_rag.parser_loader import load_parsers
from codebase_rag.language_config import get_language_config


class TestCParser:
    """Test C language parsing functionality."""
    
    @pytest.fixture
    def parsers_and_queries(self):
        """Load parsers and queries."""
        parsers, queries = load_parsers()
        return parsers, queries
    
    def test_c_parser_loaded(self, parsers_and_queries):
        """Test that C parser is successfully loaded."""
        parsers, queries = parsers_and_queries
        assert "c" in parsers
        assert "c" in queries
        assert queries["c"]["functions"] is not None
        assert queries["c"]["classes"] is not None  # For structs/unions/enums
    
    def test_c_language_config(self):
        """Test C language configuration."""
        config = get_language_config(".c")
        assert config is not None
        assert config.name == "c"
        assert ".c" in config.file_extensions
        assert ".h" in config.file_extensions
        assert "function_definition" in config.function_node_types
        assert "struct_specifier" in config.class_node_types
    
    def test_parse_simple_c_file(self, parsers_and_queries):
        """Test parsing a simple C file."""
        parsers, queries = parsers_and_queries
        parser = parsers["c"]
        
        # Read test file
        test_file = Path(__file__).parent / "fixtures" / "c_samples" / "hello.c"
        code = test_file.read_text()
        
        # Parse the code
        tree = parser.parse(bytes(code, "utf8"))
        assert tree.root_node is not None
        
        # Query for functions
        function_query = queries["c"]["functions"]
        captures = function_query.matches(tree.root_node)
        
        # Extract function names
        function_names = []
        for match in captures:
            for node, _ in match:
                if hasattr(node, 'child_by_field_name'):
                    name_node = node.child_by_field_name('declarator')
                    if name_node:
                        # Navigate through pointer declarators if present
                        while name_node.type == 'pointer_declarator':
                            name_node = name_node.child_by_field_name('declarator')
                        if name_node.type == 'function_declarator':
                            identifier = name_node.child_by_field_name('declarator')
                            if identifier and identifier.type == 'identifier':
                                function_names.append(identifier.text.decode('utf-8'))
        
        assert "print_hello" in function_names
        assert "add" in function_names
        assert "main" in function_names
    
    def test_parse_structs_and_enums(self, parsers_and_queries):
        """Test parsing structs and enums."""
        parsers, queries = parsers_and_queries
        parser = parsers["c"]
        
        # Read test file
        test_file = Path(__file__).parent / "fixtures" / "c_samples" / "structs.c"
        code = test_file.read_text()
        
        # Parse the code
        tree = parser.parse(bytes(code, "utf8"))
        
        # Query for classes (structs/unions/enums)
        class_query = queries["c"]["classes"]
        captures = class_query.matches(tree.root_node)
        
        # Check that we found some structs/enums
        assert len(list(captures)) > 0
    
    def test_parse_header_file(self, parsers_and_queries):
        """Test parsing a header file."""
        parsers, queries = parsers_and_queries
        parser = parsers["c"]
        
        # Read test file
        test_file = Path(__file__).parent / "fixtures" / "c_samples" / "math_utils.h"
        code = test_file.read_text()
        
        # Parse the code
        tree = parser.parse(bytes(code, "utf8"))
        assert tree.root_node is not None
        
        # The header should parse without errors
        assert not tree.root_node.has_error