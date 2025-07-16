"""Security analysis for vulnerability detection and path analysis."""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
from tree_sitter import Node
from loguru import logger
import re
import subprocess
import json


@dataclass
class Vulnerability:
    """Represents a detected security vulnerability."""
    vuln_type: str  # "buffer_overflow", "sql_injection", "xss", "race_condition", etc.
    severity: str  # "high", "medium", "low"
    description: str
    file_path: str
    line_number: int
    code_snippet: str
    cwe_id: Optional[str] = None  # Common Weakness Enumeration ID
    recommendation: Optional[str] = None
    confidence: float = 0.8  # 0.0 to 1.0


@dataclass
class TaintFlow:
    """Represents a taint flow from source to sink."""
    source_type: str  # "user_input", "file", "network", "env_var"
    source_location: Tuple[str, int]  # (file, line)
    sink_type: str  # "exec", "sql", "file_write", "network", "kernel"
    sink_location: Tuple[str, int]  # (file, line)
    flow_path: List[Tuple[str, int]]  # List of (file, line) tuples
    is_validated: bool = False


class SecurityAnalyzer:
    """Analyzes code for security vulnerabilities and taint flows."""
    
    def __init__(self, parser, queries: Dict, language: str):
        self.parser = parser
        self.queries = queries
        self.language = language
        self._source_lines: List[str] = []
        
        # Common vulnerability patterns by language
        self.vulnerability_patterns = self._init_vulnerability_patterns()
        
        # Taint sources and sinks
        self.taint_sources = self._init_taint_sources()
        self.taint_sinks = self._init_taint_sinks()
        
    def analyze_file(self, file_path: str, content: str, module_qn: str) -> List[Vulnerability]:
        """Analyze a file for security vulnerabilities."""
        self._source_lines = content.split("\n")
        vulnerabilities = []
        
        # Parse the file
        tree = self.parser.parse(content.encode("utf-8"))
        root_node = tree.root_node
        
        # Run different analyses based on language
        if self.language == "python":
            vulnerabilities.extend(self._analyze_python_vulnerabilities(root_node, file_path))
        elif self.language in ["javascript", "typescript"]:
            vulnerabilities.extend(self._analyze_javascript_vulnerabilities(root_node, file_path))
        elif self.language == "c":
            vulnerabilities.extend(self._analyze_c_vulnerabilities(root_node, file_path))
        
        # Run pattern-based detection for all languages
        vulnerabilities.extend(self._detect_pattern_vulnerabilities(content, file_path))
        
        # Run semgrep if available
        semgrep_vulns = self._run_semgrep_analysis(file_path, content)
        vulnerabilities.extend(semgrep_vulns)
        
        return vulnerabilities
    
    def analyze_taint_flow(self, file_path: str, content: str, data_flows: List) -> List[TaintFlow]:
        """Analyze taint flows from sources to sinks."""
        taint_flows = []
        
        # Parse the file
        tree = self.parser.parse(content.encode("utf-8"))
        root_node = tree.root_node
        
        # Find taint sources
        sources = self._find_taint_sources(root_node, file_path)
        
        # Find taint sinks
        sinks = self._find_taint_sinks(root_node, file_path)
        
        # Trace flows from sources to sinks using data flow information
        for source in sources:
            for sink in sinks:
                flow_path = self._trace_taint_flow(source, sink, data_flows)
                if flow_path:
                    taint_flow = TaintFlow(
                        source_type=source[0],
                        source_location=(file_path, source[1]),
                        sink_type=sink[0],
                        sink_location=(file_path, sink[1]),
                        flow_path=flow_path,
                        is_validated=self._check_validation(flow_path, root_node)
                    )
                    taint_flows.append(taint_flow)
        
        return taint_flows
    
    def _analyze_python_vulnerabilities(self, root_node: Node, file_path: str) -> List[Vulnerability]:
        """Analyze Python-specific vulnerabilities."""
        vulnerabilities = []
        
        # Check for dangerous function calls
        call_query = """
        (call
            function: [(identifier) @func_name
                      (attribute
                        attribute: (identifier) @method_name)]
            arguments: (argument_list) @args
        ) @call
        """
        
        try:
            query = self.parser.language.query(call_query)
            captures = query.captures(root_node)
            
            # Tree-sitter returns a dict of capture_name -> list of nodes
            for node in captures.get("call", []):
                func_node = node.child_by_field_name("function")
                if func_node:
                    func_name = self._get_node_text(func_node)
                    
                    # Check for eval/exec
                    if func_name in ["eval", "exec"]:
                        vuln = Vulnerability(
                            vuln_type="code_injection",
                            severity="high",
                            description=f"Use of dangerous function '{func_name}' can lead to code injection",
                            file_path=file_path,
                            line_number=node.start_point[0] + 1,
                            code_snippet=self._get_line_snippet(node),
                            cwe_id="CWE-94",
                            recommendation="Avoid using eval/exec, use ast.literal_eval or safer alternatives"
                        )
                        vulnerabilities.append(vuln)
                    
                    # Check for SQL queries (handle both execute and cursor.execute)
                    elif func_name.endswith("execute") or func_name.endswith("executemany") or ".execute" in func_name:
                        # Check if using string concatenation
                        args = node.child_by_field_name("arguments")
                        if args and self._has_string_concatenation(args):
                            vuln = Vulnerability(
                                vuln_type="sql_injection",
                                severity="high",
                                description="Potential SQL injection from string concatenation",
                                file_path=file_path,
                                line_number=node.start_point[0] + 1,
                                code_snippet=self._get_line_snippet(node),
                                cwe_id="CWE-89",
                                recommendation="Use parameterized queries instead of string concatenation"
                            )
                            vulnerabilities.append(vuln)
                    
                    # Check for subprocess with shell=True
                    elif func_name in ["subprocess.run", "subprocess.call", "subprocess.Popen"]:
                        args = node.child_by_field_name("arguments")
                        if args and self._has_shell_true(args):
                            vuln = Vulnerability(
                                vuln_type="command_injection",
                                severity="high",
                                description="Use of subprocess with shell=True is vulnerable to command injection",
                                file_path=file_path,
                                line_number=node.start_point[0] + 1,
                                code_snippet=self._get_line_snippet(node),
                                cwe_id="CWE-78",
                                recommendation="Use shell=False and pass arguments as a list"
                            )
                            vulnerabilities.append(vuln)
        except Exception as e:
            logger.error(f"Error analyzing Python vulnerabilities: {e}")
        
        return vulnerabilities
    
    def _analyze_javascript_vulnerabilities(self, root_node: Node, file_path: str) -> List[Vulnerability]:
        """Analyze JavaScript/TypeScript vulnerabilities."""
        vulnerabilities = []
        
        # Check for dangerous patterns
        js_query = """
        [
            (call_expression
                function: (identifier) @func
            ) @call
            (call_expression
                function: (member_expression
                    property: (property_identifier) @method
                )
            ) @method_call
        ]
        """
        
        try:
            query = self.parser.language.query(js_query)
            captures = query.captures(root_node)
            
            # Check eval usage
            for node in captures.get("func", []):
                if self._get_node_text(node) == "eval":
                    vuln = Vulnerability(
                        vuln_type="code_injection",
                        severity="high",
                        description="Use of eval() can lead to code injection",
                        file_path=file_path,
                        line_number=node.start_point[0] + 1,
                        code_snippet=self._get_line_snippet(node.parent),
                        cwe_id="CWE-94",
                        recommendation="Avoid eval(), use JSON.parse() or safer alternatives"
                    )
                    vulnerabilities.append(vuln)
            
            # Check for innerHTML
            for node in captures.get("method", []):
                if self._get_node_text(node) == "innerHTML":
                    vuln = Vulnerability(
                        vuln_type="xss",
                        severity="high",
                        description="Use of innerHTML can lead to XSS vulnerabilities",
                        file_path=file_path,
                        line_number=node.start_point[0] + 1,
                        code_snippet=self._get_line_snippet(node.parent.parent),
                        cwe_id="CWE-79",
                        recommendation="Use textContent or sanitize HTML input"
                    )
                    vulnerabilities.append(vuln)
        except Exception as e:
            logger.error(f"Error analyzing JavaScript vulnerabilities: {e}")
        
        return vulnerabilities
    
    def _analyze_c_vulnerabilities(self, root_node: Node, file_path: str) -> List[Vulnerability]:
        """Analyze C-specific vulnerabilities."""
        vulnerabilities = []
        
        # Check for dangerous function calls
        c_query = """
        (call_expression
            function: (identifier) @func
        ) @call
        """
        
        try:
            query = self.parser.language.query(c_query)
            captures = query.captures(root_node)
            
            dangerous_functions = {
                "strcpy": ("buffer_overflow", "Use strncpy or strlcpy instead"),
                "strcat": ("buffer_overflow", "Use strncat or strlcat instead"),
                "sprintf": ("buffer_overflow", "Use snprintf instead"),
                "gets": ("buffer_overflow", "Use fgets instead"),
                "scanf": ("buffer_overflow", "Use fgets with sscanf instead"),
                "memcpy": ("buffer_overflow", "Ensure destination buffer is large enough"),
            }
            
            for node in captures.get("func", []):
                func_name = self._get_node_text(node)
                if func_name in dangerous_functions:
                    vuln_type, recommendation = dangerous_functions[func_name]
                    vuln = Vulnerability(
                        vuln_type=vuln_type,
                        severity="high",
                        description=f"Use of unsafe function '{func_name}'",
                        file_path=file_path,
                        line_number=node.start_point[0] + 1,
                        code_snippet=self._get_line_snippet(node.parent),
                        cwe_id="CWE-120",
                        recommendation=recommendation
                    )
                    vulnerabilities.append(vuln)
        except Exception as e:
            logger.error(f"Error analyzing C vulnerabilities: {e}")
        
        # Check for race conditions in kernel code
        if "kernel" in file_path.lower() or "driver" in file_path.lower():
            vulnerabilities.extend(self._check_kernel_race_conditions(root_node, file_path))
        
        return vulnerabilities
    
    def _check_kernel_race_conditions(self, root_node: Node, file_path: str) -> List[Vulnerability]:
        """Check for potential race conditions in kernel code."""
        vulnerabilities = []
        
        # Look for patterns indicating potential race conditions
        # This is a simplified check - real kernel analysis would be more complex
        
        # Check for missing locks around shared data access
        # Look for global variables being accessed without locks
        
        return vulnerabilities
    
    def _detect_pattern_vulnerabilities(self, content: str, file_path: str) -> List[Vulnerability]:
        """Detect vulnerabilities using regex patterns."""
        vulnerabilities = []
        
        patterns = self.vulnerability_patterns.get(self.language, {})
        
        for pattern_name, pattern_info in patterns.items():
            regex = pattern_info["regex"]
            for match in re.finditer(regex, content, re.MULTILINE):
                line_num = content[:match.start()].count('\n') + 1
                vuln = Vulnerability(
                    vuln_type=pattern_info["type"],
                    severity=pattern_info["severity"],
                    description=pattern_info["description"],
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=match.group(0),
                    cwe_id=pattern_info.get("cwe_id"),
                    recommendation=pattern_info.get("recommendation")
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def _run_semgrep_analysis(self, file_path: str, content: str) -> List[Vulnerability]:
        """Run semgrep analysis if available."""
        vulnerabilities = []
        
        try:
            # Check if semgrep is available
            result = subprocess.run(["semgrep", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                return vulnerabilities
            
            # Write content to temporary file for semgrep
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix=Path(file_path).suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            # Run semgrep with auto config
            cmd = ["semgrep", "--config=auto", "--json", tmp_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for finding in data.get("results", []):
                    vuln = Vulnerability(
                        vuln_type=finding.get("check_id", "unknown"),
                        severity=finding.get("extra", {}).get("severity", "medium").lower(),
                        description=finding.get("extra", {}).get("message", "Security issue detected"),
                        file_path=file_path,
                        line_number=finding.get("start", {}).get("line", 0),
                        code_snippet=finding.get("extra", {}).get("lines", ""),
                        cwe_id=self._extract_cwe_from_metadata(finding.get("extra", {})),
                        recommendation=finding.get("extra", {}).get("fix", "")
                    )
                    vulnerabilities.append(vuln)
            
            # Clean up temp file
            Path(tmp_path).unlink()
            
        except Exception as e:
            logger.debug(f"Semgrep analysis not available or failed: {e}")
        
        return vulnerabilities
    
    def _find_taint_sources(self, root_node: Node, file_path: str) -> List[Tuple[str, int]]:
        """Find potential taint sources in the code."""
        sources = []
        
        if self.language == "python":
            # Look for input(), sys.argv, request parameters, etc.
            source_patterns = [
                ("input", "user_input"),
                ("sys.argv", "user_input"),
                ("request.args", "user_input"),
                ("request.form", "user_input"),
                ("request.json", "user_input"),
                ("open", "file"),
                ("environ", "env_var"),
            ]
            
            # Search for these patterns in function calls and attribute access
            # This is simplified - real implementation would use proper AST queries
            
        return sources
    
    def _find_taint_sinks(self, root_node: Node, file_path: str) -> List[Tuple[str, int]]:
        """Find potential taint sinks in the code."""
        sinks = []
        
        if self.language == "python":
            # Look for exec, eval, SQL queries, file operations, etc.
            sink_patterns = [
                ("exec", "exec"),
                ("eval", "exec"),
                ("execute", "sql"),
                ("executemany", "sql"),
                ("subprocess", "exec"),
                ("open", "file_write"),
                ("write", "file_write"),
            ]
            
            # Search for these patterns in function calls
            # This is simplified - real implementation would use proper AST queries
            
        return sinks
    
    def _trace_taint_flow(self, source: Tuple, sink: Tuple, data_flows: List) -> List[Tuple[str, int]]:
        """Trace taint flow from source to sink using data flow information."""
        # This would use the data flow analysis to trace paths
        # For now, return empty list
        return []
    
    def _check_validation(self, flow_path: List[Tuple[str, int]], root_node: Node) -> bool:
        """Check if the taint flow has validation."""
        # Check for validation functions like sanitize, escape, etc.
        return False
    
    def _init_vulnerability_patterns(self) -> Dict[str, Dict]:
        """Initialize regex patterns for vulnerability detection."""
        return {
            "python": {
                "hardcoded_password": {
                    "regex": r'(?i)(password|passwd|pwd|secret|api_key|SECRET_KEY)\s*=\s*["\'][^"\']+["\']',
                    "type": "hardcoded_secret",
                    "severity": "high",
                    "description": "Hardcoded password or secret detected",
                    "cwe_id": "CWE-798",
                    "recommendation": "Use environment variables or secure configuration"
                },
                "weak_random": {
                    "regex": r'\brandom\.(random|randint|choice)\(',
                    "type": "weak_randomness",
                    "severity": "medium",
                    "description": "Use of weak random number generator",
                    "cwe_id": "CWE-330",
                    "recommendation": "Use secrets module for cryptographic randomness"
                },
            },
            "javascript": {
                "hardcoded_password": {
                    "regex": r'(?i)(password|passwd|pwd|secret|api_key)\s*=\s*["\'][^"\']+["\']',
                    "type": "hardcoded_secret", 
                    "severity": "high",
                    "description": "Hardcoded password or secret detected",
                    "cwe_id": "CWE-798",
                    "recommendation": "Use environment variables or secure configuration"
                },
            },
            "c": {
                "format_string": {
                    "regex": r'printf\s*\([^,)]+\)',
                    "type": "format_string",
                    "severity": "high",
                    "description": "Potential format string vulnerability",
                    "cwe_id": "CWE-134",
                    "recommendation": "Use printf with format specifiers"
                },
            }
        }
    
    def _init_taint_sources(self) -> Dict[str, List[str]]:
        """Initialize taint source patterns by language."""
        return {
            "python": ["input", "sys.argv", "request", "environ"],
            "javascript": ["process.argv", "req.body", "req.query", "req.params"],
            "c": ["argv", "getenv", "scanf", "gets", "read"],
        }
    
    def _init_taint_sinks(self) -> Dict[str, List[str]]:
        """Initialize taint sink patterns by language."""
        return {
            "python": ["eval", "exec", "execute", "subprocess", "open"],
            "javascript": ["eval", "innerHTML", "document.write", "exec"],
            "c": ["system", "execve", "strcpy", "sprintf", "fopen"],
        }
    
    def _has_string_concatenation(self, args_node: Node) -> bool:
        """Check if arguments contain string concatenation."""
        # Look for + operator or % formatting in arguments
        for child in args_node.children:
            if child.type == "binary_operator":
                op = child.child_by_field_name("operator")
                if op and self._get_node_text(op) in ["+", "%"]:
                    return True
            elif child.type == "concatenated_string":  # f-string concatenation
                return True
            # Check if first argument is a formatted/concatenated string
            elif child.type in ["string", "formatted_string_literal"]:
                # If it's an f-string, it's potentially dangerous
                if child.type == "formatted_string_literal":
                    return True
        return False
    
    def _has_shell_true(self, args_node: Node) -> bool:
        """Check if arguments contain shell=True."""
        for child in args_node.children:
            if child.type == "keyword_argument":
                name = child.child_by_field_name("name")
                value = child.child_by_field_name("value")
                if name and value:
                    if self._get_node_text(name) == "shell" and self._get_node_text(value) == "True":
                        return True
        return False
    
    def _extract_cwe_from_metadata(self, metadata: Dict) -> Optional[str]:
        """Extract CWE ID from semgrep metadata."""
        cwe = metadata.get("cwe", [])
        if cwe and isinstance(cwe, list) and len(cwe) > 0:
            return cwe[0]
        return None
    
    def _get_line_snippet(self, node: Node) -> str:
        """Get the line of code containing the node."""
        line_num = node.start_point[0]
        if 0 <= line_num < len(self._source_lines):
            return self._source_lines[line_num].strip()
        return ""
    
    def _get_node_text(self, node: Node) -> str:
        """Get text content of a node."""
        start_line = node.start_point[0]
        start_col = node.start_point[1]
        end_line = node.end_point[0]
        end_col = node.end_point[1]
        
        if start_line == end_line:
            return self._source_lines[start_line][start_col:end_col]
        else:
            # Multi-line node
            lines = []
            lines.append(self._source_lines[start_line][start_col:])
            for i in range(start_line + 1, end_line):
                lines.append(self._source_lines[i])
            lines.append(self._source_lines[end_line][:end_col])
            return "\n".join(lines)