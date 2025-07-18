#!/usr/bin/env python3
"""
Comprehensive example demonstrating all Graph-Code RAG features working together.

This example shows:
1. Multi-language parsing with C support
2. Security vulnerability detection
3. Test coverage analysis
4. Git history integration
5. Configuration parsing
6. Data flow tracking
7. Query generation and execution
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from codebase_rag.graph_loader import load_graph
from codebase_rag.main import parse_and_store_codebase

console = Console()


def display_codebase_overview(graph_data: dict[str, Any]) -> None:
    """Display an overview of the analyzed codebase."""
    console.print(Panel("[bold cyan]Codebase Overview[/bold cyan]", style="cyan"))

    # Count nodes by type
    node_counts = {}
    for node in graph_data.get("nodes", []):
        label = node["label"]
        node_counts[label] = node_counts.get(label, 0) + 1

    # Create overview table
    table = Table(title="Graph Statistics")
    table.add_column("Node Type", style="cyan")
    table.add_column("Count", style="green")

    # Sort by count
    for node_type, count in sorted(
        node_counts.items(), key=lambda x: x[1], reverse=True
    ):
        table.add_row(node_type, str(count))

    console.print(table)

    # Show relationship counts
    rel_counts = {}
    for rel in graph_data.get("relationships", []):
        rel_type = rel["rel_type"]
        rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1

    console.print(
        f"\nTotal Relationships: [blue]{len(graph_data.get('relationships', []))}[/blue]"
    )
    console.print("Top relationship types:")
    for rel_type, count in sorted(rel_counts.items(), key=lambda x: x[1], reverse=True)[
        :5
    ]:
        console.print(f"  • {rel_type}: {count}")


def analyze_language_features(graph_data: dict[str, Any]) -> None:
    """Analyze language-specific features."""
    console.print(Panel("[bold green]Language Analysis[/bold green]", style="green"))

    # Group files by extension
    extensions = {}
    for node in graph_data.get("nodes", []):
        if node["label"] == "File":
            ext = node["properties"].get("extension", "unknown")
            extensions[ext] = extensions.get(ext, 0) + 1

    # Language distribution
    table = Table(title="Language Distribution")
    table.add_column("Extension", style="cyan")
    table.add_column("Files", style="green")

    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
        table.add_row(ext, str(count))

    console.print(table)

    # C-specific analysis
    c_nodes = {"Struct": [], "Macro": [], "FunctionPointer": [], "Typedef": []}

    for node in graph_data.get("nodes", []):
        if node["label"] in c_nodes:
            c_nodes[node["label"]].append(node)

    if any(c_nodes.values()):
        console.print("\n[bold]C Language Features:[/bold]")
        for node_type, nodes in c_nodes.items():
            if nodes:
                console.print(f"  • {node_type}: {len(nodes)}")
                # Show examples
                for node in nodes[:3]:
                    name = node["properties"].get("name", "unnamed")
                    console.print(f"    - {name}")


def analyze_security_findings(graph_data: dict[str, Any]) -> None:
    """Analyze security vulnerabilities in the graph."""
    console.print(Panel("[bold red]Security Analysis[/bold red]", style="red"))

    vulnerabilities = []
    vulnerable_nodes = []

    for node in graph_data.get("nodes", []):
        if node["label"] == "Vulnerability":
            vulnerabilities.append(node)

    # Find nodes with vulnerabilities
    for rel in graph_data.get("relationships", []):
        if rel["rel_type"] == "HAS_VULNERABILITY":
            vulnerable_nodes.append(rel["start_key"])

    console.print(
        f"Found [red]{len(vulnerabilities)}[/red] vulnerabilities affecting [yellow]{len(set(vulnerable_nodes))}[/yellow] code elements"
    )

    if vulnerabilities:
        # Group by severity
        by_severity = {}
        for vuln in vulnerabilities:
            severity = vuln["properties"].get("severity", "UNKNOWN")
            by_severity[severity] = by_severity.get(severity, 0) + 1

        table = Table(title="Vulnerabilities by Severity")
        table.add_column("Severity", style="bold")
        table.add_column("Count", style="red")

        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if severity in by_severity:
                table.add_row(severity, str(by_severity[severity]))

        console.print(table)

        # Show critical vulnerabilities
        critical = [
            v for v in vulnerabilities if v["properties"].get("severity") == "CRITICAL"
        ]
        if critical:
            console.print("\n[bold red]Critical Vulnerabilities:[/bold red]")
            for vuln in critical[:5]:
                vuln_type = vuln["properties"].get("type", "Unknown")
                desc = vuln["properties"].get("description", "No description")
                console.print(f"  • {vuln_type}: {desc}")


def analyze_test_coverage(graph_data: dict[str, Any]) -> None:
    """Analyze test coverage from the graph."""
    console.print(
        Panel("[bold green]Test Coverage Analysis[/bold green]", style="green")
    )

    # Count test-related nodes
    test_suites = []
    test_cases = []
    tested_functions = set()
    all_functions = []

    for node in graph_data.get("nodes", []):
        if node["label"] == "TestSuite":
            test_suites.append(node)
        elif node["label"] == "TestCase":
            test_cases.append(node)
        elif node["label"] in ["Function", "Method"]:
            all_functions.append(node)

    # Find tested functions
    for rel in graph_data.get("relationships", []):
        if rel["rel_type"] == "TESTS":
            tested_functions.add(rel["end_key"])

    coverage = len(tested_functions) / len(all_functions) * 100 if all_functions else 0

    console.print(f"Test Suites: [green]{len(test_suites)}[/green]")
    console.print(f"Test Cases: [blue]{len(test_cases)}[/blue]")
    console.print(f"Functions/Methods: [yellow]{len(all_functions)}[/yellow]")
    console.print(f"Tested Functions: [green]{len(tested_functions)}[/green]")
    console.print(
        f"Coverage: [{'green' if coverage > 80 else 'yellow' if coverage > 60 else 'red'}]{coverage:.1f}%[/]"
    )

    # Find untested critical functions
    untested = []
    for func in all_functions:
        func_id = (
            f"{func['properties'].get('qualified_name', '')}:{func.get('node_id', '')}"
        )
        if func_id not in tested_functions:
            # Check if it has vulnerabilities
            has_vuln = False
            for rel in graph_data.get("relationships", []):
                if (
                    rel["rel_type"] == "HAS_VULNERABILITY"
                    and rel["start_key"] == func_id
                ):
                    has_vuln = True
                    break
            if has_vuln:
                untested.append(func)

    if untested:
        console.print(
            f"\n[bold red]⚠️  {len(untested)} vulnerable functions lack tests![/bold red]"
        )


def analyze_git_integration(graph_data: dict[str, Any]) -> None:
    """Analyze Git history from the graph."""
    console.print(
        Panel("[bold magenta]Git History Analysis[/bold magenta]", style="magenta")
    )

    authors = []
    commits = []

    for node in graph_data.get("nodes", []):
        if node["label"] == "Author":
            authors.append(node)
        elif node["label"] == "Commit":
            commits.append(node)

    console.print(f"Contributors: [magenta]{len(authors)}[/magenta]")
    console.print(f"Total Commits: [blue]{len(commits)}[/blue]")

    if authors:
        # Top contributors
        top_authors = sorted(
            authors, key=lambda a: a["properties"].get("total_commits", 0), reverse=True
        )[:5]

        table = Table(title="Top Contributors")
        table.add_column("Name", style="cyan")
        table.add_column("Email", style="yellow")
        table.add_column("Commits", style="green")

        for author in top_authors:
            table.add_row(
                author["properties"].get("name", "Unknown"),
                author["properties"].get("email", ""),
                str(author["properties"].get("total_commits", 0)),
            )

        console.print(table)


def show_example_queries() -> None:
    """Show example queries for the analyzed codebase."""
    console.print(Panel("[bold yellow]Example Queries[/bold yellow]", style="yellow"))

    queries = [
        {
            "description": "Find all C structs larger than 1KB",
            "query": "MATCH (s:Struct) WHERE s.size > 1024 RETURN s.name AS struct_name, s.size AS size_bytes ORDER BY s.size DESC",
        },
        {
            "description": "Show untested functions with vulnerabilities",
            "query": """MATCH (f:Function|Method)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE NOT (f)<-[:TESTS]-(:TestCase)
RETURN f.qualified_name AS function, v.type AS vulnerability, v.severity AS severity""",
        },
        {
            "description": "Find who introduced security issues",
            "query": """MATCH (f:File)<-[:MODIFIED_IN]-(c:Commit)-[:AUTHORED_BY]->(a:Author)
WHERE EXISTS { (f)-[:CONTAINS]->()-[:HAS_VULNERABILITY]->() }
RETURN DISTINCT a.name AS author, count(DISTINCT f) AS vulnerable_files""",
        },
        {
            "description": "Show configuration files with database settings",
            "query": """MATCH (c:ConfigFile)-[:DEFINES_SETTING]->(s:ConfigSetting)
WHERE toLower(s.key) CONTAINS 'database' OR toLower(s.key) CONTAINS 'db'
RETURN c.file_path AS config_file, s.key AS setting, s.value AS value""",
        },
        {
            "description": "Trace data flow for sensitive variables",
            "query": """MATCH path = (v1:Variable)-[:FLOWS_TO*1..5]->(v2:Variable)
WHERE v1.name IN ['password', 'token', 'api_key', 'secret']
RETURN path""",
        },
    ]

    for i, query_info in enumerate(queries, 1):
        console.print(f"\n[yellow]{i}. {query_info['description']}:[/yellow]")
        syntax = Syntax(
            query_info["query"], "cypher", theme="monokai", line_numbers=False
        )
        console.print(syntax)


def create_analysis_report(graph_data: dict[str, Any], output_file: str) -> None:
    """Create a comprehensive analysis report."""
    report = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "summary": {
            "total_nodes": len(graph_data.get("nodes", [])),
            "total_relationships": len(graph_data.get("relationships", [])),
            "node_types": {},
            "relationship_types": {},
        },
        "languages": {},
        "security": {
            "total_vulnerabilities": 0,
            "by_severity": {},
            "vulnerable_files": [],
        },
        "testing": {"test_suites": 0, "test_cases": 0, "coverage_estimate": 0},
        "git": {"contributors": 0, "total_commits": 0, "top_contributors": []},
        "configuration": {"config_files": 0, "formats": {}},
    }

    # Populate report
    for node in graph_data.get("nodes", []):
        label = node["label"]
        report["summary"]["node_types"][label] = (
            report["summary"]["node_types"].get(label, 0) + 1
        )

        if label == "File":
            ext = node["properties"].get("extension", "unknown")
            report["languages"][ext] = report["languages"].get(ext, 0) + 1
        elif label == "Vulnerability":
            report["security"]["total_vulnerabilities"] += 1
            severity = node["properties"].get("severity", "UNKNOWN")
            report["security"]["by_severity"][severity] = (
                report["security"]["by_severity"].get(severity, 0) + 1
            )
        elif label == "TestSuite":
            report["testing"]["test_suites"] += 1
        elif label == "TestCase":
            report["testing"]["test_cases"] += 1
        elif label == "Author":
            report["git"]["contributors"] += 1
        elif label == "Commit":
            report["git"]["total_commits"] += 1
        elif label == "ConfigFile":
            report["configuration"]["config_files"] += 1
            fmt = node["properties"].get("format", "unknown")
            report["configuration"]["formats"][fmt] = (
                report["configuration"]["formats"].get(fmt, 0) + 1
            )

    # Save report
    with Path(output_file).open("w") as f:
        json.dump(report, f, indent=2)

    console.print(f"\n[green]Analysis report saved to: {output_file}[/green]")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comprehensive Graph-Code RAG Analysis"
    )
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    parser.add_argument("-o", "--output", help="Output file for graph export (JSON)")
    parser.add_argument("--report", help="Generate analysis report (JSON)")
    parser.add_argument(
        "--update-graph", action="store_true", help="Update the graph database"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Clean existing graph data"
    )
    parser.add_argument(
        "--parallel", action="store_true", help="Use parallel processing"
    )
    parser.add_argument("--workers", type=int, help="Number of worker processes")

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        console.print(f"[red]Error: Repository path does not exist: {repo_path}[/red]")
        return 1

    console.print(
        Panel(
            f"[bold cyan]Comprehensive Graph-Code RAG Analysis[/bold cyan]\n"
            f"Repository: {repo_path}\n"
            f"Features: All (C support, Security, Testing, Git, Config, Data Flow)",
            style="cyan",
        )
    )

    # Parse and update graph if requested
    if args.update_graph:
        console.print("\n[yellow]Parsing codebase and updating graph...[/yellow]")
        try:
            parse_and_store_codebase(
                str(repo_path),
                clean=args.clean,
                parallel=args.parallel,
                workers=args.workers,
            )
            console.print("[green]✓ Graph updated successfully[/green]")
        except Exception as e:
            console.print(f"[red]Error updating graph: {e}[/red]")
            return 1

    # Export or load graph data
    if True:  # Always analyze
        if args.output and Path(args.output).exists():
            console.print(
                f"\n[yellow]Loading existing graph from {args.output}...[/yellow]"
            )
            graph = load_graph(args.output)
            graph_data = {"nodes": graph.nodes, "relationships": graph.relationships}
        else:
            console.print("\n[yellow]Exporting graph data...[/yellow]")
            # This would normally export from Memgraph
            # For demo, we'll use empty data
            graph_data = {"nodes": [], "relationships": []}
            console.print(
                "[yellow]Note: Run with --update-graph to analyze actual repository[/yellow]"
            )

    # Perform comprehensive analysis
    console.print("\n" + "=" * 80 + "\n")
    display_codebase_overview(graph_data)

    console.print("\n" + "=" * 80 + "\n")
    analyze_language_features(graph_data)

    console.print("\n" + "=" * 80 + "\n")
    analyze_security_findings(graph_data)

    console.print("\n" + "=" * 80 + "\n")
    analyze_test_coverage(graph_data)

    console.print("\n" + "=" * 80 + "\n")
    analyze_git_integration(graph_data)

    console.print("\n" + "=" * 80 + "\n")
    show_example_queries()

    # Generate report if requested
    if args.report:
        create_analysis_report(graph_data, args.report)

    console.print("\n[green]✨ Comprehensive analysis complete![/green]")
    console.print(
        "\n[dim]Use the example queries above with the main codebase_rag tool to explore your codebase.[/dim]"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
