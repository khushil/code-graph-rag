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
# print(result)

# code = "print('hello')"
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

    def test_build_security_graph(self, parsers_and_queries):
        """Test building security graph with Vulnerability nodes."""
        parsers, queries = parsers_and_queries

        from codebase_rag.analysis.security import TaintFlow, Vulnerability

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")

        # Create test vulnerabilities
        vulnerabilities = [
            Vulnerability(
                vuln_type="sql_injection",
                severity="critical",
                description="SQL injection vulnerability",
                file_path="module.py",
                line_number=100,
                code_snippet="execute(query)",
                cwe_id="CWE-89",
                recommendation="Use parameterized queries",
                confidence=0.9,
            ),
            Vulnerability(
                vuln_type="xss",
                severity="high",
                description="Cross-site scripting vulnerability",
                file_path="module.py",
                line_number=200,
                code_snippet="innerHTML = user_input",
                cwe_id="CWE-79",
                recommendation="Sanitize user input",
                confidence=0.85,
            ),
        ]

        # Create test taint flows
        taint_flows = [
            TaintFlow(
                source_type="user_input",
                source_location=("module.py", 50),
                sink_type="sql",
                sink_location=("module.py", 100),
                flow_path=[("module.py", 50), ("module.py", 75), ("module.py", 100)],
                is_validated=False,
            )
        ]

        nodes, relationships = analyzer.build_security_graph(
            "module", vulnerabilities, taint_flows
        )

        # Check Vulnerability nodes
        assert len(nodes) == 2
        vuln_node = nodes[0]
        assert vuln_node["label"] == "Vulnerability"
        assert vuln_node["properties"]["type"] == "sql_injection"
        assert vuln_node["properties"]["severity"] == "critical"
        assert vuln_node["properties"]["cwe_id"] == "CWE-89"
        assert vuln_node["properties"]["confidence"] == 0.9

        # Check HAS_VULNERABILITY relationships
        has_vuln_rels = [
            r for r in relationships if r["rel_type"] == "HAS_VULNERABILITY"
        ]
        assert len(has_vuln_rels) == 2
        assert has_vuln_rels[0]["start_value"] == "module"
        assert has_vuln_rels[0]["properties"]["severity"] == "critical"

        # Check EXPLOIT_PATH relationships
        exploit_rels = [r for r in relationships if r["rel_type"] == "EXPLOIT_PATH"]
        assert len(exploit_rels) == 2  # Two segments in the path

        # Check TAINT_FLOW relationship
        taint_rels = [r for r in relationships if r["rel_type"] == "TAINT_FLOW"]
        assert len(taint_rels) == 1
        assert taint_rels[0]["properties"]["source_type"] == "user_input"
        assert taint_rels[0]["properties"]["sink_type"] == "sql"
        assert not taint_rels[0]["properties"]["is_validated"]

    def test_generate_security_report(self, parsers_and_queries):
        """Test generating comprehensive security report."""
        parsers, queries = parsers_and_queries

        from codebase_rag.analysis.security import TaintFlow, Vulnerability

        analyzer = SecurityAnalyzer(parsers["python"], queries["python"], "python")

        vulnerabilities = [
            Vulnerability(
                vuln_type="sql_injection",
                severity="critical",
                description="SQL injection",
                file_path="file1.py",
                line_number=10,
                code_snippet="execute(query)",
                cwe_id="CWE-89",
            ),
            Vulnerability(
                vuln_type="xss",
                severity="high",
                description="XSS vulnerability",
                file_path="file2.py",
                line_number=20,
                code_snippet="innerHTML",
                cwe_id="CWE-79",
            ),
            Vulnerability(
                vuln_type="hardcoded_secret",
                severity="medium",
                description="Hardcoded password",
                file_path="file3.py",
                line_number=30,
                code_snippet="password='secret'",
                cwe_id="CWE-798",
            ),
        ]

        taint_flows = [
            TaintFlow(
                source_type="user_input",
                source_location=("file1.py", 5),
                sink_type="sql",
                sink_location=("file1.py", 10),
                flow_path=[("file1.py", 5), ("file1.py", 10)],
                is_validated=False,
            ),
            TaintFlow(
                source_type="env_var",
                source_location=("file2.py", 15),
                sink_type="exec",
                sink_location=("file2.py", 25),
                flow_path=[("file2.py", 15), ("file2.py", 25)],
                is_validated=True,
            ),
        ]

        report = analyzer.generate_security_report(vulnerabilities, taint_flows)

        # Check vulnerability counts
        assert report["total_vulnerabilities"] == 3
        assert report["critical_count"] == 1
        assert report["high_count"] == 1
        assert report["medium_count"] == 1
        assert report["low_count"] == 0

        # Check vulnerability breakdown
        assert report["vulnerability_breakdown"]["sql_injection"] == 1
        assert report["vulnerability_breakdown"]["xss"] == 1
        assert report["vulnerability_breakdown"]["hardcoded_secret"] == 1

        # Check CWE distribution
        assert report["cwe_distribution"]["CWE-89"] == 1
        assert report["cwe_distribution"]["CWE-79"] == 1
        assert report["cwe_distribution"]["CWE-798"] == 1

        # Check taint flows
        assert report["taint_flows"]["total"] == 2
        assert report["taint_flows"]["validated"] == 1
        assert report["taint_flows"]["unvalidated"] == 1
        assert report["taint_flows"]["by_source_type"]["user_input"] == 1
        assert report["taint_flows"]["by_source_type"]["env_var"] == 1
        assert report["taint_flows"]["by_sink_type"]["sql"] == 1
        assert report["taint_flows"]["by_sink_type"]["exec"] == 1

        # Check recommendations
        assert len(report["recommendations"]) >= 3
        assert any("critical" in r for r in report["recommendations"])
        assert any("parameterized queries" in r for r in report["recommendations"])
        assert any("validation" in r for r in report["recommendations"])
