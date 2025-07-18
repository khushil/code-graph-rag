#!/usr/bin/env python3
"""
Example MCP Client for Graph-Code RAG System

This demonstrates how AI agents can interact with the Graph-Code RAG
system through the MCP protocol.
"""

import asyncio
import json
import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeGraphMCPClient:
    """Example client for interacting with the Graph-Code RAG MCP server."""

    def __init__(self):
        self.session: ClientSession | None = None

    async def connect(self):
        """Connect to the MCP server."""
        server_params = StdioServerParameters(
            command="python", args=["-m", "mcp_server.server"], env=None
        )

        self.session = await stdio_client(server_params)
        await self.session.initialize()

        logger.info("Connected to Graph-Code RAG MCP Server")
        logger.info(
            f"Server: {self.session.server_info.name} v{self.session.server_info.version}"
        )

    async def load_repository(self, repo_path: str) -> dict[str, Any]:
        """Load a repository for analysis."""
        result = await self.session.call_tool(
            "load_repository", arguments={"repo_path": repo_path, "parallel": True}
        )
        return json.loads(result[0].text)

    async def query_codebase(self, query: str) -> dict[str, Any]:
        """Query the codebase using natural language."""
        result = await self.session.call_tool(
            "query_graph", arguments={"query": query, "query_type": "natural"}
        )
        return json.loads(result[0].text)

    async def analyze_security(self) -> dict[str, Any]:
        """Analyze security vulnerabilities."""
        result = await self.session.call_tool(
            "analyze_security", arguments={"severity_filter": "high"}
        )
        return json.loads(result[0].text)

    async def get_metrics(self) -> dict[str, Any]:
        """Get code quality metrics."""
        result = await self.session.call_tool(
            "get_code_metrics", arguments={"metric_types": ["all"]}
        )
        return json.loads(result[0].text)

    async def find_untested_code(self) -> dict[str, Any]:
        """Find code that lacks test coverage."""
        result = await self.session.call_tool(
            "analyze_test_coverage", arguments={"include_bdd": True}
        )
        return json.loads(result[0].text)

    async def close(self):
        """Close the connection."""
        if self.session:
            await self.session.close()


async def example_workflow():
    """Example workflow showing how to use the MCP client."""
    client = CodeGraphMCPClient()

    try:
        # Connect to server
        await client.connect()
        logger.info("\n" + "=" * 60 + "\n")

        # Load a repository
        logger.info("Loading repository...")
        repo_result = await client.load_repository("/path/to/your/repo")
        logger.info(
            f"Loaded: {repo_result['nodes']} nodes, {repo_result['relationships']} relationships"
        )
        logger.info("\n" + "=" * 60 + "\n")

        # Query the codebase
        logger.info("Querying codebase...")
        queries = [
            "Find all functions that handle authentication",
            "Show me the most complex functions",
            "What are the circular dependencies?",
            "Find functions without test coverage",
        ]

        for query in queries:
            logger.info(f"\nQuery: {query}")
            result = await client.query_codebase(query)
            logger.info(f"Results: {json.dumps(result, indent=2)}")

        logger.info("\n" + "=" * 60 + "\n")

        # Analyze security
        logger.info("Analyzing security...")
        security_result = await client.analyze_security()
        logger.info(f"Found {security_result['total_vulnerabilities']} vulnerabilities")
        logger.info(
            f"By severity: {json.dumps(security_result['by_severity'], indent=2)}"
        )

        logger.info("\n" + "=" * 60 + "\n")

        # Get metrics
        logger.info("Getting code metrics...")
        metrics = await client.get_metrics()
        logger.info(f"Summary: {json.dumps(metrics['summary'], indent=2)}")

        logger.info("\n" + "=" * 60 + "\n")

        # Find untested code
        logger.info("Finding untested code...")
        coverage = await client.find_untested_code()
        logger.info(f"Overall coverage: {coverage['overall_coverage']}%")
        logger.info(f"Untested functions: {coverage['untested_functions']}")

    finally:
        await client.close()


async def ai_agent_example():
    """Example of how an AI agent might use the MCP server."""
    client = CodeGraphMCPClient()

    try:
        await client.connect()

        # AI Agent Task: "Improve code quality in the authentication module"
        logger.info("AI Agent: Analyzing authentication module for improvements...\n")

        # Step 1: Load the repository
        await client.load_repository("/path/to/repo")

        # Step 2: Find authentication-related code
        auth_code = await client.query_codebase(
            "Find all functions and classes related to authentication, login, or user verification"
        )

        # Step 3: Check for security issues
        security = await client.analyze_security()

        # Step 4: Check test coverage
        coverage = await client.find_untested_code()

        # Step 5: Get complexity metrics
        metrics = await client.get_metrics()

        # AI Agent generates recommendations
        logger.info("AI Agent Recommendations:")
        logger.info("1. Security Issues Found:")
        if security["total_vulnerabilities"] > 0:
            logger.info(
                f"   - Found {security['total_vulnerabilities']} security vulnerabilities"
            )
            logger.info("   - Priority: Fix critical and high severity issues first")
        else:
            logger.info("   - No security vulnerabilities detected ✓")

        logger.info("\n2. Test Coverage:")
        logger.info(f"   - Current coverage: {coverage['overall_coverage']}%")
        if coverage["overall_coverage"] < 80:
            logger.info(
                "   - Recommendation: Add tests for critical authentication functions"
            )

        logger.info("\n3. Code Quality:")
        logger.info(
            "   - Review high-complexity functions for refactoring opportunities"
        )
        logger.info(
            "   - Consider extracting common authentication patterns into utilities"
        )

    finally:
        await client.close()


if __name__ == "__main__":
    # Run the example workflow
    logger.info("Graph-Code RAG MCP Client Example")
    logger.info("=================================\n")

    # Choose which example to run
    # asyncio.run(example_workflow())
    asyncio.run(ai_agent_example())
