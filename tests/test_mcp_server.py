"""
Tests for the MCP Server
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mcp_server.server import CodeGraphContext, CodeGraphMCPServer
from mcp_server.tools import CodeGraphTools


class TestCodeGraphTools:
    """Test the CodeGraphTools utility class."""

    def test_format_query_result(self):
        """Test formatting of query results."""
        result = {
            "nodes": [
                {
                    "label": "Function",
                    "properties": {"name": "authenticate", "file_path": "auth.py"},
                },
                {
                    "label": "Class",
                    "properties": {"name": "User", "file_path": "models.py"},
                },
            ],
            "relationships": [
                {
                    "rel_type": "CALLS",
                    "start_properties": {"name": "login"},
                    "end_properties": {"name": "authenticate"},
                }
            ],
        }

        formatted = CodeGraphTools.format_query_result(result)
        assert "Found 2 nodes:" in formatted
        assert "Function: authenticate (auth.py)" in formatted
        assert "Class: User (models.py)" in formatted
        assert "Found 1 relationships:" in formatted
        assert "login --[CALLS]--> authenticate" in formatted

    def test_suggest_queries(self):
        """Test query suggestions based on context."""
        # Python context
        suggestions = CodeGraphTools.suggest_queries("python project")
        assert any("BaseModel" in s for s in suggestions)
        assert any("async functions" in s for s in suggestions)

        # JavaScript context
        suggestions = CodeGraphTools.suggest_queries("javascript codebase")
        assert any("React components" in s for s in suggestions)
        assert any("async/await" in s for s in suggestions)

        # C context
        suggestions = CodeGraphTools.suggest_queries("c language kernel")
        assert any("malloc/free" in s for s in suggestions)
        assert any("system calls" in s for s in suggestions)

    def test_generate_cypher_query(self):
        """Test Cypher query generation from natural language."""
        # Test circular dependencies
        query = CodeGraphTools.generate_cypher_query("find circular dependencies")
        assert "path" in query.lower() or "match" in query.lower()

        # Test complex functions
        query = CodeGraphTools.generate_cypher_query("show me complex functions")
        assert "match" in query.lower()

        # Test default query
        query = CodeGraphTools.generate_cypher_query("random query")
        assert "MATCH (n) RETURN n LIMIT 25" == query

    def test_analyze_codebase_health(self):
        """Test codebase health analysis."""
        metrics = {
            "test_coverage": {"overall": 75},
            "complexity": {"high_complexity_functions": 5},
            "dependencies": {"circular_count": 0},
            "security": {"critical": 0, "high": 2},
        }

        health = CodeGraphTools.analyze_codebase_health(metrics)

        assert health["health_score"] > 0
        assert health["health_score"] <= 100
        assert health["status"] in ["Excellent", "Good", "Fair", "Poor", "Critical"]
        assert isinstance(health["issues"], list)
        assert isinstance(health["recommendations"], list)

    def test_get_refactoring_suggestions(self):
        """Test refactoring suggestions generation."""
        graph_data = {
            "nodes": [
                {
                    "label": "Function",
                    "properties": {
                        "name": "process_data",
                        "complexity": 25,
                        "line_count": 150,
                        "file_path": "processor.py",
                    },
                },
                {
                    "label": "Function",
                    "properties": {
                        "name": "simple_func",
                        "complexity": 5,
                        "line_count": 20,
                        "file_path": "utils.py",
                    },
                },
            ]
        }

        suggestions = CodeGraphTools.get_refactoring_suggestions(graph_data)

        assert len(suggestions) > 0
        assert suggestions[0]["type"] == "high_complexity"
        assert suggestions[0]["severity"] == "high"
        assert suggestions[0]["target"] == "process_data"
        assert "techniques" in suggestions[0]

    def test_generate_documentation_outline(self):
        """Test documentation outline generation."""
        graph_data = {
            "nodes": [
                {"label": "Module", "properties": {"language": "python"}},
                {
                    "label": "Function",
                    "properties": {"name": "api_endpoint", "is_public": True},
                },
                {
                    "label": "Class",
                    "properties": {"name": "UserModel", "method_count": 5},
                },
            ]
        }

        outline = CodeGraphTools.generate_documentation_outline(graph_data)

        assert outline["project_overview"]["total_modules"] == 1
        assert outline["project_overview"]["total_functions"] == 1
        assert outline["project_overview"]["total_classes"] == 1
        assert "python" in outline["project_overview"]["languages"]
        assert len(outline["api_documentation"]["public_functions"]) == 1
        assert len(outline["api_documentation"]["classes"]) == 1


@pytest.mark.asyncio
class TestCodeGraphMCPServer:
    """Test the MCP server implementation."""

    async def test_server_initialization(self):
        """Test server initialization."""
        server = CodeGraphMCPServer()
        assert server.server.name == "code-graph-rag"
        assert isinstance(server.context, CodeGraphContext)
        assert len(server.context.available_languages) > 0

    @patch("mcp_server.server.parse_and_store_codebase")
    @patch("mcp_server.server.export_graph_to_file")
    @patch("mcp_server.server.load_graph")
    async def test_load_repository(self, mock_load, mock_export, mock_parse):
        """Test repository loading."""
        # Setup mocks
        mock_graph = Mock()
        mock_graph.to_dict.return_value = {
            "nodes": [{"label": "Function"}],
            "relationships": [],
        }
        mock_load.return_value = mock_graph

        server = CodeGraphMCPServer()

        # Test loading repository
        result = await server._load_repository(
            {"repo_path": "/tmp/test_repo", "clean": True, "parallel": True}
        )

        assert result["status"] == "success"
        assert result["nodes"] == 1
        assert result["relationships"] == 0
        assert server.context.repo_path == Path("/tmp/test_repo")

        mock_parse.assert_called_once()
        mock_export.assert_called_once()
        mock_load.assert_called_once()

    async def test_query_graph_no_data(self):
        """Test querying without loaded graph."""
        server = CodeGraphMCPServer()

        with pytest.raises(ValueError, match="No graph loaded"):
            await server._query_graph({"query": "test query"})

    async def test_query_graph_with_data(self):
        """Test querying with loaded graph."""
        server = CodeGraphMCPServer()
        server.context.graph_data = {"nodes": [], "relationships": []}

        result = await server._query_graph(
            {"query": "Find functions", "query_type": "natural"}
        )

        assert "query" in result
        assert "results" in result
        assert "suggestions" in result

    async def test_analyze_security(self):
        """Test security analysis."""
        server = CodeGraphMCPServer()
        server.context.graph_data = {"nodes": [], "relationships": []}

        with patch("mcp_server.server.SecurityAnalyzer") as mock_analyzer:
            mock_instance = Mock()
            mock_instance.find_all_vulnerabilities.return_value = [
                {"severity": "HIGH", "type": "SQL_INJECTION"}
            ]
            mock_instance.get_vulnerability_summary.return_value = {
                "high": 1,
                "medium": 0,
                "low": 0,
            }
            mock_analyzer.return_value = mock_instance

            result = await server._analyze_security({"severity_filter": "all"})

            assert result["total_vulnerabilities"] == 1
            assert "by_severity" in result
            assert "vulnerabilities" in result

    async def test_get_code_metrics(self):
        """Test code metrics retrieval."""
        server = CodeGraphMCPServer()
        server.context.graph_data = {
            "nodes": [
                {"label": "Module"},
                {"label": "Function"},
                {"label": "Function"},
                {"label": "Class"},
            ],
            "relationships": [],
        }

        result = await server._get_code_metrics({"metric_types": ["all"]})

        assert result["summary"]["total_files"] == 1
        assert result["summary"]["total_functions"] == 2
        assert result["summary"]["total_classes"] == 1

    async def test_export_graph(self):
        """Test graph export functionality."""
        server = CodeGraphMCPServer()
        server.context.graph_data = {"nodes": [], "relationships": []}

        with patch("mcp_server.server.export_graph_to_file") as mock_export:
            result = await server._export_graph(
                {"output_path": "/tmp/graph.json", "format": "json"}
            )

            assert result["status"] == "success"
            assert result["output_path"] == "/tmp/graph.json"
            assert result["format"] == "json"
            mock_export.assert_called_once_with("/tmp/graph.json")

    async def test_analyze_git_history(self):
        """Test git history analysis."""
        server = CodeGraphMCPServer()
        server.context.repo_path = Path("/tmp/test_repo")

        with patch("mcp_server.server.VCSAnalyzer") as mock_vcs:
            mock_instance = Mock()
            mock_instance.get_commits.return_value = []
            mock_instance.get_top_contributors.return_value = []
            mock_vcs.return_value = mock_instance

            result = await server._analyze_git_history(
                {"since_days": 30, "top_contributors": 10}
            )

            assert "total_commits" in result
            assert "date_range" in result
            assert "top_contributors" in result
            assert "recent_commits" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
