"""Graph indexing and query optimization for performance (REQ-SCL-3)."""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from .services.graph_service import MemgraphIngestor


@dataclass
class IndexDefinition:
    """Definition of a graph index."""
    label: str
    property: str
    index_type: str = "BTREE"  # BTREE or HASH
    name: Optional[str] = None
    
    def get_name(self) -> str:
        """Get index name."""
        return self.name or f"idx_{self.label.lower()}_{self.property}"


@dataclass
class QueryStats:
    """Statistics for a query execution."""
    query: str
    execution_time: float
    nodes_accessed: int
    cache_hit: bool = False


class GraphIndexManager:
    """Manages graph indexes for optimized query performance (REQ-SCL-3)."""
    
    # Core indexes for common query patterns
    CORE_INDEXES = [
        # Node lookups by qualified name
        IndexDefinition("Function", "qualified_name"),
        IndexDefinition("Method", "qualified_name"),
        IndexDefinition("Class", "qualified_name"),
        IndexDefinition("Module", "qualified_name"),
        IndexDefinition("Package", "qualified_name"),
        
        # Node lookups by name (for search)
        IndexDefinition("Function", "name", "HASH"),
        IndexDefinition("Method", "name", "HASH"),
        IndexDefinition("Class", "name", "HASH"),
        
        # File and path lookups
        IndexDefinition("File", "path"),
        IndexDefinition("Module", "path"),
        IndexDefinition("Folder", "path"),
        
        # Test-related indexes
        IndexDefinition("TestCase", "name"),
        IndexDefinition("TestSuite", "qualified_name"),
        IndexDefinition("BDDFeature", "name"),
        IndexDefinition("BDDScenario", "name"),
        
        # C-specific indexes
        IndexDefinition("Macro", "name"),
        IndexDefinition("Struct", "name"),
        IndexDefinition("GlobalVariable", "name"),
        IndexDefinition("Pointer", "qualified_name"),
        
        # Performance indexes for relationships
        IndexDefinition("Project", "name"),  # Root traversal
        IndexDefinition("ExternalPackage", "name"),  # Dependency queries
    ]
    
    def __init__(self, ingestor: MemgraphIngestor):
        self.ingestor = ingestor
        self.existing_indexes: Set[str] = set()
        self._fetch_existing_indexes()
    
    def _fetch_existing_indexes(self) -> None:
        """Fetch existing indexes from the database."""
        try:
            # For Memgraph, use SHOW INDEX INFO
            result = self.ingestor.execute_query("SHOW INDEX INFO")
            for record in result:
                if 'index_name' in record:
                    self.existing_indexes.add(record['index_name'])
        except Exception as e:
            logger.warning(f"Could not fetch existing indexes: {e}")
    
    def create_indexes(self, additional_indexes: Optional[List[IndexDefinition]] = None) -> None:
        """Create all necessary indexes for optimal performance."""
        indexes_to_create = self.CORE_INDEXES.copy()
        if additional_indexes:
            indexes_to_create.extend(additional_indexes)
        
        created_count = 0
        for index_def in indexes_to_create:
            if self._create_index(index_def):
                created_count += 1
        
        logger.info(f"Created {created_count} new indexes (total: {len(self.existing_indexes)})")
    
    def _create_index(self, index_def: IndexDefinition) -> bool:
        """Create a single index."""
        index_name = index_def.get_name()
        
        if index_name in self.existing_indexes:
            logger.debug(f"Index {index_name} already exists")
            return False
        
        try:
            # Memgraph syntax for creating indexes
            query = f"CREATE INDEX ON :{index_def.label}({index_def.property})"
            
            start_time = time.time()
            self.ingestor.execute_query(query)
            elapsed = time.time() - start_time
            
            self.existing_indexes.add(index_name)
            logger.info(f"Created index {index_name} in {elapsed:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False
    
    def analyze_query_performance(self, query: str) -> QueryStats:
        """Analyze query performance and suggest optimizations."""
        # Execute query with profiling
        profile_query = f"PROFILE {query}"
        
        start_time = time.time()
        try:
            result = self.ingestor.execute_query(profile_query)
            execution_time = time.time() - start_time
            
            # Extract statistics from profile
            # This is simplified - actual implementation would parse the profile
            nodes_accessed = len(list(result))
            
            return QueryStats(
                query=query,
                execution_time=execution_time,
                nodes_accessed=nodes_accessed,
                cache_hit=False
            )
        except Exception as e:
            logger.error(f"Failed to profile query: {e}")
            return QueryStats(query=query, execution_time=-1, nodes_accessed=-1)
    
    def get_optimization_hints(self, stats: QueryStats) -> List[str]:
        """Get optimization hints based on query statistics."""
        hints = []
        
        if stats.execution_time > 1.0:
            hints.append("Query is slow (>1s). Consider adding indexes on filtered properties.")
        
        if stats.nodes_accessed > 10000:
            hints.append("Query accesses many nodes. Consider using LIMIT or more specific filters.")
        
        if "qualified_name" in stats.query and "Function" in stats.query:
            hints.append("Use indexed lookup: MATCH (f:Function {qualified_name: $qn}) for direct access")
        
        if not any(idx in stats.query for idx in ["qualified_name", "path", "name"]):
            hints.append("Query doesn't use indexed properties. Consider filtering by indexed fields.")
        
        return hints
    
    def drop_index(self, label: str, property: str) -> bool:
        """Drop an index."""
        try:
            query = f"DROP INDEX ON :{label}({property})"
            self.ingestor.execute_query(query)
            
            index_name = f"idx_{label.lower()}_{property}"
            self.existing_indexes.discard(index_name)
            
            logger.info(f"Dropped index on {label}.{property}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop index: {e}")
            return False
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Get statistics about existing indexes."""
        stats = {
            "total_indexes": len(self.existing_indexes),
            "indexes": list(self.existing_indexes),
            "coverage": self._calculate_index_coverage()
        }
        return stats
    
    def _calculate_index_coverage(self) -> Dict[str, float]:
        """Calculate what percentage of each label's nodes are covered by indexes."""
        coverage = {}
        
        # Get node counts by label
        try:
            labels_query = "MATCH (n) RETURN labels(n)[0] as label, count(n) as count"
            result = self.ingestor.execute_query(labels_query)
            
            for record in result:
                label = record.get('label')
                if label:
                    # Check if this label has any indexes
                    has_index = any(
                        idx.startswith(f"idx_{label.lower()}_") 
                        for idx in self.existing_indexes
                    )
                    coverage[label] = 100.0 if has_index else 0.0
                    
        except Exception as e:
            logger.error(f"Failed to calculate index coverage: {e}")
            
        return coverage


class QueryCache:
    """Simple in-memory cache for query results."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.access_count: Dict[str, int] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                self.access_count[key] = self.access_count.get(key, 0) + 1
                return value
            else:
                # Expired
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        # Evict least recently used if at capacity
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[key] = (value, time.time())
        self.access_count[key] = 0
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self.cache:
            return
            
        # Find least accessed key
        lru_key = min(self.access_count.keys(), key=lambda k: self.access_count.get(k, 0))
        del self.cache[lru_key]
        del self.access_count[lru_key]
    
    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        self.access_count.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_accesses = sum(self.access_count.values())
        hit_rate = total_accesses / max(1, total_accesses + len(self.cache)) * 100
        
        return {
            "size": len(self.cache),
            "total_accesses": total_accesses,
            "hit_rate": hit_rate,
            "most_accessed": sorted(
                self.access_count.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        }


class OptimizedQuerier:
    """Provides optimized query methods using indexes and caching."""
    
    def __init__(self, ingestor: MemgraphIngestor, cache_enabled: bool = True):
        self.ingestor = ingestor
        self.cache = QueryCache() if cache_enabled else None
        
    def find_function_by_name(self, name: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Find functions by name using index."""
        cache_key = f"func_name:{name}"
        
        if use_cache and self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Use indexed query
        query = """
        MATCH (f:Function {name: $name})
        RETURN f.qualified_name as qn, f.name as name, 
               f.start_line as start_line, f.end_line as end_line
        """
        
        result = list(self.ingestor.execute_query(query, {"name": name}))
        
        if use_cache and self.cache:
            self.cache.set(cache_key, result)
            
        return result
    
    def find_by_qualified_name(self, qn: str, label: str = None) -> Optional[Dict[str, Any]]:
        """Find node by qualified name using index."""
        cache_key = f"qn:{label}:{qn}" if label else f"qn:any:{qn}"
        
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        if label:
            query = f"MATCH (n:{label} {{qualified_name: $qn}}) RETURN n"
        else:
            query = "MATCH (n {qualified_name: $qn}) RETURN n"
        
        result = list(self.ingestor.execute_query(query, {"qn": qn}))
        value = result[0]['n'] if result else None
        
        if self.cache and value:
            self.cache.set(cache_key, value)
            
        return value
    
    def find_module_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Find module by file path using index."""
        query = "MATCH (m:Module {path: $path}) RETURN m"
        result = list(self.ingestor.execute_query(query, {"path": path}))
        return result[0]['m'] if result else None
    
    def get_call_hierarchy(self, function_qn: str, depth: int = 3) -> Dict[str, Any]:
        """Get call hierarchy for a function with depth limit."""
        cache_key = f"call_hierarchy:{function_qn}:{depth}"
        
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        query = f"""
        MATCH path = (f {{qualified_name: $qn}})-[:CALLS*1..{depth}]->(called)
        WITH f, called, length(path) as depth
        RETURN f.qualified_name as root, 
               collect(DISTINCT {{
                   name: called.qualified_name,
                   depth: depth,
                   type: labels(called)[0]
               }}) as calls
        """
        
        result = list(self.ingestor.execute_query(query, {"qn": function_qn}))
        hierarchy = result[0] if result else {"root": function_qn, "calls": []}
        
        if self.cache:
            self.cache.set(cache_key, hierarchy)
            
        return hierarchy