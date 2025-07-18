"""Query caching module for improved performance (REQ-SCL-3)."""

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class CacheEntry:
    """Represents a cached query result."""
    query: str
    params: dict[str, Any] | None
    result: Any
    timestamp: float
    access_count: int = 0
    
    def is_expired(self, ttl: float) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.timestamp > ttl
    
    def mark_accessed(self) -> None:
        """Mark this entry as accessed."""
        self.access_count += 1


class QueryCache:
    """LRU cache for Cypher query results."""
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl: float = 3600,  # 1 hour default TTL
        enabled: bool = True,
    ):
        self.max_size = max_size
        self.ttl = ttl
        self.enabled = enabled
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }
        
    def get(self, query: str, params: dict[str, Any] | None = None) -> Any | None:
        """Get cached result for a query."""
        if not self.enabled:
            return None
            
        cache_key = self._get_cache_key(query, params)
        
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            
            # Check if expired
            if entry.is_expired(self.ttl):
                self._remove_entry(cache_key)
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None
                
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            entry.mark_accessed()
            
            self._stats["hits"] += 1
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return entry.result
            
        self._stats["misses"] += 1
        return None
        
    def put(
        self,
        query: str,
        result: Any,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Cache a query result."""
        if not self.enabled:
            return
            
        cache_key = self._get_cache_key(query, params)
        
        # Remove oldest entry if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)
            self._stats["evictions"] += 1
            
        # Add new entry
        entry = CacheEntry(
            query=query,
            params=params,
            result=result,
            timestamp=time.time(),
        )
        self._cache[cache_key] = entry
        logger.debug(f"Cached result for query: {query[:50]}...")
        
    def invalidate(self, pattern: str | None = None) -> int:
        """Invalidate cache entries matching a pattern."""
        if pattern is None:
            # Clear entire cache
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared entire cache ({count} entries)")
            return count
            
        # Remove entries matching pattern
        to_remove = []
        for key, entry in self._cache.items():
            if pattern in entry.query:
                to_remove.append(key)
                
        for key in to_remove:
            self._remove_entry(key)
            
        logger.info(f"Invalidated {len(to_remove)} cache entries matching '{pattern}'")
        return len(to_remove)
        
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests if total_requests > 0 else 0
        )
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "enabled": self.enabled,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "expirations": self._stats["expirations"],
        }
        
    def _get_cache_key(self, query: str, params: dict[str, Any] | None) -> str:
        """Generate a cache key for a query and parameters."""
        # Normalize query by removing extra whitespace
        normalized_query = " ".join(query.split())
        
        # Create a stable string representation
        if params:
            # Sort params for consistent hashing
            params_str = json.dumps(params, sort_keys=True)
            key_str = f"{normalized_query}|{params_str}"
        else:
            key_str = normalized_query
            
        # Return hash for more efficient storage
        return hashlib.sha256(key_str.encode()).hexdigest()
        
    def _remove_entry(self, key: str) -> None:
        """Remove a cache entry."""
        if key in self._cache:
            del self._cache[key]


class CachedQueryExecutor:
    """Wraps a query executor with caching functionality."""
    
    def __init__(
        self,
        executor,
        cache: QueryCache | None = None,
        cache_reads: bool = True,
        cache_writes: bool = False,
    ):
        self.executor = executor
        self.cache = cache or QueryCache()
        self.cache_reads = cache_reads
        self.cache_writes = cache_writes
        
    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a query with caching."""
        # Determine if query is cacheable
        is_read_query = self._is_read_query(query)
        
        # Try cache for read queries
        if is_read_query and self.cache_reads:
            cached_result = self.cache.get(query, params)
            if cached_result is not None:
                return cached_result
                
        # Execute query
        result = self.executor(query, params)
        
        # Cache result if appropriate
        if is_read_query and self.cache_reads:
            self.cache.put(query, result, params)
        elif not is_read_query and self.cache_writes:
            # Invalidate related cache entries for write queries
            self._invalidate_related_cache(query)
            
        return result
        
    def _is_read_query(self, query: str) -> bool:
        """Determine if a query is read-only."""
        # Simple heuristic: check for write keywords
        write_keywords = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE"]
        query_upper = query.upper()
        
        for keyword in write_keywords:
            if keyword in query_upper:
                return False
                
        return True
        
    def _invalidate_related_cache(self, write_query: str) -> None:
        """Invalidate cache entries that might be affected by a write query."""
        # Extract node labels from the write query
        # This is a simplified approach - a real implementation would
        # parse the query more thoroughly
        
        # Look for common patterns like (:Label) or (n:Label)
        import re
        label_patterns = [
            r'\(:(\w+)\)',  # (:Label)
            r'\(\w+:(\w+)',  # (n:Label
        ]
        
        labels = []
        for pattern in label_patterns:
            labels.extend(re.findall(pattern, write_query))
        
        # Invalidate queries mentioning these labels
        for label in labels:
            self.cache.invalidate(f":{label}")
            
        logger.debug(f"Invalidated cache entries for labels: {labels}")
        
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
        
    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self.cache.invalidate()


# Decorator for caching function results
def cached_query(ttl: float = 3600):
    """Decorator to cache query results."""
    cache = QueryCache(ttl=ttl)
    
    def decorator(func):
        def wrapper(query: str, *args, **kwargs):
            # Use query as cache key
            cached_result = cache.get(query)
            if cached_result is not None:
                return cached_result
                
            # Execute function
            result = func(query, *args, **kwargs)
            
            # Cache result
            cache.put(query, result)
            
            return result
            
        wrapper.cache = cache
        return wrapper
        
    return decorator