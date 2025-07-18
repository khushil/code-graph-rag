"""Graph indexing module for query optimization (REQ-SCL-3)."""

from typing import Any

from loguru import logger

from .services.graph_service import MemgraphIngestor


class GraphIndexManager:
    """Manages graph indexes for optimized query performance."""

    def __init__(self, ingestor: MemgraphIngestor):
        self.ingestor = ingestor

    def create_indexes(self) -> None:
        """Create all necessary indexes for the knowledge graph."""
        logger.info("Creating graph indexes for optimized query performance...")
        
        # Node label indexes
        self._create_node_indexes()
        
        # Relationship type indexes
        self._create_relationship_indexes()
        
        # Full-text search indexes
        self._create_text_indexes()
        
        logger.info("Graph indexes created successfully")

    def _create_node_indexes(self) -> None:
        """Create indexes on node labels and properties."""
        # File nodes
        self._create_index("File", "path")
        self._create_index("File", "name")
        self._create_index("File", "language")
        
        # Code structure nodes
        self._create_index("Function", "qualified_name")
        self._create_index("Function", "name")
        self._create_index("Class", "qualified_name")
        self._create_index("Class", "name")
        self._create_index("Method", "qualified_name")
        self._create_index("Method", "name")
        
        # Module and package nodes
        self._create_index("Module", "qualified_name")
        self._create_index("Package", "qualified_name")
        
        # Test nodes
        self._create_index("TestCase", "qualified_name")
        self._create_index("TestCase", "name")
        self._create_index("TestFunction", "qualified_name")
        self._create_index("TestFunction", "name")
        self._create_index("TestScenario", "name")
        
        # C-specific nodes
        self._create_index("Struct", "qualified_name")
        self._create_index("Struct", "name")
        self._create_index("Macro", "name")
        self._create_index("FunctionPointer", "name")
        self._create_index("Typedef", "name")
        self._create_index("Union", "name")
        self._create_index("Enum", "name")
        
        # Import nodes
        self._create_index("Import", "module")
        
        # Version control nodes
        self._create_index("Commit", "hash")
        self._create_index("Contributor", "email")

    def _create_relationship_indexes(self) -> None:
        """Create indexes on relationship types."""
        # This is more for documentation - Memgraph automatically indexes relationship types
        relationship_types = [
            "HAS_FILE",
            "CONTAINS",
            "IMPORTS",
            "CALLS",
            "INHERITS_FROM",
            "IMPLEMENTS",
            "OVERRIDES",
            "RETURNS",
            "USES_TYPE",
            "TESTS",
            "COVERS",
            "ASSERTS",
            "FLOWS_TO",
            "MODIFIES",
            "POINTS_TO",
            "ASSIGNS_FP",
            "INVOKES_FP",
            "EXPANDS_TO",
            "INCLUDES",
            "LOCKS",
            "UNLOCKS",
        ]
        
        logger.debug(f"Relationship types to be indexed: {relationship_types}")

    def _create_text_indexes(self) -> None:
        """Create full-text search indexes."""
        # Create text indexes for searchable content
        text_index_configs = [
            ("Function", ["name", "docstring"]),
            ("Class", ["name", "docstring"]),
            ("Module", ["qualified_name", "docstring"]),
            ("File", ["path", "name"]),
            ("TestScenario", ["name", "description"]),
            ("Commit", ["message"]),
        ]
        
        for label, properties in text_index_configs:
            self._create_text_index(label, properties)

    def _create_index(self, label: str, property_name: str) -> None:
        """Create a single property index."""
        try:
            query = f"CREATE INDEX ON :{label}({property_name})"
            self.ingestor.execute_write(query)
            logger.debug(f"Created index on {label}.{property_name}")
        except Exception as e:
            # Index might already exist
            if "already defined" in str(e) or "already exists" in str(e):
                logger.debug(f"Index on {label}.{property_name} already exists")
            else:
                logger.warning(f"Failed to create index on {label}.{property_name}: {e}")

    def _create_text_index(self, label: str, properties: list[str]) -> None:
        """Create a text search index."""
        try:
            # Memgraph doesn't support full-text indexes in the same way as Neo4j
            # Instead, we create regular indexes on text properties
            for prop in properties:
                self._create_index(label, prop)
        except Exception as e:
            logger.warning(f"Failed to create text index on {label}: {e}")

    def drop_all_indexes(self) -> None:
        """Drop all indexes (use with caution)."""
        try:
            # Get all existing indexes
            result = self.ingestor.fetch_all("SHOW INDEX INFO")
            
            for record in result:
                index_name = record.get("index_name")
                if index_name:
                    self.ingestor.execute_write(f"DROP INDEX {index_name}")
                    logger.debug(f"Dropped index: {index_name}")
                    
            logger.info("All indexes dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop indexes: {e}")

    def get_index_stats(self) -> list[dict[str, Any]]:
        """Get statistics about existing indexes."""
        try:
            result = self.ingestor.fetch_all("SHOW INDEX INFO")
            stats = []
            
            for record in result:
                stats.append({
                    "name": record.get("index_name"),
                    "label": record.get("label"),
                    "property": record.get("property"),
                    "type": record.get("index_type", "btree"),
                })
                
            return stats
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return []

    def analyze_query_performance(self, cypher_query: str) -> dict[str, Any]:
        """Analyze the performance of a Cypher query."""
        try:
            # Use EXPLAIN to get the query plan
            explain_query = f"EXPLAIN {cypher_query}"
            result = self.ingestor.fetch_all(explain_query)
            
            # Extract query plan information
            plan_info = {
                "query": cypher_query,
                "uses_indexes": False,
                "estimated_rows": 0,
                "operators": [],
            }
            
            for record in result:
                operator = record.get("operator", "")
                if "index" in operator.lower():
                    plan_info["uses_indexes"] = True
                plan_info["operators"].append(operator)
                
            return plan_info
        except Exception as e:
            logger.error(f"Failed to analyze query: {e}")
            return {"error": str(e)}

    def optimize_for_common_queries(self) -> None:
        """Create indexes optimized for common query patterns."""
        logger.info("Creating indexes for common query patterns...")
        
        # Pattern 1: Finding functions by name across the codebase
        self._create_index("Function", "name")
        self._create_index("Method", "name")
        
        # Pattern 2: Finding all code in a specific file
        self._create_index("File", "path")
        
        # Pattern 3: Finding implementations of an interface/class
        self._create_index("Class", "name")
        self._create_index("Interface", "name")
        
        # Pattern 4: Finding test coverage
        self._create_index("TestCase", "qualified_name")
        self._create_index("TestFunction", "qualified_name")
        
        # Pattern 5: Import analysis
        self._create_index("Import", "module")
        
        # Pattern 6: Finding code by qualified name
        self._create_index("Function", "qualified_name")
        self._create_index("Class", "qualified_name")
        self._create_index("Method", "qualified_name")
        
        logger.info("Common query pattern indexes created")