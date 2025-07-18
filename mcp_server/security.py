"""
Security and Rate Limiting for MCP Server

This module provides security features including input validation,
rate limiting, and access control for the MCP server.
"""

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Default limits per tool
    tool_limits: dict[str, int] = field(
        default_factory=lambda: {
            "load_repository": 10,  # 10 per hour
            "query_graph": 100,  # 100 per hour
            "analyze_security": 20,  # 20 per hour
            "analyze_data_flow": 50,  # 50 per hour
            "analyze_test_coverage": 30,  # 30 per hour
            "analyze_dependencies": 30,  # 30 per hour
            "find_code_patterns": 50,  # 50 per hour
            "export_graph": 20,  # 20 per hour
            "get_code_metrics": 50,  # 50 per hour
            "analyze_git_history": 30,  # 30 per hour
        }
    )

    # Time window in seconds (default: 1 hour)
    window_seconds: int = 3600

    # Global rate limit (all tools combined)
    global_limit: int = 500  # 500 requests per hour


@dataclass
class SecurityConfig:
    """Configuration for security features."""

    # Allowed repository paths (if empty, all paths allowed)
    allowed_paths: set[Path] = field(default_factory=set)

    # Blocked patterns in paths
    blocked_patterns: set[str] = field(
        default_factory=lambda: {
            "..",  # Path traversal
            "~",  # Home directory
            "$",  # Environment variables
            "|",  # Command injection
            ";",  # Command chaining
            "&",  # Background execution
            ">",  # Output redirection
            "<",  # Input redirection
            "`",  # Command substitution
        }
    )

    # Maximum path depth
    max_path_depth: int = 10

    # Maximum query length
    max_query_length: int = 10000

    # Maximum result size (in bytes)
    max_result_size: int = 10 * 1024 * 1024  # 10MB

    # Sensitive file patterns to block
    sensitive_files: set[str] = field(
        default_factory=lambda: {
            ".env",
            ".git/config",
            ".ssh",
            "*.pem",
            "*.key",
            "*.pfx",
            "id_rsa",
            "id_dsa",
            "id_ecdsa",
            "id_ed25519",
        }
    )


class RateLimiter:
    """Rate limiter for MCP server operations."""

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self.requests = defaultdict(lambda: defaultdict(list))

    def _clean_old_requests(self, client_id: str, tool: str):
        """Remove requests older than the time window."""
        cutoff = time.time() - self.config.window_seconds
        self.requests[client_id][tool] = [
            req_time for req_time in self.requests[client_id][tool] if req_time > cutoff
        ]

    def check_rate_limit(self, client_id: str, tool: str) -> bool:
        """Check if the request is within rate limits."""
        self._clean_old_requests(client_id, tool)

        # Check tool-specific limit
        tool_limit = self.config.tool_limits.get(tool, 50)
        tool_requests = len(self.requests[client_id][tool])
        if tool_requests >= tool_limit:
            return False

        # Check global limit
        total_requests = sum(
            len(requests) for requests in self.requests[client_id].values()
        )
        if total_requests >= self.config.global_limit:
            return False

        # Record the request
        self.requests[client_id][tool].append(time.time())
        return True

    def get_reset_time(self, client_id: str, tool: str) -> datetime:
        """Get the time when the rate limit resets."""
        if not self.requests[client_id][tool]:
            return datetime.now()

        oldest_request = min(self.requests[client_id][tool])
        reset_time = oldest_request + self.config.window_seconds
        return datetime.fromtimestamp(reset_time)


class SecurityValidator:
    """Security validator for MCP server inputs."""

    def __init__(self, config: SecurityConfig | None = None):
        self.config = config or SecurityConfig()

    def validate_path(self, path: str) -> bool:
        """Validate a file path for security issues."""
        try:
            path_obj = Path(path).resolve()

            # Check for blocked patterns
            for pattern in self.config.blocked_patterns:
                if pattern in str(path):
                    return False

            # Check path depth
            if len(path_obj.parts) > self.config.max_path_depth:
                return False

            # Check if path is in allowed list (if configured)
            if self.config.allowed_paths:
                allowed = any(
                    path_obj.is_relative_to(allowed_path)
                    for allowed_path in self.config.allowed_paths
                )
                if not allowed:
                    return False

            # Check for sensitive files
            for pattern in self.config.sensitive_files:
                if path_obj.match(pattern):
                    return False

            return True

        except Exception:
            return False

    def validate_query(self, query: str) -> bool:
        """Validate a query for security issues."""
        # Check length
        if len(query) > self.config.max_query_length:
            return False

        # Check for potential injection patterns
        dangerous_patterns = [
            "DELETE",  # Cypher deletion
            "DETACH",  # Cypher detach
            "DROP",  # SQL/Cypher drop
            "CREATE INDEX",  # Index manipulation
            "CREATE CONSTRAINT",  # Constraint manipulation
            ";",  # Query chaining
            "//",  # Comments that might hide malicious code
            "/*",  # Block comments
        ]

        query_upper = query.upper()
        for pattern in dangerous_patterns:
            if pattern in query_upper:
                return False

        return True

    def sanitize_output(self, output: Any, max_size: int | None = None) -> Any:
        """Sanitize output data for security."""
        max_size = max_size or self.config.max_result_size

        # Convert to string for size check
        output_str = str(output)
        if len(output_str) > max_size:
            return {
                "error": "Output too large",
                "size": len(output_str),
                "max_size": max_size,
            }

        # Remove sensitive information patterns
        sensitive_patterns = [
            r"password\s*=\s*['\"].*?['\"]",
            r"api_key\s*=\s*['\"].*?['\"]",
            r"secret\s*=\s*['\"].*?['\"]",
            r"token\s*=\s*['\"].*?['\"]",
        ]

        # Return sanitized output
        return output


def rate_limit(tool_name: str):
    """Decorator for rate limiting MCP tool calls."""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get client ID (in real implementation, this would come from auth)
            client_id = getattr(self, "client_id", "default")

            # Check rate limit
            if not self.rate_limiter.check_rate_limit(client_id, tool_name):
                reset_time = self.rate_limiter.get_reset_time(client_id, tool_name)
                return {
                    "error": "Rate limit exceeded",
                    "tool": tool_name,
                    "reset_time": reset_time.isoformat(),
                }

            # Execute the function
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_inputs(
    path_params: set[str] | None = None, query_params: set[str] | None = None
):
    """Decorator for validating inputs to MCP tools."""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, args: dict[str, Any], *extra_args, **kwargs):
            # Validate paths
            if path_params:
                for param in path_params:
                    if param in args:
                        path = args[param]
                        if not self.security_validator.validate_path(path):
                            return {
                                "error": f"Invalid path: {path}",
                                "parameter": param,
                            }

            # Validate queries
            if query_params:
                for param in query_params:
                    if param in args:
                        query = args[param]
                        if not self.security_validator.validate_query(query):
                            return {"error": "Invalid query", "parameter": param}

            # Execute the function
            return await func(self, args, *extra_args, **kwargs)

        return wrapper

    return decorator


class SecureMCPServer:
    """Mixin for adding security features to MCP server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rate_limiter = RateLimiter()
        self.security_validator = SecurityValidator()
        self.client_id = self._generate_client_id()

    def _generate_client_id(self) -> str:
        """Generate a unique client ID."""
        # In production, this would use proper authentication
        timestamp = str(time.time()).encode()
        return hashlib.sha256(timestamp).hexdigest()[:16]

    def configure_security(
        self,
        rate_limit_config: RateLimitConfig | None = None,
        security_config: SecurityConfig | None = None,
    ):
        """Configure security settings."""
        if rate_limit_config:
            self.rate_limiter.config = rate_limit_config
        if security_config:
            self.security_validator.config = security_config


# Example usage in the MCP server:
# from mcp_server.security import SecureMCPServer, rate_limit, validate_inputs
#
# class CodeGraphMCPServer(SecureMCPServer):
#
#     @rate_limit("load_repository")
#     @validate_inputs(path_params={"repo_path"})
#     async def _load_repository(self, args: Dict[str, Any]) -> Dict[str, Any]:
#         # Implementation here
#         pass
#
#     @rate_limit("query_graph")
#     @validate_inputs(query_params={"query"})
#     async def _query_graph(self, args: Dict[str, Any]) -> Dict[str, Any]:
#         # Implementation here
#         pass
