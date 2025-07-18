#!/usr/bin/env python3
"""
Multi-Repository Analysis Example

This example demonstrates how to analyze multiple related repositories:
1. Ecosystem analysis
2. Cross-repository dependencies
3. Shared component detection
4. API contract validation
5. Security vulnerability propagation
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

console = Console()


class Repository:
    """Represents a single repository in the ecosystem."""

    def __init__(self, name: str, path: str, url: str | None = None):
        self.name = name
        self.path = Path(path)
        self.url = url
        self.metadata = {
            "languages": defaultdict(int),
            "dependencies": set(),
            "exports": set(),
            "imports": set(),
            "apis": [],
            "vulnerabilities": [],
        }

    def clone_or_update(self) -> bool:
        """Clone repository if it doesn't exist, or update if it does."""
        if self.path.exists():
            console.print(f"[yellow]Updating {self.name}...[/yellow]")
            try:
                subprocess.run(
                    ["git", "-C", str(self.path), "pull"],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                console.print(f"[red]Failed to update {self.name}[/red]")
                return False
            else:
                return True
        else:
            if not self.url:
                console.print(f"[red]No URL provided for {self.name}[/red]")
                return False

            console.print(f"[yellow]Cloning {self.name}...[/yellow]")
            try:
                subprocess.run(
                    ["git", "clone", self.url, str(self.path)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                console.print(f"[red]Failed to clone {self.name}[/red]")
                return False
            else:
                return True

    def analyze_languages(self) -> None:
        """Analyze language distribution in the repository."""
        for file_path in self.path.rglob("*"):
            if file_path.is_file() and file_path.suffix:
                self.metadata["languages"][file_path.suffix] += 1

    def analyze_dependencies(self) -> None:
        """Extract dependencies from various package files."""
        # Package.json for JavaScript/TypeScript
        package_json = self.path / "package.json"
        if package_json.exists():
            with package_json.open() as f:
                data = json.load(f)
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                self.metadata["dependencies"].update(deps.keys())
                self.metadata["dependencies"].update(dev_deps.keys())

        # Requirements.txt for Python
        requirements = self.path / "requirements.txt"
        if requirements.exists():
            with requirements.open() as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg = line.split("==")[0].split(">=")[0].split("~=")[0]
                        self.metadata["dependencies"].add(pkg)

        # Go.mod for Go
        go_mod = self.path / "go.mod"
        if go_mod.exists():
            with go_mod.open() as f:
                for line in f:
                    if line.strip().startswith("require"):
                        # Simple parsing, real implementation would be more robust
                        parts = line.split()
                        if len(parts) >= 2:
                            self.metadata["dependencies"].add(parts[1])

        # Cargo.toml for Rust
        cargo_toml = self.path / "Cargo.toml"
        if cargo_toml.exists():
            # Simple parsing for demonstration
            with cargo_toml.open() as f:
                in_deps = False
                for line in f:
                    if "[dependencies]" in line:
                        in_deps = True
                    elif line.startswith("[") and in_deps:
                        in_deps = False
                    elif in_deps and "=" in line:
                        dep = line.split("=")[0].strip()
                        self.metadata["dependencies"].add(dep)

    def analyze_apis(self) -> None:
        """Extract API endpoints from the repository."""
        # Look for common API patterns
        api_patterns = {
            "rest": [
                r"@app\.route\(.*\)",  # Flask
                r"@router\.(get|post|put|delete)\(.*\)",  # FastAPI
                r"app\.(get|post|put|delete)\(.*\)",  # Express.js
                r"@GetMapping|@PostMapping|@PutMapping|@DeleteMapping",  # Spring
            ],
            "graphql": [
                r"type Query",
                r"type Mutation",
                r"@Query\(",
                r"@Mutation\(",
            ],
            "grpc": [
                r"service \w+ \{",
                r"rpc \w+\(",
            ],
        }

        # Simplified API detection
        api_files = list(self.path.rglob("*api*")) + list(self.path.rglob("*route*"))
        for file in api_files[:10]:  # Limit for performance
            if file.suffix in [".py", ".js", ".ts", ".java", ".go"]:
                try:
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    # Simple endpoint extraction (real implementation would parse properly)
                    if "route" in content or "endpoint" in content:
                        self.metadata["apis"].append(
                            {
                                "file": str(file.relative_to(self.path)),
                                "type": "rest",  # Simplified
                            }
                        )
                except Exception:
                    pass


class EcosystemAnalyzer:
    """Analyzes multiple repositories as an ecosystem."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.repositories: list[Repository] = []
        self.cross_dependencies = defaultdict(set)
        self.shared_components = defaultdict(list)
        self.api_providers = defaultdict(list)
        self.api_consumers = defaultdict(list)

    def add_repository(
        self, name: str, url: str | None = None, path: str | None = None
    ) -> None:
        """Add a repository to the ecosystem."""
        repo_path = path or str(self.base_path / name)
        repo = Repository(name, repo_path, url)
        self.repositories.append(repo)

    def setup_repositories(self) -> None:
        """Clone or update all repositories."""
        console.print(
            Panel("[bold cyan]Setting up repositories[/bold cyan]", style="cyan")
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Setting up...", total=len(self.repositories))

            for repo in self.repositories:
                repo.clone_or_update()
                progress.update(task, advance=1)

    def analyze_ecosystem(self) -> None:
        """Analyze all repositories in the ecosystem."""
        console.print(
            Panel("[bold green]Analyzing ecosystem[/bold green]", style="green")
        )

        # Analyze individual repositories
        for repo in self.repositories:
            console.print(f"\n[cyan]Analyzing {repo.name}...[/cyan]")
            repo.analyze_languages()
            repo.analyze_dependencies()
            repo.analyze_apis()

        # Analyze cross-repository relationships
        self._analyze_cross_dependencies()
        self._find_shared_components()
        self._analyze_api_contracts()

    def _analyze_cross_dependencies(self) -> None:
        """Find dependencies between repositories."""
        console.print("\n[yellow]Analyzing cross-repository dependencies...[/yellow]")

        # Build a map of which repo provides which packages
        package_providers = {}
        for repo in self.repositories:
            # Simple heuristic: repo name might be in package.json
            package_json = repo.path / "package.json"
            if package_json.exists():
                with package_json.open() as f:
                    data = json.load(f)
                    pkg_name = data.get("name", "")
                    if pkg_name:
                        package_providers[pkg_name] = repo.name

        # Find cross-dependencies
        for repo in self.repositories:
            for dep in repo.metadata["dependencies"]:
                if dep in package_providers and package_providers[dep] != repo.name:
                    self.cross_dependencies[repo.name].add(package_providers[dep])

    def _find_shared_components(self) -> None:
        """Find components shared across repositories."""
        console.print("\n[yellow]Finding shared components...[/yellow]")

        # Look for common file patterns
        file_patterns = defaultdict(list)

        for repo in self.repositories:
            for file_path in repo.path.rglob("*.js"):
                if (
                    "utils" in str(file_path)
                    or "common" in str(file_path)
                    or "shared" in str(file_path)
                ):
                    rel_path = file_path.relative_to(repo.path)
                    file_patterns[str(rel_path)].append(repo.name)

        # Files that appear in multiple repos might be shared
        for file_path, repos in file_patterns.items():
            if len(repos) > 1:
                self.shared_components[file_path] = repos

    def _analyze_api_contracts(self) -> None:
        """Analyze API contracts between services."""
        console.print("\n[yellow]Analyzing API contracts...[/yellow]")

        # Simple analysis: look for API definitions and consumers
        api_providers = defaultdict(list)
        api_consumers = defaultdict(list)

        for repo in self.repositories:
            # Check if it provides APIs
            if repo.metadata["apis"]:
                api_providers[repo.name] = repo.metadata["apis"]

            # Check if it consumes APIs (look for HTTP client code)
            for file_path in repo.path.rglob("*.js"):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if (
                        "fetch(" in content
                        or "axios." in content
                        or "http.get" in content
                    ):
                        api_consumers[repo.name].append(
                            str(file_path.relative_to(repo.path))
                        )
                except Exception:
                    pass

        # Store the results for later use
        self.api_providers = api_providers
        self.api_consumers = api_consumers

    def find_security_propagation(self) -> dict[str, list[str]]:
        """Find how security vulnerabilities might propagate across repos."""
        propagation = defaultdict(list)

        # Simulate vulnerability detection
        vulnerable_packages = ["lodash<4.17.21", "axios<0.21.1", "express<4.17.3"]

        for repo in self.repositories:
            for dep in repo.metadata["dependencies"]:
                for vuln in vulnerable_packages:
                    if vuln.split("<")[0] in dep:
                        propagation[vuln].append(repo.name)

        return dict(propagation)

    def generate_dependency_graph(self) -> str:
        """Generate a visual representation of dependencies."""
        tree = Tree("[bold]Ecosystem Dependencies[/bold]")

        for repo_name, deps in self.cross_dependencies.items():
            repo_branch = tree.add(f"[cyan]{repo_name}[/cyan]")
            for dep in deps:
                repo_branch.add(f"[yellow]→ {dep}[/yellow]")

        return tree

    def generate_report(self) -> dict[str, Any]:
        """Generate a comprehensive ecosystem analysis report."""
        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "ecosystem": {
                "total_repositories": len(self.repositories),
                "total_files": sum(
                    sum(repo.metadata["languages"].values())
                    for repo in self.repositories
                ),
            },
            "languages": {},
            "cross_dependencies": {
                repo: list(deps) for repo, deps in self.cross_dependencies.items()
            },
            "shared_components": {
                comp: repos for comp, repos in self.shared_components.items()
            },
            "repositories": {},
        }

        # Aggregate language statistics
        for repo in self.repositories:
            for lang, count in repo.metadata["languages"].items():
                report["languages"][lang] = report["languages"].get(lang, 0) + count

            report["repositories"][repo.name] = {
                "path": str(repo.path),
                "languages": dict(repo.metadata["languages"]),
                "dependencies": list(repo.metadata["dependencies"]),
                "api_count": len(repo.metadata["apis"]),
            }

        return report


def display_ecosystem_summary(analyzer: EcosystemAnalyzer) -> None:
    """Display a summary of the ecosystem analysis."""
    console.print(Panel("[bold cyan]Ecosystem Summary[/bold cyan]", style="cyan"))

    # Repository overview
    table = Table(title="Repository Overview")
    table.add_column("Repository", style="cyan")
    table.add_column("Primary Language", style="yellow")
    table.add_column("Dependencies", style="green")
    table.add_column("APIs", style="blue")

    for repo in analyzer.repositories:
        # Find primary language
        if repo.metadata["languages"]:
            primary_lang = max(repo.metadata["languages"].items(), key=lambda x: x[1])[
                0
            ]
        else:
            primary_lang = "Unknown"

        table.add_row(
            repo.name,
            primary_lang,
            str(len(repo.metadata["dependencies"])),
            str(len(repo.metadata["apis"])),
        )

    console.print(table)

    # Cross-dependencies
    if analyzer.cross_dependencies:
        console.print("\n[bold]Cross-Repository Dependencies:[/bold]")
        dep_tree = analyzer.generate_dependency_graph()
        console.print(dep_tree)

    # Shared components
    if analyzer.shared_components:
        console.print("\n[bold]Shared Components:[/bold]")
        for component, repos in list(analyzer.shared_components.items())[:5]:
            console.print(f"  • {component}: {', '.join(repos)}")

    # Security propagation
    propagation = analyzer.find_security_propagation()
    if propagation:
        console.print("\n[bold red]Security Vulnerability Propagation:[/bold red]")
        for vuln, affected in propagation.items():
            console.print(f"  • {vuln} affects: {', '.join(affected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-Repository Ecosystem Analysis")
    parser.add_argument(
        "--base-path", default="ecosystem", help="Base path for cloning repositories"
    )
    parser.add_argument(
        "--config", help="Configuration file with repository definitions"
    )
    parser.add_argument("--report", help="Output report file")

    args = parser.parse_args()

    analyzer = EcosystemAnalyzer(args.base_path)

    # Example ecosystem configuration
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            config = json.load(f)
            for repo in config.get("repositories", []):
                analyzer.add_repository(repo["name"], repo.get("url"), repo.get("path"))
    else:
        # Default example repositories
        console.print("[yellow]Using example repository configuration[/yellow]")
        analyzer.add_repository("frontend", "https://github.com/example/frontend")
        analyzer.add_repository("backend", "https://github.com/example/backend")
        analyzer.add_repository("shared-lib", "https://github.com/example/shared-lib")

    console.print(
        Panel(
            f"[bold cyan]Multi-Repository Ecosystem Analysis[/bold cyan]\n"
            f"Base Path: {args.base_path}\n"
            f"Repositories: {len(analyzer.repositories)}",
            style="cyan",
        )
    )

    # Setup and analyze
    # analyzer.setup_repositories()  # Commented out to avoid actual cloning
    analyzer.analyze_ecosystem()

    # Display results
    display_ecosystem_summary(analyzer)

    # Generate report
    if args.report:
        report = analyzer.generate_report()
        with Path(args.report).open("w") as f:
            json.dump(report, f, indent=2)
        console.print(f"\n[green]Report saved to: {args.report}[/green]")

    # Example queries for multi-repo analysis
    console.print("\n" + "=" * 80)
    console.print(
        Panel(
            "[bold green]Example Multi-Repository Queries[/bold green]", style="green"
        )
    )

    example_queries = [
        "Show all REST APIs across all services",
        "Find functions that are duplicated in multiple repositories",
        "Show security vulnerabilities that affect multiple services",
        "Find version conflicts in shared dependencies",
        "Show which services depend on the authentication module",
        "Find circular dependencies between repositories",
        "Show test coverage across the entire ecosystem",
        "Find deprecated APIs still being used by consumers",
    ]

    for i, query in enumerate(example_queries, 1):
        console.print(f"{i}. {query}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
