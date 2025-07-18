#!/usr/bin/env python3
"""
Example demonstrating Security and Test Coverage analysis features.

This example shows how to:
1. Scan code for security vulnerabilities
2. Analyze test coverage
3. Track data flows
4. Find untested critical code
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from codebase_rag.analysis.security import SecurityAnalyzer
from codebase_rag.analysis.test_analyzer import TestAnalyzer

console = Console()


def analyze_security(repo_path: str, language: str = "python") -> dict[str, Any]:
    """Analyze security vulnerabilities in the codebase."""
    console.print(
        Panel(
            f"[bold red]Security Analysis[/bold red]\nLanguage: {language}", style="red"
        )
    )

    security = SecurityAnalyzer()
    vulnerabilities = []

    # Find source files
    extensions = {
        "python": ["*.py"],
        "javascript": ["*.js", "*.jsx"],
        "typescript": ["*.ts", "*.tsx"],
        "c": ["*.c", "*.h"],
        "cpp": ["*.cpp", "*.cc", "*.cxx", "*.hpp", "*.h"],
        "java": ["*.java"],
        "rust": ["*.rs"],
        "go": ["*.go"],
    }

    patterns = extensions.get(language, ["*.py"])
    repo = Path(repo_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning for vulnerabilities...", total=None)

        for pattern in patterns:
            for file_path in repo.rglob(pattern):
                # Skip test files and hidden directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue
                if "test" in file_path.name.lower():
                    continue

                try:
                    with Path(file_path).open(encoding="utf-8") as f:
                        content = f.read()

                    file_vulns = security.analyze_file(
                        str(file_path), content, language
                    )
                    vulnerabilities.extend(file_vulns)

                except Exception as e:
                    logger.warning(f"Error analyzing {file_path}: {e}")

    console.print(
        f"\nFound [red]{len(vulnerabilities)}[/red] potential vulnerabilities"
    )

    # Group by severity
    by_severity = defaultdict(list)
    for vuln in vulnerabilities:
        by_severity[vuln.severity].append(vuln)

    # Show vulnerability summary
    table = Table(title="Security Vulnerabilities by Severity")
    table.add_column("Severity", style="bold")
    table.add_column("Count", style="red")
    table.add_column("Types", style="yellow")

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        vulns = by_severity.get(severity, [])
        if vulns:
            types = {v.type for v in vulns}
            table.add_row(
                severity,
                str(len(vulns)),
                ", ".join(sorted(types)[:3]),  # Show first 3 types
            )

    console.print(table)

    # Show critical vulnerabilities
    critical = by_severity.get("CRITICAL", [])
    if critical:
        console.print("\n[bold red]Critical Vulnerabilities:[/bold red]")
        for vuln in critical[:5]:  # Show first 5
            console.print(
                f"  • {vuln.type} in {Path(vuln.file_path).name}:{vuln.line_number}"
            )
            console.print(f"    {vuln.description}")
            if vuln.recommendation:
                console.print(f"    [green]Fix:[/green] {vuln.recommendation}")

    return vulnerabilities


def analyze_test_coverage(repo_path: str, language: str = "python") -> dict[str, Any]:
    """Analyze test coverage and find untested code."""
    console.print(
        Panel(
            f"[bold green]Test Coverage Analysis[/bold green]\nLanguage: {language}",
            style="green",
        )
    )

    test_analyzer = TestAnalyzer()

    # Analyze test files and coverage
    repo = Path(repo_path)
    test_suites = []
    test_cases = []

    # Find test files based on language
    test_patterns = {
        "python": ["test_*.py", "*_test.py", "tests/*.py"],
        "javascript": ["*.test.js", "*.spec.js", "__tests__/*.js"],
        "typescript": ["*.test.ts", "*.spec.ts", "__tests__/*.ts"],
        "java": ["*Test.java", "*Tests.java"],
        "go": ["*_test.go"],
        "rust": ["tests/*.rs"],
        "c": ["test_*.c", "*_test.c"],
    }

    patterns = test_patterns.get(language, ["test_*.py"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Analyzing test files...", total=None)

        for pattern in patterns:
            for file_path in repo.rglob(pattern):
                try:
                    with Path(file_path).open(encoding="utf-8") as f:
                        content = f.read()

                    # Analyze based on language
                    if language == "python":
                        suites, cases = test_analyzer.analyze_python_tests(
                            str(file_path), content
                        )
                    elif language in ["javascript", "typescript"]:
                        suites, cases = test_analyzer.analyze_javascript_tests(
                            str(file_path), content
                        )
                    elif language == "c":
                        suites, cases = test_analyzer.analyze_c_tests(
                            str(file_path), content
                        )
                    else:
                        continue

                    test_suites.extend(suites)
                    test_cases.extend(cases)

                except Exception as e:
                    logger.warning(f"Error analyzing test file {file_path}: {e}")

    console.print(
        f"\nFound [green]{len(test_suites)}[/green] test suites with [blue]{len(test_cases)}[/blue] test cases"
    )

    # Show test summary
    table = Table(title="Test Coverage Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Test Suites", str(len(test_suites)))
    table.add_row("Total Test Cases", str(len(test_cases)))

    # Count by framework
    frameworks = defaultdict(int)
    for suite in test_suites:
        frameworks[suite.framework] += 1

    for framework, count in frameworks.items():
        table.add_row(f"{framework} Suites", str(count))

    console.print(table)

    # Show example test cases
    if test_cases:
        console.print("\n[bold]Sample Test Cases:[/bold]")
        for case in test_cases[:5]:
            console.print(f"  • {case.name} ({case.test_type})")

    return test_suites, test_cases


def analyze_data_flow(
    repo_path: str, variable_name: str | None = None
) -> dict[str, Any]:
    """Analyze data flow for security-sensitive variables."""
    console.print(Panel("[bold blue]Data Flow Analysis[/bold blue]", style="blue"))

    # data_flow = DataFlowAnalyzer()  # Not used in this example

    # Common sensitive variable patterns
    sensitive_patterns = [
        "password",
        "passwd",
        "pwd",
        "token",
        "api_key",
        "apikey",
        "secret",
        "private_key",
        "credit_card",
        "ssn",
        "email",
        "username",
    ]

    if variable_name:
        patterns = [variable_name]
    else:
        patterns = sensitive_patterns

    console.print(f"Analyzing data flow for: {', '.join(patterns[:5])}...")

    # This is a simplified example - real implementation would parse AST
    flows = []
    repo = Path(repo_path)

    for py_file in repo.rglob("*.py"):
        try:
            with Path(py_file).open(encoding="utf-8") as f:
                content = f.read()

            # Simple pattern matching for demonstration
            for pattern in patterns:
                if pattern.lower() in content.lower():
                    # Mock data flow edge
                    flows.append(
                        {
                            "pattern": pattern,
                            "file": str(py_file.relative_to(repo_path)),
                            "type": "assignment"
                            if f"{pattern} =" in content
                            else "usage",
                        }
                    )

        except Exception:
            continue

    console.print(f"\nFound [blue]{len(flows)}[/blue] data flow points")

    # Group by pattern
    by_pattern = defaultdict(list)
    for flow in flows:
        by_pattern[flow["pattern"]].append(flow)

    # Show summary
    table = Table(title="Sensitive Data Flow")
    table.add_column("Variable Pattern", style="cyan")
    table.add_column("Occurrences", style="yellow")
    table.add_column("Files", style="green")

    for pattern, pattern_flows in list(by_pattern.items())[:10]:
        files = {f["file"] for f in pattern_flows}
        table.add_row(pattern, str(len(pattern_flows)), str(len(files)))

    console.print(table)

    return flows


def find_untested_critical_code(
    vulnerabilities: list[dict[str, Any]], test_cases: list[dict[str, Any]]
) -> set[str]:
    """Find critical code with vulnerabilities that lacks tests."""
    console.print(
        Panel("[bold yellow]Untested Critical Code[/bold yellow]", style="yellow")
    )

    # Extract tested files from test cases
    tested_files = set()
    for case in test_cases:
        # Simple heuristic: test file tests corresponding source file
        test_file = Path(case.file_path).name
        if test_file.startswith("test_"):
            source_file = test_file[5:]
        elif test_file.endswith("_test.py"):
            source_file = test_file[:-8] + ".py"
        else:
            continue
        tested_files.add(source_file)

    # Find vulnerable files without tests
    untested_vulnerable = []
    for vuln in vulnerabilities:
        if vuln.severity in ["CRITICAL", "HIGH"]:
            file_name = Path(vuln.file_path).name
            if file_name not in tested_files:
                untested_vulnerable.append(vuln)

    console.print(
        f"\nFound [red]{len(untested_vulnerable)}[/red] high/critical vulnerabilities in untested code"
    )

    if untested_vulnerable:
        table = Table(title="Untested Vulnerable Code")
        table.add_column("File", style="red")
        table.add_column("Vulnerability", style="yellow")
        table.add_column("Severity", style="red")

        for vuln in untested_vulnerable[:10]:  # Show first 10
            table.add_row(Path(vuln.file_path).name, vuln.type, vuln.severity)

        console.print(table)

        console.print(
            "\n[bold red]⚠️  These files contain critical vulnerabilities but lack test coverage![/bold red]"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Security and Test Analysis Example")
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    parser.add_argument(
        "--language",
        default="python",
        choices=[
            "python",
            "javascript",
            "typescript",
            "c",
            "cpp",
            "java",
            "rust",
            "go",
        ],
        help="Programming language to analyze (default: python)",
    )
    parser.add_argument(
        "--variable", help="Specific variable name to track in data flow analysis"
    )
    parser.add_argument(
        "--skip-security", action="store_true", help="Skip security analysis"
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip test analysis")
    parser.add_argument(
        "--skip-dataflow", action="store_true", help="Skip data flow analysis"
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        console.print(f"[red]Error: Repository path does not exist: {repo_path}[/red]")
        return 1

    vulnerabilities = []
    test_suites = []
    test_cases = []

    # Run security analysis
    if not args.skip_security:
        vulnerabilities = analyze_security(str(repo_path), args.language)
        console.print("\n" + "=" * 80 + "\n")

    # Run test analysis
    if not args.skip_tests:
        test_suites, test_cases = analyze_test_coverage(str(repo_path), args.language)
        console.print("\n" + "=" * 80 + "\n")

    # Run data flow analysis
    if not args.skip_dataflow:
        analyze_data_flow(str(repo_path), args.variable)
        console.print("\n" + "=" * 80 + "\n")

    # Cross-reference security and tests
    if vulnerabilities and test_cases:
        find_untested_critical_code(vulnerabilities, test_cases)

    console.print("\n[green]Analysis complete![/green]")
    console.print("\n[dim]Note: This is a demonstration of the analysis capabilities.")
    console.print(
        "For full integration, use the main codebase_rag tool to build the graph.[/dim]"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
