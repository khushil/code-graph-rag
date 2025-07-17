# Migration Guide

This guide helps you migrate to the latest version and take advantage of new features.

## New Features Overview

### Multi-Provider LLM Support
The system now supports multiple AI providers:
- **Google Gemini** - Best overall performance
- **OpenAI** - GPT-4 and GPT-4o models
- **Anthropic Claude** - Claude 3.5 Sonnet and Haiku
- **Local Models** - Privacy-focused with Ollama

You can mix providers for different tasks and switch at runtime.

### 1. C Language Support
The system now fully supports C codebases, including:
- Function and struct definitions
- Pointer analysis and function pointers
- Macro expansion tracking
- Linux kernel patterns (syscalls, exports, locks)

### 2. Test Framework Integration
Automatic detection and parsing of tests:
- Unit tests across all major frameworks
- BDD/Gherkin feature files
- Test-to-code linking
- Coverage analysis

### 3. Performance Enhancements
Major scalability improvements:
- Parallel processing with multiple workers
- Memory optimization for large files
- Graph indexing for faster queries
- Query result caching

## Migration Steps

### Step 1: Update Dependencies

```bash
# Pull latest changes
git pull origin main

# Update dependencies including new C support
uv sync --extra treesitter-full

# For development
make dev
```

### Step 2: Tree-sitter API Changes

If you have custom parsers or extensions, note that we've updated to handle tree-sitter API changes:

- The `captures()` method now returns a dictionary format: `{"capture_name": [nodes]}`
- We support both the old tuple format and new dict format for compatibility
- Tree-sitter-c version is pinned to 0.23.1 for compatibility

Example of the updated pattern:
```python
# Old pattern (still supported)
for node, name in query.captures(root_node):
    if name == "function":
        # process node

# New pattern (recommended)
captures = query.captures(root_node)
for capture_name, nodes in captures.items():
    if capture_name == "function":
        for node in nodes:
            # process node
```

### Step 2: Re-ingest Your Codebase

To take advantage of new features, re-ingest your codebase:

```bash
# Basic re-ingestion (replaces existing data)
python -m codebase_rag.main start --repo-path /path/to/repo --update-graph --clean

# With parallel processing for large codebases
python -m codebase_rag.main start --repo-path /path/to/repo --update-graph --clean --parallel

# For very large codebases, process specific folders
python -m codebase_rag.main start --repo-path /path/to/linux-kernel \
  --update-graph --clean --parallel --workers 16 \
  --folder-filter "drivers,kernel,fs"
```

### Step 3: Configure Multiple Providers (Optional)

You can now configure multiple AI providers in your `.env` file:

```bash
# Configure all providers
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### Step 4: Leverage New Features

#### Multi-Provider AI
```bash
# Use Anthropic Claude
python -m codebase_rag.main start --repo-path /path/to/repo \
  --orchestrator-model claude-3-5-sonnet-20241022

# Mix providers: Claude for orchestration, Gemini for Cypher
python -m codebase_rag.main start --repo-path /path/to/repo \
  --orchestrator-model claude-3-5-sonnet-20241022 \
  --cypher-model gemini-2.5-flash-lite-preview-06-17
```

#### Parallel Processing
```bash
# Enable parallel processing (auto-detects workers)
python -m codebase_rag.main start --repo-path /path/to/repo --update-graph --parallel

# Specify worker count
python -m codebase_rag.main start --repo-path /path/to/repo --update-graph --parallel --workers 8
```

#### Memory Optimization
Automatically enabled for files >10MB. Monitor with progress reporter.

#### Test Analysis
Tests are now automatically detected and linked. Query them:
```
"Show me all functions that have unit tests"
"Find untested functions in the authentication module"
"List all BDD scenarios for user management"
```

#### C Code Queries
New queries for C codebases:
```
"Find all functions that use spinlocks"
"Show pointer relationships in driver code"
"List all syscall implementations"
"Find macro expansions for CONFIG_DEBUG"
```

## Breaking Changes

### None
This release maintains full backward compatibility. All existing features continue to work as before.

## Performance Tips

### For Large Codebases (>100K LOC)
1. Use parallel processing: `--parallel --workers 16`
2. Filter folders: `--folder-filter "src,lib"`
3. Skip tests initially: `--skip-tests`
4. Process incrementally by folder

### For C Kernel Code
1. Start with subsystems: `--folder-filter "drivers/net"`
2. Use higher worker count: `--workers 32`
3. Monitor memory usage during processing

### Query Performance
1. Indexes are automatically created on first run
2. Use qualified names in queries when possible
3. Cache warms up after first queries

## New Example Scripts

Check out the new example scripts:

```bash
# Analyze large codebases
python examples/large_codebase_example.py /path/to/linux --workers 16

# Analyze C code and tests
python examples/c_and_test_analysis_example.py --report
```

## Troubleshooting

### Out of Memory Errors
- Reduce worker count: `--workers 4`
- Process folders separately
- Enable swap space for very large repos

### Slow Processing
- Enable parallel mode: `--parallel`
- Skip test files: `--skip-tests`
- Filter to specific folders

### C Parsing Issues
- Ensure tree-sitter-c==0.21.3 is installed
- Check for non-standard C syntax
- Report issues with specific code samples

## Getting Help

- Check [CHANGELOG.md](CHANGELOG.md) for detailed changes
- See [README.md](README.md) for updated documentation
- Open an issue for migration problems
