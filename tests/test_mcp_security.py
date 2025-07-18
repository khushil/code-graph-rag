"""
Tests for MCP Server Security Features
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mcp_server.security import (
    RateLimitConfig,
    RateLimiter,
    SecureMCPServer,
    SecurityConfig,
    SecurityValidator,
    rate_limit,
    validate_inputs,
)


class TestRateLimiter:
    """Test the rate limiting functionality."""

    def test_basic_rate_limiting(self):
        """Test basic rate limiting."""
        config = RateLimitConfig(tool_limits={"test_tool": 3}, window_seconds=60)
        limiter = RateLimiter(config)

        # First 3 requests should pass
        assert limiter.check_rate_limit("client1", "test_tool")
        assert limiter.check_rate_limit("client1", "test_tool")
        assert limiter.check_rate_limit("client1", "test_tool")

        # 4th request should fail
        assert not limiter.check_rate_limit("client1", "test_tool")

    def test_different_clients(self):
        """Test rate limiting for different clients."""
        config = RateLimitConfig(tool_limits={"test_tool": 2})
        limiter = RateLimiter(config)

        # Client 1
        assert limiter.check_rate_limit("client1", "test_tool")
        assert limiter.check_rate_limit("client1", "test_tool")
        assert not limiter.check_rate_limit("client1", "test_tool")

        # Client 2 should have its own limit
        assert limiter.check_rate_limit("client2", "test_tool")
        assert limiter.check_rate_limit("client2", "test_tool")
        assert not limiter.check_rate_limit("client2", "test_tool")

    def test_global_rate_limit(self):
        """Test global rate limiting across all tools."""
        config = RateLimitConfig(tool_limits={"tool1": 10, "tool2": 10}, global_limit=5)
        limiter = RateLimiter(config)

        # Use different tools
        assert limiter.check_rate_limit("client1", "tool1")
        assert limiter.check_rate_limit("client1", "tool1")
        assert limiter.check_rate_limit("client1", "tool2")
        assert limiter.check_rate_limit("client1", "tool2")
        assert limiter.check_rate_limit("client1", "tool1")

        # Global limit reached
        assert not limiter.check_rate_limit("client1", "tool1")
        assert not limiter.check_rate_limit("client1", "tool2")

    def test_reset_time(self):
        """Test rate limit reset time calculation."""
        config = RateLimitConfig(window_seconds=3600)
        limiter = RateLimiter(config)

        # Make a request
        limiter.check_rate_limit("client1", "test_tool")

        # Check reset time
        reset_time = limiter.get_reset_time("client1", "test_tool")
        expected_reset = datetime.now() + timedelta(seconds=3600)

        # Allow 1 second tolerance
        assert abs((reset_time - expected_reset).total_seconds()) < 1


class TestSecurityValidator:
    """Test the security validation functionality."""

    def test_path_validation_basic(self):
        """Test basic path validation."""
        validator = SecurityValidator()

        # Valid paths
        assert validator.validate_path("/home/user/project")
        assert validator.validate_path("./src/main.py")
        assert validator.validate_path("data/file.txt")

        # Invalid paths
        assert not validator.validate_path("../../etc/passwd")
        assert not validator.validate_path("~/secrets")
        assert not validator.validate_path("path;rm -rf /")
        assert not validator.validate_path("path|cat /etc/passwd")

    def test_path_validation_with_allowed_paths(self):
        """Test path validation with allowed paths."""
        config = SecurityConfig(
            allowed_paths={Path("/home/user/projects"), Path("/tmp")}
        )
        validator = SecurityValidator(config)

        # Allowed paths
        assert validator.validate_path("/home/user/projects/myapp")
        assert validator.validate_path("/tmp/data.txt")

        # Disallowed paths
        assert not validator.validate_path("/etc/passwd")
        assert not validator.validate_path("/home/user/secrets")

    def test_sensitive_file_blocking(self):
        """Test blocking of sensitive files."""
        validator = SecurityValidator()

        assert not validator.validate_path(".env")
        assert not validator.validate_path(".git/config")
        assert not validator.validate_path("id_rsa")
        assert not validator.validate_path("private.key")
        assert not validator.validate_path("cert.pem")

    def test_query_validation(self):
        """Test query validation."""
        validator = SecurityValidator()

        # Valid queries
        assert validator.validate_query("MATCH (n:Function) RETURN n")
        assert validator.validate_query("Find all functions")

        # Invalid queries
        assert not validator.validate_query("DELETE FROM users")
        assert not validator.validate_query("DETACH DELETE n")
        assert not validator.validate_query("DROP TABLE users")
        assert not validator.validate_query("CREATE INDEX ON :User(name)")

        # Query too long
        long_query = "x" * 20000
        assert not validator.validate_query(long_query)

    def test_output_sanitization(self):
        """Test output sanitization."""
        validator = SecurityValidator()

        # Normal output
        output = {"data": "normal content"}
        assert validator.sanitize_output(output) == output

        # Large output
        config = SecurityConfig(max_result_size=100)
        validator = SecurityValidator(config)
        large_output = {"data": "x" * 1000}
        result = validator.sanitize_output(large_output)
        assert result["error"] == "Output too large"


class MockMCPServer(SecureMCPServer):
    """Mock MCP server for testing security features."""

    @rate_limit("test_tool")
    async def rate_limited_method(self, args):
        return {"status": "success"}

    @validate_inputs(path_params={"file_path"})
    async def path_validated_method(self, args):
        return {"file": args["file_path"]}

    @validate_inputs(query_params={"query"})
    async def query_validated_method(self, args):
        return {"query": args["query"]}


@pytest.mark.asyncio
class TestSecureDecorators:
    """Test the security decorators."""

    async def test_rate_limit_decorator(self):
        """Test rate limit decorator."""
        server = MockMCPServer()
        server.rate_limiter.config.tool_limits["test_tool"] = 2

        # First two calls should succeed
        result1 = await server.rate_limited_method({})
        assert result1["status"] == "success"

        result2 = await server.rate_limited_method({})
        assert result2["status"] == "success"

        # Third call should be rate limited
        result3 = await server.rate_limited_method({})
        assert result3["error"] == "Rate limit exceeded"

    async def test_path_validation_decorator(self):
        """Test path validation decorator."""
        server = MockMCPServer()

        # Valid path
        result = await server.path_validated_method({"file_path": "/home/user/file.py"})
        assert result["file"] == "/home/user/file.py"

        # Invalid path
        result = await server.path_validated_method({"file_path": "../../etc/passwd"})
        assert "error" in result
        assert "Invalid path" in result["error"]

    async def test_query_validation_decorator(self):
        """Test query validation decorator."""
        server = MockMCPServer()

        # Valid query
        result = await server.query_validated_method({"query": "MATCH (n) RETURN n"})
        assert result["query"] == "MATCH (n) RETURN n"

        # Invalid query
        result = await server.query_validated_method({"query": "DELETE FROM users"})
        assert "error" in result
        assert "Invalid query" in result["error"]


class TestSecureMCPServer:
    """Test the SecureMCPServer mixin."""

    def test_client_id_generation(self):
        """Test client ID generation."""
        server1 = MockMCPServer()
        server2 = MockMCPServer()

        # Each server should have a unique client ID
        assert server1.client_id != server2.client_id
        assert len(server1.client_id) == 16
        assert len(server2.client_id) == 16

    def test_configure_security(self):
        """Test security configuration."""
        server = MockMCPServer()

        # Configure rate limiting
        rate_config = RateLimitConfig(
            tool_limits={"custom_tool": 5}, window_seconds=120
        )
        server.configure_security(rate_limit_config=rate_config)
        assert server.rate_limiter.config.tool_limits["custom_tool"] == 5
        assert server.rate_limiter.config.window_seconds == 120

        # Configure security
        sec_config = SecurityConfig(max_query_length=5000, max_path_depth=5)
        server.configure_security(security_config=sec_config)
        assert server.security_validator.config.max_query_length == 5000
        assert server.security_validator.config.max_path_depth == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
