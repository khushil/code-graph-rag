"""Integration test for data flow analysis with graph updater."""

from unittest.mock import Mock

import pytest

from codebase_rag.graph_updater import GraphUpdater
from codebase_rag.parser_loader import load_parsers


class TestDataFlowIntegration:
    """Test data flow analysis integration with graph updater."""

    @pytest.fixture
    def mock_ingestor(self):
        """Create a mock ingestor."""
        mock = Mock()
        mock.batch_update_nodes = Mock()
        mock.batch_update_relationships = Mock()
        mock.clear_and_flush_buffer = Mock()
        return mock

    @pytest.fixture
    def graph_updater(self, mock_ingestor, tmp_path):
        """Create a graph updater with mock ingestor."""
        parsers, queries = load_parsers()
        return GraphUpdater(mock_ingestor, tmp_path, parsers, queries)

    def test_data_flow_nodes_created(self, graph_updater, mock_ingestor, tmp_path):
        """Test that Variable nodes are created during data flow analysis."""
        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.write_text('''
# Global variable
config = {"debug": True}

def process_data(input_data):
    # Local variable
    result = input_data * 2
    temp = result + 10
    return temp

class DataHandler:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)
        count = len(self.data)
        return count
''')

        # Process the file
        graph_updater.parse_and_ingest_file(test_file, "python")

        # Check that Variable nodes were created
        variable_nodes = []
        for call in mock_ingestor.batch_update_nodes.call_args_list:
            label, nodes = call[0]
            if label == "Variable":
                variable_nodes.extend(nodes)

        # Verify we have the expected variables
        var_names = {node["name"] for node in variable_nodes}
        assert "config" in var_names, "Global variable 'config' not found"
        assert "input_data" in var_names, "Parameter 'input_data' not found"
        assert "result" in var_names, "Local variable 'result' not found"
        assert "temp" in var_names, "Local variable 'temp' not found"
        assert "data" in var_names, "Class field 'data' not found"
        assert "count" in var_names, "Local variable 'count' not found"

        # Check variable types
        var_by_name = {node["name"]: node for node in variable_nodes}
        assert var_by_name["config"]["var_type"] == "global"
        assert var_by_name["input_data"]["var_type"] == "parameter"
        assert var_by_name["result"]["var_type"] == "local"
        assert var_by_name["data"]["var_type"] == "field"

    def test_data_flow_relationships_created(self, graph_updater, mock_ingestor, tmp_path):
        """Test that FLOWS_TO relationships are created."""
        # Create test file with clear data flows
        test_file = tmp_path / "flows.py"
        test_file.write_text('''
def calculate(x):
    # Direct assignment
    y = x
    # Binary operation
    z = y + 10
    # Function call
    result = transform(z)
    return result

def transform(value):
    return value * 2
''')

        # Process the file
        graph_updater.parse_and_ingest_file(test_file, "python")

        # Check that FLOWS_TO relationships were created
        flows_to_rels = []
        for call in mock_ingestor.batch_update_relationships.call_args_list:
            rels = call[0][0]  # First positional argument is the list of relationships
            for rel in rels:
                if len(rel) >= 2 and rel[1] == "FLOWS_TO":
                    flows_to_rels.append(rel)

        # We should have some FLOWS_TO relationships
        assert len(flows_to_rels) > 0, "No FLOWS_TO relationships were created"
