#!/usr/bin/env python3
"""
Example script demonstrating C language analysis and test framework integration.

This script shows:
1. How to analyze C codebases including kernel code
2. How to extract pointer relationships and function pointers
3. How to detect and link test cases to implementation
4. How to parse BDD feature files and link to code
"""

import argparse
import sys
from pathlib import Path

# Add the parent directory to Python path so we can import codebase_rag
sys.path.insert(0, str(Path(__file__).parent.parent))

from codebase_rag.services.graph_service import MemgraphIngestor
from loguru import logger


def analyze_c_code(ingestor: MemgraphIngestor):
    """Analyze C-specific features in the codebase."""
    print("\n🔧 Analyzing C Language Features")
    print("=" * 60)
    
    # Find all C functions
    query = """
    MATCH (f:Function)-[:DEFINED_IN]->(m:Module)
    WHERE m.path ENDS WITH '.c' OR m.path ENDS WITH '.h'
    RETURN f.qualified_name as name, f.start_line as line, m.path as file
    ORDER BY m.path, f.start_line
    LIMIT 10
    """
    
    print("\n📌 Sample C Functions:")
    results = list(ingestor.execute_query(query))
    for r in results:
        print(f"   • {r['name']} at {r['file']}:{r['line']}")
    
    # Find pointer relationships
    query = """
    MATCH (p:Pointer)-[r:POINTS_TO]->(target)
    RETURN p.qualified_name as pointer, type(r) as rel, 
           labels(target)[0] as target_type, target.name as target_name
    LIMIT 10
    """
    
    print("\n🎯 Pointer Relationships:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['pointer']} -> {r['target_type']}:{r['target_name']}")
    else:
        print("   (No pointer relationships found)")
    
    # Find function pointers
    query = """
    MATCH (fp:Pointer)-[r:ASSIGNS_FP|INVOKES_FP]->(f:Function)
    RETURN fp.qualified_name as func_ptr, type(r) as rel_type, 
           f.qualified_name as function
    LIMIT 10
    """
    
    print("\n📞 Function Pointer Usage:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['func_ptr']} {r['rel_type']} {r['function']}")
    else:
        print("   (No function pointers found)")
    
    # Find kernel-specific patterns
    query = """
    MATCH (n)
    WHERE n:Syscall OR n:KernelExport OR (n:Function AND n.lock_count > 0)
    RETURN labels(n)[0] as type, n.qualified_name as name, 
           n.syscall_number as syscall_num, n.lock_count as locks
    LIMIT 10
    """
    
    print("\n🐧 Linux Kernel Patterns:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            if r['type'] == 'Syscall':
                print(f"   • SYSCALL: {r['name']} (nr: {r['syscall_num']})")
            elif r['type'] == 'KernelExport':
                print(f"   • EXPORT: {r['name']}")
            else:
                print(f"   • LOCKS: {r['name']} uses {r['locks']} locks")
    else:
        print("   (No kernel patterns found)")


def analyze_tests(ingestor: MemgraphIngestor):
    """Analyze test framework integration."""
    print("\n🧪 Analyzing Test Frameworks")
    print("=" * 60)
    
    # Find test suites by framework
    query = """
    MATCH (ts:TestSuite)
    RETURN ts.framework as framework, count(ts) as count
    ORDER BY count DESC
    """
    
    print("\n📊 Test Frameworks Found:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['framework']}: {r['count']} test suites")
    else:
        print("   (No test suites found)")
    
    # Find test cases
    query = """
    MATCH (tc:TestCase)-[:IN_SUITE]->(ts:TestSuite)
    RETURN ts.qualified_name as suite, tc.name as test, 
           tc.start_line as line
    ORDER BY ts.qualified_name, tc.start_line
    LIMIT 10
    """
    
    print("\n🔍 Sample Test Cases:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['suite']} :: {r['test']} (line {r['line']})")
    else:
        print("   (No test cases found)")
    
    # Find tests that test specific functions
    query = """
    MATCH (tc:TestCase)-[t:TESTS]->(f:Function)
    RETURN tc.name as test, f.qualified_name as function, 
           t.confidence as confidence
    ORDER BY t.confidence DESC
    LIMIT 10
    """
    
    print("\n🎯 Test Coverage Links:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            conf = r.get('confidence', 'N/A')
            print(f"   • {r['test']} tests {r['function']} (confidence: {conf})")
    else:
        print("   (No test coverage links found)")
    
    # Find assertions
    query = """
    MATCH (a:Assertion)-[:IN_TEST]->(tc:TestCase)
    RETURN tc.name as test, a.type as assert_type, 
           a.actual as actual, a.expected as expected
    LIMIT 10
    """
    
    print("\n✅ Sample Assertions:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            if r['expected']:
                print(f"   • {r['test']}: {r['assert_type']}({r['actual']}, {r['expected']})")
            else:
                print(f"   • {r['test']}: {r['assert_type']}({r['actual']})")
    else:
        print("   (No assertions found)")


def analyze_bdd(ingestor: MemgraphIngestor):
    """Analyze BDD/Gherkin features."""
    print("\n🥒 Analyzing BDD Features")
    print("=" * 60)
    
    # Find BDD features
    query = """
    MATCH (f:BDDFeature)
    RETURN f.name as feature, f.description as desc
    LIMIT 5
    """
    
    print("\n📋 BDD Features:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • Feature: {r['feature']}")
            if r['desc']:
                print(f"     {r['desc'][:60]}...")
    else:
        print("   (No BDD features found)")
    
    # Find scenarios
    query = """
    MATCH (s:BDDScenario)-[:IN_FEATURE]->(f:BDDFeature)
    RETURN f.name as feature, s.name as scenario, s.tags as tags
    LIMIT 10
    """
    
    print("\n🎬 BDD Scenarios:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            tags = ", ".join(r['tags']) if r['tags'] else "no tags"
            print(f"   • {r['feature']} :: {r['scenario']} [{tags}]")
    else:
        print("   (No BDD scenarios found)")
    
    # Find step implementations
    query = """
    MATCH (st:BDDStep)-[i:IMPLEMENTS_STEP]->(f:Function)
    RETURN st.keyword as keyword, st.text as step, 
           f.qualified_name as implementation
    LIMIT 10
    """
    
    print("\n🔗 Step Implementations:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['keyword']} {r['step']}")
            print(f"     → {r['implementation']}")
    else:
        print("   (No step implementations found)")


def generate_test_report(ingestor: MemgraphIngestor):
    """Generate a comprehensive test coverage report."""
    print("\n📈 Test Coverage Report")
    print("=" * 60)
    
    # Count functions with and without tests
    query = """
    MATCH (f:Function)
    OPTIONAL MATCH (tc:TestCase)-[:TESTS]->(f)
    WITH f, count(tc) as test_count
    RETURN 
        CASE WHEN test_count > 0 THEN 'tested' ELSE 'untested' END as status,
        count(f) as count
    """
    
    results = list(ingestor.execute_query(query))
    tested = untested = 0
    for r in results:
        if r['status'] == 'tested':
            tested = r['count']
        else:
            untested = r['count']
    
    total = tested + untested
    if total > 0:
        coverage = (tested / total) * 100
        print(f"\n📊 Function Coverage:")
        print(f"   • Total functions: {total:,}")
        print(f"   • Tested: {tested:,} ({coverage:.1f}%)")
        print(f"   • Untested: {untested:,} ({100-coverage:.1f}%)")
    
    # Functions with most tests
    query = """
    MATCH (tc:TestCase)-[:TESTS]->(f:Function)
    WITH f, count(tc) as test_count
    RETURN f.qualified_name as function, test_count
    ORDER BY test_count DESC
    LIMIT 5
    """
    
    print(f"\n🏆 Most Tested Functions:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['function']}: {r['test_count']} tests")
    else:
        print("   (No tested functions found)")
    
    # Complex untested functions
    query = """
    MATCH (f:Function)
    WHERE NOT EXISTS((tc:TestCase)-[:TESTS]->(f))
    AND (f.end_line - f.start_line) > 20
    RETURN f.qualified_name as function, 
           (f.end_line - f.start_line) as lines
    ORDER BY lines DESC
    LIMIT 5
    """
    
    print(f"\n⚠️  Large Untested Functions:")
    results = list(ingestor.execute_query(query))
    if results:
        for r in results:
            print(f"   • {r['function']}: {r['lines']} lines")
    else:
        print("   (All large functions have tests!)")


def main():
    """Main function to demonstrate C and test analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze C code and test frameworks in the codebase graph.",
        epilog="""
This script requires that you have already ingested a codebase with:
  python -m codebase_rag.main start --repo-path /path/to/repo --update-graph

Examples:
  # Analyze all features
  python examples/c_and_test_analysis_example.py

  # Analyze only C code
  python examples/c_and_test_analysis_example.py --c-only

  # Analyze only tests
  python examples/c_and_test_analysis_example.py --tests-only

  # Generate test report
  python examples/c_and_test_analysis_example.py --report
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    
    parser.add_argument(
        "--c-only",
        action="store_true",
        help="Analyze only C language features",
    )
    parser.add_argument(
        "--tests-only",
        action="store_true",
        help="Analyze only test frameworks",
    )
    parser.add_argument(
        "--bdd-only",
        action="store_true",
        help="Analyze only BDD features",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate test coverage report",
    )
    
    args = parser.parse_args()
    
    try:
        # Connect to Memgraph
        ingestor = MemgraphIngestor("localhost", 7687)
        
        # Check if graph has data
        result = list(ingestor.execute_query("MATCH (n) RETURN count(n) as count LIMIT 1"))
        if not result or result[0]['count'] == 0:
            print("❌ No data in graph. Please ingest a codebase first.", file=sys.stderr)
            print("   Run: python -m codebase_rag.main start --repo-path /path/to/repo --update-graph")
            sys.exit(1)
        
        # Run requested analyses
        if args.report:
            generate_test_report(ingestor)
        elif args.c_only:
            analyze_c_code(ingestor)
        elif args.tests_only:
            analyze_tests(ingestor)
        elif args.bdd_only:
            analyze_bdd(ingestor)
        else:
            # Run all analyses
            analyze_c_code(ingestor)
            analyze_tests(ingestor)
            analyze_bdd(ingestor)
            generate_test_report(ingestor)
        
        print("\n✅ Analysis complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        logger.exception("Analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()