"""Tests for graph indexing functionality (REQ-SCL-3)."""

import time
from unittest.mock import MagicMock

import pytest

from codebase_rag.graph_indexing import (
    GraphIndexManager,
    IndexDefinition,
    OptimizedQuerier,
    QueryCache,
    QueryStats,
)


class TestIndexDefinition:
    """Test index definition functionality."""

    def test_index_definition_creation(self):
        """Test creating index definitions."""
        index = IndexDefinition("Function", "qualified_name", "BTREE")

        assert index.label == "Function"
        assert index.property == "qualified_name"
        assert index.index_type == "BTREE"
        assert index.get_name() == "idx_function_qualified_name"

    def test_custom_index_name(self):
        """Test index with custom name."""
        index = IndexDefinition("Function", "name", "HASH", "custom_idx")
        assert index.get_name() == "custom_idx"


class TestGraphIndexManager:
    """Test graph index manager functionality."""

    @pytest.fixture
    def mock_ingestor(self):
        """Create a mock ingestor."""
        ingestor = MagicMock()
        ingestor.execute_query = MagicMock(return_value=[])
        return ingestor

    def test_index_manager_initialization(self, mock_ingestor):
        """Test index manager initialization."""
        manager = GraphIndexManager(mock_ingestor)

        assert manager.ingestor == mock_ingestor
        assert isinstance(manager.existing_indexes, set)
        # Should have tried to fetch existing indexes
        mock_ingestor.execute_query.assert_called_with("SHOW INDEX INFO")

    def test_create_single_index(self, mock_ingestor):
        """Test creating a single index."""
        manager = GraphIndexManager(mock_ingestor)
        index_def = IndexDefinition("Function", "qualified_name")

        result = manager._create_index(index_def)

        assert result is True
        assert "idx_function_qualified_name" in manager.existing_indexes
        mock_ingestor.execute_query.assert_called_with(
            "CREATE INDEX ON :Function(qualified_name)"
        )

    def test_skip_existing_index(self, mock_ingestor):
        """Test skipping existing indexes."""
        manager = GraphIndexManager(mock_ingestor)
        manager.existing_indexes.add("idx_function_qualified_name")

        index_def = IndexDefinition("Function", "qualified_name")
        result = manager._create_index(index_def)

        assert result is False
        # Should not try to create index
        assert mock_ingestor.execute_query.call_count == 1  # Only initial fetch

    def test_create_all_indexes(self, mock_ingestor):
        """Test creating all core indexes."""
        manager = GraphIndexManager(mock_ingestor)
        manager.create_indexes()

        # Should create all core indexes
        assert mock_ingestor.execute_query.call_count > len(GraphIndexManager.CORE_INDEXES)

    def test_query_performance_analysis(self, mock_ingestor):
        """Test query performance analysis."""
        mock_ingestor.execute_query.return_value = [{"node": "data"}]

        manager = GraphIndexManager(mock_ingestor)
        stats = manager.analyze_query_performance("MATCH (n) RETURN n")

        assert isinstance(stats, QueryStats)
        assert stats.query == "MATCH (n) RETURN n"
        assert stats.execution_time >= 0
        assert stats.nodes_accessed == 1

    def test_optimization_hints(self, mock_ingestor):
        """Test getting optimization hints."""
        manager = GraphIndexManager(mock_ingestor)

        # Slow query
        slow_stats = QueryStats("MATCH (n) RETURN n", 2.0, 100)
        hints = manager.get_optimization_hints(slow_stats)
        assert any("slow" in hint.lower() for hint in hints)

        # Query with many nodes
        many_nodes_stats = QueryStats("MATCH (n) RETURN n", 0.5, 20000)
        hints = manager.get_optimization_hints(many_nodes_stats)
        assert any("many nodes" in hint.lower() for hint in hints)

    def test_drop_index(self, mock_ingestor):
        """Test dropping an index."""
        manager = GraphIndexManager(mock_ingestor)
        manager.existing_indexes.add("idx_function_qualified_name")

        result = manager.drop_index("Function", "qualified_name")

        assert result is True
        assert "idx_function_qualified_name" not in manager.existing_indexes
        mock_ingestor.execute_query.assert_called_with(
            "DROP INDEX ON :Function(qualified_name)"
        )


class TestQueryCache:
    """Test query cache functionality."""

    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        cache = QueryCache(max_size=10, ttl_seconds=60)

        # Set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Non-existent key
        assert cache.get("key2") is None

        # Clear cache
        cache.clear()
        assert cache.get("key1") is None

    def test_cache_ttl(self):
        """Test cache TTL expiration."""
        cache = QueryCache(max_size=10, ttl_seconds=0.1)  # 100ms TTL

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_cache_eviction(self):
        """Test LRU eviction."""
        cache = QueryCache(max_size=3, ttl_seconds=300)

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 and key2 to make them more recently used
        cache.get("key1")
        cache.get("key2")

        # Add new item - should evict key3 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") is None  # Evicted
        assert cache.get("key4") == "value4"

    def test_cache_statistics(self):
        """Test cache statistics."""
        cache = QueryCache(max_size=10, ttl_seconds=300)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Access key1 multiple times
        cache.get("key1")
        cache.get("key1")
        cache.get("key2")

        stats = cache.get_stats()
        assert stats["size"] == 2
        assert stats["total_accesses"] == 3
        assert len(stats["most_accessed"]) == 2
        assert stats["most_accessed"][0][0] == "key1"  # Most accessed


class TestOptimizedQuerier:
    """Test optimized query functionality."""

    @pytest.fixture
    def mock_ingestor(self):
        """Create a mock ingestor."""
        ingestor = MagicMock()
        return ingestor

    def test_find_function_by_name(self, mock_ingestor):
        """Test finding functions by name."""
        mock_ingestor.execute_query.return_value = [
            {
                "qn": "module.function",
                "name": "function",
                "start_line": 10,
                "end_line": 20
            }
        ]

        querier = OptimizedQuerier(mock_ingestor)
        results = querier.find_function_by_name("function")

        assert len(results) == 1
        assert results[0]["name"] == "function"

        # Check query used index
        called_query = mock_ingestor.execute_query.call_args[0][0]
        assert "Function {name: $name}" in called_query

    def test_find_by_qualified_name(self, mock_ingestor):
        """Test finding by qualified name."""
        mock_ingestor.execute_query.return_value = [
            {"n": {"qualified_name": "module.Class.method", "name": "method"}}
        ]

        querier = OptimizedQuerier(mock_ingestor)
        result = querier.find_by_qualified_name("module.Class.method", "Method")

        assert result is not None
        assert result["qualified_name"] == "module.Class.method"

        # Check query specified label
        called_query = mock_ingestor.execute_query.call_args[0][0]
        assert ":Method" in called_query

    def test_query_caching(self, mock_ingestor):
        """Test query result caching."""
        mock_ingestor.execute_query.return_value = [
            {"qn": "module.function", "name": "function"}
        ]

        querier = OptimizedQuerier(mock_ingestor, cache_enabled=True)

        # First call - should query database
        result1 = querier.find_function_by_name("function")
        assert mock_ingestor.execute_query.call_count == 1

        # Second call - should use cache
        result2 = querier.find_function_by_name("function")
        assert mock_ingestor.execute_query.call_count == 1  # No additional call
        assert result1 == result2

    def test_call_hierarchy(self, mock_ingestor):
        """Test getting call hierarchy."""
        mock_ingestor.execute_query.return_value = [
            {
                "root": "main",
                "calls": [
                    {"name": "func1", "depth": 1, "type": "Function"},
                    {"name": "func2", "depth": 2, "type": "Function"}
                ]
            }
        ]

        querier = OptimizedQuerier(mock_ingestor)
        hierarchy = querier.get_call_hierarchy("main", depth=3)

        assert hierarchy["root"] == "main"
        assert len(hierarchy["calls"]) == 2

        # Check depth limit in query
        called_query = mock_ingestor.execute_query.call_args[0][0]
        assert "[:CALLS*1..3]" in called_query
