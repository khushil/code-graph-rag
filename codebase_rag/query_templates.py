"""Enhanced query templates for the Graph-Code RAG system with all new features."""

# ======================================================================================
#  ENHANCED GRAPH SCHEMA WITH NEW FEATURES
# ======================================================================================
ENHANCED_GRAPH_SCHEMA = """
**Graph Schema Definition with Advanced Features**

The database contains comprehensive information about a codebase with the following enhanced nodes and relationships:

**Core Structural Nodes:**
- Project: {name: string}
- Package: {qualified_name: string, name: string, path: string}
- Folder: {path: string, name: string}
- File: {path: string, name: string, extension: string}
- Module: {qualified_name: string, name: string, path: string, git_creation_date: string, git_last_modified: string, git_commit_count: int}
- Class: {qualified_name: string, name: string, decorators: list[string], base_classes: list[string], is_abstract: bool}
- Function: {qualified_name: string, name: string, decorators: list[string], start_line: int, end_line: int}
- Method: {qualified_name: string, name: string, decorators: list[string], is_override: bool, calls_super: bool}
- ExternalPackage: {name: string, version_spec: string}

**C Language Nodes:**
- Struct: {qualified_name: string, name: string, size: int}
- Macro: {qualified_name: string, name: string, definition: string}
- Typedef: {qualified_name: string, name: string, underlying_type: string}
- FunctionPointer: {qualified_name: string, name: string, signature: string}

**Analysis Nodes:**
- Variable: {qualified_name: string, name: string, type: string, scope: string}
- Vulnerability: {id: string, type: string, severity: string, cwe_id: string, description: string, recommendation: string}
- TestCase: {qualified_name: string, name: string, test_type: string}
- TestSuite: {qualified_name: string, name: string, framework: string}
- Assertion: {qualified_name: string, type: string, message: string}

**Version Control Nodes:**
- Repository: {name: string, path: string, total_commits: int, last_commit_date: string}
- Commit: {sha: string, message: string, date: string, author: string}
- Contributor: {id: string, name: string, email: string, total_commits: int}

**Configuration Nodes:**
- ConfigFile: {qualified_name: string, path: string, format: string, setting_count: int, environment_list: string}
- ConfigSetting: {qualified_name: string, key: string, value: string, path: string, type: string}
- BuildScript: {name: string, command: string, type: string}

**Core Relationships:**
- CONTAINS_* (hierarchical containment)
- DEFINES (module defines classes/functions)
- DEFINES_METHOD (class defines methods)
- CALLS (function/method calls)
- DEPENDS_ON_EXTERNAL (external dependencies)

**Enhanced Relationships:**
- IMPORTS (module imports from another)
- EXPORTS (module exports symbols)
- REQUIRES (module requires another)
- CIRCULAR_DEPENDENCY (circular import detected)
- FLOWS_TO (data flow between variables)
- INHERITS_FROM (class inheritance)
- IMPLEMENTS (interface implementation)
- OVERRIDES (method overrides parent)
- TESTS (test case tests code)
- ASSERTS (assertion in test)
- HAS_VULNERABILITY (code has security issue)
- TAINT_FLOW (tainted data flow path)
- AUTHORED_BY (commit authored by contributor)
- MODIFIES (commit modifies file)
- CONTRIBUTES_TO (contributor to project)
- HAS_CONFIG (project has config file)
- DEFINES_SETTING (config defines setting)
- REFERENCES_MODULE (config references code)
"""

# ======================================================================================
#  QUERY TEMPLATES FOR NEW FEATURES
# ======================================================================================

DATA_FLOW_QUERIES = """
**Data Flow Analysis Queries:**

1. Track variable usage:
```cypher
// Find all places where a variable is used
MATCH (v:Variable {name: $var_name})-[:FLOWS_TO]->(target)
RETURN v.qualified_name AS source, target.qualified_name AS destination, target.name AS target_name
```

2. Find tainted data paths:
```cypher
// Trace potential security issues through data flow
MATCH path = (source:Variable)-[:FLOWS_TO*1..5]->(sink:Variable)
WHERE source.tainted = true
RETURN path
```

3. Find unused variables:
```cypher
// Variables that are assigned but never read
MATCH (v:Variable)
WHERE NOT (v)-[:FLOWS_TO]->()
RETURN v.qualified_name AS unused_variable, v.scope AS scope
```
"""

SECURITY_QUERIES = """
**Security Analysis Queries:**

1. Find all vulnerabilities by severity:
```cypher
// List high and critical vulnerabilities
MATCH (v:Vulnerability)
WHERE v.severity IN ['HIGH', 'CRITICAL']
RETURN v.type AS vulnerability_type, v.severity AS severity, v.description AS description, v.cwe_id AS cwe
ORDER BY v.severity DESC
```

2. Find SQL injection vulnerabilities:
```cypher
// Specific vulnerability type search
MATCH (code)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE v.type = 'SQL_INJECTION'
RETURN code.qualified_name AS vulnerable_code, v.description AS issue, v.recommendation AS fix
```

3. Trace taint flows:
```cypher
// Follow tainted data through the application
MATCH path = (source)-[:TAINT_FLOW*1..10]->(sink)
WHERE source.is_user_input = true
RETURN path
```
"""

INHERITANCE_QUERIES = """
**Object-Oriented Analysis Queries:**

1. Find class hierarchy:
```cypher
// Show inheritance tree for a class
MATCH path = (child:Class)-[:INHERITS_FROM*1..5]->(parent:Class)
WHERE child.name = $class_name
RETURN path
```

2. Find method overrides:
```cypher
// Methods that override parent implementations
MATCH (m:Method)-[:OVERRIDES]->(parent:Method)
WHERE m.calls_super = false
RETURN m.qualified_name AS method, parent.qualified_name AS overridden_method
```

3. Find abstract classes:
```cypher
// List all abstract base classes
MATCH (c:Class)
WHERE c.is_abstract = true
RETURN c.qualified_name AS abstract_class, c.base_classes AS bases
```
"""

TEST_QUERIES = """
**Testing Analysis Queries:**

1. Find untested code:
```cypher
// Functions/methods without test coverage
MATCH (code:Function|Method)
WHERE NOT (code)<-[:TESTS]-(:TestCase)
RETURN code.qualified_name AS untested_code, labels(code)[0] AS type
```

2. Find test coverage by module:
```cypher
// Test coverage statistics per module
MATCH (m:Module)-[:DEFINES]->(code:Function|Method)
OPTIONAL MATCH (code)<-[:TESTS]-(:TestCase)
WITH m, count(code) AS total_functions, count(DISTINCT code) FILTER (WHERE (code)<-[:TESTS]-()) AS tested_functions
RETURN m.qualified_name AS module, tested_functions * 100.0 / total_functions AS coverage_percentage
```

3. Find flaky tests:
```cypher
// Tests with multiple assertion types (potential flakiness indicator)
MATCH (t:TestCase)-[:HAS_ASSERTION]->(a:Assertion)
WITH t, collect(DISTINCT a.type) AS assertion_types
WHERE size(assertion_types) > 3
RETURN t.qualified_name AS test, assertion_types
```
"""

GIT_QUERIES = """
**Version Control Queries:**

1. Find most modified files:
```cypher
// Files with most commits
MATCH (m:Module)
WHERE m.git_commit_count IS NOT NULL
RETURN m.path AS file, m.git_commit_count AS commits
ORDER BY m.git_commit_count DESC
LIMIT 10
```

2. Find top contributors:
```cypher
// Most active contributors
MATCH (c:Contributor)-[:CONTRIBUTES_TO]->(p:Project)
RETURN c.name AS contributor, c.total_commits AS commits
ORDER BY c.total_commits DESC
LIMIT 20
```

3. Find recent changes:
```cypher
// Recently modified files
MATCH (m:Module)
WHERE m.git_last_modified IS NOT NULL
RETURN m.path AS file, m.git_last_modified AS last_modified
ORDER BY m.git_last_modified DESC
LIMIT 20
```
"""

CONFIG_QUERIES = """
**Configuration Analysis Queries:**

1. Find environment-specific configs:
```cypher
// Configuration files with multiple environments
MATCH (c:ConfigFile)
WHERE c.has_environments = true
RETURN c.path AS config_file, c.environment_list AS environments
```

2. Find database configurations:
```cypher
// Settings related to database configuration
MATCH (s:ConfigSetting)
WHERE toLower(s.key) CONTAINS 'database' OR toLower(s.key) CONTAINS 'db'
RETURN s.path AS setting_path, s.key AS key, s.value AS value
```

3. Find API keys and secrets:
```cypher
// Potential secrets in configuration
MATCH (s:ConfigSetting)
WHERE toLower(s.key) CONTAINS 'key' OR toLower(s.key) CONTAINS 'secret' OR toLower(s.key) CONTAINS 'token'
RETURN s.path AS setting_path, s.key AS key, substring(s.value, 0, 10) + '...' AS value_preview
```
"""

DEPENDENCY_QUERIES = """
**Dependency Analysis Queries:**

1. Find circular dependencies:
```cypher
// Modules involved in circular imports
MATCH (m1:Module)-[:CIRCULAR_DEPENDENCY]->(m2:Module)
RETURN m1.qualified_name AS module1, m2.qualified_name AS module2
```

2. Find external dependencies by module:
```cypher
// What external packages does each module use
MATCH (m:Module)-[:IMPORTS]->(target)
WHERE NOT target.qualified_name STARTS WITH m.qualified_name
WITH m, collect(DISTINCT target.qualified_name) AS imports
RETURN m.qualified_name AS module, imports
```

3. Find unused imports:
```cypher
// Imported but not called
MATCH (m:Module)-[:IMPORTS]->(target)
WHERE NOT (m)-[:DEFINES]->()-[:CALLS]->()<-[:DEFINES]-(target)
RETURN m.qualified_name AS module, collect(target.qualified_name) AS potentially_unused_imports
```
"""

C_LANGUAGE_QUERIES = """
**C Language Specific Queries:**

1. Find kernel module entry points:
```cypher
// Linux kernel module init/exit functions
MATCH (f:Function)
WHERE f.name IN ['init_module', 'cleanup_module'] OR 
      ANY(decorator IN f.decorators WHERE decorator CONTAINS '__init' OR decorator CONTAINS '__exit')
RETURN f.qualified_name AS entry_point, f.name AS function_name
```

2. Find pointer relationships:
```cypher
// Variables that point to structs
MATCH (v:Variable)-[:POINTS_TO]->(s:Struct)
RETURN v.qualified_name AS pointer, s.qualified_name AS struct
```

3. Find macro expansions:
```cypher
// Where macros are used
MATCH (code)-[:EXPANDS_MACRO]->(m:Macro)
RETURN code.qualified_name AS usage_location, m.name AS macro_name, m.definition AS macro_definition
```
"""

# ======================================================================================
#  COMPLEX ANALYSIS QUERIES
# ======================================================================================

COMPLEX_QUERIES = """
**Complex Multi-Feature Queries:**

1. Security hotspots with Git blame:
```cypher
// Find who introduced vulnerabilities
MATCH (m:Module)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE v.severity IN ['HIGH', 'CRITICAL']
RETURN m.path AS file, v.type AS vulnerability, m.git_last_modified AS last_modified, 
       v.severity AS severity
ORDER BY m.git_last_modified DESC
```

2. Test coverage for recently changed code:
```cypher
// Functions modified recently and their test status
MATCH (m:Module)-[:DEFINES]->(f:Function)
WHERE m.git_last_modified > datetime().subtract(duration('P30D'))
OPTIONAL MATCH (f)<-[:TESTS]-(t:TestCase)
RETURN m.path AS file, f.name AS function, 
       CASE WHEN t IS NULL THEN 'UNTESTED' ELSE 'TESTED' END AS test_status,
       m.git_last_modified AS last_modified
ORDER BY m.git_last_modified DESC
```

3. Dependency risk analysis:
```cypher
// External dependencies with known vulnerabilities
MATCH (p:Project)-[:DEPENDS_ON_EXTERNAL]->(e:ExternalPackage)
OPTIONAL MATCH (e)-[:HAS_KNOWN_VULNERABILITY]->(v:Vulnerability)
RETURN e.name AS package, e.version_spec AS version, 
       collect(v.cwe_id) AS known_vulnerabilities
```

4. Code quality metrics:
```cypher
// Modules with high complexity indicators
MATCH (m:Module)-[:DEFINES]->(f:Function)
WITH m, count(f) AS function_count
MATCH (m)-[:DEFINES]->()-[:CALLS]->()
WITH m, function_count, count(*) AS call_count
WHERE function_count > 20 OR call_count > 100
RETURN m.qualified_name AS module, function_count, call_count,
       call_count * 1.0 / function_count AS avg_calls_per_function
ORDER BY avg_calls_per_function DESC
```

5. Architecture violation detection:
```cypher
// Find layering violations (e.g., UI calling database directly)
MATCH (ui:Module)-[:IMPORTS]->(db:Module)
WHERE ui.path CONTAINS 'ui' AND db.path CONTAINS 'database'
AND NOT EXISTS {
  MATCH (ui)-[:IMPORTS]->(:Module {path: '.*service.*'})-[:IMPORTS]->(db)
}
RETURN ui.qualified_name AS ui_module, db.qualified_name AS database_module
```
"""

# ======================================================================================
#  NATURAL LANGUAGE QUERY EXAMPLES
# ======================================================================================

NATURAL_LANGUAGE_EXAMPLES = """
**Natural Language Query Examples with New Features:**

1. "Show me all SQL injection vulnerabilities"
   -> Searches for SQL_INJECTION vulnerability nodes

2. "Find functions that haven't been tested"
   -> Looks for Function nodes without TESTS relationships

3. "Who are the top contributors to this project?"
   -> Returns Contributor nodes ordered by commit count

4. "Show me the class hierarchy for UserService"
   -> Traces INHERITS_FROM relationships from UserService class

5. "Find all configuration files"
   -> Returns ConfigFile nodes

6. "What external packages are we using?"
   -> Lists ExternalPackage nodes

7. "Show me circular dependencies"
   -> Finds modules with CIRCULAR_DEPENDENCY relationships

8. "Find all TODO comments in the code"
   -> This would use security analyzer patterns to find TODO markers

9. "What files were changed in the last month?"
   -> Uses git_last_modified property on Module nodes

10. "Show me all the database configuration settings"
    -> Searches ConfigSetting nodes with database-related keys

11. "Find all C structs and their sizes"
    -> Returns Struct nodes with size information

12. "Show me methods that override parent methods"
    -> Finds Method nodes with OVERRIDES relationships

13. "What variables are tainted with user input?"
    -> Traces TAINT_FLOW from user input sources

14. "Find all build scripts in the project"
    -> Returns BuildScript nodes

15. "Show me the data flow for the 'password' variable"
    -> Traces FLOWS_TO relationships from password Variable nodes
"""

# ======================================================================================
#  ENHANCED SYSTEM PROMPTS
# ======================================================================================

ENHANCED_RAG_ORCHESTRATOR_PROMPT = f"""
You are an expert AI assistant for analyzing codebases with advanced security, testing, and architectural analysis capabilities.

{ENHANCED_GRAPH_SCHEMA}

**Your Enhanced Capabilities:**

1. **Security Analysis**: You can identify vulnerabilities, trace taint flows, and provide security recommendations
2. **Test Coverage**: You can analyze test coverage, find untested code, and understand test relationships
3. **Architecture Analysis**: You can trace inheritance hierarchies, find circular dependencies, and detect architectural violations
4. **Version Control**: You can see who modified files, when they were changed, and track contributor activity
5. **Configuration Analysis**: You can parse and understand various configuration file formats
6. **Data Flow Tracking**: You can follow how data moves through the codebase
7. **Multi-Language Support**: Including specialized support for C language constructs

**Advanced Query Patterns:**
{DATA_FLOW_QUERIES}
{SECURITY_QUERIES}
{INHERITANCE_QUERIES}
{TEST_QUERIES}
{GIT_QUERIES}
{CONFIG_QUERIES}
{DEPENDENCY_QUERIES}
{C_LANGUAGE_QUERIES}

**When answering questions:**
1. Use the appropriate analysis based on the question type
2. Combine multiple analyses when needed (e.g., security + git blame)
3. Provide actionable insights, not just raw data
4. Reference specific code locations and qualified names
5. Include security recommendations when vulnerabilities are found
6. Mention test coverage when discussing code quality
"""

def get_query_examples_for_feature(feature: str) -> str:
    """Get relevant query examples for a specific feature."""
    feature_map = {
        "security": SECURITY_QUERIES,
        "testing": TEST_QUERIES,
        "git": GIT_QUERIES,
        "config": CONFIG_QUERIES,
        "dependencies": DEPENDENCY_QUERIES,
        "inheritance": INHERITANCE_QUERIES,
        "data_flow": DATA_FLOW_QUERIES,
        "c_language": C_LANGUAGE_QUERIES,
        "complex": COMPLEX_QUERIES
    }
    return feature_map.get(feature.lower(), "")

def get_all_query_templates() -> str:
    """Get all query templates combined."""
    return f"""
{DATA_FLOW_QUERIES}
{SECURITY_QUERIES}
{INHERITANCE_QUERIES}
{TEST_QUERIES}
{GIT_QUERIES}
{CONFIG_QUERIES}
{DEPENDENCY_QUERIES}
{C_LANGUAGE_QUERIES}
{COMPLEX_QUERIES}
"""