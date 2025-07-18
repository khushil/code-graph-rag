#!/usr/bin/env python3
"""
MCP Server Demo - Shows how AI agents can use Graph-Code RAG

This example demonstrates the MCP server capabilities for AI agents
to analyze codebases and make intelligent recommendations.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def simulate_ai_agent_workflow():
    """Simulate an AI agent using the MCP server to analyze a codebase."""

    console.print(
        Panel(
            "[bold cyan]AI Agent: Code Quality Analyzer[/bold cyan]\n"
            "This demo simulates an AI agent using the Graph-Code RAG MCP server",
            style="cyan",
        )
    )

    # Simulated MCP responses (in production, these would come from the actual server)

    # Step 1: Load repository
    console.print("\n[yellow]AI Agent:[/yellow] Loading repository for analysis...")
    repo_result = {
        "status": "success",
        "repo_path": "/home/user/my-project",
        "nodes": 1247,
        "relationships": 3891,
    }
    console.print(
        f"✓ Loaded {repo_result['nodes']} nodes and {repo_result['relationships']} relationships"
    )

    # Step 2: Analyze security
    console.print(
        "\n[yellow]AI Agent:[/yellow] Checking for security vulnerabilities..."
    )
    security_result = {
        "total_vulnerabilities": 5,
        "by_severity": {"critical": 1, "high": 2, "medium": 2, "low": 0},
        "vulnerabilities": [
            {
                "type": "SQL_INJECTION",
                "severity": "CRITICAL",
                "file": "api/database.py",
                "line": 45,
                "message": "User input directly concatenated into SQL query",
            },
            {
                "type": "HARDCODED_SECRET",
                "severity": "HIGH",
                "file": "config/settings.py",
                "line": 12,
                "message": "API key hardcoded in source",
            },
        ],
    }

    # Display security issues
    if security_result["total_vulnerabilities"] > 0:
        table = Table(title="Security Vulnerabilities Found")
        table.add_column("Severity", style="red")
        table.add_column("Type", style="yellow")
        table.add_column("Location", style="cyan")

        for vuln in security_result["vulnerabilities"][:3]:
            table.add_row(
                vuln["severity"], vuln["type"], f"{vuln['file']}:{vuln['line']}"
            )
        console.print(table)

    # Step 3: Check test coverage
    console.print("\n[yellow]AI Agent:[/yellow] Analyzing test coverage...")
    coverage_result = {
        "overall_coverage": 62.5,
        "untested_functions": 47,
        "test_statistics": {"total_tests": 234, "total_assertions": 891},
        "untested_samples": [
            {"name": "process_payment", "file": "api/payment.py", "complexity": 15},
            {"name": "validate_user", "file": "auth/validator.py", "complexity": 12},
            {
                "name": "send_notification",
                "file": "services/notify.py",
                "complexity": 8,
            },
        ],
    }

    console.print(
        f"📊 Overall test coverage: [yellow]{coverage_result['overall_coverage']}%[/yellow]"
    )
    console.print(
        f"⚠️  Untested functions: [red]{coverage_result['untested_functions']}[/red]"
    )

    # Step 4: Get code metrics
    console.print("\n[yellow]AI Agent:[/yellow] Calculating code quality metrics...")
    _ = {
        "summary": {
            "total_files": 156,
            "total_functions": 892,
            "total_classes": 124,
            "total_lines": 28450,
        },
        "complexity": {"high_complexity_functions": 23, "average_complexity": 4.7},
        "dependencies": {"external": 42, "circular": 3},
    }

    # Step 5: Query for specific patterns
    console.print(
        "\n[yellow]AI Agent:[/yellow] Looking for code improvement opportunities..."
    )
    _ = {
        "pattern": "functions without error handling",
        "matches": 31,
        "samples": [
            {
                "function": "fetch_data",
                "file": "api/client.py",
                "issue": "No try-except block",
            },
            {
                "function": "save_config",
                "file": "utils/config.py",
                "issue": "No error handling for file operations",
            },
        ],
    }

    # Generate AI recommendations
    console.print("\n" + "=" * 60)
    console.print(
        Panel("[bold green]AI Agent Recommendations[/bold green]", style="green")
    )

    recommendations = [
        {
            "priority": "CRITICAL",
            "category": "Security",
            "action": "Fix SQL injection vulnerability in api/database.py:45",
            "impact": "Prevents potential data breach and unauthorized access",
        },
        {
            "priority": "HIGH",
            "category": "Security",
            "action": "Move hardcoded API key to environment variables",
            "impact": "Protects sensitive credentials from exposure",
        },
        {
            "priority": "HIGH",
            "category": "Testing",
            "action": "Add tests for payment processing functions",
            "impact": "Critical business logic needs test coverage",
        },
        {
            "priority": "MEDIUM",
            "category": "Code Quality",
            "action": "Refactor high-complexity functions (23 found)",
            "impact": "Improves maintainability and reduces bug risk",
        },
        {
            "priority": "MEDIUM",
            "category": "Architecture",
            "action": "Resolve 3 circular dependencies",
            "impact": "Improves code organization and testability",
        },
    ]

    for i, rec in enumerate(recommendations, 1):
        color = {"CRITICAL": "red", "HIGH": "yellow", "MEDIUM": "cyan"}[rec["priority"]]
        console.print(
            f"\n{i}. [{color}]{rec['priority']}[/{color}] - {rec['category']}"
        )
        console.print(f"   Action: {rec['action']}")
        console.print(f"   Impact: {rec['impact']}")

    # Summary
    console.print("\n" + "=" * 60)
    health_score = 68  # Calculated based on all metrics
    health_color = (
        "red" if health_score < 60 else "yellow" if health_score < 80 else "green"
    )

    console.print(
        f"\n[bold]Overall Code Health Score: [{health_color}]{health_score}/100[/{health_color}][/bold]"
    )
    console.print(
        "\n[dim]This analysis was performed by an AI agent using the Graph-Code RAG MCP server.[/dim]"
    )


async def demonstrate_mcp_tools():
    """Demonstrate available MCP tools."""
    console.print("\n" + "=" * 60)
    console.print(
        Panel(
            "[bold magenta]Available MCP Tools for AI Agents[/bold magenta]",
            style="magenta",
        )
    )

    tools = [
        {
            "name": "load_repository",
            "description": "Load and analyze a codebase",
            "example": {"repo_path": "/path/to/repo", "parallel": True},
        },
        {
            "name": "query_graph",
            "description": "Query code structure using natural language",
            "example": {"query": "Find all API endpoints", "limit": 50},
        },
        {
            "name": "analyze_security",
            "description": "Detect security vulnerabilities",
            "example": {"severity_filter": "high"},
        },
        {
            "name": "analyze_test_coverage",
            "description": "Find untested code",
            "example": {"include_bdd": True},
        },
        {
            "name": "get_code_metrics",
            "description": "Calculate quality metrics",
            "example": {"metric_types": ["complexity", "loc", "dependencies"]},
        },
        {
            "name": "analyze_git_history",
            "description": "Analyze contribution patterns",
            "example": {"since_days": 30, "top_contributors": 10},
        },
    ]

    for tool in tools:
        console.print(f"\n[cyan]Tool:[/cyan] {tool['name']}")
        console.print(f"[dim]{tool['description']}[/dim]")
        console.print(f"Example: {json.dumps(tool['example'], indent=2)}")


def main():
    """Run the MCP demo."""
    console.print(
        Panel(
            "[bold cyan]Graph-Code RAG MCP Server Demo[/bold cyan]\n"
            "Demonstrating AI agent capabilities for code analysis",
            style="cyan",
        )
    )

    # Run the simulated workflow
    asyncio.run(simulate_ai_agent_workflow())

    # Show available tools
    asyncio.run(demonstrate_mcp_tools())

    console.print("\n[green]To use the actual MCP server:[/green]")
    console.print("1. Start Memgraph: docker-compose up -d")
    console.print("2. Run MCP server: python -m mcp_server.server")
    console.print("3. Configure your AI agent to connect to the server")
    console.print("\nSee mcp_server/README.md for detailed documentation.")


if __name__ == "__main__":
    main()
