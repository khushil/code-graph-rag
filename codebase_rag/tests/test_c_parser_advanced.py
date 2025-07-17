
import pytest

from codebase_rag.parser_loader import load_parsers
from codebase_rag.parsers.c_parser import CParser


class TestCParserAdvanced:
    """Test advanced C parsing features."""

    @pytest.fixture
    def c_parser(self):
        """Create C parser instance."""
        parsers, queries = load_parsers()
        return CParser(parsers["c"], queries["c"])

    def test_parse_typedefs(self, c_parser):
        """Test typedef parsing and TYPE_OF relationships."""
        code = """
        typedef int MyInt;
        typedef struct Point {
            int x;
            int y;
        } Point;
        typedef struct {
            double lat;
            double lon;
        } GeoLocation;
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check typedef nodes
        typedefs = [n for n in nodes if n.node_type == "typedef"]
        assert len(typedefs) == 3

        typedef_names = [t.name for t in typedefs]
        assert "MyInt" in typedef_names
        assert "Point" in typedef_names
        assert "GeoLocation" in typedef_names

        # Check TYPE_OF relationships
        type_ofs = [(r[0], r[3]) for r in relationships if r[1] == "TYPE_OF"]
        assert ("MyInt", "int") in type_ofs

    def test_parse_preprocessor(self, c_parser):
        """Test preprocessor directive parsing."""
        code = """
        #include <stdio.h>
        #include "myheader.h"

        #define MAX_SIZE 100
        #define SQUARE(x) ((x) * (x))

        #ifdef DEBUG
        #define LOG(msg) printf("DEBUG: %s\\n", msg)
        #else
        #define LOG(msg)
        #endif
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check macro nodes
        macros = [n for n in nodes if n.node_type == "macro"]
        assert len(macros) >= 3  # MAX_SIZE, SQUARE, LOG

        macro_dict = {m.name: m for m in macros}
        assert "MAX_SIZE" in macro_dict
        assert "SQUARE" in macro_dict
        assert macro_dict["SQUARE"].properties["is_function_like"] is True
        assert macro_dict["MAX_SIZE"].properties["is_function_like"] is False

        # Check INCLUDES relationships
        includes = [(r[3]) for r in relationships if r[1] == "INCLUDES"]
        assert "stdio.h" in includes
        assert "myheader.h" in includes

        # Check USES_MACRO relationships
        uses_macros = [(r[3]) for r in relationships if r[1] == "USES_MACRO"]
        assert "DEBUG" in uses_macros

    def test_parse_global_variables(self, c_parser):
        """Test global variable extraction."""
        code = """
        int global_counter = 0;
        static const char* VERSION = "1.0.0";
        extern int errno;

        struct Config {
            int port;
            char host[256];
        } server_config = {8080, "localhost"};

        void func() {
            int local_var = 10;  // Should not be extracted
        }
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check global variables
        globals = [n for n in nodes if n.node_type == "global_var"]
        assert len(globals) == 4

        global_dict = {g.name: g for g in globals}
        assert "global_counter" in global_dict
        assert "VERSION" in global_dict
        assert "errno" in global_dict
        assert "server_config" in global_dict

        # Check properties
        assert global_dict["VERSION"].properties["is_static"] is True
        assert global_dict["VERSION"].properties["is_const"] is True
        assert global_dict["errno"].properties["is_extern"] is True

    def test_parse_function_calls(self, c_parser):
        """Test function call extraction."""
        code = """
        void helper() {
            printf("Helper function\\n");
        }

        int calculate(int a, int b) {
            helper();
            return add(a, b);
        }

        int main() {
            int result = calculate(5, 3);
            helper();
            return 0;
        }
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check CALLS relationships
        calls = [(r[0], r[3]) for r in relationships if r[1] == "CALLS"]
        assert ("calculate", "helper") in calls
        assert ("calculate", "add") in calls
        assert ("main", "calculate") in calls
        assert ("main", "helper") in calls

    def test_parse_structs_with_fields(self, c_parser):
        """Test struct field extraction."""
        code = """
        struct Person {
            char name[50];
            int age;
            struct Address* address;
        };

        union Data {
            int i;
            float f;
            char str[20];
        };
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check struct node
        structs = [n for n in nodes if n.node_type == "struct"]
        assert len(structs) == 1

        person_struct = structs[0]
        assert person_struct.name == "Person"

        # Check fields
        fields = person_struct.properties["fields"]
        assert len(fields) == 3
        field_names = [f["name"] for f in fields]
        assert "name" in field_names
        assert "age" in field_names
        assert "address" in field_names

        # Check union
        unions = [n for n in nodes if n.node_type == "union"]
        assert len(unions) == 1
        assert unions[0].name == "Data"

    def test_parse_enums(self, c_parser):
        """Test enum parsing with values."""
        code = """
        enum Status {
            OK = 0,
            ERROR = -1,
            PENDING
        };

        enum {
            FLAG_READ = 1 << 0,
            FLAG_WRITE = 1 << 1,
            FLAG_EXECUTE = 1 << 2
        };
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check enum nodes
        enums = [n for n in nodes if n.node_type == "enum"]
        assert len(enums) == 2

        # Check named enum
        status_enum = next((e for e in enums if e.name == "Status"), None)
        assert status_enum is not None

        # Check enum values
        values = status_enum.properties["values"]
        assert len(values) == 3
        value_dict = {v["name"]: v["value"] for v in values}
        assert value_dict["OK"] == "0"
        assert value_dict["ERROR"] == "-1"
        assert value_dict["PENDING"] is None  # No explicit value

        # Check anonymous enum
        anon_enums = [e for e in enums if e.properties.get("is_anonymous", False)]
        assert len(anon_enums) == 1

    def test_parse_function_with_parameters(self, c_parser):
        """Test function parameter extraction."""
        code = """
        int add(int a, int b) {
            return a + b;
        }

        void process_data(const char* data, size_t len, int flags) {
            // Process data
        }

        static inline int max(int x, int y) {
            return x > y ? x : y;
        }
        """

        nodes, relationships = c_parser.parse_file("test.c", code)

        # Check functions
        functions = [n for n in nodes if n.node_type == "function"]
        assert len(functions) == 3

        func_dict = {f.name: f for f in functions}

        # Check add function
        assert func_dict["add"].properties["return_type"] == "int"
        add_params = func_dict["add"].properties["parameters"]
        assert len(add_params) == 2
        assert add_params[0]["name"] == "a"
        assert add_params[0]["type"] == "int"

        # Check process_data function
        process_params = func_dict["process_data"].properties["parameters"]
        assert len(process_params) == 3
        assert process_params[0]["type"] == "const char*"
        assert process_params[1]["name"] == "len"

        # Check static inline function
        assert func_dict["max"].properties["is_static"] is True
        assert func_dict["max"].properties["is_inline"] is True
