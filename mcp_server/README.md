# Graph-Code RAG MCP Server

The Graph-Code RAG MCP (Model Context Protocol) Server enables AI agents and LLMs to interact with codebases through a standardized protocol. This allows for seamless integration of code analysis capabilities into AI workflows.

## Overview

The MCP server provides:
- **Code Graph Analysis**: Query and analyze code structure, dependencies, and relationships
- **Security Scanning**: Detect vulnerabilities and security issues
- **Test Coverage Analysis**: Find untested code and calculate coverage metrics
- **Code Quality Metrics**: Get complexity, maintainability, and other metrics
- **Git History Analysis**: Analyze contributors, commits, and code evolution
- **Multi-Language Support**: Analyze Python, JavaScript, TypeScript, Rust, Go, Java, Scala, C++, and C

## Installation

1. Install the Graph-Code RAG system:
```bash
cd /path/to/code-graph-rag
pip install -e .
```

2. Install MCP dependencies:
```bash
pip install mcp>=0.9.0
```

3. Ensure Memgraph is running:
```bash
docker-compose up -d
```

## Usage

### Starting the MCP Server

```bash
python -m mcp_server.server
```

Or with environment variables:
```bash
MEMGRAPH_HOST=localhost MEMGRAPH_PORT=7687 python -m mcp_server.server
```

### Available Tools

#### 1. load_repository
Load a repository and build its code graph.

**Parameters:**
- `repo_path` (string, required): Path to the repository
- `clean` (boolean): Whether to clean existing graph data
- `parallel` (boolean): Use parallel processing
- `folder_filter` (string): Comma-separated list of folders to include

**Example:**
```json
{
  "tool": "load_repository",
  "arguments": {
    "repo_path": "/path/to/repo",
    "parallel": true,
    "folder_filter": "src,lib,tests"
  }
}
```

#### 2. query_graph
Query the code graph using natural language or Cypher.

**Parameters:**
- `query` (string, required): Natural language query or Cypher query
- `query_type` (string): "natural" or "cypher"
- `limit` (integer): Maximum number of results

**Example:**
```json
{
  "tool": "query_graph",
  "arguments": {
    "query": "Find all functions that handle authentication",
    "query_type": "natural",
    "limit": 50
  }
}
```

#### 3. analyze_security
Analyze security vulnerabilities in the codebase.

**Parameters:**
- `severity_filter` (string): Filter by severity (critical, high, medium, low, all)
- `vulnerability_types` (array): Types of vulnerabilities to check

**Example:**
```json
{
  "tool": "analyze_security",
  "arguments": {
    "severity_filter": "high",
    "vulnerability_types": ["sql_injection", "xss", "hardcoded_secrets"]
  }
}
```

#### 4. analyze_test_coverage
Analyze test coverage and find untested code.

**Parameters:**
- `include_bdd` (boolean): Include BDD scenarios
- `module_filter` (string): Filter by module name

**Example:**
```json
{
  "tool": "analyze_test_coverage",
  "arguments": {
    "include_bdd": true,
    "module_filter": "auth"
  }
}
```

#### 5. get_code_metrics
Get code quality metrics and statistics.

**Parameters:**
- `metric_types` (array): Types of metrics to retrieve

**Example:**
```json
{
  "tool": "get_code_metrics",
  "arguments": {
    "metric_types": ["complexity", "loc", "dependencies", "test_ratio"]
  }
}
```

### Using with AI Agents

#### Claude Desktop Integration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "code-graph-rag": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/code-graph-rag",
      "env": {
        "MEMGRAPH_HOST": "localhost",
        "MEMGRAPH_PORT": "7687"
      }
    }
  }
}
```

#### Custom AI Agent Integration

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def analyze_codebase():
    # Connect to MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
        env={"MEMGRAPH_HOST": "localhost"}
    )

    session = await stdio_client(server_params)
    await session.initialize()

    # Load repository
    result = await session.call_tool(
        "load_repository",
        arguments={"repo_path": "/path/to/repo"}
    )

    # Query for security issues
    security = await session.call_tool(
        "analyze_security",
        arguments={"severity_filter": "high"}
    )

    # Get test coverage
    coverage = await session.call_tool(
        "analyze_test_coverage",
        arguments={}
    )

    await session.close()

asyncio.run(analyze_codebase())
```

## Use Cases

### 1. Code Review Assistant
AI agents can use the MCP server to:
- Analyze pull requests for security issues
- Check test coverage for new code
- Identify complex functions that need refactoring
- Find circular dependencies

### 2. Documentation Generator
- Extract API documentation from code
- Generate architecture diagrams
- Create test documentation
- Build dependency graphs

### 3. Security Auditor
- Scan for vulnerabilities
- Track security issues across versions
- Generate security reports
- Monitor for new vulnerabilities

### 4. Test Coverage Monitor
- Find untested code paths
- Track coverage trends
- Identify critical untested functions
- Generate coverage reports

### 5. Code Quality Dashboard
- Monitor complexity metrics
- Track technical debt
- Identify refactoring opportunities
- Generate quality reports

## Advanced Features

### Caching
The MCP server implements intelligent caching:
- Graph data is cached in memory
- Analysis results are cached with TTL
- Repository state is tracked for invalidation

### Parallel Processing
Large codebases are processed efficiently:
- Multi-threaded file parsing
- Batch processing for memory efficiency
- Incremental updates for changed files

### Security
The MCP server includes security features:
- Input validation for all parameters
- Path traversal protection
- Rate limiting for expensive operations
- Secure handling of credentials

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Ensure Memgraph is running: `docker-compose ps`
   - Check MEMGRAPH_HOST and MEMGRAPH_PORT settings

2. **Repository Not Found**
   - Verify the repository path exists
   - Check file permissions

3. **Out of Memory**
   - Use folder_filter to limit scope
   - Enable parallel processing
   - Increase Docker memory limits

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG python -m mcp_server.server
```

## API Reference

### Response Format

All tool responses follow this format:
```json
{
  "status": "success" | "error",
  "data": {},
  "error": "error message if status is error",
  "metadata": {
    "execution_time": "0.123s",
    "cache_hit": false
  }
}
```

### Error Codes

- `REPO_NOT_FOUND`: Repository path does not exist
- `GRAPH_NOT_LOADED`: No graph data available
- `INVALID_QUERY`: Query syntax error
- `TIMEOUT`: Operation timed out
- `PERMISSION_DENIED`: Insufficient permissions

## Contributing

See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.
