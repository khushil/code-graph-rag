"""Tests for query caching functionality (REQ-SCL-3)."""

import time
from unittest.mock import MagicMock

import pytest

from codebase_rag.query_cache import (
    CacheEntry,
    CachedQueryExecutor,
    QueryCache,
    cached_query,
)


class TestCacheEntry:
    """Test the CacheEntry class."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            query="MATCH (n) RETURN n",
            params={"limit": 10},
            result=["node1", "node2"],
            timestamp=time.time(),
        )
        
        assert entry.query == "MATCH (n) RETURN n"
        assert entry.params == {"limit": 10}
        assert entry.result == ["node1", "node2"]
        assert entry.access_count == 0
        
    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        entry = CacheEntry(
            query="MATCH (n) RETURN n",
            params=None,
            result=[],
            timestamp=time.time() - 3700,  # 1 hour + 100 seconds ago
        )
        
        assert entry.is_expired(3600)  # 1 hour TTL
        assert not entry.is_expired(4000)  # Longer TTL
        
    def test_mark_accessed(self):
        """Test marking entry as accessed."""
        entry = CacheEntry(
            query="MATCH (n) RETURN n",
            params=None,
            result=[],
            timestamp=time.time(),
        )
        
        assert entry.access_count == 0
        entry.mark_accessed()
        assert entry.access_count == 1
        entry.mark_accessed()
        assert entry.access_count == 2


class TestQueryCache:
    """Test the QueryCache class."""
    
    @pytest.fixture
    def cache(self):
        """Create a query cache instance."""
        return QueryCache(max_size=3, ttl=3600)
        
    def test_cache_get_miss(self, cache):
        """Test cache miss."""
        result = cache.get("MATCH (n) RETURN n")
        assert result is None
        assert cache.get_stats()["misses"] == 1
        assert cache.get_stats()["hits"] == 0
        
    def test_cache_put_and_get(self, cache):
        """Test putting and getting from cache."""
        query = "MATCH (n:Person) RETURN n"
        result = ["person1", "person2"]
        
        cache.put(query, result)
        cached_result = cache.get(query)
        
        assert cached_result == result
        assert cache.get_stats()["hits"] == 1
        assert cache.get_stats()["size"] == 1
        
    def test_cache_with_params(self, cache):
        """Test caching with parameters."""
        query = "MATCH (n:Person) WHERE n.age > $age RETURN n"
        params1 = {"age": 25}
        params2 = {"age": 30}
        result1 = ["person1"]
        result2 = ["person2", "person3"]
        
        # Cache with different params
        cache.put(query, result1, params1)
        cache.put(query, result2, params2)
        
        # Should get different results for different params
        assert cache.get(query, params1) == result1
        assert cache.get(query, params2) == result2
        assert cache.get_stats()["hits"] == 2
        
    def test_cache_lru_eviction(self, cache):
        """Test LRU eviction when cache is full."""
        # Fill cache to capacity
        cache.put("query1", "result1")
        cache.put("query2", "result2")
        cache.put("query3", "result3")
        
        # Add one more - should evict oldest (query1)
        cache.put("query4", "result4")
        
        assert cache.get("query1") is None  # Evicted
        assert cache.get("query2") == "result2"
        assert cache.get("query3") == "result3"
        assert cache.get("query4") == "result4"
        assert cache.get_stats()["evictions"] == 1
        
    def test_cache_expiration(self, cache):
        """Test cache entry expiration."""
        # Create cache with short TTL
        cache = QueryCache(ttl=0.1)  # 100ms
        
        cache.put("query1", "result1")
        assert cache.get("query1") == "result1"
        
        # Wait for expiration
        time.sleep(0.2)
        
        assert cache.get("query1") is None
        assert cache.get_stats()["expirations"] == 1
        
    def test_cache_invalidate_all(self, cache):
        """Test invalidating entire cache."""
        cache.put("query1", "result1")
        cache.put("query2", "result2")
        
        count = cache.invalidate()
        
        assert count == 2
        assert cache.get("query1") is None
        assert cache.get("query2") is None
        assert cache.get_stats()["size"] == 0
        
    def test_cache_invalidate_pattern(self, cache):
        """Test invalidating cache entries by pattern."""
        cache.put("MATCH (n:Person) RETURN n", "result1")
        cache.put("MATCH (n:Company) RETURN n", "result2")
        cache.put("MATCH (n:Person) WHERE n.age > 25 RETURN n", "result3")
        
        # Invalidate Person queries
        count = cache.invalidate(":Person")
        
        assert count == 2
        assert cache.get("MATCH (n:Person) RETURN n") is None
        assert cache.get("MATCH (n:Person) WHERE n.age > 25 RETURN n") is None
        assert cache.get("MATCH (n:Company) RETURN n") == "result2"
        
    def test_cache_disabled(self):
        """Test cache when disabled."""
        cache = QueryCache(enabled=False)
        
        cache.put("query1", "result1")
        assert cache.get("query1") is None
        assert cache.get_stats()["size"] == 0


class TestCachedQueryExecutor:
    """Test the CachedQueryExecutor class."""
    
    @pytest.fixture
    def mock_executor(self):
        """Create a mock query executor."""
        executor = MagicMock()
        executor.return_value = ["result1", "result2"]
        return executor
        
    @pytest.fixture
    def cached_executor(self, mock_executor):
        """Create a cached query executor."""
        cache = QueryCache(max_size=10, ttl=3600)
        return CachedQueryExecutor(mock_executor, cache)
        
    @pytest.fixture
    def cached_executor_with_writes(self, mock_executor):
        """Create a cached query executor with write caching enabled."""
        cache = QueryCache(max_size=10, ttl=3600)
        return CachedQueryExecutor(mock_executor, cache, cache_writes=True)
        
    def test_execute_read_query_cached(self, cached_executor, mock_executor):
        """Test executing a read query with caching."""
        query = "MATCH (n) RETURN n"
        
        # First execution - cache miss
        result1 = cached_executor.execute(query)
        assert result1 == ["result1", "result2"]
        assert mock_executor.call_count == 1
        
        # Second execution - cache hit
        result2 = cached_executor.execute(query)
        assert result2 == ["result1", "result2"]
        assert mock_executor.call_count == 1  # Not called again
        
        stats = cached_executor.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        
    def test_execute_write_query_not_cached(self, cached_executor, mock_executor):
        """Test that write queries are not cached."""
        query = "CREATE (n:Person {name: 'John'})"
        
        result1 = cached_executor.execute(query)
        result2 = cached_executor.execute(query)
        
        assert mock_executor.call_count == 2  # Called both times
        assert cached_executor.get_cache_stats()["size"] == 0
        
    def test_write_query_invalidates_cache(self, cached_executor_with_writes, mock_executor):
        """Test that write queries invalidate related cache entries."""
        # Cache a read query
        read_query = "MATCH (n:Person) RETURN n"
        cached_executor_with_writes.execute(read_query)
        assert cached_executor_with_writes.get_cache_stats()["size"] == 1
        
        # Execute write query that should invalidate cache
        write_query = "CREATE (n:Person {name: 'Jane'})"
        cached_executor_with_writes.execute(write_query)
        
        # Cache should be invalidated
        cached_executor_with_writes.execute(read_query)
        assert mock_executor.call_count == 3  # Called again after invalidation


class TestCachedQueryDecorator:
    """Test the cached_query decorator."""
    
    def test_cached_query_decorator(self):
        """Test caching function results with decorator."""
        call_count = 0
        
        @cached_query(ttl=3600)
        def execute_query(query: str) -> list:
            nonlocal call_count
            call_count += 1
            return [f"result{call_count}"]
            
        # First call - cache miss
        result1 = execute_query("MATCH (n) RETURN n")
        assert result1 == ["result1"]
        assert call_count == 1
        
        # Second call - cache hit
        result2 = execute_query("MATCH (n) RETURN n")
        assert result2 == ["result1"]  # Same result
        assert call_count == 1  # Not called again
        
        # Different query - cache miss
        result3 = execute_query("MATCH (n:Person) RETURN n")
        assert result3 == ["result2"]
        assert call_count == 2
        
        # Check cache stats
        stats = execute_query.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 2