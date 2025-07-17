# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Fixed tree-sitter-c compatibility issues by handling API changes in captures() method
- Fixed C parser to properly extract typedefs, preprocessor directives, and function parameters
- Fixed pointer analyzer to detect pointer initializations and function pointers
- Fixed kernel analyzer to handle None nodes and improve pattern matching
- Updated integration test mocks to match actual API calls
- Fixed 25 failing tests bringing test failure count to 0

### Added

#### Multi-Provider LLM Support
- Added support for Anthropic Claude models (claude-3-5-sonnet, claude-3-5-haiku)
- Unified provider interface for seamless switching between:
  - Google Gemini
  - OpenAI (GPT-4, GPT-4o)
  - Anthropic Claude
  - Local models (Ollama)
- Auto-detection of provider based on model name
- Support for mixing providers (e.g., Claude for orchestration, Gemini for Cypher)
- Updated configuration to support all providers

#### Sprint 1: C Language Foundation (REQ-LNG-1, REQ-LNG-2)
- Full C language support with Tree-sitter-c parser
- C-specific node types: Function, Struct, Union, Enum, Typedef, Macro, GlobalVariable
- Preprocessor directive parsing (#define, #ifdef, etc.)
- Header file analysis and inclusion tracking

#### Sprint 2: Advanced C & Kernel Features (REQ-DF-1, REQ-DF-2, REQ-SEC-5)
- Pointer analysis with POINTS_TO relationships
- Function pointer tracking (ASSIGNS_FP, INVOKES_FP edges)
- Linux kernel pattern detection:
  - SYSCALL_DEFINE macros
  - EXPORT_SYMBOL declarations
  - Spinlock/mutex usage (LOCKS/UNLOCKS edges)
- Callback pattern recognition

#### Sprint 3: Testing Framework Integration (REQ-TST-1, REQ-TST-2, REQ-TST-5)
- Multi-language test framework detection:
  - Python: pytest, unittest
  - JavaScript/TypeScript: Jest, Mocha, Jasmine
  - C: Unity, Check, CMocka
  - Rust: cargo test
  - Go: testing package, Ginkgo
  - Java: JUnit, TestNG
- BDD/Gherkin support for .feature files
- Test-to-code linking with TESTS relationships
- Assertion extraction and analysis
- Step definition matching for BDD

#### Sprint 4: Scalability & Performance (REQ-SCL-1, REQ-SCL-2, REQ-SCL-3)
- Parallel file processing with multiprocessing
  - Configurable worker pools (default: 80% CPU cores)
  - Thread-safe registry updates
  - Real-time progress reporting with ETA
- Memory optimization for large files:
  - Streaming file reader with chunked processing
  - Memory-mapped file support for files >10MB
  - Automatic garbage collection at 80% memory usage
- Graph indexing system:
  - 20+ predefined indexes for common queries
  - Query optimization hints
  - LRU cache with configurable TTL
- New CLI options:
  - `--parallel`: Enable parallel processing
  - `--workers N`: Set number of worker processes
  - `--folder-filter`: Process specific folders only
  - `--file-pattern`: Filter files by pattern
  - `--skip-tests`: Exclude test files from processing

### Enhanced
- Extended graph schema with new node types and relationships
- Improved language_config.py with C language configuration
- Updated graph_updater.py to handle C parsing and test detection
- Enhanced main.py with parallel processing options
- Added comprehensive example scripts for new features

### Dependencies
- tree-sitter-c==0.21.3 (for C language support)
- tqdm>=4.67.1 (for progress reporting)
- psutil>=5.9.0 (for memory monitoring)

## [0.0.2] - Previous Release

### Added
- Multi-language support for Python, JavaScript, TypeScript, Rust, Go, Scala, Java, C++
- Tree-sitter based parsing
- Memgraph knowledge graph storage
- Natural language querying with AI
- Code snippet retrieval
- File editing capabilities
- Shell command execution
- Code optimization features
- Graph export functionality

### Changed
- Improved error handling
- Better documentation
- Enhanced query performance

### Fixed
- Various bug fixes and stability improvements
