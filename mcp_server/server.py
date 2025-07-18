#!/usr/bin/env python3
"""
MCP Server for Graph-Code RAG System

This server provides tools for AI agents to query and analyze codebases
through the Graph-Code RAG system.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from mcp import Resource, Tool
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import EmbeddedResource, ImageContent, TextContent

from codebase_rag.analysis.data_flow import DataFlowAnalyzer
from codebase_rag.analysis.security import SecurityAnalyzer
from codebase_rag.analysis.test_coverage import TestCoverageAnalyzer
from codebase_rag.analysis.vcs import VCSAnalyzer
from codebase_rag.graph_loader import export_graph_to_file, load_graph
from codebase_rag.main import parse_and_store_codebase

from .security import SecureMCPServer, rate_limit, validate_inputs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CodeGraphContext:
    """Context for the current codebase analysis session."""

    repo_path: Path | None = None
    graph_data: dict[str, Any] | None = None
    active_analyzers: dict[str, Any] = field(default_factory=dict)
    cached_results: dict[str, Any] = field(default_factory=dict)
    available_languages: set[str] = field(
        default_factory=lambda: {
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "scala",
            "cpp",
            "c",
        }
    )


class CodeGraphMCPServer(SecureMCPServer):
    """MCP Server for Graph-Code RAG System with security features."""

    def __init__(self):
        super().__init__()
        self.server = Server("code-graph-rag")
        self.context = CodeGraphContext()
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up MCP server handlers."""

        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List available resources."""
            resources = []

            if self.context.repo_path and self.context.repo_path.exists():
                resources.append(
                    Resource(
                        uri=f"repo://{self.context.repo_path}",
                        name=f"Repository: {self.context.repo_path.name}",
                        description=f"Currently loaded repository at {self.context.repo_path}",
                        mimeType="application/x-repository",
                    )
                )

            if self.context.graph_data:
                resources.append(
                    Resource(
                        uri="graph://current",
                        name="Current Graph",
                        description=f"Graph with {len(self.context.graph_data.get('nodes', []))} nodes",
                        mimeType="application/x-graph",
                    )
                )

            return resources

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific resource."""
            if uri == "graph://current" and self.context.graph_data:
                summary = {
                    "nodes": len(self.context.graph_data.get("nodes", [])),
                    "relationships": len(
                        self.context.graph_data.get("relationships", [])
                    ),
                    "languages": list(self.context.available_languages),
                }
                return json.dumps(summary, indent=2)

            if uri.startswith("repo://") and self.context.repo_path:
                return str(self.context.repo_path)

            raise ValueError(f"Unknown resource: {uri}")

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available tools for codebase analysis."""
            return [
                Tool(
                    name="load_repository",
                    description="Load a repository and build its code graph",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repo_path": {
                                "type": "string",
                                "description": "Path to the repository",
                            },
                            "clean": {
                                "type": "boolean",
                                "description": "Whether to clean existing graph data",
                                "default": False,
                            },
                            "parallel": {
                                "type": "boolean",
                                "description": "Use parallel processing",
                                "default": True,
                            },
                            "folder_filter": {
                                "type": "string",
                                "description": "Comma-separated list of folders to include",
                            },
                        },
                        "required": ["repo_path"],
                    },
                ),
                Tool(
                    name="query_graph",
                    description="Query the code graph using natural language or Cypher",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language query or Cypher query",
                            },
                            "query_type": {
                                "type": "string",
                                "enum": ["natural", "cypher"],
                                "default": "natural",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 50,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="analyze_security",
                    description="Analyze security vulnerabilities in the codebase",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "severity_filter": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low", "all"],
                                "default": "all",
                            },
                            "vulnerability_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Types of vulnerabilities to check",
                            },
                        },
                    },
                ),
                Tool(
                    name="analyze_data_flow",
                    description="Analyze data flow through the codebase",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "variable_name": {
                                "type": "string",
                                "description": "Variable to track",
                            },
                            "function_name": {
                                "type": "string",
                                "description": "Function to analyze",
                            },
                            "track_taint": {
                                "type": "boolean",
                                "description": "Track tainted data flow",
                                "default": False,
                            },
                        },
                    },
                ),
                Tool(
                    name="analyze_test_coverage",
                    description="Analyze test coverage and find untested code",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_bdd": {
                                "type": "boolean",
                                "description": "Include BDD scenarios",
                                "default": True,
                            },
                            "module_filter": {
                                "type": "string",
                                "description": "Filter by module name",
                            },
                        },
                    },
                ),
                Tool(
                    name="analyze_dependencies",
                    description="Analyze code dependencies and circular imports",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "check_circular": {
                                "type": "boolean",
                                "description": "Check for circular dependencies",
                                "default": True,
                            },
                            "include_external": {
                                "type": "boolean",
                                "description": "Include external dependencies",
                                "default": False,
                            },
                        },
                    },
                ),
                Tool(
                    name="find_code_patterns",
                    description="Find specific code patterns or anti-patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Pattern to search for",
                            },
                            "pattern_type": {
                                "type": "string",
                                "enum": ["antipattern", "design_pattern", "custom"],
                                "default": "custom",
                            },
                            "language": {
                                "type": "string",
                                "description": "Language to search in",
                            },
                        },
                        "required": ["pattern"],
                    },
                ),
                Tool(
                    name="export_graph",
                    description="Export the current graph to a file",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {
                                "type": "string",
                                "description": "Path to save the graph",
                            },
                            "format": {
                                "type": "string",
                                "enum": ["json", "graphml", "cypher"],
                                "default": "json",
                            },
                        },
                        "required": ["output_path"],
                    },
                ),
                Tool(
                    name="get_code_metrics",
                    description="Get code quality metrics and statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "metric_types": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "complexity",
                                        "loc",
                                        "dependencies",
                                        "test_ratio",
                                        "all",
                                    ],
                                },
                                "default": ["all"],
                            }
                        },
                    },
                ),
                Tool(
                    name="analyze_git_history",
                    description="Analyze git history and contributor patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "since_days": {
                                "type": "integer",
                                "description": "Number of days to look back",
                                "default": 30,
                            },
                            "top_contributors": {
                                "type": "integer",
                                "description": "Number of top contributors to show",
                                "default": 10,
                            },
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any] | None = None
        ) -> list[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool execution."""
            try:
                if name == "load_repository":
                    result = await self._load_repository(arguments or {})
                elif name == "query_graph":
                    result = await self._query_graph(arguments or {})
                elif name == "analyze_security":
                    result = await self._analyze_security(arguments or {})
                elif name == "analyze_data_flow":
                    result = await self._analyze_data_flow(arguments or {})
                elif name == "analyze_test_coverage":
                    result = await self._analyze_test_coverage(arguments or {})
                elif name == "analyze_dependencies":
                    result = await self._analyze_dependencies(arguments or {})
                elif name == "find_code_patterns":
                    result = await self._find_code_patterns(arguments or {})
                elif name == "export_graph":
                    result = await self._export_graph(arguments or {})
                elif name == "get_code_metrics":
                    result = await self._get_code_metrics(arguments or {})
                elif name == "analyze_git_history":
                    result = await self._analyze_git_history(arguments or {})
                else:
                    raise ValueError(f"Unknown tool: {name}")

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": str(e), "tool": name}, indent=2),
                    )
                ]

    @rate_limit("load_repository")
    @validate_inputs(path_params={"repo_path"})
    async def _load_repository(self, args: dict[str, Any]) -> dict[str, Any]:
        """Load a repository and build its graph."""
        repo_path = Path(args["repo_path"])
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        self.context.repo_path = repo_path

        # Parse and store codebase
        parse_and_store_codebase(
            str(repo_path),
            clean=args.get("clean", False),
            parallel=args.get("parallel", True),
            folder_filter=args.get("folder_filter"),
        )

        # Export and load graph
        temp_file = "/tmp/graph_export.json"  # nosec B108
        export_graph_to_file(temp_file)
        self.context.graph_data = load_graph(temp_file).to_dict()

        return {
            "status": "success",
            "repo_path": str(repo_path),
            "nodes": len(self.context.graph_data.get("nodes", [])),
            "relationships": len(self.context.graph_data.get("relationships", [])),
        }

    @rate_limit("query_graph")
    @validate_inputs(query_params={"query"})
    async def _query_graph(self, args: dict[str, Any]) -> dict[str, Any]:
        """Query the code graph."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        query = args["query"]
        query_type = args.get("query_type", "natural")
        limit = args.get("limit", 50)

        # For natural language queries, we'd integrate with the RAG system
        # For now, return a structured response
        if query_type == "natural":
            # This would integrate with the actual RAG query system
            results = {
                "query": query,
                "interpretation": "Finding relevant code elements...",
                "results": [],
                "suggestions": [
                    "Try: 'Find all functions that handle authentication'",
                    "Try: 'Show me circular dependencies'",
                    "Try: 'What are the most complex functions?'",
                ],
            }
        else:
            # Cypher query execution would go here
            results = {"query": query, "results": [], "execution_time": "0.05s"}

        return results

    @rate_limit("analyze_security")
    async def _analyze_security(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze security vulnerabilities."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        # Get or create security analyzer
        if "security" not in self.context.active_analyzers:
            self.context.active_analyzers["security"] = SecurityAnalyzer(
                self.context.graph_data
            )

        analyzer = self.context.active_analyzers["security"]
        vulnerabilities = analyzer.find_all_vulnerabilities()

        # Filter by severity if requested
        severity_filter = args.get("severity_filter", "all")
        if severity_filter != "all":
            vulnerabilities = [
                v
                for v in vulnerabilities
                if v["severity"].lower() == severity_filter.lower()
            ]

        return {
            "total_vulnerabilities": len(vulnerabilities),
            "by_severity": analyzer.get_vulnerability_summary(),
            "vulnerabilities": vulnerabilities[:20],  # Limit results
        }

    async def _analyze_data_flow(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze data flow."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        # Get or create data flow analyzer
        if "data_flow" not in self.context.active_analyzers:
            self.context.active_analyzers["data_flow"] = DataFlowAnalyzer(
                self.context.graph_data
            )

        analyzer = self.context.active_analyzers["data_flow"]

        results = {"variable_flows": [], "taint_paths": [], "data_dependencies": []}

        if "variable_name" in args:
            # Analyze specific variable flow
            pass

        if args.get("track_taint", False):
            # Track tainted data flow
            pass

        return results

    async def _analyze_test_coverage(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze test coverage."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        # Get or create test coverage analyzer
        if "test_coverage" not in self.context.active_analyzers:
            self.context.active_analyzers["test_coverage"] = TestCoverageAnalyzer(
                self.context.graph_data
            )

        analyzer = self.context.active_analyzers["test_coverage"]
        untested = analyzer.find_untested_functions()
        coverage = analyzer.calculate_coverage()

        return {
            "overall_coverage": coverage,
            "untested_functions": len(untested),
            "test_statistics": {
                "total_tests": analyzer.get_test_count(),
                "total_assertions": analyzer.get_assertion_count(),
            },
            "untested_samples": untested[:10],  # Sample of untested functions
        }

    async def _analyze_dependencies(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze dependencies."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        results = {
            "total_dependencies": 0,
            "circular_dependencies": [],
            "dependency_graph": {},
        }

        if args.get("check_circular", True):
            # Check for circular dependencies
            pass

        return results

    async def _find_code_patterns(self, args: dict[str, Any]) -> dict[str, Any]:
        """Find code patterns."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        pattern = args["pattern"]
        pattern_type = args.get("pattern_type", "custom")

        results = {
            "pattern": pattern,
            "pattern_type": pattern_type,
            "matches": [],
            "total_matches": 0,
        }

        # Pattern matching logic would go here

        return results

    @rate_limit("export_graph")
    @validate_inputs(path_params={"output_path"})
    async def _export_graph(self, args: dict[str, Any]) -> dict[str, Any]:
        """Export the graph."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        output_path = args["output_path"]
        format_type = args.get("format", "json")

        if format_type == "json":
            export_graph_to_file(output_path)
        else:
            # Other format exports would go here
            raise ValueError(f"Unsupported format: {format_type}")

        return {
            "status": "success",
            "output_path": output_path,
            "format": format_type,
            "size_bytes": Path(output_path).stat().st_size
            if Path(output_path).exists()
            else 0,
        }

    async def _get_code_metrics(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get code metrics."""
        if not self.context.graph_data:
            raise ValueError("No graph loaded. Use load_repository first.")

        metric_types = args.get("metric_types", ["all"])

        metrics = {
            "summary": {
                "total_files": 0,
                "total_functions": 0,
                "total_classes": 0,
                "total_lines": 0,
            },
            "by_language": {},
            "complexity": {},
            "test_metrics": {},
        }

        # Calculate metrics from graph data
        nodes = self.context.graph_data.get("nodes", [])
        for node in nodes:
            if node["label"] == "Module":
                metrics["summary"]["total_files"] += 1
            elif node["label"] == "Function":
                metrics["summary"]["total_functions"] += 1
            elif node["label"] == "Class":
                metrics["summary"]["total_classes"] += 1

        return metrics

    async def _analyze_git_history(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze git history."""
        if not self.context.repo_path:
            raise ValueError("No repository loaded.")

        # Get or create VCS analyzer
        if "vcs" not in self.context.active_analyzers:
            self.context.active_analyzers["vcs"] = VCSAnalyzer(
                str(self.context.repo_path)
            )

        analyzer = self.context.active_analyzers["vcs"]

        since_days = args.get("since_days", 30)
        top_n = args.get("top_contributors", 10)

        # Get commit history
        commits = analyzer.get_commits(since_days=since_days)
        contributors = analyzer.get_top_contributors(top_n=top_n)

        return {
            "total_commits": len(commits),
            "date_range": f"Last {since_days} days",
            "top_contributors": [
                {
                    "name": contrib.name,
                    "email": contrib.email,
                    "commit_count": contrib.commit_count,
                    "lines_added": contrib.lines_added,
                    "lines_removed": contrib.lines_removed,
                }
                for contrib in contributors
            ],
            "recent_commits": [
                {
                    "hash": commit.commit_hash,
                    "author": commit.author_name,
                    "message": commit.message,
                    "timestamp": commit.timestamp.isoformat(),
                }
                for commit in commits[:10]
            ],
        }

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            init_options = InitializationOptions(
                server_name="code-graph-rag",
                server_version="1.0.0",
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )

            await self.server.run(
                read_stream,
                write_stream,
                init_options,
            )


async def main():
    """Main entry point."""
    server = CodeGraphMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
