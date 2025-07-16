#!/usr/bin/env python3
"""
Example script demonstrating how to process large codebases with parallel processing
and memory optimization features.

This script shows:
1. How to use parallel processing for large repositories
2. How to filter specific folders and file patterns
3. How to monitor progress and memory usage
4. How to leverage graph indexing for performance
"""

import argparse
import sys
import time
from pathlib import Path

# Add the parent directory to Python path so we can import codebase_rag
sys.path.insert(0, str(Path(__file__).parent.parent))

from codebase_rag.parallel_processor import ParallelProcessor
from codebase_rag.memory_optimizer import MemoryOptimizedParser
from codebase_rag.graph_indexing import GraphIndexManager, OptimizedQuerier
from codebase_rag.services.graph_service import MemgraphIngestor
from loguru import logger


def setup_indexes(ingestor: MemgraphIngestor) -> None:
    """Create indexes for optimal query performance."""
    print("\n📊 Setting up graph indexes...")
    index_manager = GraphIndexManager(ingestor)
    index_manager.create_indexes()
    
    stats = index_manager.get_index_statistics()
    print(f"   ✅ Created {stats['total_indexes']} indexes")
    print(f"   📈 Index coverage: {len(stats['coverage'])} node types covered")


def process_large_repo(repo_path: str, workers: int = None, folder_filter: str = None):
    """Process a large repository with parallel processing."""
    print(f"\n🚀 Processing large repository: {repo_path}")
    print("=" * 60)
    
    # Setup Memgraph connection
    ingestor = MemgraphIngestor("localhost", 7687)
    
    # Clean existing data (optional)
    print("🗑️  Cleaning existing graph data...")
    ingestor.clean_graph()
    
    # Setup indexes first for better performance
    setup_indexes(ingestor)
    
    # Configure parallel processor
    processor = ParallelProcessor(
        max_workers=workers,
        chunk_size=100,
        enable_memory_optimization=True
    )
    
    # Parse folder filter
    folders = folder_filter.split(",") if folder_filter else None
    
    # Process repository
    print(f"\n⚡ Starting parallel processing with {processor.max_workers} workers...")
    start_time = time.time()
    
    results = processor.process_repository(
        repo_path=repo_path,
        folder_filter=folders,
        file_pattern=None,  # Process all supported files
        skip_tests=False    # Include test files
    )
    
    elapsed = time.time() - start_time
    
    # Show results
    print(f"\n✅ Processing complete in {elapsed:.2f} seconds!")
    print(f"   • Files processed: {results.files_processed:,}")
    print(f"   • Total size: {results.total_size / (1024*1024):.2f} MB")
    print(f"   • Processing rate: {results.files_processed / elapsed:.1f} files/sec")
    print(f"   • Average file size: {results.total_size / max(1, results.files_processed) / 1024:.1f} KB")
    
    if results.errors:
        print(f"\n⚠️  Encountered {len(results.errors)} errors:")
        for err in results.errors[:5]:
            print(f"   • {err}")
        if len(results.errors) > 5:
            print(f"   ... and {len(results.errors) - 5} more")


def query_with_indexes(ingestor: MemgraphIngestor):
    """Demonstrate optimized querying with indexes."""
    print("\n🔍 Demonstrating optimized queries...")
    
    querier = OptimizedQuerier(ingestor, cache_enabled=True)
    
    # Example 1: Find functions by name (uses index)
    print("\n1️⃣ Finding functions named 'main':")
    start = time.time()
    functions = querier.find_function_by_name("main")
    elapsed = time.time() - start
    print(f"   Found {len(functions)} functions in {elapsed*1000:.1f}ms")
    
    # Example 2: Get call hierarchy (uses caching)
    if functions:
        print("\n2️⃣ Getting call hierarchy for first 'main' function:")
        func_qn = functions[0]['qn']
        
        # First call (cache miss)
        start = time.time()
        hierarchy = querier.get_call_hierarchy(func_qn, depth=2)
        elapsed1 = time.time() - start
        
        # Second call (cache hit)
        start = time.time()
        hierarchy = querier.get_call_hierarchy(func_qn, depth=2)
        elapsed2 = time.time() - start
        
        print(f"   First query: {elapsed1*1000:.1f}ms (cache miss)")
        print(f"   Second query: {elapsed2*1000:.1f}ms (cache hit)")
        print(f"   Speedup: {elapsed1/elapsed2:.1f}x")
    
    # Show cache statistics
    if querier.cache:
        stats = querier.cache.get_stats()
        print(f"\n📊 Cache statistics:")
        print(f"   • Cache size: {stats['size']} entries")
        print(f"   • Total accesses: {stats['total_accesses']}")
        print(f"   • Hit rate: {stats['hit_rate']:.1f}%")


def main():
    """Main function to demonstrate large codebase processing."""
    parser = argparse.ArgumentParser(
        description="Process large codebases with parallel processing and optimization.",
        epilog="""
Examples:
  # Process entire repository with auto-detected workers
  python examples/large_codebase_example.py /path/to/large/repo

  # Process with specific number of workers
  python examples/large_codebase_example.py /path/to/repo --workers 16

  # Process only specific folders
  python examples/large_codebase_example.py /path/to/linux --folder-filter "drivers,kernel,fs"

  # Run optimized queries after processing
  python examples/large_codebase_example.py /path/to/repo --query-demo
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    
    parser.add_argument("repo_path", help="Path to the repository to process")
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of worker processes (default: auto-detect)",
    )
    parser.add_argument(
        "--folder-filter",
        help="Comma-separated list of folders to process",
    )
    parser.add_argument(
        "--query-demo",
        action="store_true",
        help="Run query demonstration after processing",
    )
    
    args = parser.parse_args()
    
    # Validate repo path
    repo_path = Path(args.repo_path)
    if not repo_path.exists() or not repo_path.is_dir():
        print(f"❌ Invalid repository path: {repo_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Process the repository
        process_large_repo(
            str(repo_path),
            workers=args.workers,
            folder_filter=args.folder_filter
        )
        
        # Optionally run query demo
        if args.query_demo:
            ingestor = MemgraphIngestor("localhost", 7687)
            query_with_indexes(ingestor)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        logger.exception("Processing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()