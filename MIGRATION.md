# Migration Guide

This guide helps you migrate to the latest version and take advantage of new features.

## Version 0.2.0 - Major Feature Release

### New Features Overview

#### Multi-Provider LLM Support
The system now supports multiple AI providers:
- **Google Gemini** - Best overall performance
- **OpenAI** - GPT-4 and GPT-4o models
- **Anthropic Claude** - Claude 3.5 Sonnet and Haiku
- **Local Models** - Privacy-focused with Ollama

You can mix providers for different tasks and switch at runtime.

#### 1. C Language Support
The system now fully supports C codebases, including:
- Function and struct definitions
- Pointer analysis and function pointers
- Macro expansion tracking
- Linux kernel patterns (syscalls, exports, locks)
- Preprocessor directive handling
- Type definitions and unions

#### 2. Advanced Analysis Features

**Security Analysis:**
- SQL/Command injection detection
- XSS vulnerability scanning
- Buffer overflow analysis (C/C++)
- Hardcoded secrets detection
- Taint flow tracking
- CWE mapping for vulnerabilities

**Test Framework Integration:**
- Unit tests across all major frameworks
- BDD/Gherkin feature files
- Test-to-code linking
- Coverage analysis and metrics
- Assertion extraction
- Test suite organization

**Data Flow Analysis:**
- Variable usage tracking
- Taint propagation paths
- Data transformation tracking
- Sensitive data detection

**Inheritance & OOP Analysis:**
- Full inheritance hierarchies
- Interface implementations
- Method override tracking
- Abstract class detection
- Polymorphism analysis

#### 3. Version Control Integration
Full Git repository analysis:
- Commit history with metadata
- Author contribution tracking
- File modification frequency
- Blame information
- Change patterns over time
- Test file history

#### 4. Configuration File Support
Parse and analyze configuration files:
- YAML, JSON, TOML, INI formats
- Makefile and build scripts
- Kconfig (Linux kernel configs)
- Environment variable files
- Configuration dependencies
- Secret detection in configs

#### 5. Performance Enhancements
Major scalability improvements:
- Parallel processing with multiple workers
- Memory optimization for large files
- Graph indexing for faster queries
- Query result caching
- Progress reporting with ETA
- Streaming parsers for huge files

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

**New Dependencies Added:**
- `gitpython>=3.1.0` - Git repository analysis
- `pyyaml>=6.0.0` - YAML configuration parsing
- Additional analysis modules for security, testing, and data flow

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

#### Security Analysis Queries
```
"Show me all SQL injection vulnerabilities"
"Find hardcoded passwords or API keys"
"List buffer overflow risks in C code"
"Show me taint flows from user input"
"Find CWE-79 XSS vulnerabilities"
```

#### Test Coverage Queries
```
"Show me all functions that have unit tests"
"Find untested functions in the authentication module"
"List all BDD scenarios for user management"
"What's the test coverage for the database module?"
"Show me flaky tests with multiple assertion types"
```

#### Version Control Queries
```
"Who are the top contributors?"
"Show files changed in the last week"
"Who last modified the auth module?"
"Find commits by John Doe"
"Show me the most frequently modified files"
```

#### Configuration Analysis Queries
```
"Find all database configuration settings"
"Show me API keys in config files"
"List all Makefile targets"
"Find environment-specific configs"
"Show configuration dependencies"
```

#### C Code Queries
```
"Find all struct definitions"
"Show me function pointers"
"List all macro definitions"
"Find kernel module entry points"
"Show pointer relationships"
"Find all syscall implementations"
"List EXPORT_SYMBOL declarations"
```

#### Data Flow Queries
```
"Trace the password variable through the code"
"Find all uses of user_input"
"Show me data transformations"
"Track sensitive data flows"
"Find variable reassignments"
```

#### OOP/Inheritance Queries
```
"Show inheritance tree for UserService"
"Find all interface implementations"
"List methods that override parent methods"
"Show me abstract classes"
"Find deep inheritance hierarchies"
```

## Upgrading from v0.1 to v0.2

### What's Changed
1. **Enhanced Graph Schema**: New node types (Vulnerability, Author, Commit, ConfigFile) and relationships
2. **Improved Query Templates**: More sophisticated natural language understanding
3. **Better C Support**: Full kernel code analysis capabilities
4. **Analysis Modules**: New modules in `codebase_rag/analysis/` for specialized analysis

### Required Actions
1. **Re-ingest your codebase** to populate new node types and relationships
2. **Update your `.env`** file with any new provider API keys
3. **Review new query patterns** in the Query Cookbook for enhanced capabilities

### Optional Optimizations
1. Enable parallel processing for faster ingestion
2. Use folder filtering for incremental updates
3. Configure multiple AI providers for flexibility

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

Check out the enhanced example scripts:

```bash
# Analyze large codebases with parallel processing
python examples/large_codebase_example.py /path/to/linux --workers 16

# Analyze C code and test coverage
python examples/c_and_test_analysis_example.py --report

# Version control and configuration analysis
python examples/vcs_and_config_example.py /path/to/repo --days 30 --show-queries

# Security vulnerabilities and test coverage
python examples/security_and_test_example.py /path/to/repo --language python

# Comprehensive analysis with all features
python examples/comprehensive_analysis_example.py /path/to/repo --report analysis.json
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
