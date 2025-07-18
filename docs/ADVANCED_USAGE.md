# Advanced Usage Scenarios

This guide covers advanced usage scenarios for the Graph-Code RAG system, including kernel analysis, security auditing, and large-scale codebase management.

## Table of Contents

1. [Linux Kernel Analysis](#linux-kernel-analysis)
2. [Security Auditing Workflow](#security-auditing-workflow)
3. [Large-Scale Codebase Management](#large-scale-codebase-management)
4. [Multi-Repository Analysis](#multi-repository-analysis)
5. [Performance Optimization](#performance-optimization)
6. [Custom Query Development](#custom-query-development)

## Linux Kernel Analysis

### Setting Up for Kernel Analysis

The system is optimized for analyzing large C codebases like the Linux kernel:

```bash
# Clone a subset of the kernel for testing
git clone --depth 1 --single-branch https://github.com/torvalds/linux.git linux-kernel
cd linux-kernel

# Analyze specific subsystems to manage scale
python -m codebase_rag.main start \
  --repo-path . \
  --update-graph --clean \
  --parallel --workers 16 \
  --folder-filter "drivers/net,drivers/usb,kernel,fs" \
  --skip-tests
```

### Kernel-Specific Queries

```python
# Find all network drivers
"Show me all network device drivers"

# Trace syscall implementations
"Show the implementation path for sys_read syscall"

# Find interrupt handlers
"List all interrupt handlers in the USB subsystem"

# Analyze locking patterns
"Show all functions using spin_lock_irqsave"

# Find memory allocation patterns
"Find all kmalloc calls with GFP_ATOMIC flag"

# Trace data structures
"Show all functions that modify struct net_device"

# Find exported symbols
"List all EXPORT_SYMBOL functions in the network stack"

# Analyze Kconfig dependencies
"Show configuration options for CONFIG_DEBUG_KERNEL"
```

### Understanding Kernel Macros

```python
# Find macro expansions
"Show what DEFINE_MUTEX expands to"

# Trace macro usage
"Find all uses of list_for_each_entry macro"

# Analyze kernel patterns
"Show all SYSCALL_DEFINE implementations"
```

## Security Auditing Workflow

### Comprehensive Security Analysis

```bash
# Run security analysis with all features
python examples/security_and_test_example.py /path/to/codebase \
  --language c \
  --report security_audit.json
```

### Security Query Patterns

```python
# Input validation vulnerabilities
"Find functions that use strcpy without bounds checking"

# Memory safety issues
"Show buffer overflow vulnerabilities in C code"

# Authentication bypasses
"Find authentication functions that can return early"

# SQL injection risks
"Show all SQL query constructions using string concatenation"

# Command injection
"Find exec/system calls with user input"

# Privilege escalation
"Show functions that call setuid or change privileges"

# Race conditions
"Find TOCTOU vulnerabilities in file operations"

# Cryptographic weaknesses
"Show hardcoded encryption keys or weak random number usage"
```

### Automated Security Scanning

```python
# Create a security scanning script
import sys
sys.path.append('.')

from codebase_rag.analysis.security import SecurityAnalyzer
from codebase_rag.main import parse_and_store_codebase
from pathlib import Path

def security_audit(repo_path: str):
    # Parse codebase
    parse_and_store_codebase(repo_path, clean=True, parallel=True)

    # Run security analysis
    analyzer = SecurityAnalyzer()
    vulnerabilities = analyzer.analyze_repository(repo_path)

    # Generate report
    critical = [v for v in vulnerabilities if v.severity == "CRITICAL"]
    high = [v for v in vulnerabilities if v.severity == "HIGH"]

    print(f"Found {len(critical)} critical and {len(high)} high severity issues")

    # Export for further analysis
    return vulnerabilities
```

## Large-Scale Codebase Management

### Optimizing for Million-Line Codebases

```bash
# Use parallel processing with memory optimization
python -m codebase_rag.main start \
  --repo-path /path/to/large/codebase \
  --update-graph --clean \
  --parallel --workers 32 \
  --batch-size 100 \
  --memory-limit 8G
```

### Incremental Updates

```python
# Update only changed files since last analysis
import subprocess
from datetime import datetime, timedelta

def incremental_update(repo_path: str, since_days: int = 1):
    # Get changed files
    since = datetime.now() - timedelta(days=since_days)
    cmd = f"git log --since='{since.isoformat()}' --name-only --pretty=format:"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    changed_files = set(result.stdout.strip().split('\n'))

    # Update only changed files
    for file in changed_files:
        if file.endswith(('.c', '.h', '.py', '.js', '.rs', '.go')):
            # Update graph for this file
            update_file_in_graph(file)
```

### Partitioning Large Graphs

```python
# Analyze by subsystem
subsystems = [
    "frontend/src",
    "backend/api",
    "backend/core",
    "infrastructure",
    "tests"
]

for subsystem in subsystems:
    print(f"Analyzing {subsystem}...")
    python -m codebase_rag.main start \
        --repo-path . \
        --folder-filter subsystem \
        --update-graph \
        --graph-partition subsystem
```

### Memory-Efficient Queries

```python
# Use LIMIT and pagination for large results
"Show first 100 functions in the codebase"
"Find critical vulnerabilities LIMIT 50"

# Use specific filters
"Show functions in module 'auth' with complexity > 10"
"Find classes in package 'com.example.core' with > 500 LOC"

# Aggregate queries
"Count functions by module"
"Show top 10 most complex functions"
```

## Multi-Repository Analysis

### Analyzing Multiple Related Projects

```python
# analyze_ecosystem.py
import os
from pathlib import Path

repositories = [
    {"name": "frontend", "url": "https://github.com/org/frontend"},
    {"name": "backend", "url": "https://github.com/org/backend"},
    {"name": "shared-lib", "url": "https://github.com/org/shared-lib"},
]

base_path = Path("ecosystem_analysis")
base_path.mkdir(exist_ok=True)

for repo in repositories:
    repo_path = base_path / repo["name"]

    # Clone if needed
    if not repo_path.exists():
        os.system(f"git clone {repo['url']} {repo_path}")

    # Analyze with namespace
    os.system(f"""
        python -m codebase_rag.main start \
            --repo-path {repo_path} \
            --update-graph \
            --namespace {repo['name']}
    """)

# Query across repositories
queries = [
    "Show all API endpoints across all services",
    "Find shared dependencies between frontend and backend",
    "Show cross-repository function calls",
    "Find duplicate code between repositories"
]
```

### Cross-Repository Dependency Analysis

```python
# Find shared components
"Show modules imported by multiple repositories"

# API contract validation
"Find REST endpoints in backend not used by frontend"

# Version consistency
"Show package versions across all repositories"

# Security across ecosystem
"Find vulnerabilities in shared libraries affecting multiple services"
```

## Performance Optimization

### Benchmarking Script

```python
# benchmark_performance.py
import time
import psutil
import os
from pathlib import Path

class PerformanceBenchmark:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.metrics = {}

    def measure_ingestion(self, parallel: bool = False, workers: int = 4):
        """Measure ingestion performance."""
        process = psutil.Process(os.getpid())

        start_time = time.time()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run ingestion
        cmd = f"python -m codebase_rag.main start --repo-path {self.repo_path} --update-graph --clean"
        if parallel:
            cmd += f" --parallel --workers {workers}"

        os.system(cmd)

        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024

        self.metrics['ingestion'] = {
            'time': end_time - start_time,
            'memory_peak': end_memory,
            'memory_delta': end_memory - start_memory,
            'parallel': parallel,
            'workers': workers
        }

    def measure_query_performance(self, queries: list):
        """Measure query performance."""
        # Implementation for query benchmarking
        pass

    def generate_report(self):
        """Generate performance report."""
        print("Performance Benchmark Report")
        print("=" * 50)

        if 'ingestion' in self.metrics:
            m = self.metrics['ingestion']
            print(f"Ingestion Time: {m['time']:.2f} seconds")
            print(f"Memory Usage: {m['memory_peak']:.2f} MB")
            print(f"Parallel: {m['parallel']} (workers: {m['workers']})")
```

### Query Optimization Tips

1. **Use Indexes**
   ```cypher
   // Ensure indexes exist for common queries
   CREATE INDEX ON :Function(name);
   CREATE INDEX ON :Module(file_path);
   CREATE INDEX ON :Class(qualified_name);
   ```

2. **Limit Graph Traversal**
   ```cypher
   // Bad: Unbounded traversal
   MATCH (f:Function)-[*]->(target)

   // Good: Bounded traversal
   MATCH (f:Function)-[*1..3]->(target)
   ```

3. **Use Query Caching**
   ```python
   # Enable query cache
   export ENABLE_QUERY_CACHE=true
   export QUERY_CACHE_TTL=3600  # 1 hour
   ```

## Custom Query Development

### Creating Domain-Specific Queries

```python
# financial_analysis_queries.py
FINANCIAL_QUERIES = {
    "transaction_flows": """
        MATCH (f:Function)-[:CALLS]->(g:Function)
        WHERE f.name CONTAINS 'transaction' OR g.name CONTAINS 'payment'
        RETURN f, g
    """,

    "pci_compliance": """
        MATCH (f:Function)-[:HANDLES]->(d:Data)
        WHERE d.type = 'credit_card' OR d.name CONTAINS 'card_number'
        RETURN f, d
    """,

    "audit_trail": """
        MATCH (f:Function)-[:LOGS]->(l:LogStatement)
        WHERE f.name CONTAINS 'audit' OR f.name CONTAINS 'compliance'
        RETURN f, l
    """
}
```

### Extending the Query System

```python
# custom_analyzer.py
from codebase_rag.rag_interface import ChainAgent

class DomainSpecificAnalyzer(ChainAgent):
    def __init__(self, domain: str):
        super().__init__()
        self.domain = domain
        self.load_domain_patterns()

    def load_domain_patterns(self):
        """Load domain-specific patterns and queries."""
        if self.domain == "finance":
            self.patterns = FINANCIAL_QUERIES
        elif self.domain == "healthcare":
            self.patterns = HEALTHCARE_QUERIES
        # Add more domains

    def analyze(self, query: str):
        """Enhanced analysis with domain knowledge."""
        # Domain-specific processing
        return super().analyze(query)
```

## Best Practices

1. **Start Small**: Begin with subsystems before analyzing entire large codebases
2. **Use Parallel Processing**: Enable for significant performance gains
3. **Filter Wisely**: Use folder and file filters to focus analysis
4. **Monitor Resources**: Watch memory usage for large repositories
5. **Incremental Updates**: Use incremental analysis for daily updates
6. **Cache Results**: Enable caching for frequently used queries
7. **Partition Graphs**: Split large graphs by subsystem or module
8. **Custom Indexes**: Create indexes for your specific query patterns

## Troubleshooting

### Memory Issues
```bash
# Increase heap size for Memgraph
docker run -p 7687:7687 -e MEMGRAPH_MEMORY_LIMIT=8GB memgraph/memgraph

# Use batch processing
python -m codebase_rag.main start --batch-size 50 --memory-limit 4G
```

### Performance Issues
```bash
# Profile slow queries
MATCH (n) RETURN n PROFILE

# Check index usage
SHOW INDEX INFO;
```

### Scale Issues
```bash
# Process in chunks
find . -name "*.c" | split -l 1000 - chunk_
for chunk in chunk_*; do
    python -m codebase_rag.main start --file-list $chunk --update-graph
done
```
