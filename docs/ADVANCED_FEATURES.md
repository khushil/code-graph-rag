# Advanced Features Guide - Graph-Code RAG System

This guide covers all the advanced features added to the Graph-Code RAG system, including security analysis, test coverage tracking, version control integration, and more.

## Table of Contents

1. [Data Flow Analysis](#data-flow-analysis)
2. [Security Vulnerability Detection](#security-vulnerability-detection)
3. [Inheritance and OOP Analysis](#inheritance-and-oop-analysis)
4. [Test Coverage Tracking](#test-coverage-tracking)
5. [Git Integration](#git-integration)
6. [Configuration File Parsing](#configuration-file-parsing)
7. [Enhanced Dependency Tracking](#enhanced-dependency-tracking)
8. [C Language Support](#c-language-support)
9. [Query Examples](#query-examples)

## Data Flow Analysis

The system tracks how data flows through your codebase by analyzing variable assignments, function parameters, and return values.

### Features:
- **Variable Tracking**: Creates `Variable` nodes for all variables with scope information
- **Flow Relationships**: `FLOWS_TO` edges show data movement
- **Taint Analysis**: Track potentially dangerous data flows

### Example Queries:

```cypher
// Find all places where user input flows
MATCH path = (v:Variable {name: "user_input"})-[:FLOWS_TO*]->(target)
RETURN path
```

## Security Vulnerability Detection

Comprehensive security scanning using pattern matching and AST analysis.

### Detected Vulnerabilities:
- SQL Injection
- Command Injection
- XSS (Cross-Site Scripting)
- Path Traversal
- Hardcoded Secrets
- Buffer Overflows (C/C++)
- Weak Cryptography

### Vulnerability Properties:
- `type`: Category of vulnerability
- `severity`: LOW, MEDIUM, HIGH, CRITICAL
- `cwe_id`: Common Weakness Enumeration ID
- `description`: Detailed explanation
- `recommendation`: How to fix

### Example Queries:

```cypher
// Find all high-severity vulnerabilities
MATCH (code)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE v.severity IN ['HIGH', 'CRITICAL']
RETURN code.qualified_name, v.type, v.description, v.recommendation
```

## Inheritance and OOP Analysis

Track class hierarchies, interface implementations, and method overrides.

### Features:
- **Inheritance Tracking**: `INHERITS_FROM` relationships
- **Interface Implementation**: `IMPLEMENTS` relationships
- **Method Overrides**: `OVERRIDES` relationships with `calls_super` property
- **Abstract Classes**: `is_abstract` property on Class nodes

### Example Queries:

```cypher
// Find all classes that inherit from BaseModel
MATCH (child:Class)-[:INHERITS_FROM*]->(parent:Class {name: "BaseModel"})
RETURN child.qualified_name
```

## Test Coverage Tracking

Analyze test coverage and test-to-code relationships.

### Features:
- **Test Detection**: Automatically identifies test files and test cases
- **Test Relationships**: `TESTS` edges link tests to tested code
- **Assertion Tracking**: `HAS_ASSERTION` relationships for test assertions
- **Framework Support**: pytest, unittest, Jest, Mocha, JUnit, and more

### Example Queries:

```cypher
// Find untested functions
MATCH (f:Function)
WHERE NOT (f)<-[:TESTS]-(:TestCase)
RETURN f.qualified_name AS untested_function
```

```cypher
// Calculate test coverage by module
MATCH (m:Module)-[:DEFINES]->(f:Function)
OPTIONAL MATCH (f)<-[:TESTS]-(t:TestCase)
WITH m, count(f) AS total, count(t) AS tested
RETURN m.name, (tested * 100.0 / total) AS coverage_percentage
```

## Git Integration

Track version control history and contributor information.

### Features:
- **Commit History**: Git blame information on Module nodes
- **Contributors**: `Contributor` nodes with commit counts
- **File History**: Track when files were created and last modified
- **Commit Metadata**: Author, date, message for each commit

### Module Properties:
- `git_creation_date`: When the file was first created
- `git_last_modified`: Last modification date
- `git_commit_count`: Number of commits to this file

### Example Queries:

```cypher
// Find recently modified files
MATCH (m:Module)
WHERE m.git_last_modified > datetime('2024-01-01')
RETURN m.path, m.git_last_modified
ORDER BY m.git_last_modified DESC
```

## Configuration File Parsing

Parse and analyze various configuration file formats.

### Supported Formats:
- JSON (`.json`)
- YAML (`.yaml`, `.yml`)
- TOML (`.toml`)
- INI (`.ini`, `.cfg`, `.conf`)
- Environment files (`.env`)
- Properties files (`.properties`)
- Special files: `Dockerfile`, `Makefile`, `package.json`, etc.

### Features:
- **Setting Extraction**: Creates `ConfigSetting` nodes
- **Dependency Detection**: Links to external packages
- **Environment Detection**: Identifies environment-specific configs
- **Build Scripts**: Extracts npm scripts, make targets, etc.

### Example Queries:

```cypher
// Find all database configuration settings
MATCH (s:ConfigSetting)
WHERE toLower(s.key) CONTAINS 'database'
RETURN s.key, s.value, s.path
```

## Enhanced Dependency Tracking

Advanced module dependency analysis.

### Features:
- **Import Tracking**: `IMPORTS` relationships between modules
- **Export Tracking**: `EXPORTS` relationships for public APIs
- **Circular Dependencies**: `CIRCULAR_DEPENDENCY` detection
- **Transitive Dependencies**: Follow dependency chains

### Example Queries:

```cypher
// Find circular dependencies
MATCH (m1:Module)-[:CIRCULAR_DEPENDENCY]->(m2:Module)
RETURN m1.qualified_name, m2.qualified_name
```

## C Language Support

Specialized support for C codebases including kernel code.

### Features:
- **Struct Analysis**: `Struct` nodes with size information
- **Macro Expansion**: `Macro` nodes and `EXPANDS_MACRO` relationships
- **Function Pointers**: `FunctionPointer` nodes with signatures
- **Pointer Analysis**: `POINTS_TO` relationships
- **Kernel Constructs**: Support for `SYSCALL_DEFINE`, `EXPORT_SYMBOL`, etc.

### Example Queries:

```cypher
// Find all kernel module entry points
MATCH (f:Function)
WHERE f.name IN ['init_module', 'cleanup_module']
RETURN f.qualified_name, f.name
```

## Query Examples

### Complex Multi-Feature Queries

#### Security Hotspots with Git Blame
```cypher
// Find who introduced vulnerabilities
MATCH (m:Module)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE v.severity = 'CRITICAL'
RETURN m.path, v.type, m.git_last_modified
```

#### Test Coverage for Changed Code
```cypher
// Functions changed recently and their test status
MATCH (m:Module)-[:DEFINES]->(f:Function)
WHERE m.git_last_modified > datetime().subtract(duration('P7D'))
OPTIONAL MATCH (f)<-[:TESTS]-(t:TestCase)
RETURN m.path, f.name, t IS NOT NULL AS is_tested
```

#### Architecture Violations
```cypher
// Find direct database access from UI layer
MATCH (ui:Module)-[:IMPORTS]->(db:Module)
WHERE ui.path CONTAINS 'ui' AND db.path CONTAINS 'database'
RETURN ui.qualified_name AS violation_source
```

## Natural Language Query Support

The system supports natural language queries that are automatically translated to Cypher:

- "Show me all SQL injection vulnerabilities"
- "Find functions that haven't been tested"
- "Who are the top contributors?"
- "Show me the class hierarchy for UserService"
- "Find all configuration files"
- "What files changed in the last week?"
- "Show me circular dependencies"

## Best Practices

1. **Regular Analysis**: Run security and dependency analysis regularly
2. **Test Coverage Goals**: Use queries to maintain coverage targets
3. **Security Reviews**: Focus on high-severity vulnerabilities first
4. **Architecture Monitoring**: Set up queries to detect violations
5. **Configuration Auditing**: Regularly check for exposed secrets

## Performance Considerations

- The system uses batched operations for large codebases
- Partial ingestion is supported for incremental updates
- Graph partitioning can be used for very large repositories
- Indexes are created on frequently queried properties

## Future Enhancements

- Real-time vulnerability feeds
- Machine learning for code smell detection
- Integration with CI/CD pipelines
- Custom rule definition for security scanning
- Performance profiling integration