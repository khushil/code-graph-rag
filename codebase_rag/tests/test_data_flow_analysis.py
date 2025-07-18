"""Tests for data flow analysis (REQ-DF-1, REQ-DF-2)."""

from unittest.mock import MagicMock, patch

import pytest
from tree_sitter import Node

from codebase_rag.analysis.data_flow import (
    DataFlowAnalyzer,
    DataFlowEdge,
    VariableDefinition,
)


class TestDataFlowAnalyzer:
    """Test the data flow analysis functionality."""

    @pytest.fixture
    def mock_parser(self):
        """Create a mock parser."""
        return MagicMock()

    @pytest.fixture
    def analyzer(self, mock_parser):
        """Create a data flow analyzer."""
        queries = {
            "assignment": MagicMock(),
            "function_definition": MagicMock(),
            "return_statement": MagicMock(),
        }
        return DataFlowAnalyzer(mock_parser, queries, "python")

    def test_variable_definition(self):
        """Test VariableDefinition dataclass."""
        var_def = VariableDefinition(
            name="count",
            type_hint="int",
            line_number=10,
            scope="module.function",
            initial_value="0",
            is_parameter=False,
            is_global=False,
            is_mutable=True,
        )
        
        assert var_def.name == "count"
        assert var_def.type_hint == "int"
        assert var_def.line_number == 10
        assert var_def.scope == "module.function"
        assert var_def.initial_value == "0"
        assert not var_def.is_parameter
        assert not var_def.is_global
        assert var_def.is_mutable

    def test_data_flow_edge(self):
        """Test DataFlowEdge dataclass."""
        flow = DataFlowEdge(
            source="user_input",
            target="data",
            flow_type="ASSIGNS",
            line_number=20,
            is_tainted=True,
            taint_source="input",
        )
        
        assert flow.source == "user_input"
        assert flow.target == "data"
        assert flow.flow_type == "ASSIGNS"
        assert flow.line_number == 20
        assert flow.is_tainted
        assert flow.taint_source == "input"

    def test_taint_detection(self, analyzer):
        """Test taint source detection."""
        assert analyzer._is_tainted("request.get('data')")
        assert analyzer._is_tainted("sys.argv[1]")
        assert analyzer._is_tainted("input()")
        assert analyzer._is_tainted("os.environ['KEY']")
        assert not analyzer._is_tainted("'hello world'")
        assert not analyzer._is_tainted("42")

    def test_taint_source_extraction(self, analyzer):
        """Test extracting taint source from expression."""
        assert analyzer._get_taint_source("request.get('data')") == "request"
        assert analyzer._get_taint_source("sys.argv[1]") == "argv"
        assert analyzer._get_taint_source("input()") == "input"
        assert analyzer._get_taint_source("'hello'") is None

    def test_process_assignment(self, analyzer):
        """Test processing assignment statements."""
        # Mock nodes
        target_node = MagicMock()
        target_node.start_point = (9, 0)  # Line 10
        source_node = MagicMock()
        
        match = {"target": target_node, "source": source_node}
        
        # Mock get_node_text to return specific values
        with patch(
            "codebase_rag.analysis.data_flow.get_node_text"
        ) as mock_get_text:
            mock_get_text.side_effect = ["x", "input()"]
            
            analyzer._process_assignment(match, "source_code", "module")
            
            # Check variable was created
            assert "x" in analyzer.variables
            var_def = analyzer.variables["x"]
            assert var_def.name == "x"
            assert var_def.initial_value == "input()"
            assert var_def.line_number == 10
            
            # Check data flow was created
            assert len(analyzer.data_flows) == 1
            flow = analyzer.data_flows[0]
            assert flow.source == "input()"
            assert flow.target == "x"
            assert flow.flow_type == "ASSIGNS"
            assert flow.is_tainted
            assert flow.taint_source == "input"

    def test_process_function_params(self, analyzer):
        """Test processing function parameters."""
        func_name_node = MagicMock()
        param_node = MagicMock()
        param_node.start_point = (4, 0)  # Line 5
        
        match = {"func_name": func_name_node, "param": param_node}
        
        with patch(
            "codebase_rag.analysis.data_flow.get_node_text"
        ) as mock_get_text:
            mock_get_text.side_effect = ["arg1", "my_function"]
            
            analyzer._process_function_params(match, "source_code", "module")
            
            # Check parameter variable was created
            assert "arg1" in analyzer.variables
            var_def = analyzer.variables["arg1"]
            assert var_def.name == "arg1"
            assert var_def.is_parameter
            assert var_def.scope == "module.my_function"
            assert var_def.line_number == 5

    def test_process_return(self, analyzer):
        """Test processing return statements."""
        return_node = MagicMock()
        return_node.start_point = (19, 0)  # Line 20
        
        match = {"return_value": return_node}
        
        with patch(
            "codebase_rag.analysis.data_flow.get_node_text"
        ) as mock_get_text:
            mock_get_text.return_value = "result + 1"
            
            analyzer._process_return(match, "source_code", "module")
            
            # Check return flow was created
            assert len(analyzer.data_flows) == 1
            flow = analyzer.data_flows[0]
            assert flow.source == "result + 1"
            assert flow.target == "@return"
            assert flow.flow_type == "RETURNS"
            assert flow.line_number == 20

    def test_c_variable_name_extraction(self, analyzer):
        """Test extracting variable names from C declarators."""
        # Simple identifier
        node = MagicMock()
        node.type = "identifier"
        
        with patch(
            "codebase_rag.analysis.data_flow.get_node_text"
        ) as mock_get_text:
            mock_get_text.return_value = "var_name"
            
            name = analyzer._extract_c_var_name(node, "source")
            assert name == "var_name"

    def test_build_graph_elements(self, analyzer):
        """Test building graph nodes and relationships."""
        # Add some test data
        analyzer.variables["x"] = VariableDefinition(
            name="x",
            type_hint="int",
            line_number=10,
            scope="module.func",
            initial_value="0",
        )
        
        analyzer.data_flows.append(
            DataFlowEdge(
                source="0",
                target="x",
                flow_type="ASSIGNS",
                line_number=10,
            )
        )
        
        nodes, relationships = analyzer._build_graph_elements("module")
        
        # Check Variable node
        assert len(nodes) == 1
        var_node = nodes[0]
        assert var_node["label"] == "Variable"
        assert var_node["properties"]["name"] == "x"
        assert var_node["properties"]["qualified_name"] == "module.func.x"
        assert var_node["properties"]["type_hint"] == "int"
        
        # Check FLOWS_TO relationship
        assert len(relationships) == 1
        flow_rel = relationships[0]
        assert flow_rel["rel_type"] == "FLOWS_TO"
        assert flow_rel["start_value"] == "0"
        assert flow_rel["end_value"] == "x"
        assert flow_rel["properties"]["flow_type"] == "ASSIGNS"

    def test_cross_function_flows(self, analyzer):
        """Test tracking cross-function data flows."""
        call_graph = {
            "main": ["process_data", "validate"],
            "process_data": ["transform"],
        }
        
        flows = analyzer.track_cross_function_flows(call_graph)
        
        assert len(flows) == 3
        
        # Check first flow
        flow1 = flows[0]
        assert flow1["start_value"] == "main"
        assert flow1["end_value"] == "process_data"
        assert flow1["rel_type"] == "PASSES_DATA_TO"

    def test_taint_analysis(self, analyzer):
        """Test performing taint analysis."""
        # Add tainted flows
        analyzer.data_flows.extend([
            DataFlowEdge(
                source="input()",
                target="user_data",
                flow_type="ASSIGNS",
                line_number=10,
                is_tainted=True,
                taint_source="input",
            ),
            DataFlowEdge(
                source="user_data",
                target="processed",
                flow_type="ASSIGNS",
                line_number=20,
                is_tainted=True,
                taint_source="input",
            ),
        ])
        
        taint_paths = analyzer.perform_taint_analysis(["main"])
        
        assert len(taint_paths) == 2
        assert ("input", "user_data", "ASSIGNS") in taint_paths
        assert ("input", "processed", "ASSIGNS") in taint_paths