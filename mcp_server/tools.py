"""
MCP Tools for Graph-Code RAG System

This module provides high-level tools that can be used by AI agents
to interact with codebases through the MCP protocol.
"""

from dataclasses import dataclass
from typing import Any

from codebase_rag.query_templates import QUERY_TEMPLATES


@dataclass
class CodeGraphTools:
    """High-level tools for code graph analysis."""

    @staticmethod
    def format_query_result(result: dict[str, Any]) -> str:
        """Format query results for better readability."""
        formatted = []

        if "nodes" in result:
            formatted.append(f"Found {len(result['nodes'])} nodes:")
            for node in result["nodes"][:10]:  # Limit to 10
                node_type = node.get("label", "Unknown")
                name = node.get("properties", {}).get("name", "unnamed")
                path = node.get("properties", {}).get("file_path", "")
                formatted.append(f"  - {node_type}: {name} ({path})")

        if "relationships" in result:
            formatted.append(f"\nFound {len(result['relationships'])} relationships:")
            for rel in result["relationships"][:10]:  # Limit to 10
                rel_type = rel.get("rel_type", "Unknown")
                start = rel.get("start_properties", {}).get("name", "?")
                end = rel.get("end_properties", {}).get("name", "?")
                formatted.append(f"  - {start} --[{rel_type}]--> {end}")

        return "\n".join(formatted)

    @staticmethod
    def suggest_queries(context: str) -> list[str]:
        """Suggest relevant queries based on context."""
        suggestions = []

        # Language-specific suggestions
        if "python" in context.lower():
            suggestions.extend(
                [
                    "Find all classes that inherit from BaseModel",
                    "Show me functions with cyclomatic complexity > 10",
                    "Find all async functions",
                    "What decorators are used in this codebase?",
                ]
            )
        elif "javascript" in context.lower() or "typescript" in context.lower():
            suggestions.extend(
                [
                    "Find all React components",
                    "Show me functions that use async/await",
                    "What npm packages are we depending on?",
                    "Find all API endpoints",
                ]
            )
        elif "c" in context.lower():
            suggestions.extend(
                [
                    "Find all functions using malloc/free",
                    "Show me global variables",
                    "What system calls are used?",
                    "Find potential buffer overflows",
                ]
            )

        # General suggestions
        suggestions.extend(
            [
                "Show me the most complex functions",
                "Find circular dependencies",
                "What functions lack test coverage?",
                "Show recent changes by top contributors",
                "Find security vulnerabilities",
            ]
        )

        return suggestions

    @staticmethod
    def generate_cypher_query(natural_query: str) -> str:
        """Generate a Cypher query from natural language."""
        # This is a simplified version - in production, this would use
        # the actual LLM-based query generation from the main system

        query_lower = natural_query.lower()

        # Pattern matching for common queries
        if "circular" in query_lower and "depend" in query_lower:
            return QUERY_TEMPLATES["circular_dependencies"]["cypher"]
        if "complex" in query_lower and "function" in query_lower:
            return QUERY_TEMPLATES["complex_functions"]["cypher"]
        if "test" in query_lower and "coverage" in query_lower:
            return QUERY_TEMPLATES["test_coverage"]["cypher"]
        if "security" in query_lower or "vulnerab" in query_lower:
            return QUERY_TEMPLATES["security_vulnerabilities"]["cypher"]
        # Default query
        return "MATCH (n) RETURN n LIMIT 25"

    @staticmethod
    def analyze_codebase_health(metrics: dict[str, Any]) -> dict[str, Any]:
        """Analyze overall codebase health based on metrics."""
        health_score = 100
        issues = []
        recommendations = []

        # Check test coverage
        if "test_coverage" in metrics:
            coverage = metrics["test_coverage"].get("overall", 0)
            if coverage < 50:
                health_score -= 20
                issues.append("Low test coverage")
                recommendations.append("Increase test coverage to at least 70%")
            elif coverage < 70:
                health_score -= 10
                issues.append("Moderate test coverage")
                recommendations.append("Consider adding more tests for critical paths")

        # Check complexity
        if "complexity" in metrics:
            high_complexity_count = metrics["complexity"].get(
                "high_complexity_functions", 0
            )
            if high_complexity_count > 20:
                health_score -= 15
                issues.append("Many high-complexity functions")
                recommendations.append(
                    "Refactor complex functions to improve maintainability"
                )

        # Check dependencies
        if "dependencies" in metrics:
            circular_deps = metrics["dependencies"].get("circular_count", 0)
            if circular_deps > 0:
                health_score -= 10
                issues.append(f"{circular_deps} circular dependencies found")
                recommendations.append(
                    "Resolve circular dependencies to improve architecture"
                )

        # Check security
        if "security" in metrics:
            critical_vulns = metrics["security"].get("critical", 0)
            high_vulns = metrics["security"].get("high", 0)
            if critical_vulns > 0:
                health_score -= 25
                issues.append(f"{critical_vulns} critical security vulnerabilities")
                recommendations.append("Address critical security issues immediately")
            if high_vulns > 0:
                health_score -= 15
                issues.append(f"{high_vulns} high severity vulnerabilities")
                recommendations.append("Review and fix high severity security issues")

        # Determine health status
        if health_score >= 90:
            status = "Excellent"
        elif health_score >= 75:
            status = "Good"
        elif health_score >= 60:
            status = "Fair"
        elif health_score >= 40:
            status = "Poor"
        else:
            status = "Critical"

        return {
            "health_score": max(0, health_score),
            "status": status,
            "issues": issues,
            "recommendations": recommendations,
        }

    @staticmethod
    def get_refactoring_suggestions(
        graph_data: dict[str, Any], focus_area: str | None = None
    ) -> list[dict[str, Any]]:
        """Generate refactoring suggestions based on code analysis."""
        suggestions = []

        # Analyze functions
        functions = [n for n in graph_data.get("nodes", []) if n["label"] == "Function"]

        for func in functions:
            props = func.get("properties", {})

            # Check complexity
            complexity = props.get("complexity", 0)
            if complexity > 15:
                suggestions.append(
                    {
                        "type": "high_complexity",
                        "severity": "high" if complexity > 20 else "medium",
                        "target": props.get("name", "unknown"),
                        "file": props.get("file_path", ""),
                        "suggestion": f"Function has complexity {complexity}. Consider breaking it down into smaller functions.",
                        "techniques": [
                            "Extract method refactoring",
                            "Replace conditional with polymorphism",
                            "Introduce parameter object",
                        ],
                    }
                )

            # Check function length
            line_count = props.get("line_count", 0)
            if line_count > 50:
                suggestions.append(
                    {
                        "type": "long_function",
                        "severity": "medium",
                        "target": props.get("name", "unknown"),
                        "file": props.get("file_path", ""),
                        "suggestion": f"Function has {line_count} lines. Consider splitting into smaller, focused functions.",
                        "techniques": [
                            "Extract method",
                            "Replace temp with query",
                            "Decompose conditional",
                        ],
                    }
                )

        # Sort by severity
        suggestions.sort(
            key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3)
        )

        return suggestions[:20]  # Return top 20 suggestions

    @staticmethod
    def generate_documentation_outline(graph_data: dict[str, Any]) -> dict[str, Any]:
        """Generate a documentation outline based on code structure."""
        outline = {
            "project_overview": {
                "total_modules": 0,
                "total_functions": 0,
                "total_classes": 0,
                "languages": set(),
            },
            "architecture": {
                "main_components": [],
                "external_dependencies": [],
                "internal_structure": {},
            },
            "api_documentation": {
                "public_functions": [],
                "classes": [],
                "endpoints": [],
            },
            "testing": {
                "test_suites": [],
                "coverage_areas": [],
            },
        }

        # Analyze nodes
        for node in graph_data.get("nodes", []):
            label = node["label"]
            props = node.get("properties", {})

            if label == "Module":
                outline["project_overview"]["total_modules"] += 1
                lang = props.get("language", "unknown")
                outline["project_overview"]["languages"].add(lang)
            elif label == "Function":
                outline["project_overview"]["total_functions"] += 1
                if props.get("is_public", False):
                    outline["api_documentation"]["public_functions"].append(
                        {
                            "name": props.get("name", "unknown"),
                            "module": props.get("module", ""),
                            "description": props.get("docstring", "No description"),
                        }
                    )
            elif label == "Class":
                outline["project_overview"]["total_classes"] += 1
                outline["api_documentation"]["classes"].append(
                    {
                        "name": props.get("name", "unknown"),
                        "module": props.get("module", ""),
                        "methods": props.get("method_count", 0),
                    }
                )

        # Convert set to list for JSON serialization
        outline["project_overview"]["languages"] = list(
            outline["project_overview"]["languages"]
        )

        return outline
