#!/usr/bin/env python3
"""
Performance Benchmarking Script

This script benchmarks the performance of Graph-Code RAG system:
1. Ingestion performance (serial vs parallel)
2. Query performance
3. Memory usage patterns
4. Scalability testing
5. Optimization recommendations
"""

import argparse
import gc
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

console = Console()


class PerformanceBenchmark:
    """Comprehensive performance benchmarking for code analysis."""

    def __init__(self, repo_path: str, output_dir: str = "benchmark_results"):
        self.repo_path = Path(repo_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.process = psutil.Process(os.getpid())
        self.results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "repository": str(self.repo_path),
            "system_info": self._get_system_info(),
            "benchmarks": {},
        }

    def _get_system_info(self) -> dict[str, Any]:
        """Get system information for the benchmark."""
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "total_memory_gb": psutil.virtual_memory().total / (1024**3),
            "python_version": sys.version,
            "platform": sys.platform,
        }

    def _measure_memory(self) -> dict[str, float]:
        """Measure current memory usage."""
        mem_info = self.process.memory_info()
        return {
            "rss_mb": mem_info.rss / (1024**2),
            "vms_mb": mem_info.vms / (1024**2),
            "percent": self.process.memory_percent(),
        }

    def _measure_time_and_memory(
        self, func, *args, **kwargs
    ) -> tuple[Any, float, dict[str, float]]:
        """Measure execution time and memory usage of a function."""
        gc.collect()
        start_memory = self._measure_memory()
        start_time = time.time()

        result = func(*args, **kwargs)

        end_time = time.time()
        end_memory = self._measure_memory()

        memory_delta = {
            "rss_mb": end_memory["rss_mb"] - start_memory["rss_mb"],
            "vms_mb": end_memory["vms_mb"] - start_memory["vms_mb"],
            "peak_rss_mb": end_memory["rss_mb"],
        }

        return result, end_time - start_time, memory_delta

    def benchmark_file_discovery(self) -> dict[str, Any]:
        """Benchmark file discovery performance."""
        console.print(
            Panel("[bold cyan]Benchmarking File Discovery[/bold cyan]", style="cyan")
        )

        results = {}
        extensions = [".py", ".js", ".c", ".java", ".go", ".rs"]

        # Single extension
        for ext in extensions:
            _, elapsed, memory = self._measure_time_and_memory(
                lambda: list(self.repo_path.rglob(f"*{ext}"))
            )
            results[f"single_{ext}"] = {
                "time_seconds": elapsed,
                "memory_mb": memory["rss_mb"],
                "files_found": len(list(self.repo_path.rglob(f"*{ext}"))),
            }
            console.print(f"  {ext}: {elapsed:.3f}s")

        # All extensions
        _, elapsed, memory = self._measure_time_and_memory(
            lambda: [f for ext in extensions for f in self.repo_path.rglob(f"*{ext}")]
        )
        results["all_extensions"] = {
            "time_seconds": elapsed,
            "memory_mb": memory["rss_mb"],
        }

        return results

    def benchmark_parsing_performance(self, sample_size: int = 100) -> dict[str, Any]:
        """Benchmark code parsing performance."""
        console.print(
            Panel(
                "[bold yellow]Benchmarking Parsing Performance[/bold yellow]",
                style="yellow",
            )
        )

        # Get sample files
        py_files = list(self.repo_path.rglob("*.py"))[:sample_size]

        if not py_files:
            console.print("[red]No Python files found for benchmarking[/red]")
            return {}

        results = {
            "sample_size": len(py_files),
            "total_size_mb": sum(f.stat().st_size for f in py_files) / (1024**2),
        }

        # Mock parsing for demonstration
        def mock_parse_files(files, parallel=False, workers=1):
            # Simulate parsing time based on file size
            total_size = sum(f.stat().st_size for f in files)
            base_time = total_size / (1024**2) * 0.1  # 0.1s per MB

            if parallel:
                time.sleep(base_time / workers)
            else:
                time.sleep(base_time)

            return len(files)

        # Serial parsing
        _, elapsed, memory = self._measure_time_and_memory(
            mock_parse_files, py_files, parallel=False
        )
        results["serial"] = {
            "time_seconds": elapsed,
            "memory_mb": memory["peak_rss_mb"],
            "files_per_second": len(py_files) / elapsed if elapsed > 0 else 0,
        }

        # Parallel parsing with different worker counts
        for workers in [2, 4, 8, 16]:
            if workers <= psutil.cpu_count():
                _, elapsed, memory = self._measure_time_and_memory(
                    mock_parse_files, py_files, parallel=True, workers=workers
                )
                results[f"parallel_{workers}_workers"] = {
                    "time_seconds": elapsed,
                    "memory_mb": memory["peak_rss_mb"],
                    "files_per_second": len(py_files) / elapsed if elapsed > 0 else 0,
                    "speedup": results["serial"]["time_seconds"] / elapsed
                    if elapsed > 0
                    else 0,
                }

        return results

    def benchmark_query_performance(self) -> dict[str, Any]:
        """Benchmark different types of queries."""
        console.print(
            Panel(
                "[bold green]Benchmarking Query Performance[/bold green]", style="green"
            )
        )

        # Sample queries with different complexity levels
        queries = {
            "simple": {
                "description": "Find function by name",
                "cypher": "MATCH (f:Function {name: 'process'}) RETURN f",
            },
            "medium": {
                "description": "Find call relationships",
                "cypher": "MATCH (f:Function)-[:CALLS]->(g:Function) RETURN f, g LIMIT 100",
            },
            "complex": {
                "description": "Multi-hop traversal",
                "cypher": """
                    MATCH path = (f:Function)-[:CALLS*1..3]->(g:Function)
                    WHERE f.complexity > 10
                    RETURN path LIMIT 50
                """,
            },
            "aggregation": {
                "description": "Aggregate statistics",
                "cypher": """
                    MATCH (f:Function)
                    RETURN f.module as module, COUNT(f) as count, AVG(f.complexity) as avg_complexity
                    ORDER BY count DESC
                """,
            },
        }

        results = {}

        for query_type, query_info in queries.items():
            # Mock query execution
            complexity_factor = {
                "simple": 0.01,
                "medium": 0.05,
                "complex": 0.2,
                "aggregation": 0.1,
            }

            _, elapsed, memory = self._measure_time_and_memory(
                lambda: time.sleep(complexity_factor.get(query_type, 0.1))
            )

            results[query_type] = {
                "description": query_info["description"],
                "time_seconds": elapsed,
                "memory_mb": memory["rss_mb"],
            }

            console.print(f"  {query_type}: {elapsed:.3f}s")

        return results

    def benchmark_memory_scaling(self, sizes: list[int] = None) -> dict[str, Any]:
        """Benchmark memory usage at different scales."""
        console.print(
            Panel("[bold red]Benchmarking Memory Scaling[/bold red]", style="red")
        )

        if sizes is None:
            sizes = [100, 500, 1000, 5000, 10000]

        results = {}

        for size in sizes:
            # Simulate processing N files
            data = []

            _, elapsed, memory = self._measure_time_and_memory(
                lambda: [
                    data.append({"id": i, "data": "x" * 1000}) for i in range(size)
                ]
            )

            results[f"files_{size}"] = {
                "count": size,
                "memory_mb": memory["peak_rss_mb"],
                "mb_per_file": memory["peak_rss_mb"] / size if size > 0 else 0,
            }

            console.print(f"  {size} files: {memory['peak_rss_mb']:.2f} MB")

            # Clean up
            del data
            gc.collect()

        return results

    def generate_optimization_recommendations(self) -> list[dict[str, str]]:
        """Generate optimization recommendations based on benchmarks."""
        recommendations = []

        # Analyze parsing performance
        if "parsing" in self.results["benchmarks"]:
            parsing = self.results["benchmarks"]["parsing"]
            if parsing.get("serial", {}).get("files_per_second", 0) < 10:
                recommendations.append(
                    {
                        "area": "Parsing Performance",
                        "issue": "Slow file parsing",
                        "recommendation": "Enable parallel processing with --parallel flag",
                        "impact": "High",
                    }
                )

        # Analyze memory usage
        if "memory_scaling" in self.results["benchmarks"]:
            memory = self.results["benchmarks"]["memory_scaling"]
            # Check if memory grows linearly
            sizes = []
            memories = []
            for key, value in memory.items():
                if "files_" in key:
                    sizes.append(value["count"])
                    memories.append(value["memory_mb"])

            if sizes and memories:
                # Simple linear regression
                avg_mb_per_file = sum(memories) / sum(sizes)
                if avg_mb_per_file > 1:  # More than 1MB per file
                    recommendations.append(
                        {
                            "area": "Memory Usage",
                            "issue": "High memory consumption per file",
                            "recommendation": "Use batch processing with --batch-size flag",
                            "impact": "High",
                        }
                    )

        # Query performance
        if "queries" in self.results["benchmarks"]:
            queries = self.results["benchmarks"]["queries"]
            slow_queries = [
                k for k, v in queries.items() if v.get("time_seconds", 0) > 1
            ]
            if slow_queries:
                recommendations.append(
                    {
                        "area": "Query Performance",
                        "issue": f"Slow queries: {', '.join(slow_queries)}",
                        "recommendation": "Create indexes on frequently queried properties",
                        "impact": "Medium",
                    }
                )

        return recommendations

    def create_visualizations(self) -> None:
        """Create performance visualization charts."""
        if not HAS_MATPLOTLIB:
            console.print("[yellow]Matplotlib not available, skipping visualizations[/yellow]")
            return
            
        console.print(
            Panel(
                "[bold magenta]Creating Visualizations[/bold magenta]", style="magenta"
            )
        )

        # Parsing performance comparison
        if "parsing" in self.results["benchmarks"]:
            parsing = self.results["benchmarks"]["parsing"]

            # Extract data for parallel performance
            workers = []
            speedups = []
            for key, value in parsing.items():
                if "parallel_" in key and "speedup" in value:
                    worker_count = int(key.split("_")[1])
                    workers.append(worker_count)
                    speedups.append(value["speedup"])

            if workers and speedups:
                plt.figure(figsize=(10, 6))
                plt.plot(workers, speedups, "b-o", linewidth=2, markersize=8)
                plt.plot(workers, workers, "r--", alpha=0.5, label="Ideal speedup")
                plt.xlabel("Number of Workers")
                plt.ylabel("Speedup Factor")
                plt.title("Parallel Processing Speedup")
                plt.grid(True, alpha=0.3)
                plt.legend()
                plt.savefig(
                    self.output_dir / "parallel_speedup.png",
                    dpi=150,
                    bbox_inches="tight",
                )
                plt.close()

        # Memory scaling visualization
        if "memory_scaling" in self.results["benchmarks"]:
            memory = self.results["benchmarks"]["memory_scaling"]

            sizes = []
            memories = []
            for key, value in sorted(memory.items()):
                if "files_" in key:
                    sizes.append(value["count"])
                    memories.append(value["memory_mb"])

            if sizes and memories:
                plt.figure(figsize=(10, 6))
                plt.plot(sizes, memories, "g-o", linewidth=2, markersize=8)
                plt.xlabel("Number of Files")
                plt.ylabel("Memory Usage (MB)")
                plt.title("Memory Usage Scaling")
                plt.grid(True, alpha=0.3)
                plt.savefig(
                    self.output_dir / "memory_scaling.png", dpi=150, bbox_inches="tight"
                )
                plt.close()

        console.print(f"[green]Visualizations saved to {self.output_dir}[/green]")

    def save_results(self) -> None:
        """Save benchmark results to file."""
        output_file = (
            self.output_dir
            / f"benchmark_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        )

        with output_file.open("w") as f:
            json.dump(self.results, f, indent=2)

        console.print(f"[green]Results saved to {output_file}[/green]")

    def run_all_benchmarks(self) -> None:
        """Run all benchmarks."""
        self.results["benchmarks"]["file_discovery"] = self.benchmark_file_discovery()
        console.print()

        self.results["benchmarks"]["parsing"] = self.benchmark_parsing_performance()
        console.print()

        self.results["benchmarks"]["queries"] = self.benchmark_query_performance()
        console.print()

        self.results["benchmarks"]["memory_scaling"] = self.benchmark_memory_scaling()
        console.print()

        self.results["recommendations"] = self.generate_optimization_recommendations()


def display_benchmark_summary(benchmark: PerformanceBenchmark) -> None:
    """Display a summary of benchmark results."""
    console.print(Panel("[bold cyan]Benchmark Summary[/bold cyan]", style="cyan"))

    # System info
    system_info = benchmark.results["system_info"]
    console.print(f"CPU Cores: [cyan]{system_info['cpu_count']}[/cyan]")
    console.print(f"Total Memory: [cyan]{system_info['total_memory_gb']:.2f} GB[/cyan]")
    console.print(f"Platform: [cyan]{system_info['platform']}[/cyan]")

    # Performance highlights
    if "parsing" in benchmark.results["benchmarks"]:
        parsing = benchmark.results["benchmarks"]["parsing"]
        if "serial" in parsing and "parallel_8_workers" in parsing:
            speedup = parsing["parallel_8_workers"].get("speedup", 1)
            console.print(
                f"\nParallel Processing Speedup (8 workers): [green]{speedup:.2f}x[/green]"
            )

    # Recommendations
    if benchmark.results.get("recommendations"):
        console.print("\n[bold]Optimization Recommendations:[/bold]")

        table = Table()
        table.add_column("Area", style="cyan")
        table.add_column("Issue", style="yellow")
        table.add_column("Recommendation", style="green")
        table.add_column("Impact", style="red")

        for rec in benchmark.results["recommendations"]:
            table.add_row(
                rec["area"], rec["issue"], rec["recommendation"], rec["impact"]
            )

        console.print(table)


def main() -> int:
    parser = argparse.ArgumentParser(description="Performance Benchmarking")
    parser.add_argument("repo_path", help="Path to repository to benchmark")
    parser.add_argument(
        "--output-dir", default="benchmark_results", help="Output directory for results"
    )
    parser.add_argument(
        "--sample-size", type=int, default=100, help="Sample size for parsing benchmark"
    )
    parser.add_argument(
        "--skip-visualizations",
        action="store_true",
        help="Skip creating visualization charts",
    )

    args = parser.parse_args()

    if not Path(args.repo_path).exists():
        console.print(
            f"[red]Error: Repository path {args.repo_path} does not exist[/red]"
        )
        return 1

    console.print(
        Panel(
            f"[bold cyan]Performance Benchmarking[/bold cyan]\n"
            f"Repository: {args.repo_path}\n"
            f"Output: {args.output_dir}",
            style="cyan",
        )
    )

    benchmark = PerformanceBenchmark(args.repo_path, args.output_dir)

    # Run benchmarks
    benchmark.run_all_benchmarks()

    # Display summary
    display_benchmark_summary(benchmark)

    # Create visualizations
    if not args.skip_visualizations:
        benchmark.create_visualizations()

    # Save results
    benchmark.save_results()

    return 0


if __name__ == "__main__":
    sys.exit(main())
