"""Tests for graph indexing functionality (REQ-SCL-3)."""

from unittest.mock import MagicMock, call

import pytest

from codebase_rag.graph_indexing import GraphIndexManager


class TestGraphIndexManager:
    """Test the graph indexing functionality."""

    @pytest.fixture
    def mock_ingestor(self):
        """Create a mock ingestor."""
        ingestor = MagicMock()
        ingestor.execute_write = MagicMock()
        ingestor.fetch_all = MagicMock(return_value=[])
        return ingestor

    @pytest.fixture
    def index_manager(self, mock_ingestor):
        """Create an index manager with mock ingestor."""
        return GraphIndexManager(mock_ingestor)

    def test_create_indexes(self, index_manager, mock_ingestor):
        """Test creating all indexes."""
        index_manager.create_indexes()
        
        # Should have created multiple indexes
        assert mock_ingestor.execute_write.call_count > 10
        
        # Check some specific indexes were created
        calls = mock_ingestor.execute_write.call_args_list
        index_queries = [call[0][0] for call in calls]
        
        # File indexes
        assert "CREATE INDEX ON :File(path)" in index_queries
        assert "CREATE INDEX ON :File(name)" in index_queries
        assert "CREATE INDEX ON :File(language)" in index_queries
        
        # Function indexes
        assert "CREATE INDEX ON :Function(qualified_name)" in index_queries
        assert "CREATE INDEX ON :Function(name)" in index_queries
        
        # Class indexes
        assert "CREATE INDEX ON :Class(qualified_name)" in index_queries
        assert "CREATE INDEX ON :Class(name)" in index_queries

    def test_create_index_already_exists(self, index_manager, mock_ingestor):
        """Test handling when index already exists."""
        # Simulate index already exists error
        mock_ingestor.execute_write.side_effect = Exception("Index already exists")
        
        # Should not raise exception
        index_manager._create_index("File", "path")
        
        # Should have attempted to create
        mock_ingestor.execute_write.assert_called_once_with("CREATE INDEX ON :File(path)")

    def test_drop_all_indexes(self, index_manager, mock_ingestor):
        """Test dropping all indexes."""
        # Mock existing indexes
        mock_ingestor.fetch_all.return_value = [
            {"index_name": "idx_file_path"},
            {"index_name": "idx_function_name"},
        ]
        
        index_manager.drop_all_indexes()
        
        # Should fetch index info
        mock_ingestor.fetch_all.assert_called_once_with("SHOW INDEX INFO")
        
        # Should drop each index
        expected_drops = [
            call("DROP INDEX idx_file_path"),
            call("DROP INDEX idx_function_name"),
        ]
        mock_ingestor.execute_write.assert_has_calls(expected_drops)

    def test_get_index_stats(self, index_manager, mock_ingestor):
        """Test getting index statistics."""
        # Mock index info
        mock_ingestor.fetch_all.return_value = [
            {
                "index_name": "idx_file_path",
                "label": "File",
                "property": "path",
                "index_type": "btree",
            },
            {
                "index_name": "idx_function_name",
                "label": "Function",
                "property": "name",
                "index_type": "btree",
            },
        ]
        
        stats = index_manager.get_index_stats()
        
        assert len(stats) == 2
        assert stats[0]["name"] == "idx_file_path"
        assert stats[0]["label"] == "File"
        assert stats[0]["property"] == "path"
        assert stats[1]["name"] == "idx_function_name"
        assert stats[1]["label"] == "Function"
        assert stats[1]["property"] == "name"

    def test_analyze_query_performance(self, index_manager, mock_ingestor):
        """Test analyzing query performance."""
        # Mock query plan
        mock_ingestor.fetch_all.return_value = [
            {"operator": "IndexScan"},
            {"operator": "Filter"},
            {"operator": "Return"},
        ]
        
        query = "MATCH (f:Function {name: 'test'}) RETURN f"
        plan_info = index_manager.analyze_query_performance(query)
        
        assert plan_info["query"] == query
        assert plan_info["uses_indexes"] is True
        assert "IndexScan" in plan_info["operators"]
        assert len(plan_info["operators"]) == 3

    def test_optimize_for_common_queries(self, index_manager, mock_ingestor):
        """Test creating indexes for common query patterns."""
        index_manager.optimize_for_common_queries()
        
        # Should create indexes for common patterns
        calls = mock_ingestor.execute_write.call_args_list
        index_queries = [call[0][0] for call in calls]
        
        # Check common pattern indexes
        assert "CREATE INDEX ON :Function(name)" in index_queries
        assert "CREATE INDEX ON :Method(name)" in index_queries
        assert "CREATE INDEX ON :File(path)" in index_queries
        assert "CREATE INDEX ON :Class(name)" in index_queries
        assert "CREATE INDEX ON :Import(module)" in index_queries