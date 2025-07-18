# Graph-Code RAG Query Cookbook

This cookbook provides practical examples of queries you can use with the Graph-Code RAG system to analyze your codebase. The system supports natural language queries that are automatically translated to Cypher queries for the Neo4j graph database.

## Table of Contents

1. [Basic Code Navigation](#basic-code-navigation)
2. [C Language Queries](#c-language-queries)
3. [Security Analysis](#security-analysis)
4. [Testing & Coverage](#testing--coverage)
5. [Version Control & Git](#version-control--git)
6. [Configuration Analysis](#configuration-analysis)
7. [Dependency Analysis](#dependency-analysis)
8. [Data Flow Analysis](#data-flow-analysis)
9. [Architecture & Design](#architecture--design)
10. [Complex Multi-Feature Queries](#complex-multi-feature-queries)

## Basic Code Navigation

### Find specific files
```
"Find the main README file"
"Show me all Python files"
"List files in the src directory"
"Find all test files"
"Show me configuration files"
```

### Find code elements
```
"Find all classes in the project"
"Show me functions that start with 'process_'"
"Find methods with decorators"
"List all abstract classes"
"Show me the main entry point"
```

### Search by keyword
```
"Find code related to authentication"
"Show me database connection code"
"Find API endpoints"
"Search for logging functionality"
```

## C Language Queries

### Kernel & System Programming
```
"Find kernel module entry points"
"Show me all syscall definitions"
"Find interrupt handlers"
"List kernel subsystem interfaces"
"Show me EXPORT_SYMBOL declarations"
```

### C Structures & Types
```
"Find all struct definitions"
"Show me union types"
"List typedef declarations"
"Find structs larger than 1KB"
"Show me packed structures"
```

### Preprocessor & Macros
```
"Find all macro definitions"
"Show me conditional compilation blocks"
"Find CONFIG_* macros"
"List header guard patterns"
"Show me macro expansions"
```

### Function Pointers & Callbacks
```
"Find function pointer declarations"
"Show me callback registrations"
"Find vtable definitions"
"List function pointer parameters"
"Show me indirect function calls"
```

### Memory Management
```
"Find malloc/free patterns"
"Show me memory allocation sites"
"Find potential memory leaks"
"List custom allocators"
"Show me DMA operations"
```

## Security Analysis

### Vulnerability Detection
```
"Find all security vulnerabilities"
"Show me high severity issues"
"Find SQL injection vulnerabilities"
"List buffer overflow risks"
"Show me XSS vulnerabilities"
```

### Taint Analysis
```
"Trace user input through the code"
"Find tainted data flows"
"Show me sanitization functions"
"Find paths from input to database"
"List validation checkpoints"
```

### Authentication & Authorization
```
"Find authentication code"
"Show me authorization checks"
"Find password handling code"
"List JWT implementations"
"Show me session management"
```

### Cryptography
```
"Find cryptographic operations"
"Show me hash functions"
"Find encryption/decryption code"
"List random number generation"
"Show me certificate handling"
```

## Testing & Coverage

### Test Discovery
```
"Find all test files"
"Show me unit tests"
"Find integration tests"
"List BDD scenarios"
"Show me test fixtures"
```

### Coverage Analysis
```
"Find untested functions"
"Show me test coverage by module"
"Find code without assertions"
"List most tested modules"
"Show me flaky tests"
```

### Test Relationships
```
"What does this test cover?"
"Find tests for UserService class"
"Show me tests that use mocks"
"Find performance tests"
"List failing test patterns"
```

### BDD/TDD Queries
```
"Show me Gherkin scenarios"
"Find Given-When-Then patterns"
"List step definitions"
"Show me scenario outlines"
"Find unimplemented steps"
```

## Version Control & Git

### Commit History
```
"Show recent changes"
"Who modified this file?"
"Find commits by John Doe"
"Show me hotfix commits"
"List merge commits"
```

### Contributors
```
"Show top contributors"
"Who owns this module?"
"Find inactive contributors"
"List contributors by language"
"Show me first-time contributors"
```

### File History
```
"Show file modification frequency"
"Find most changed files"
"List recently added files"
"Show me deleted files"
"Find renamed files"
```

### Code Age
```
"Find oldest code"
"Show me recent additions"
"Find stale code"
"List files not changed in 6 months"
"Show me technical debt areas"
```

## Configuration Analysis

### Config Files
```
"Find all configuration files"
"Show me YAML configs"
"Find environment-specific configs"
"List build configurations"
"Show me runtime configs"
```

### Settings & Values
```
"Find database configuration"
"Show me API keys"
"Find feature flags"
"List environment variables"
"Show me timeout settings"
```

### Dependencies
```
"What configs does this module use?"
"Find config inheritance"
"Show me config overrides"
"List default values"
"Find missing configurations"
```

## Dependency Analysis

### Import/Export
```
"What does this module import?"
"Find circular dependencies"
"Show me unused imports"
"List export statements"
"Find re-exports"
```

### External Dependencies
```
"List all external packages"
"Find outdated dependencies"
"Show me security advisories"
"List peer dependencies"
"Find dependency conflicts"
```

### Module Relationships
```
"Show module dependency graph"
"Find tightly coupled modules"
"List independent modules"
"Show me layering violations"
"Find shared dependencies"
```

## Data Flow Analysis

### Variable Tracking
```
"Trace the 'user_id' variable"
"Find all uses of 'password'"
"Show me global variables"
"Track data transformations"
"Find variable reassignments"
```

### Flow Patterns
```
"Find data validation points"
"Show me data sanitization"
"Track request flow"
"Find data aggregation"
"Show me caching points"
```

### State Management
```
"Find state mutations"
"Show me immutable data"
"Find shared state"
"List state containers"
"Show me race conditions"
```

## Architecture & Design

### Class Hierarchies
```
"Show inheritance tree for User"
"Find interface implementations"
"List abstract methods"
"Show me override patterns"
"Find deep inheritance"
```

### Design Patterns
```
"Find singleton patterns"
"Show me factory methods"
"Find observer patterns"
"List decorator usage"
"Show me strategy patterns"
```

### Architecture Violations
```
"Find layering violations"
"Show me circular dependencies"
"Find god classes"
"List anti-patterns"
"Show me code smells"
```

### Modularity
```
"Find highly cohesive modules"
"Show me loosely coupled code"
"Find module boundaries"
"List public APIs"
"Show me internal modules"
```

## Complex Multi-Feature Queries

### Security + Testing
```
"Find untested security-critical code"
"Show me vulnerabilities in tested code"
"Find security tests"
"List penetration test results"
"Show me security assertions"
```

### Performance + Git
```
"Find performance bottlenecks in recent commits"
"Who introduced this slow query?"
"Show me optimization commits"
"Find performance regression"
"List benchmarking code"
```

### Architecture + Dependencies
```
"Find architectural violations in external dependencies"
"Show me framework-specific patterns"
"Find abstraction leaks"
"List plugin architectures"
"Show me extension points"
```

### Quality Metrics
```
"Show me code complexity metrics"
"Find high-maintenance modules"
"List code review comments"
"Show me refactoring candidates"
"Find duplicate code"
```

### Release Preparation
```
"Find TODOs and FIXMEs"
"Show me deprecated code"
"Find breaking changes"
"List migration requirements"
"Show me release notes items"
```

## Query Tips

1. **Be Specific**: More specific queries yield better results
   - Instead of: "find bugs"
   - Use: "find SQL injection vulnerabilities in the user module"

2. **Use Context**: Provide file paths or module names when known
   - "Find functions in src/auth/login.py"
   - "Show me tests for the UserService class"

3. **Combine Filters**: Mix different aspects for precise results
   - "Find untested functions modified in the last week"
   - "Show me high-severity vulnerabilities in external dependencies"

4. **Explore Relationships**: Use the graph structure
   - "What calls this function?"
   - "Show me all dependencies of this module"
   - "Trace data flow from API to database"

5. **Leverage Metadata**: Use git, test, and config information
   - "Who should review changes to this module?"
   - "What configuration affects this feature?"
   - "Show me the test coverage trend"

## Common Use Cases

### Code Review
```
"Show me complex functions that need review"
"Find code without tests"
"List recent changes by new contributors"
"Show me potential security issues"
```

### Debugging
```
"Trace execution path for this error"
"Find all callers of this function"
"Show me related configuration"
"Find similar error patterns"
```

### Refactoring
```
"Find duplicate code patterns"
"Show me unused code"
"Find candidates for extraction"
"List tightly coupled modules"
```

### Onboarding
```
"Show me the main entry points"
"Explain the module structure"
"Find documentation files"
"Show me example usage"
```

### Compliance
```
"Find license declarations"
"Show me audit log code"
"Find PII handling"
"List security controls"
```
