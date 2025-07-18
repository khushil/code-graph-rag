#!/usr/bin/env python3
"""
Large-Scale Codebase Management Example

This example demonstrates how to manage and analyze large codebases:
1. Incremental updates
2. Memory-efficient processing
3. Partitioned analysis
4. Performance monitoring
5. Multi-language statistics
"""

import argparse
import gc
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console()


class LargeScaleAnalyzer:
    """Analyzer for large-scale codebases with performance monitoring."""

    def __init__(self, repo_path: str, config: dict[str, Any]):
        self.repo_path = Path(repo_path)
        self.config = config
        self.metrics = {
            "start_time": time.time(),
            "memory_usage": [],
            "processing_times": {},
            "file_counts": defaultdict(int),
        }
        self.process = psutil.Process(os.getpid())

    def get_changed_files(self, since_days: int = 1) -> set[str]:
        """Get files changed in the last N days."""
        try:
            since = datetime.now(UTC) - timedelta(days=since_days)
            cmd = [
                "git",
                "-C",
                str(self.repo_path),
                "log",
                f"--since={since.isoformat()}",
                "--name-only",
                "--pretty=format:",
            ]

            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            files = {f for f in result.stdout.strip().split("\n") if f}

            # Filter by supported extensions
            supported_extensions = {
                ".py",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".rs",
                ".go",
                ".java",
                ".scala",
                ".sc",
                ".cpp",
                ".cc",
                ".cxx",
                ".hpp",
                ".h",
                ".c",
            }

            return {f for f in files if Path(f).suffix in supported_extensions}
        except Exception as e:
            console.print(f"[red]Error getting changed files: {e}[/red]")
            return set()

    def measure_memory(self) -> float:
        """Measure current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def partition_files_by_size(self, max_batch_size: int = 100) -> list[list[str]]:
        """Partition files into batches for processing."""
        all_files = []

        for ext in self.config.get("extensions", [".py", ".js", ".c"]):
            files = list(self.repo_path.rglob(f"*{ext}"))
            all_files.extend(files)
            self.metrics["file_counts"][ext] = len(files)

        # Sort by size to balance batches
        all_files.sort(key=lambda f: f.stat().st_size, reverse=True)

        # Create balanced batches
        batches = []
        current_batch = []
        current_size = 0

        for file in all_files:
            file_size = file.stat().st_size
            if current_size + file_size > max_batch_size * 1024 * 1024:  # MB to bytes
                if current_batch:
                    batches.append(current_batch)
                current_batch = [str(file)]
                current_size = file_size
            else:
                current_batch.append(str(file))
                current_size += file_size

        if current_batch:
            batches.append(current_batch)

        return batches

    def process_batch(
        self, batch: list[str], batch_num: int, total_batches: int
    ) -> None:
        """Process a batch of files."""
        start_time = time.time()
        start_memory = self.measure_memory()

        console.print(f"\n[cyan]Processing batch {batch_num}/{total_batches}[/cyan]")
        console.print(f"Files in batch: {len(batch)}")
        console.print(f"Memory before: {start_memory:.2f} MB")

        # Process files (mock for example)
        # In real implementation, this would update the graph
        for _file in batch:
            # Simulate processing
            time.sleep(0.001)

        end_memory = self.measure_memory()
        processing_time = time.time() - start_time

        self.metrics["processing_times"][f"batch_{batch_num}"] = processing_time
        self.metrics["memory_usage"].append(end_memory)

        console.print(
            f"Memory after: {end_memory:.2f} MB (Δ {end_memory - start_memory:.2f} MB)"
        )
        console.print(f"Processing time: {processing_time:.2f} seconds")

    def incremental_update(self) -> None:
        """Perform incremental update of changed files."""
        console.print(
            Panel("[bold yellow]Incremental Update[/bold yellow]", style="yellow")
        )

        changed_files = self.get_changed_files(self.config.get("since_days", 1))

        if not changed_files:
            console.print("[green]No files changed since last update[/green]")
            return

        console.print(f"Found [cyan]{len(changed_files)}[/cyan] changed files")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Updating graph...", total=len(changed_files))

            for _file in changed_files:
                # Update graph for this file (mock)
                time.sleep(0.01)
                progress.update(task, advance=1)

        console.print("[green]Incremental update complete[/green]")

    def analyze_subsystems(self) -> dict[str, Any]:
        """Analyze code distribution by subsystem."""
        subsystems = defaultdict(
            lambda: {"files": 0, "lines": 0, "languages": defaultdict(int)}
        )

        # Common subsystem patterns
        patterns = {
            "frontend": ["src/components", "src/pages", "src/ui", "client", "web"],
            "backend": ["src/api", "src/services", "server", "api"],
            "database": ["src/db", "src/models", "migrations", "schema"],
            "tests": ["test", "tests", "__tests__", "spec"],
            "docs": ["docs", "documentation", "doc"],
            "config": ["config", "configs", ".config"],
            "scripts": ["scripts", "tools", "bin"],
        }

        for file_path in self.repo_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [
                ".py",
                ".js",
                ".ts",
                ".java",
                ".c",
                ".cpp",
                ".rs",
                ".go",
            ]:
                # Determine subsystem
                subsystem = "other"
                for name, paths in patterns.items():
                    if any(p in str(file_path) for p in paths):
                        subsystem = name
                        break

                # Count statistics
                subsystems[subsystem]["files"] += 1
                subsystems[subsystem]["languages"][file_path.suffix] += 1

                try:
                    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                        lines = len(f.readlines())
                        subsystems[subsystem]["lines"] += lines
                except Exception:
                    pass

        return dict(subsystems)

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate a performance analysis report."""
        total_time = time.time() - self.metrics["start_time"]

        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "repository": str(self.repo_path),
            "performance": {
                "total_time_seconds": total_time,
                "average_memory_mb": sum(self.metrics["memory_usage"])
                / len(self.metrics["memory_usage"])
                if self.metrics["memory_usage"]
                else 0,
                "peak_memory_mb": max(self.metrics["memory_usage"])
                if self.metrics["memory_usage"]
                else 0,
                "batches_processed": len(self.metrics["processing_times"]),
            },
            "file_statistics": dict(self.metrics["file_counts"]),
            "processing_times": self.metrics["processing_times"],
        }

        return report

    def optimize_queries(self) -> None:
        """Demonstrate query optimization techniques."""
        console.print(
            Panel("[bold green]Query Optimization Tips[/bold green]", style="green")
        )

        optimizations = [
            {
                "title": "Use Indexes",
                "bad": "MATCH (f:Function) WHERE f.name = 'processOrder' RETURN f",
                "good": "CREATE INDEX ON :Function(name);\nMATCH (f:Function {name: 'processOrder'}) RETURN f",
            },
            {
                "title": "Limit Graph Traversal",
                "bad": "MATCH (f:Function)-[*]->(g:Function) RETURN f, g",
                "good": "MATCH (f:Function)-[*1..3]->(g:Function) RETURN f, g LIMIT 100",
            },
            {
                "title": "Use Specific Relationships",
                "bad": "MATCH (f:Function)-[]->(g:Function) RETURN f, g",
                "good": "MATCH (f:Function)-[:CALLS]->(g:Function) RETURN f, g",
            },
            {
                "title": "Filter Early",
                "bad": "MATCH (f:Function)-[:CALLS]->(g:Function) RETURN f, g WHERE f.complexity > 10",
                "good": "MATCH (f:Function) WHERE f.complexity > 10 MATCH (f)-[:CALLS]->(g:Function) RETURN f, g",
            },
        ]

        for opt in optimizations:
            console.print(f"\n[bold]{opt['title']}:[/bold]")
            console.print("[red]Bad:[/red]")
            console.print(f"  {opt['bad']}")
            console.print("[green]Good:[/green]")
            console.print(f"  {opt['good']}")


def display_subsystem_analysis(subsystems: dict[str, Any]) -> None:
    """Display subsystem analysis results."""
    console.print(Panel("[bold cyan]Subsystem Analysis[/bold cyan]", style="cyan"))

    table = Table(title="Code Distribution by Subsystem")
    table.add_column("Subsystem", style="cyan")
    table.add_column("Files", style="yellow")
    table.add_column("Lines", style="green")
    table.add_column("Primary Language", style="blue")

    for name, stats in sorted(
        subsystems.items(), key=lambda x: x[1]["files"], reverse=True
    ):
        # Find primary language
        if stats["languages"]:
            primary_lang = max(stats["languages"].items(), key=lambda x: x[1])[0]
        else:
            primary_lang = "N/A"

        table.add_row(
            name.capitalize(), str(stats["files"]), f"{stats['lines']:,}", primary_lang
        )

    console.print(table)


def main() -> int:
    parser = argparse.ArgumentParser(description="Large-Scale Codebase Management")
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental", "analyze"],
        default="analyze",
        help="Processing mode",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Maximum batch size in MB"
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="Number of parallel workers"
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=1,
        help="Days to look back for incremental updates",
    )
    parser.add_argument("--report", help="Output report file")

    args = parser.parse_args()

    config = {
        "batch_size": args.batch_size,
        "workers": args.workers,
        "since_days": args.since_days,
        "extensions": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".rs", ".go"],
    }

    analyzer = LargeScaleAnalyzer(args.repo_path, config)

    console.print(
        Panel(
            f"[bold cyan]Large-Scale Codebase Management[/bold cyan]\n"
            f"Repository: {args.repo_path}\n"
            f"Mode: {args.mode}",
            style="cyan",
        )
    )

    if args.mode == "full":
        # Full processing with batching
        console.print("\n[yellow]Starting full codebase analysis...[/yellow]")

        batches = analyzer.partition_files_by_size(args.batch_size)
        console.print(f"Created [green]{len(batches)}[/green] batches for processing")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing batches...", total=len(batches))

            for i, batch in enumerate(batches, 1):
                analyzer.process_batch(batch, i, len(batches))
                progress.update(task, advance=1)

                # Memory management
                if analyzer.measure_memory() > 4000:  # 4GB threshold
                    console.print(
                        "[yellow]High memory usage detected, running garbage collection[/yellow]"
                    )
                    gc.collect()

    elif args.mode == "incremental":
        # Incremental update
        analyzer.incremental_update()

    elif args.mode == "analyze":
        # Analysis only
        console.print("\n[yellow]Analyzing codebase structure...[/yellow]")
        subsystems = analyzer.analyze_subsystems()
        display_subsystem_analysis(subsystems)

        # Show optimization tips
        analyzer.optimize_queries()

    # Generate performance report
    if args.report:
        report = analyzer.generate_performance_report()
        report["subsystems"] = analyzer.analyze_subsystems()

        with Path(args.report).open("w") as f:
            json.dump(report, f, indent=2)

        console.print(f"\n[green]Report saved to: {args.report}[/green]")

    # Display final metrics
    console.print("\n" + "=" * 80)
    console.print(Panel("[bold green]Performance Summary[/bold green]", style="green"))

    total_time = time.time() - analyzer.metrics["start_time"]
    console.print(f"Total processing time: [cyan]{total_time:.2f}[/cyan] seconds")

    if analyzer.metrics["memory_usage"]:
        avg_memory = sum(analyzer.metrics["memory_usage"]) / len(
            analyzer.metrics["memory_usage"]
        )
        peak_memory = max(analyzer.metrics["memory_usage"])
        console.print(f"Average memory usage: [cyan]{avg_memory:.2f}[/cyan] MB")
        console.print(f"Peak memory usage: [cyan]{peak_memory:.2f}[/cyan] MB")

    total_files = sum(analyzer.metrics["file_counts"].values())
    console.print(f"Total files analyzed: [cyan]{total_files:,}[/cyan]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
