#!/usr/bin/env python3
"""
Linux Kernel Analysis Example

This example demonstrates how to analyze Linux kernel code including:
1. Syscall tracing
2. Driver analysis
3. Locking pattern detection
4. Memory management analysis
5. Kernel configuration dependencies
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codebase_rag.graph_loader import export_graph_to_file, load_graph
from codebase_rag.main import parse_and_store_codebase

console = Console()


def analyze_syscalls(graph_data: dict[str, Any]) -> None:
    """Analyze system call implementations."""
    console.print(Panel("[bold cyan]System Call Analysis[/bold cyan]", style="cyan"))

    syscalls = []
    syscall_macros = []

    for node in graph_data.get("nodes", []):
        if node["label"] == "Macro":
            name = node["properties"].get("name", "")
            if name.startswith("SYSCALL_DEFINE"):
                syscall_macros.append(node)
        elif node["label"] == "Function":
            name = node["properties"].get("name", "")
            if name.startswith(("sys_", "__x64_sys_")):
                syscalls.append(node)

    console.print(f"Found [green]{len(syscalls)}[/green] syscall implementations")
    console.print(f"Found [green]{len(syscall_macros)}[/green] SYSCALL_DEFINE macros")

    if syscalls:
        console.print("\n[bold]Sample System Calls:[/bold]")
        for syscall in syscalls[:10]:
            name = syscall["properties"]["name"]
            file_path = syscall["properties"].get("file_path", "unknown")
            console.print(f"  • {name} in {file_path}")


def analyze_drivers(graph_data: dict[str, Any], subsystem: str = "net") -> None:
    """Analyze device drivers in a subsystem."""
    console.print(
        Panel(f"[bold blue]Driver Analysis - {subsystem}[/bold blue]", style="blue")
    )

    drivers = []
    driver_ops = []
    module_inits = []

    for node in graph_data.get("nodes", []):
        if node["label"] == "Module":
            path = node["properties"].get("file_path", "")
            if f"drivers/{subsystem}" in path:
                drivers.append(node)
        elif node["label"] == "Struct":
            name = node["properties"].get("name", "")
            if name.endswith(("_ops", "_driver")):
                driver_ops.append(node)
        elif node["label"] == "Function":
            name = node["properties"].get("name", "")
            if name.endswith("_init") or "module_init" in name:
                module_inits.append(node)

    console.print(f"Found [green]{len(drivers)}[/green] driver modules")
    console.print(f"Found [green]{len(driver_ops)}[/green] driver operation structs")
    console.print(f"Found [green]{len(module_inits)}[/green] module init functions")

    # Analyze driver patterns
    if driver_ops:
        console.print("\n[bold]Driver Operation Structures:[/bold]")
        for ops in driver_ops[:5]:
            name = ops["properties"]["name"]
            console.print(f"  • {name}")


def analyze_locking_patterns(graph_data: dict[str, Any]) -> None:
    """Analyze kernel locking patterns."""
    console.print(Panel("[bold red]Locking Pattern Analysis[/bold red]", style="red"))

    lock_functions = {
        "spinlock": [
            "spin_lock",
            "spin_unlock",
            "spin_lock_irqsave",
            "spin_unlock_irqrestore",
        ],
        "mutex": ["mutex_lock", "mutex_unlock", "mutex_trylock"],
        "rwlock": ["read_lock", "write_lock", "read_unlock", "write_unlock"],
        "rcu": ["rcu_read_lock", "rcu_read_unlock", "synchronize_rcu"],
        "semaphore": ["down", "up", "down_interruptible"],
    }

    lock_usage = defaultdict(list)

    # Find function calls to locking primitives
    for rel in graph_data.get("relationships", []):
        if rel["rel_type"] == "CALLS":
            for lock_type, functions in lock_functions.items():
                for func in functions:
                    if rel.get("end_properties", {}).get("name") == func:
                        caller = rel.get("start_properties", {}).get("name", "unknown")
                        lock_usage[lock_type].append(
                            {
                                "caller": caller,
                                "lock_func": func,
                                "file": rel.get("start_properties", {}).get(
                                    "file_path", "unknown"
                                ),
                            }
                        )

    # Report findings
    table = Table(title="Locking Primitive Usage")
    table.add_column("Lock Type", style="cyan")
    table.add_column("Usage Count", style="yellow")
    table.add_column("Common Patterns", style="green")

    for lock_type, usages in lock_usage.items():
        count = len(usages)
        patterns = {u["lock_func"] for u in usages}
        table.add_row(lock_type, str(count), ", ".join(list(patterns)[:3]))

    console.print(table)

    # Check for potential issues
    console.print("\n[bold]Potential Locking Issues:[/bold]")

    # Find functions that lock but don't unlock
    lock_calls = set()
    unlock_calls = set()

    for usage in lock_usage.values():
        for u in usage:
            if "lock" in u["lock_func"] and "unlock" not in u["lock_func"]:
                lock_calls.add(u["caller"])
            elif "unlock" in u["lock_func"]:
                unlock_calls.add(u["caller"])

    missing_unlocks = lock_calls - unlock_calls
    if missing_unlocks:
        console.print(
            f"  ⚠️  Functions with locks but no unlocks: {len(missing_unlocks)}"
        )
        for func in list(missing_unlocks)[:5]:
            console.print(f"    - {func}")


def analyze_memory_management(graph_data: dict[str, Any]) -> None:
    """Analyze memory allocation patterns."""
    console.print(
        Panel("[bold yellow]Memory Management Analysis[/bold yellow]", style="yellow")
    )

    alloc_functions = {
        "kmalloc": ["GFP_KERNEL", "GFP_ATOMIC", "GFP_DMA"],
        "kzalloc": ["GFP_KERNEL", "GFP_ATOMIC"],
        "vmalloc": [],
        "get_free_pages": ["GFP_KERNEL", "GFP_ATOMIC"],
        "__get_free_pages": ["GFP_KERNEL", "GFP_ATOMIC"],
    }

    free_functions = ["kfree", "vfree", "free_pages"]

    allocations = defaultdict(list)
    frees = []

    # Find memory allocations
    for node in graph_data.get("nodes", []):
        if node["label"] == "Function":
            for rel in graph_data.get("relationships", []):
                if (
                    rel["rel_type"] == "CALLS"
                    and rel.get("start_properties", {}).get("name")
                    == node["properties"]["name"]
                ):
                    called_func = rel.get("end_properties", {}).get("name", "")

                    for alloc_func in alloc_functions:
                        if called_func == alloc_func:
                            allocations[alloc_func].append(
                                {
                                    "caller": node["properties"]["name"],
                                    "file": node["properties"].get(
                                        "file_path", "unknown"
                                    ),
                                }
                            )

                    if called_func in free_functions:
                        frees.append(
                            {
                                "caller": node["properties"]["name"],
                                "free_func": called_func,
                            }
                        )

    # Report allocation patterns
    console.print(
        f"Total allocations found: [green]{sum(len(v) for v in allocations.values())}[/green]"
    )
    console.print(f"Total frees found: [green]{len(frees)}[/green]")

    console.print("\n[bold]Memory Allocation Patterns:[/bold]")
    for alloc_func, calls in allocations.items():
        if calls:
            console.print(f"  • {alloc_func}: {len(calls)} calls")
            for call in calls[:2]:
                console.print(f"    - Called by {call['caller']}")

    # Check for potential leaks
    allocating_functions = set()
    freeing_functions = set()

    for calls in allocations.values():
        for call in calls:
            allocating_functions.add(call["caller"])

    for free in frees:
        freeing_functions.add(free["caller"])

    potential_leaks = allocating_functions - freeing_functions
    if potential_leaks:
        console.print("\n[bold red]⚠️  Potential Memory Leaks:[/bold red]")
        console.print(f"Functions that allocate but don't free: {len(potential_leaks)}")
        for func in list(potential_leaks)[:5]:
            console.print(f"  - {func}")


def analyze_kernel_config(graph_data: dict[str, Any]) -> None:
    """Analyze kernel configuration dependencies."""
    console.print(
        Panel(
            "[bold magenta]Kernel Configuration Analysis[/bold magenta]",
            style="magenta",
        )
    )

    config_files = []
    config_options = set()

    for node in graph_data.get("nodes", []):
        if node["label"] == "ConfigFile":
            if "Kconfig" in node["properties"].get("file_path", ""):
                config_files.append(node)
        elif node["label"] == "Macro":
            name = node["properties"].get("name", "")
            if name.startswith("CONFIG_"):
                config_options.add(name)

    console.print(f"Found [green]{len(config_files)}[/green] Kconfig files")
    console.print(f"Found [green]{len(config_options)}[/green] CONFIG options")

    # Analyze common configurations
    common_configs = [
        "CONFIG_DEBUG_KERNEL",
        "CONFIG_SMP",
        "CONFIG_PREEMPT",
        "CONFIG_MODULES",
        "CONFIG_NET",
        "CONFIG_PCI",
        "CONFIG_USB",
    ]

    console.print("\n[bold]Common Configuration Options:[/bold]")
    for config in common_configs:
        if config in config_options:
            console.print(f"  ✓ {config}")
        else:
            console.print(f"  ✗ {config} (not found)")


def analyze_exported_symbols(graph_data: dict[str, Any]) -> None:
    """Analyze exported kernel symbols."""
    console.print(
        Panel("[bold green]Exported Symbols Analysis[/bold green]", style="green")
    )

    exports = []
    export_types = defaultdict(int)

    for node in graph_data.get("nodes", []):
        if node["label"] == "KernelExport":
            exports.append(node)
            export_type = node["properties"].get("export_type", "EXPORT_SYMBOL")
            export_types[export_type] += 1

    console.print(f"Total exported symbols: [green]{len(exports)}[/green]")

    console.print("\n[bold]Export Types:[/bold]")
    for export_type, count in export_types.items():
        console.print(f"  • {export_type}: {count}")

    if exports:
        console.print("\n[bold]Sample Exported Functions:[/bold]")
        for export in exports[:10]:
            name = export["properties"].get("symbol_name", "unknown")
            export_type = export["properties"].get("export_type", "EXPORT_SYMBOL")
            console.print(f"  • {name} ({export_type})")


def generate_kernel_report(graph_data: dict[str, Any], output_file: str) -> None:
    """Generate a comprehensive kernel analysis report."""
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "analysis_type": "kernel",
        "summary": {
            "total_nodes": len(graph_data.get("nodes", [])),
            "total_relationships": len(graph_data.get("relationships", [])),
        },
        "subsystems": defaultdict(int),
        "complexity_metrics": {},
        "security_considerations": [],
    }

    # Analyze subsystems
    for node in graph_data.get("nodes", []):
        if node["label"] == "Module":
            path = node["properties"].get("file_path", "")
            if path.startswith("drivers/"):
                subsystem = path.split("/")[1]
                report["subsystems"][subsystem] += 1
            elif path.startswith("kernel/"):
                report["subsystems"]["kernel"] += 1
            elif path.startswith("fs/"):
                report["subsystems"]["filesystem"] += 1
            elif path.startswith("net/"):
                report["subsystems"]["networking"] += 1

    # Save report
    with Path(output_file).open("w") as f:
        json.dump(report, f, indent=2)

    console.print(f"\n[green]Kernel analysis report saved to: {output_file}[/green]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Linux Kernel Analysis Example")
    parser.add_argument("repo_path", help="Path to the kernel source")
    parser.add_argument(
        "--subsystem", default="net", help="Subsystem to analyze (default: net)"
    )
    parser.add_argument("--export-graph", help="Export graph to JSON file")
    parser.add_argument(
        "--report", default="kernel_analysis.json", help="Output report file"
    )
    parser.add_argument(
        "--skip-parsing", action="store_true", help="Skip parsing, use existing graph"
    )

    args = parser.parse_args()
    repo_path = Path(args.repo_path)

    if not repo_path.exists():
        console.print(f"[red]Error: Repository path {repo_path} does not exist[/red]")
        return 1

    console.print(
        Panel(
            f"[bold cyan]Linux Kernel Analysis[/bold cyan]\nRepository: {repo_path}",
            style="cyan",
        )
    )

    # Parse kernel if needed
    if not args.skip_parsing:
        console.print(
            "\n[yellow]Parsing kernel source (this may take a while)...[/yellow]"
        )
        try:
            parse_and_store_codebase(
                str(repo_path),
                clean=True,
                parallel=True,
                workers=16,
                folder_filter=f"drivers/{args.subsystem},kernel,include",
            )
        except Exception as e:
            console.print(f"[red]Error parsing codebase: {e}[/red]")
            return 1

    # Load or export graph
    if args.export_graph:
        export_graph_to_file(args.export_graph)
        graph_data = load_graph(args.export_graph)
    else:
        # Load from memory (mock for example)
        graph_data = {"nodes": [], "relationships": []}
        console.print("[yellow]Note: Using mock data for demonstration[/yellow]")

    # Run analyses
    analyze_syscalls(graph_data)
    console.print("\n" + "=" * 80 + "\n")

    analyze_drivers(graph_data, args.subsystem)
    console.print("\n" + "=" * 80 + "\n")

    analyze_locking_patterns(graph_data)
    console.print("\n" + "=" * 80 + "\n")

    analyze_memory_management(graph_data)
    console.print("\n" + "=" * 80 + "\n")

    analyze_kernel_config(graph_data)
    console.print("\n" + "=" * 80 + "\n")

    analyze_exported_symbols(graph_data)

    # Generate report
    if args.report:
        generate_kernel_report(graph_data, args.report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
