"""Test security analysis functionality."""

import pytest

from codebase_rag.analysis.security import SecurityAnalyzer
from codebase_rag.parser_loader import load_parsers


class TestSecurityAnalysis:
    """Test security vulnerability detection for various languages."""

    @pytest.fixture(scope="class")
    def parsers_and_queries(self):
        """Load parsers and queries once for all tests."""
        parsers, queries = load_parsers()
        return parsers, queries

    def test_python_eval_detection(self, parsers_and_queries):
        """Test detection of eval/exec vulnerabilities in Python."""
        parsers, queries = parsers_and_queries

        python_code = """
user_input = input("Enter expression: ")
result = eval(user_input)  # Dangerous!
print(result)

code = "print('hello')"
exec(code)  # Also dangerous!
"""

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")
        vulnerabilities = analyzer.analyze_file("test.py", python_code, "test_module")

        # Should find 2 code injection vulnerabilities
        code_injections = [
            v for v in vulnerabilities if v.vuln_type == "code_injection"
        ]
        assert len(code_injections) >= 2

        # Check eval vulnerability
        eval_vulns = [v for v in code_injections if "eval" in v.description]
        assert len(eval_vulns) >= 1
        assert eval_vulns[0].severity == "high"
        assert eval_vulns[0].cwe_id == "CWE-94"

        # Check exec vulnerability
        exec_vulns = [v for v in code_injections if "exec" in v.description]
        assert len(exec_vulns) >= 1
        assert exec_vulns[0].severity == "high"

    def test_python_sql_injection_detection(self, parsers_and_queries):
        """Test detection of SQL injection vulnerabilities."""
        parsers, queries = parsers_and_queries

        python_code = """
import sqlite3

def unsafe_query(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Unsafe - string concatenation directly in execute
    cursor.execute("SELECT * FROM users WHERE id = " + user_id)

    # Safe - parameterized query
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

    # Unsafe - string formatting
    cursor.execute(f"SELECT * FROM users WHERE name = '{user_name}'")
"""

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")
        vulnerabilities = analyzer.analyze_file("test.py", python_code, "test_module")

        # Should find SQL injection vulnerabilities
        sql_injections = [v for v in vulnerabilities if v.vuln_type == "sql_injection"]
        assert len(sql_injections) >= 1
        assert sql_injections[0].severity == "high"
        assert sql_injections[0].cwe_id == "CWE-89"

    def test_python_command_injection_detection(self, parsers_and_queries):
        """Test detection of command injection vulnerabilities."""
        parsers, queries = parsers_and_queries

        python_code = """
import subprocess
import os

user_input = input("Enter filename: ")

# Unsafe - shell=True
subprocess.run("ls " + user_input, shell=True)

# Safe - shell=False
subprocess.run(["ls", user_input])

# Also unsafe
os.system("cat " + user_input)
"""

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")
        vulnerabilities = analyzer.analyze_file("test.py", python_code, "test_module")

        # Should find command injection vulnerability
        cmd_injections = [
            v for v in vulnerabilities if v.vuln_type == "command_injection"
        ]
        assert len(cmd_injections) >= 1
        assert cmd_injections[0].severity == "high"
        assert "shell=True" in cmd_injections[0].description

    def test_hardcoded_secrets_detection(self, parsers_and_queries):
        """Test detection of hardcoded secrets."""
        parsers, queries = parsers_and_queries

        python_code = """
# Hardcoded credentials
password = "admin123"
api_key = "sk-1234567890abcdef"
SECRET_KEY = "my-secret-key"

# This should be fine
password_hash = bcrypt.hash(user_password)
"""

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")
        vulnerabilities = analyzer.analyze_file("test.py", python_code, "test_module")

        # Should find hardcoded secrets
        secrets = [v for v in vulnerabilities if v.vuln_type == "hardcoded_secret"]
        assert len(secrets) >= 3
        assert all(v.severity == "high" for v in secrets)
        assert all(v.cwe_id == "CWE-798" for v in secrets)

    def test_weak_randomness_detection(self, parsers_and_queries):
        """Test detection of weak random number generation."""
        parsers, queries = parsers_and_queries

        python_code = """
import random
import secrets

# Weak - not cryptographically secure
token = random.randint(1000, 9999)
session_id = random.choice(string.ascii_letters)

# Strong - cryptographically secure
secure_token = secrets.token_hex(16)
"""

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")
        vulnerabilities = analyzer.analyze_file("test.py", python_code, "test_module")

        # Should find weak randomness
        weak_random = [v for v in vulnerabilities if v.vuln_type == "weak_randomness"]
        assert len(weak_random) >= 2
        assert all(v.severity == "medium" for v in weak_random)
        assert all("secrets" in v.recommendation for v in weak_random)

    def test_javascript_eval_detection(self, parsers_and_queries):
        """Test JavaScript eval detection."""
        parsers, queries = parsers_and_queries

        if "javascript" not in parsers:
            pytest.skip("JavaScript parser not available")

        js_code = """
const userInput = getUserInput();
const result = eval(userInput);  // Dangerous!

// Also dangerous
const code = "alert('hello')";
window.eval(code);
"""

        analyzer = SecurityAnalyzer(
            parsers["javascript"], queries["javascript"], "javascript"
        )
        vulnerabilities = analyzer.analyze_file("test.js", js_code, "test_module")

        # Should find eval vulnerabilities
        code_injections = [
            v for v in vulnerabilities if v.vuln_type == "code_injection"
        ]
        assert len(code_injections) >= 1
        assert code_injections[0].severity == "high"

    def test_javascript_xss_detection(self, parsers_and_queries):
        """Test JavaScript XSS detection."""
        parsers, queries = parsers_and_queries

        if "javascript" not in parsers:
            pytest.skip("JavaScript parser not available")

        js_code = """
const userContent = getUserContent();
document.getElementById('output').innerHTML = userContent;  // XSS vulnerability!

// Safe alternative
document.getElementById('output').textContent = userContent;
"""

        analyzer = SecurityAnalyzer(
            parsers["javascript"], queries["javascript"], "javascript"
        )
        vulnerabilities = analyzer.analyze_file("test.js", js_code, "test_module")

        # Should find XSS vulnerability
        xss_vulns = [v for v in vulnerabilities if v.vuln_type == "xss"]
        assert len(xss_vulns) >= 1
        assert xss_vulns[0].severity == "high"
        assert xss_vulns[0].cwe_id == "CWE-79"

    def test_c_buffer_overflow_detection(self, parsers_and_queries):
        """Test C buffer overflow detection."""
        parsers, queries = parsers_and_queries

        if "c" not in parsers:
            pytest.skip("C parser not available")

        c_code = """
#include <stdio.h>
#include <string.h>

void vulnerable_function(char *user_input) {
    char buffer[100];

    // Dangerous functions
    strcpy(buffer, user_input);  // Buffer overflow!
    strcat(buffer, user_input);  // Also dangerous!
    sprintf(buffer, "User: %s", user_input);  // Dangerous!

    // Safe alternatives exist
    strncpy(buffer, user_input, sizeof(buffer) - 1);
    snprintf(buffer, sizeof(buffer), "User: %s", user_input);
}
"""

        analyzer = SecurityAnalyzer(parsers["c"], queries["c"], "c")
        vulnerabilities = analyzer.analyze_file("test.c", c_code, "test_module")

        # Should find buffer overflow vulnerabilities
        buffer_overflows = [
            v for v in vulnerabilities if v.vuln_type == "buffer_overflow"
        ]
        assert len(buffer_overflows) >= 3
        assert all(v.severity == "high" for v in buffer_overflows)
        assert all(v.cwe_id == "CWE-120" for v in buffer_overflows)

        # Check specific functions
        strcpy_vulns = [v for v in buffer_overflows if "strcpy" in v.description]
        assert len(strcpy_vulns) >= 1
        assert "strncpy" in strcpy_vulns[0].recommendation

    def test_c_format_string_detection(self, parsers_and_queries):
        """Test C format string vulnerability detection."""
        parsers, queries = parsers_and_queries

        if "c" not in parsers:
            pytest.skip("C parser not available")

        c_code = """
#include <stdio.h>

void log_message(char *user_input) {
    // Dangerous - format string vulnerability
    printf(user_input);

    // Safe - use format specifier
    printf("%s", user_input);
}
"""

        analyzer = SecurityAnalyzer(parsers["c"], queries["c"], "c")
        vulnerabilities = analyzer.analyze_file("test.c", c_code, "test_module")

        # Should find format string vulnerability
        format_vulns = [v for v in vulnerabilities if v.vuln_type == "format_string"]
        assert len(format_vulns) >= 1
        assert format_vulns[0].severity == "high"
        assert format_vulns[0].cwe_id == "CWE-134"

    def test_taint_flow_analysis(self, parsers_and_queries):
        """Test taint flow analysis from sources to sinks."""
        parsers, queries = parsers_and_queries

        python_code = """
user_input = input("Enter command: ")  # Taint source
command = "echo " + user_input
os.system(command)  # Taint sink - dangerous!

# With validation
user_input2 = input("Enter number: ")
if user_input2.isdigit():
    value = int(user_input2)  # Validated
    process_value(value)
"""

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")
        _vulnerabilities = analyzer.analyze_file("test.py", python_code, "test_module")

        # In a full implementation, this would track taint flows
        # For now, just verify the analyzer doesn't crash
        data_flows = []  # Would come from data flow analysis
        taint_flows = analyzer.analyze_taint_flow("test.py", python_code, data_flows)

        assert isinstance(taint_flows, list)
