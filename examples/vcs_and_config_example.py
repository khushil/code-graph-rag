#!/usr/bin/env python3
"""
Example demonstrating VCS (Git) and Configuration analysis features.

This example shows how to:
1. Analyze Git repository history
2. Parse configuration files
3. Build and query the graph with VCS and config data
4. Generate reports on contributors and configurations
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codebase_rag.analysis.config import ConfigAnalyzer
from codebase_rag.analysis.vcs import VCSAnalyzer

console = Console()


def analyze_git_history(repo_path: str, days_back: int = 30) -> dict[str, Any]:
    """Analyze Git history for the repository."""
    console.print(
        Panel(
            f"[bold cyan]Analyzing Git History[/bold cyan]\nRepository: {repo_path}",
            style="cyan",
        )
    )

    try:
        vcs = VCSAnalyzer(repo_path)

        # Analyze repository with time filter
        since = datetime.now(tz=UTC) - timedelta(days=days_back)
        commits, authors = vcs.analyze_repository(
            branch="HEAD", since=since, max_commits=100
        )

        console.print(
            f"\nFound [green]{len(commits)}[/green] commits and [blue]{len(authors)}[/blue] authors in the last {days_back} days"
        )

        # Show top contributors
        table = Table(title="Top Contributors")
        table.add_column("Author", style="cyan")
        table.add_column("Email", style="yellow")
        table.add_column("Commits", style="green")
        table.add_column("Lines Added", style="blue")
        table.add_column("Lines Removed", style="red")

        # Sort by commit count
        sorted_authors = sorted(authors, key=lambda a: a.commit_count, reverse=True)[
            :10
        ]

        for author in sorted_authors:
            table.add_row(
                author.name,
                author.email,
                str(author.commit_count),
                str(author.lines_added),
                str(author.lines_removed),
            )

        console.print(table)

        # Show recent commits
        console.print("\n[bold]Recent Commits:[/bold]")
        for commit in commits[:5]:
            console.print(
                f"  • {commit.commit_hash[:8]} - {commit.message[:60]}... by {commit.author_name}"
            )

        # Build graph nodes and relationships
        nodes, relationships = vcs.build_vcs_graph(commits, authors)
        console.print(
            f"\nCreated [green]{len(nodes)}[/green] VCS nodes and [blue]{len(relationships)}[/blue] relationships"
        )

    except Exception as e:
        console.print(f"[red]Error analyzing Git history: {e}[/red]")
        return [], []
    else:
        return nodes, relationships


def analyze_configurations(repo_path: str) -> dict[str, Any]:
    """Analyze configuration files in the repository."""
    console.print(
        Panel("[bold cyan]Analyzing Configuration Files[/bold cyan]", style="cyan")
    )

    config_analyzer = ConfigAnalyzer()
    config_files = []

    # Find and analyze config files
    repo = Path(repo_path)
    config_patterns = [
        "**/*.yaml",
        "**/*.yml",
        "**/*.json",
        "**/Makefile",
        "**/*.mk",
        "**/.env",
        "**/*.env",
        "**/*.ini",
        "**/*.cfg",
        "**/Kconfig*",
    ]

    for pattern in config_patterns:
        for file_path in repo.glob(pattern):
            # Skip hidden directories and node_modules
            if any(part.startswith(".") and part != ".env" for part in file_path.parts):
                continue
            if "node_modules" in file_path.parts:
                continue

            config = config_analyzer.analyze_config_file(str(file_path))
            if config:
                config_files.append(config)

    console.print(f"Found [green]{len(config_files)}[/green] configuration files")

    # Show configuration summary
    table = Table(title="Configuration Files")
    table.add_column("File", style="cyan")
    table.add_column("Format", style="yellow")
    table.add_column("Values", style="green")
    table.add_column("Sections", style="blue")

    for config in config_files[:10]:  # Show first 10
        table.add_row(
            str(Path(config.file_path).relative_to(repo_path)),
            config.format,
            str(len(config.values)),
            str(len(config.sections)),
        )

    console.print(table)

    # Generate report
    report = config_analyzer.generate_config_report(config_files)

    console.print("\n[bold]Configuration Analysis:[/bold]")
    console.print(f"  • Total config files: {report['total_config_files']}")
    console.print(f"  • Total config values: {report['total_config_values']}")
    console.print(f"  • Format distribution: {report['format_distribution']}")

    if report["common_patterns"]:
        console.print("\n[bold]Common Configuration Patterns:[/bold]")
        for pattern, count in list(report["common_patterns"].items())[:5]:
            console.print(f"  • {pattern}: {count} occurrences")

    # Build graph nodes and relationships
    nodes, relationships = config_analyzer.build_config_graph(config_files)
    console.print(
        f"\nCreated [green]{len(nodes)}[/green] config nodes and [blue]{len(relationships)}[/blue] relationships"
    )

    return nodes, relationships


def query_examples(repo_path: str) -> None:  # noqa: ARG001
    """Show example queries for VCS and configuration data."""
    console.print(Panel("[bold cyan]Example Queries[/bold cyan]", style="cyan"))

    queries = [
        (
            "Find top contributors",
            "MATCH (a:Author) RETURN a.name AS name, a.total_commits AS commits ORDER BY commits DESC LIMIT 5",
        ),
        (
            "Show recent commits",
            "MATCH (c:Commit) RETURN c.hash AS hash, c.message AS message, c.date AS date ORDER BY c.date DESC LIMIT 10",
        ),
        (
            "Find who modified a specific file",
            "MATCH (f:File {path: 'README.md'})<-[:MODIFIED_IN]-(c:Commit)-[:AUTHORED_BY]->(a:Author) RETURN DISTINCT a.name AS author",
        ),
        (
            "Show configuration files",
            "MATCH (c:ConfigFile) RETURN c.file_path AS path, c.format AS format, c.value_count AS values",
        ),
        (
            "Find database configurations",
            "MATCH (c:ConfigFile)-[:DEFINES_SETTING]->(s:ConfigSetting) WHERE toLower(s.key) CONTAINS 'database' RETURN s.key AS key, s.value AS value, c.file_path AS file",
        ),
        (
            "Show files changed by a specific author",
            "MATCH (a:Author {name: 'John Doe'})<-[:AUTHORED_BY]-(c:Commit)-[:MODIFIED_IN|ADDED_IN]->(f:File) RETURN DISTINCT f.path AS file",
        ),
        (
            "Find configuration dependencies",
            "MATCH (c1:ConfigFile)-[:INCLUDES_CONFIG]->(c2:ConfigFile) RETURN c1.file_path AS source, c2.file_path AS included",
        ),
    ]

    console.print("\n[bold]Example Cypher Queries:[/bold]")
    for desc, query in queries:
        console.print(f"\n[yellow]{desc}:[/yellow]")
        console.print(f"[dim]{query}[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VCS and Configuration Analysis Example"
    )
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back in Git history (default: 30)",
    )
    parser.add_argument(
        "--update-graph",
        action="store_true",
        help="Update the graph database with VCS and config data",
    )
    parser.add_argument(
        "--show-queries", action="store_true", help="Show example queries"
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        console.print(f"[red]Error: Repository path does not exist: {repo_path}[/red]")
        return 1

    # Analyze Git history
    vcs_nodes, vcs_relationships = analyze_git_history(str(repo_path), args.days)

    console.print("\n" + "=" * 80 + "\n")

    # Analyze configurations
    config_nodes, config_relationships = analyze_configurations(str(repo_path))

    # Update graph if requested
    if args.update_graph:
        console.print("\n" + "=" * 80 + "\n")
        console.print(
            Panel("[bold cyan]Updating Graph Database[/bold cyan]", style="cyan")
        )

        try:
            from pymgclient import MemgraphConnection  # noqa: PLC0415

            # Connect to Memgraph
            MemgraphConnection(host="localhost", port=7687)

            # Create nodes and relationships
            # Note: In a real implementation, this would be integrated with GraphUpdater
            console.print(
                "[yellow]Note: Full graph integration requires running the main ingestion pipeline[/yellow]"
            )
            console.print("This example demonstrates the analysis capabilities.")

        except Exception as e:
            console.print(f"[red]Error updating graph: {e}[/red]")
            console.print(
                "[yellow]Make sure Memgraph is running (docker-compose up -d)[/yellow]"
            )

    # Show example queries
    if args.show_queries:
        console.print("\n" + "=" * 80 + "\n")
        query_examples(str(repo_path))

    console.print("\n[green]Analysis complete![/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
