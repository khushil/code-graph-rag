# CLAUDE.md - Graph-Code RAG System Enhancement

> **Note**: This file contains technical reference documentation. For session-level practices and Git discipline, use the custom instructions provided in `project-instructions-setup.md`.

## Project Overview

You are enhancing the Graph-Code RAG system to support large-scale, multi-language codebases with a focus on C language support (particularly for Linux/BSD kernels), advanced graph relationships, BDD/TDD testing framework integration, and improved scalability. You are working in an already forked repository with the code locally available.

## Key Enhancement Areas

1. **C Language Support** - Full support for C codebases including kernel-specific features
2. **Advanced Graph Relationships** - Inheritance, data flows, pointers, concurrency primitives
3. **BDD/TDD Testing Integration** - Parse and link test scenarios/assertions to code
4. **Scalability** - Handle repos with millions of lines of code
5. **Security & Performance Auditing** - Vulnerability detection and path analysis
6. **Version Control Integration** - Git history and blame support

## Development Approach

### Phase 1: Foundation & C Language Support (Priority: HIGH)
Start by extending the existing system to support C language parsing using Tree-sitter-c.

**Key Files to Modify:**
- `language_config.py` - Add C language configuration
- `main.py` - Update ingestion pipeline for C-specific features
- Create new modules for C-specific parsing (preprocessor, pointers, etc.)

**Implementation Steps:**
1. Add Tree-sitter-c parser integration
2. Define C-specific node types (Function, Struct, Macro, Pointer, etc.)
3. Implement preprocessor directive parsing (#define, #ifdef)
4. Add pointer analysis with POINTS_TO edges
5. Support function pointers and callbacks
6. Parse kernel-specific constructs (SYSCALL_DEFINE, EXPORT_SYMBOL)

### Phase 2: Testing Framework Integration (Priority: HIGH)
Implement comprehensive BDD/TDD support across all languages.

**New Components:**
- BDD parser module for Gherkin files
- Test detection and parsing for each language
- Assertion extraction and linking
- Test coverage integration

**Per-Language Support:**
- Python: pytest, unittest, behave
- JavaScript/TypeScript: Jest, Mocha, Cucumber
- Rust: cargo test, cucumber-rust
- Go: testing package, Ginkgo
- Java: JUnit, Cucumber-JVM
- C++: Google Test, Catch2
- C: Unity, Check, kselftest

### Phase 3: Advanced Graph Relationships (Priority: HIGH)
Extend the graph schema with sophisticated relationships.

**New Edge Types:**
- INHERITS_FROM, IMPLEMENTS, OVERRIDES (OOP)
- FLOWS_TO, MODIFIES (data flow)
- POINTS_TO, ASSIGNS_FP, INVOKES_FP (pointers)
- LOCKS, UNLOCKS (concurrency)
- TESTS, COVERS, ASSERTS (testing)
- IMPLEMENTS_SCENARIO, GIVEN_LINKS_TO (BDD)

### Phase 4: Scalability Enhancements (Priority: HIGH)
Optimize for large codebases like kernels.

**Features:**
- Parallel parsing with multiprocessing
- Partial ingestion with folder filtering
- Graph partitioning by subsystem
- Memory optimization strategies
- Indexing for fast queries

### Phase 5: Security & Auditing (Priority: MEDIUM)
Implement vulnerability detection and analysis.

**Components:**
- Semgrep integration
- Kernel-specific vulnerability patterns
- Taint tracking via FLOWS_TO edges
- Race condition detection
- Buffer overflow analysis

### Phase 6: Version Control & Configuration (Priority: MEDIUM)
Add Git integration and config file support.

**Features:**
- Git history parsing with gitpython
- Blame information as graph properties
- Configuration file parsing (YAML, JSON, Kconfig)
- Makefile dependency extraction

## Code Structure

Based on the existing repository structure at `https://github.com/khushil/code-graph-rag`, here's how to organize the enhancements:

```
code-graph-rag/
├── codebase_rag/                # Main package directory
│   ├── __init__.py
│   ├── main.py                  # Main entry point (existing, to be updated)
│   ├── language_config.py       # Language configurations (existing, to be extended)
│   ├── graph_loader.py          # Graph loading utilities (existing)
│   ├── parsers/                 # New directory for language parsers
│   │   ├── __init__.py
│   │   ├── c_parser.py          # New: C-specific parsing
│   │   ├── test_parser.py       # New: Test framework parsing
│   │   └── bdd_parser.py        # New: BDD/Gherkin parsing
│   ├── graph/                   # New directory for graph components
│   │   ├── __init__.py
│   │   ├── schema.py            # Extended graph schema
│   │   ├── relationships.py     # New relationship types
│   │   └── kernel_nodes.py      # New: Kernel-specific nodes
│   ├── analysis/                # New directory for analysis modules
│   │   ├── __init__.py
│   │   ├── data_flow.py         # New: Data flow analysis
│   │   ├── security.py          # New: Security scanning
│   │   └── coverage.py          # New: Test coverage
│   └── rag/                     # New directory for RAG components
│       ├── __init__.py
│       └── prompts.py           # Extended AI prompts
├── tests/
│   ├── __init__.py
│   ├── test_c_parser.py         # New tests
│   ├── test_bdd_integration.py  # New tests
│   └── fixtures/                # Test data including C files
│       ├── sample.c
│       ├── kernel_sample.c
│       └── test_scenarios.feature
├── requirements.txt             # Updated dependencies
├── setup.py                     # Package setup (if not exists)
├── README.md                    # Documentation (existing)
├── CLAUDE.md                    # This file
└── .env.example                 # Environment variables template
```

## Implementation Guidelines

### Module Import Structure:
When implementing new features, follow the existing import patterns:
```python
# Example imports in new modules
from codebase_rag.language_config import get_language_config
from codebase_rag.graph_loader import load_graph
# New imports for enhanced features
from codebase_rag.parsers.c_parser import CParser
from codebase_rag.graph.relationships import RelationshipTypes
```

### When Adding C Support:
- Extend `codebase_rag/language_config.py` with C configuration
- Create `codebase_rag/parsers/c_parser.py` following existing parser patterns
- Use Tree-sitter-c for AST parsing
- Handle preprocessor directives as separate nodes
- Create EXPANDS_TO edges for macro usage
- Parse function pointers with special attention to kernel callbacks
- Support inline assembly blocks as INLINE_ASM nodes

### When Implementing BDD/TDD:
- Create parsers in `codebase_rag/parsers/` directory
- Extend main.py to detect and route test files to appropriate parsers
- Parse Gherkin files to extract Features, Scenarios, and Steps
- Match step definitions to code using regex patterns
- Create bidirectional edges between tests and tested code
- Support assertion extraction for all major test frameworks
- Enable shell execution for test runners (optional)

### For Kernel Analysis:
- Add kernel-specific configurations in language_config.py
- Create specialized node types in `codebase_rag/graph/kernel_nodes.py`
- Add subsystem labels (e.g., :Kernel:FS, :Kernel:Net)
- Parse Kconfig and Makefiles for build dependencies
- Support syscall tracing with SYSCALL_PATH edges
- Handle concurrency primitives (spinlocks, mutexes)
- Limit graph depth for header inclusion chains

### Extending the Main Entry Point:
The existing `codebase_rag/main.py` uses a command structure. Add new commands or extend existing ones:
```python
# Example: Add new command for C-specific analysis
python -m codebase_rag.main analyze-kernel --repo-path /path/to/kernel --subsystem drivers/net

# Example: Add test analysis command
python -m codebase_rag.main analyze-tests --repo-path /path/to/repo --framework pytest
```

### Query Examples to Support:
```
# C/Kernel queries
"Trace all paths from syscall sys_read to file operations"
"Find all functions using spinlock X"
"Show macro expansion impact for CONFIG_DEBUG"
"List interrupt handlers and their IRQ mappings"

# Testing queries
"Show BDD scenarios testing user authentication"
"Find code not covered by any unit tests"
"List assertions testing function calculate_price"
"Trace Given-When-Then steps to implementation"

# Security queries
"Find taint paths from user input to kernel space"
"Detect potential race conditions in driver code"
"Show buffer overflow vulnerabilities in memcpy usage"
```

## Dependencies to Add

```python
# requirements.txt additions
tree-sitter-c>=0.20.0
gitpython>=3.1.0
semgrep>=1.0.0
gherkin-official>=24.0.0
coverage>=7.0.0
multiprocessing-logging>=0.3.0
```

## Testing Strategy

1. **Unit Tests**: For each new parser and module
2. **Integration Tests**: Using sample C files and kernel subsets
3. **Performance Tests**: Benchmark on increasing codebase sizes
4. **BDD Tests**: Test the BDD parser itself using BDD
5. **Kernel Tests**: Use Linux kernel samples (e.g., drivers/char/random.c)

## Backward Compatibility

- Maintain existing CLI interface
- Keep current language support intact
- Extend rather than replace existing node types
- Add new features behind feature flags when breaking

## Error Handling

- Graceful degradation for parse failures
- Detailed logging for debugging
- Retry mechanisms for transient failures
- User-friendly error messages

## Documentation Updates

- Update README.md with C examples
- Add kernel analysis guide
- Create BDD/TDD integration tutorial
- Document new CLI flags and options

## Priority Order for Implementation

1. **C Language Basic Support** (REQ-LNG-1, REQ-LNG-2)
2. **Basic Test Integration** (REQ-TST-1, REQ-TST-2)
3. **Data Flow Analysis** (REQ-DF-1, REQ-DF-2, REQ-DF-4)
4. **Scalability for Large Repos** (REQ-SCL-1, REQ-SCL-2)
5. **BDD Step Traceability** (REQ-TST-5, REQ-TST-6)
6. **Security Scanning** (REQ-SEC-1, REQ-SEC-2)
7. **Version Control** (REQ-VCS-1, REQ-VCS-2)
8. **Advanced Kernel Features** (REQ-SEC-5, REQ-SEC-6)

## Working with Existing Codebase

You are working in a forked repository that has already been cloned locally. The codebase is organized under the `codebase_rag` package directory.

### Key Existing Files to Understand:
1. **`codebase_rag/main.py`**: Entry point with command structure
   - Uses argparse for CLI
   - Has `start`, `query`, `optimize` commands
   - Handles repo ingestion and graph updates

2. **`codebase_rag/language_config.py`**: Language configurations
   - Contains Tree-sitter queries for each language
   - Defines file extensions, node types, and relationships
   - Add C configuration here following existing patterns

3. **`codebase_rag/graph_loader.py`**: Graph utilities
   - Handles graph export/import
   - Provides graph analysis functions
   - Extend for new node/edge types

### Integration Points:
- **Ingestion Pipeline**: Modify the parsing logic in main.py to route C files to new parser
- **Query System**: Update the RAG prompts to handle new query types
- **Graph Schema**: Extend Memgraph schema with new node labels and edge types
- **API Models**: Configure support for multiple LLM providers (Gemini, Ollama, OpenAI)

### Initial Setup Tasks:
```bash
# Install additional dependencies for enhancements
pip install tree-sitter-c gitpython semgrep gherkin-official coverage

# Ensure Memgraph is running (via Docker)
docker run -p 7687:7687 memgraph/memgraph

# Configure environment variables if not already done
# Check if .env exists, if not copy from .env.example
# Edit .env with your API keys and configurations
```

## Success Criteria

- Successfully parse and query the Linux kernel (subset)
- Link BDD scenarios to code implementations
- Detect common vulnerabilities in C code
- Handle 1M+ LOC repositories efficiently
- Maintain <5s query response times
- Achieve >90% accuracy in relationship extraction