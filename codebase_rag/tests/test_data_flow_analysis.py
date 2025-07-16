"""Test data flow analysis functionality (REQ-DF-1, REQ-DF-2)."""

import pytest
from pathlib import Path
from tree_sitter import Parser, Language

from codebase_rag.analysis.data_flow import DataFlowAnalyzer, VariableNode, FlowEdge
from codebase_rag.parser_loader import load_parsers


class TestDataFlowAnalysis:
    """Test data flow analysis for various languages."""
    
    @pytest.fixture(scope="class")
    def parsers_and_queries(self):
        """Load parsers and queries once for all tests."""
        parsers, queries = load_parsers()
        return parsers, queries
    
    def test_python_variable_detection(self, parsers_and_queries):
        """Test detection of Python variables (REQ-DF-1)."""
        parsers, queries = parsers_and_queries
        
        python_code = '''
# Global variable
global_var = 42

def calculate(x, y):
    # Local variable
    result = x + y
    temp = result * 2
    return temp

class Calculator:
    def __init__(self):
        self.value = 0
    
    def add(self, x):
        self.value += x
        local_sum = self.value + 10
        return local_sum
'''
        
        analyzer = DataFlowAnalyzer(parsers["python"], queries["python"], "python")
        variables, flows = analyzer.analyze_file("test.py", python_code, "test_module")
        
        # Check variables
        var_names = {v.name for v in variables}
        assert "global_var" in var_names
        assert "x" in var_names  # function parameter
        assert "y" in var_names  # function parameter
        assert "result" in var_names
        assert "temp" in var_names
        assert "value" in var_names  # class field
        assert "local_sum" in var_names
        
        # Check variable types
        var_by_name = {v.name: v for v in variables}
        assert var_by_name["global_var"].var_type == "global"
        assert var_by_name["x"].var_type == "parameter"
        assert var_by_name["result"].var_type == "local"
        assert var_by_name["value"].var_type == "field"
        
        # Check scopes
        assert var_by_name["global_var"].scope == "test_module"
        assert var_by_name["result"].scope == "test_module.calculate"
        assert var_by_name["value"].scope == "test_module.Calculator"
    
    def test_python_data_flow(self, parsers_and_queries):
        """Test Python data flow relationships (REQ-DF-2)."""
        parsers, queries = parsers_and_queries
        
        python_code = '''
def process_data(input_value):
    # Direct assignment flow
    x = input_value
    
    # Binary operation flow
    y = x + 10
    
    # Function call flow
    z = transform(y)
    
    # Attribute access flow
    result = self.compute(z)
    
    return result

def transform(value):
    return value * 2
'''
        
        analyzer = DataFlowAnalyzer(parsers["python"], queries["python"], "python")
        variables, flows = analyzer.analyze_file("test.py", python_code, "test_module")
        
        # Check flows exist
        assert len(flows) > 0
        
        # Check flow types
        flow_types = {f.flow_type for f in flows}
        assert "assigns" in flow_types
        assert "reads" in flow_types
        assert "returns_from" in flow_types
    
    def test_python_class_fields(self, parsers_and_queries):
        """Test detection of class fields and instance variables."""
        parsers, queries = parsers_and_queries
        
        python_code = '''
class DataProcessor:
    # Class-level field
    default_value = 100
    
    def __init__(self, name):
        # Instance fields
        self.name = name
        self.data = []
        self.count = 0
    
    def process(self, item):
        self.data.append(item)
        self.count += 1
        local_var = self.count * 2
        return local_var
'''
        
        analyzer = DataFlowAnalyzer(parsers["python"], queries["python"], "python")
        variables, flows = analyzer.analyze_file("test.py", python_code, "test_module")
        
        # Check class fields
        fields = [v for v in variables if v.var_type == "field"]
        field_names = {f.name for f in fields}
        
        assert "default_value" in field_names
        assert "name" in field_names
        assert "data" in field_names
        assert "count" in field_names
        
        # Check field scopes
        for field in fields:
            assert field.scope == "test_module.DataProcessor"
    
    def test_javascript_variable_detection(self, parsers_and_queries):
        """Test JavaScript variable detection."""
        parsers, queries = parsers_and_queries
        
        if "javascript" not in parsers:
            pytest.skip("JavaScript parser not available")
        
        js_code = '''
// Global variables
let globalVar = 42;
const CONSTANT = "hello";
var oldStyleVar = true;

function processData(input) {
    // Local variables
    let result = input * 2;
    const temp = result + 10;
    
    // Arrow function with parameters
    const transform = (x, y) => {
        let sum = x + y;
        return sum;
    };
    
    return transform(result, temp);
}

class DataHandler {
    constructor() {
        this.value = 0;
        this.items = [];
    }
    
    add(item) {
        this.items.push(item);
        let newCount = this.items.length;
        return newCount;
    }
}
'''
        
        analyzer = DataFlowAnalyzer(parsers["javascript"], queries["javascript"], "javascript")
        variables, flows = analyzer.analyze_file("test.js", js_code, "test_module")
        
        # For now, just check that analysis completes without error
        # Full JavaScript implementation would be done in the analyzer
        assert isinstance(variables, list)
        assert isinstance(flows, list)
    
    def test_c_variable_detection(self, parsers_and_queries):
        """Test C variable detection including pointers."""
        parsers, queries = parsers_and_queries
        
        if "c" not in parsers:
            pytest.skip("C parser not available")
        
        c_code = '''
// Global variables
int global_count = 0;
char* global_string = "Hello";

int process_data(int input, char* buffer) {
    // Local variables
    int result = input * 2;
    int* ptr = &result;
    char local_buffer[256];
    
    // Pointer operations
    *ptr = result + 10;
    
    return *ptr;
}

struct DataNode {
    int value;
    struct DataNode* next;
};

void update_node(struct DataNode* node) {
    node->value = 42;
    struct DataNode* temp = node->next;
    temp->value = 100;
}
'''
        
        analyzer = DataFlowAnalyzer(parsers["c"], queries["c"], "c")
        variables, flows = analyzer.analyze_file("test.c", c_code, "test_module")
        
        # For now, just check that analysis completes without error
        # Full C implementation would be done in the analyzer
        assert isinstance(variables, list)
        assert isinstance(flows, list)
    
    def test_flow_confidence(self, parsers_and_queries):
        """Test flow confidence scoring for uncertain flows."""
        parsers, queries = parsers_and_queries
        
        python_code = '''
def dynamic_flow(condition):
    if condition:
        x = 10
    else:
        x = 20
    
    # x could be from either branch
    y = x + 5
    
    # Dynamic attribute access
    obj = get_object()
    value = obj.some_attr
    
    return value
'''
        
        analyzer = DataFlowAnalyzer(parsers["python"], queries["python"], "python")
        variables, flows = analyzer.analyze_file("test.py", python_code, "test_module")
        
        # Check that flows are created
        assert len(flows) > 0
        
        # All flows should have confidence scores
        for flow in flows:
            assert 0.0 <= flow.confidence <= 1.0