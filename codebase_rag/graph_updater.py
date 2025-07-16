import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import toml
from loguru import logger
from tree_sitter import Node, Parser

from codebase_rag.services.graph_service import MemgraphIngestor

from .language_config import LanguageConfig, get_language_config
from .parsers.c_parser import CParser
from .parsers.test_parser import TestParser
from .parsers.test_detector import TestDetector
from .parsers.bdd_parser import BDDParser
from .analysis.data_flow import DataFlowAnalyzer
from .analysis.dependencies import DependencyAnalyzer
from .analysis.security import SecurityAnalyzer


class GraphUpdater:
    """Parses code using Tree-sitter and updates the graph."""

    def __init__(
        self,
        ingestor: MemgraphIngestor,
        repo_path: Path,
        parsers: dict[str, Parser],
        queries: dict[str, Any],
    ):
        self.ingestor = ingestor
        self.repo_path = repo_path
        self.parsers = parsers
        self.queries = queries
        self.project_name = repo_path.name
        self.structural_elements: dict[Path, str | None] = {}
        self.function_registry: dict[str, str] = {}  # {qualified_name: type}
        self.simple_name_lookup: dict[str, set[str]] = defaultdict(set)
        self.ast_cache: dict[Path, tuple[Node, str]] = {}
        self.module_dependencies: dict[str, set[str]] = defaultdict(set)  # Track module dependencies
        self.module_exports: dict[str, list] = defaultdict(list)  # Track module exports
        self.ignore_dirs = {
            ".git",
            "venv",
            ".venv",
            "__pycache__",
            "node_modules",
            "build",
            "dist",
            ".eggs",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".claude",
        }

    def run(self) -> None:
        """Orchestrates the parsing and ingestion process."""
        self.ingestor.ensure_node_batch("Project", {"name": self.project_name})
        logger.info(f"Ensuring Project: {self.project_name}")

        logger.info("--- Pass 1: Identifying Packages and Folders ---")
        self._identify_structure()

        logger.info(
            "\n--- Pass 2: Processing Files, Caching ASTs, and Collecting Definitions ---"
        )
        self._process_files()

        logger.info(
            f"\n--- Found {len(self.function_registry)} functions/methods in codebase ---"
        )
        logger.info("--- Pass 3: Processing Function Calls from AST Cache ---")
        self._process_function_calls()
        
        logger.info("--- Pass 4: Detecting Circular Dependencies ---")
        self._detect_and_report_circular_dependencies()

        logger.info("\n--- Analysis complete. Flushing all data to database... ---")
        self.ingestor.flush_all()

    def _identify_structure(self) -> None:
        """First pass: Walks the directory to find all packages and folders."""
        for root_str, dirs, _ in os.walk(self.repo_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            root = Path(root_str)
            relative_root = root.relative_to(self.repo_path)

            parent_rel_path = relative_root.parent
            parent_container_qn = self.structural_elements.get(parent_rel_path)

            # Check if this directory is a package for any supported language
            is_package = False
            package_indicators = set()

            # Collect package indicators from all language configs
            for lang_name, lang_queries in self.queries.items():
                lang_config = lang_queries["config"]
                package_indicators.update(lang_config.package_indicators)

            # Check if any package indicator exists
            for indicator in package_indicators:
                if (root / indicator).exists():
                    is_package = True
                    break

            if is_package:
                package_qn = ".".join([self.project_name] + list(relative_root.parts))
                self.structural_elements[relative_root] = package_qn
                logger.info(f"  Identified Package: {package_qn}")
                self.ingestor.ensure_node_batch(
                    "Package",
                    {
                        "qualified_name": package_qn,
                        "name": root.name,
                        "path": str(relative_root),
                    },
                )
                parent_label, parent_key, parent_val = (
                    ("Project", "name", self.project_name)
                    if parent_rel_path == Path(".")
                    else ("Package", "qualified_name", parent_container_qn)
                )
                self.ingestor.ensure_relationship_batch(
                    (parent_label, parent_key, parent_val),
                    "CONTAINS_PACKAGE",
                    ("Package", "qualified_name", package_qn),
                )
            elif root != self.repo_path:
                self.structural_elements[relative_root] = None  # Mark as folder
                logger.info(f"  Identified Folder: '{relative_root}'")
                self.ingestor.ensure_node_batch(
                    "Folder", {"path": str(relative_root), "name": root.name}
                )
                parent_label, parent_key, parent_val = (
                    ("Project", "name", self.project_name)
                    if parent_rel_path == Path(".")
                    else (
                        ("Package", "qualified_name", parent_container_qn)
                        if parent_container_qn
                        else ("Folder", "path", str(parent_rel_path))
                    )
                )
                self.ingestor.ensure_relationship_batch(
                    (parent_label, parent_key, parent_val),
                    "CONTAINS_FOLDER",
                    ("Folder", "path", str(relative_root)),
                )

    def _process_files(self) -> None:
        """Second pass: Walks the directory, parses files, and caches their ASTs."""
        for root_str, dirs, files in os.walk(self.repo_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            root = Path(root_str)
            relative_root = root.relative_to(self.repo_path)
            parent_container_qn = self.structural_elements.get(relative_root)

            parent_label, parent_key, parent_val = (
                ("Package", "qualified_name", parent_container_qn)
                if parent_container_qn
                else (
                    ("Folder", "path", str(relative_root))
                    if relative_root != Path(".")
                    else ("Project", "name", self.project_name)
                )
            )

            for file_name in files:
                filepath = root / file_name
                relative_filepath = str(filepath.relative_to(self.repo_path))

                # Create generic File node for all files
                self.ingestor.ensure_node_batch(
                    "File",
                    {
                        "path": relative_filepath,
                        "name": file_name,
                        "extension": filepath.suffix,
                    },
                )
                self.ingestor.ensure_relationship_batch(
                    (parent_label, parent_key, parent_val),
                    "CONTAINS_FILE",
                    ("File", "path", relative_filepath),
                )

                # Check if this file type is supported for parsing
                lang_config = get_language_config(filepath.suffix)
                if lang_config and lang_config.name in self.parsers:
                    self.parse_and_ingest_file(filepath, lang_config.name)
                elif file_name == "pyproject.toml":
                    self._parse_dependencies(filepath)
                elif filepath.suffix == ".feature":
                    # Parse BDD feature files
                    self._parse_bdd_file(filepath)

    def _get_docstring(self, node: Node) -> str | None:
        """Extracts the docstring from a function or class node's body."""
        body_node = node.child_by_field_name("body")
        if not body_node or not body_node.children:
            return None
        first_statement = body_node.children[0]
        if (
            first_statement.type == "expression_statement"
            and first_statement.children[0].type == "string"
        ):
            text = first_statement.children[0].text
            if text is not None:
                return text.decode("utf-8").strip("'\" \n")  # type: ignore[no-any-return]
        return None

    def parse_and_ingest_file(self, file_path: Path, language: str) -> None:
        """
        Parses a file, ingests its structure and definitions,
        and caches the AST for the next pass.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)
        relative_path = file_path.relative_to(self.repo_path)
        relative_path_str = str(relative_path)
        logger.info(f"Parsing and Caching AST for {language}: {relative_path_str}")

        try:
            # Check if language is supported
            if language not in self.parsers or language not in self.queries:
                logger.warning(f"Unsupported language '{language}' for {file_path}")
                return

            source_bytes = file_path.read_bytes()
            parser = self.parsers[language]
            tree = parser.parse(source_bytes)
            root_node = tree.root_node

            # Cache the parsed AST for the function call pass
            self.ast_cache[file_path] = (root_node, language)

            module_qn = ".".join(
                [self.project_name] + list(relative_path.with_suffix("").parts)
            )
            if file_path.name == "__init__.py":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )

            self.ingestor.ensure_node_batch(
                "Module",
                {
                    "qualified_name": module_qn,
                    "name": file_path.name,
                    "path": relative_path_str,
                },
            )

            # Link Module to its parent Package/Folder
            parent_rel_path = relative_path.parent
            parent_container_qn = self.structural_elements.get(parent_rel_path)
            parent_label, parent_key, parent_val = (
                ("Package", "qualified_name", parent_container_qn)
                if parent_container_qn
                else (
                    ("Folder", "path", str(parent_rel_path))
                    if parent_rel_path != Path(".")
                    else ("Project", "name", self.project_name)
                )
            )
            self.ingestor.ensure_relationship_batch(
                (parent_label, parent_key, parent_val),
                "CONTAINS_MODULE",
                ("Module", "qualified_name", module_qn),
            )

            # Check if this is a test file
            test_detector = TestDetector()
            is_test = test_detector.is_test_file(str(file_path), language)
            
            if is_test:
                # Use test parser for test files
                self._ingest_test_file(file_path, source_bytes.decode("utf-8"), module_qn, language)
            elif language == "c":
                # Use C-specific parser for C files
                self._ingest_c_file(file_path, source_bytes.decode("utf-8"), module_qn)
            else:
                # Use regular parsing for other files
                self._ingest_top_level_functions(root_node, module_qn, language)
                self._ingest_classes_and_methods(root_node, module_qn, language)
                
            # Perform data flow analysis if enabled
            if language in ["python", "javascript", "typescript", "c"]:
                self._analyze_data_flow(file_path, source_bytes.decode("utf-8"), module_qn, language)
                
            # Perform dependency analysis
            if language in ["python", "javascript", "typescript", "c"]:
                self._analyze_dependencies(file_path, source_bytes.decode("utf-8"), module_qn, language)
                
            # Perform security analysis
            if language in ["python", "javascript", "typescript", "c"]:
                self._analyze_security(file_path, source_bytes.decode("utf-8"), module_qn, language)

        except Exception as e:
            logger.error(f"Failed to parse or ingest {file_path}: {e}")

    def _ingest_top_level_functions(
        self, root_node: Node, module_qn: str, language: str
    ) -> None:
        lang_queries = self.queries[language]
        lang_config: LanguageConfig = lang_queries["config"]

        captures = lang_queries["functions"].captures(root_node)
        func_nodes = captures.get("function", [])
        for func_node in func_nodes:
            if not isinstance(func_node, Node):
                logger.warning(
                    f"Expected Node object but got {type(func_node)}: {func_node}"
                )
                continue
            if self._is_method(func_node, lang_config):
                continue

            name_node = func_node.child_by_field_name("name")
            if not name_node:
                continue
            text = name_node.text
            if text is None:
                continue
            func_name = text.decode("utf8")
            func_qn = self._build_nested_qualified_name(
                func_node, module_qn, func_name, lang_config
            )

            if not func_qn:
                continue

            props: dict[str, Any] = {
                "qualified_name": func_qn,
                "name": func_name,
                "decorators": [],
                "start_line": func_node.start_point[0] + 1,
                "end_line": func_node.end_point[0] + 1,
                "docstring": self._get_docstring(func_node),
            }
            logger.info(f"  Found Function: {func_name} (qn: {func_qn})")
            self.ingestor.ensure_node_batch("Function", props)

            self.function_registry[func_qn] = "Function"
            self.simple_name_lookup[func_name].add(func_qn)

            parent_type, parent_qn = self._determine_function_parent(
                func_node, module_qn, lang_config
            )
            self.ingestor.ensure_relationship_batch(
                (parent_type, "qualified_name", parent_qn),
                "DEFINES",
                ("Function", "qualified_name", func_qn),
            )

    def _build_nested_qualified_name(
        self,
        func_node: Node,
        module_qn: str,
        func_name: str,
        lang_config: LanguageConfig,
    ) -> str | None:
        path_parts = []
        current = func_node.parent

        if not isinstance(current, Node):
            logger.warning(
                f"Unexpected parent type for node {func_node}: {type(current)}. Skipping."
            )
            return None

        while current and current.type not in lang_config.module_node_types:
            if current.type in lang_config.function_node_types:
                if name_node := current.child_by_field_name("name"):
                    text = name_node.text
                    if text is not None:
                        path_parts.append(text.decode("utf8"))
            elif current.type in lang_config.class_node_types:
                return None  # This is a method

            current = current.parent

        path_parts.reverse()
        if path_parts:
            return f"{module_qn}.{'.'.join(path_parts)}.{func_name}"
        else:
            return f"{module_qn}.{func_name}"

    def _is_method(self, func_node: Node, lang_config: LanguageConfig) -> bool:
        current = func_node.parent
        if not isinstance(current, Node):
            return False

        while current and current.type not in lang_config.module_node_types:
            if current.type in lang_config.class_node_types:
                return True
            current = current.parent
        return False

    def _determine_function_parent(
        self, func_node: Node, module_qn: str, lang_config: LanguageConfig
    ) -> tuple[str, str]:
        current = func_node.parent
        if not isinstance(current, Node):
            return "Module", module_qn

        while current and current.type not in lang_config.module_node_types:
            if current.type in lang_config.function_node_types:
                if name_node := current.child_by_field_name("name"):
                    parent_text = name_node.text
                    if parent_text is None:
                        continue
                    parent_func_name = parent_text.decode("utf8")
                    if parent_func_qn := self._build_nested_qualified_name(
                        current, module_qn, parent_func_name, lang_config
                    ):
                        return "Function", parent_func_qn
                break

            current = current.parent

        return "Module", module_qn

    def _ingest_classes_and_methods(
        self, root_node: Node, module_qn: str, language: str
    ) -> None:
        lang_queries = self.queries[language]

        class_captures = lang_queries["classes"].captures(root_node)
        class_nodes = class_captures.get("class", [])
        for class_node in class_nodes:
            if not isinstance(class_node, Node):
                continue
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                continue
            text = name_node.text
            if text is None:
                continue
            class_name = text.decode("utf8")
            class_qn = f"{module_qn}.{class_name}"
            class_props: dict[str, Any] = {
                "qualified_name": class_qn,
                "name": class_name,
                "decorators": [],
                "start_line": class_node.start_point[0] + 1,
                "end_line": class_node.end_point[0] + 1,
                "docstring": self._get_docstring(class_node),
            }
            logger.info(f"  Found Class: {class_name} (qn: {class_qn})")
            self.ingestor.ensure_node_batch("Class", class_props)
            self.ingestor.ensure_relationship_batch(
                ("Module", "qualified_name", module_qn),
                "DEFINES",
                ("Class", "qualified_name", class_qn),
            )

            body_node = class_node.child_by_field_name("body")
            if not body_node:
                continue

            method_captures = lang_queries["functions"].captures(body_node)
            method_nodes = method_captures.get("function", [])
            for method_node in method_nodes:
                if not isinstance(method_node, Node):
                    continue
                method_name_node = method_node.child_by_field_name("name")
                if not method_name_node:
                    continue
                text = method_name_node.text
                if text is None:
                    continue
                method_name = text.decode("utf8")
                method_qn = f"{class_qn}.{method_name}"
                method_props: dict[str, Any] = {
                    "qualified_name": method_qn,
                    "name": method_name,
                    "decorators": [],
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "docstring": self._get_docstring(method_node),
                }
                logger.info(f"    Found Method: {method_name} (qn: {method_qn})")
                self.ingestor.ensure_node_batch("Method", method_props)

                self.function_registry[method_qn] = "Method"
                self.simple_name_lookup[method_name].add(method_qn)

                self.ingestor.ensure_relationship_batch(
                    ("Class", "qualified_name", class_qn),
                    "DEFINES_METHOD",
                    ("Method", "qualified_name", method_qn),
                )

    def _parse_dependencies(self, filepath: Path) -> None:
        logger.info(f"  Parsing pyproject.toml: {filepath}")
        try:
            data = toml.load(filepath)
            deps = (data.get("tool", {}).get("poetry", {}).get("dependencies", {})) or {
                dep.split(">=")[0].split("==")[0].strip(): dep
                for dep in data.get("project", {}).get("dependencies", [])
            }
            for dep_name, dep_spec in deps.items():
                if dep_name.lower() == "python":
                    continue
                logger.info(f"    Found dependency: {dep_name} (spec: {dep_spec})")
                self.ingestor.ensure_node_batch("ExternalPackage", {"name": dep_name})
                self.ingestor.ensure_relationship_batch(
                    ("Project", "name", self.project_name),
                    "DEPENDS_ON_EXTERNAL",
                    ("ExternalPackage", "name", dep_name),
                    properties={"version_spec": str(dep_spec)},
                )
        except Exception as e:
            logger.error(f"    Error parsing {filepath}: {e}")

    def _ingest_c_file(self, file_path: Path, content: str, module_qn: str) -> None:
        """Ingest C-specific nodes and relationships."""
        logger.info(f"  Processing C file with enhanced parser: {file_path}")
        
        # Create C parser instance
        c_parser = CParser(self.parsers["c"], self.queries["c"])
        nodes, relationships = c_parser.parse_file(str(file_path), content)
        
        # Ingest nodes
        for node in nodes:
            if node.node_type == "function":
                func_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "Function",
                    {
                        "qualified_name": func_qn,
                        "name": node.name,
                        "start_line": node.start_line,
                        "end_line": node.end_line,
                        "return_type": node.properties.get("return_type", "void"),
                        "is_static": node.properties.get("is_static", False),
                        "is_inline": node.properties.get("is_inline", False),
                    }
                )
                self.function_registry[func_qn] = "Function"
                self.simple_name_lookup[node.name].add(func_qn)
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES",
                    ("Function", "qualified_name", func_qn),
                )
                
            elif node.node_type == "struct":
                struct_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "Struct",
                    {
                        "qualified_name": struct_qn,
                        "name": node.name,
                        "start_line": node.start_line,
                        "end_line": node.end_line,
                        "is_anonymous": node.properties.get("is_anonymous", False),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_STRUCT",
                    ("Struct", "qualified_name", struct_qn),
                )
                
            elif node.node_type == "enum":
                enum_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "Enum",
                    {
                        "qualified_name": enum_qn,
                        "name": node.name,
                        "start_line": node.start_line,
                        "end_line": node.end_line,
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_ENUM",
                    ("Enum", "qualified_name", enum_qn),
                )
                
            elif node.node_type == "typedef":
                typedef_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "Typedef",
                    {
                        "qualified_name": typedef_qn,
                        "name": node.name,
                        "base_type": node.properties.get("base_type", ""),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_TYPEDEF",
                    ("Typedef", "qualified_name", typedef_qn),
                )
                
            elif node.node_type == "macro":
                macro_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "Macro",
                    {
                        "qualified_name": macro_qn,
                        "name": node.name,
                        "value": node.properties.get("value", ""),
                        "is_function_like": node.properties.get("is_function_like", False),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_MACRO",
                    ("Macro", "qualified_name", macro_qn),
                )
                
            elif node.node_type == "global_var":
                var_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "GlobalVariable",
                    {
                        "qualified_name": var_qn,
                        "name": node.name,
                        "type": node.properties.get("type", ""),
                        "is_static": node.properties.get("is_static", False),
                        "is_extern": node.properties.get("is_extern", False),
                        "is_const": node.properties.get("is_const", False),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_VARIABLE",
                    ("GlobalVariable", "qualified_name", var_qn),
                )
                
            elif node.node_type == "function_pointer":
                fp_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "FunctionPointer",
                    {
                        "qualified_name": fp_qn,
                        "name": node.name,
                        "return_type": node.properties.get("return_type", ""),
                        "param_types": node.properties.get("param_types", []),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_FUNCTION_POINTER",
                    ("FunctionPointer", "qualified_name", fp_qn),
                )
                
            elif node.node_type == "syscall":
                syscall_qn = f"{module_qn}.sys_{node.name}"
                self.ingestor.ensure_node_batch(
                    "Syscall",
                    {
                        "qualified_name": syscall_qn,
                        "name": node.name,
                        "param_count": node.properties.get("param_count", 0),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_SYSCALL",
                    ("Syscall", "qualified_name", syscall_qn),
                )
                
            elif node.node_type == "concurrency_primitive":
                lock_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "ConcurrencyPrimitive",
                    {
                        "qualified_name": lock_qn,
                        "name": node.name,
                        "primitive_type": node.properties.get("primitive_type", ""),
                        "is_static": node.properties.get("is_static", False),
                        "is_global": node.properties.get("is_global", False),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "DEFINES_LOCK",
                    ("ConcurrencyPrimitive", "qualified_name", lock_qn),
                )
                
            elif node.node_type == "kernel_module":
                km_qn = f"{module_qn}.module"
                self.ingestor.ensure_node_batch(
                    "KernelModule",
                    {
                        "qualified_name": km_qn,
                        "name": node.name,
                        "exported_symbols": node.properties.get("exported_symbols", []),
                        "init_function": node.properties.get("init_function", ""),
                        "exit_function": node.properties.get("exit_function", ""),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "IS_KERNEL_MODULE",
                    ("KernelModule", "qualified_name", km_qn),
                )
        
        # Ingest relationships
        for source, rel_type, target_type, target in relationships:
            if rel_type == "CALLS":
                # Handle function calls
                source_qn = f"{module_qn}.{source}"
                target_qn = f"{module_qn}.{target}"  # Assume same module for now
                if source_qn in self.function_registry:
                    self.ingestor.ensure_relationship_batch(
                        ("Function", "qualified_name", source_qn),
                        "CALLS",
                        ("Function", "qualified_name", target_qn),
                    )
            elif rel_type == "TYPE_OF":
                # Handle typedef relationships
                source_qn = f"{module_qn}.{source}"
                self.ingestor.ensure_relationship_batch(
                    ("Typedef", "qualified_name", source_qn),
                    "TYPE_OF",
                    (target_type, "name", target),
                )
            elif rel_type == "INCLUDES":
                # Handle include relationships
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "INCLUDES",
                    ("File", "path", target),
                )
            elif rel_type == "USES_MACRO":
                # Handle macro usage
                macro_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "USES_MACRO",
                    ("Macro", "qualified_name", macro_qn),
                )
            elif rel_type == "ASSIGNS_FP":
                # Handle function pointer assignments
                fp_qn = f"{module_qn}.{source}"
                func_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("FunctionPointer", "qualified_name", fp_qn),
                    "ASSIGNS_FP",
                    ("Function", "qualified_name", func_qn),
                )
            elif rel_type == "INVOKES_FP":
                # Handle function pointer invocations
                fp_qn = f"{module_qn}.{source}"
                func_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("FunctionPointer", "qualified_name", fp_qn),
                    "INVOKES_FP", 
                    ("Function", "qualified_name", func_qn),
                )
            elif rel_type in ["LOCKS", "UNLOCKS"]:
                # Handle lock operations
                func_qn = f"{module_qn}.{source}"
                lock_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("Function", "qualified_name", func_qn),
                    rel_type,
                    ("ConcurrencyPrimitive", "qualified_name", lock_qn),
                )
            elif rel_type == "EXPORTS":
                # Handle symbol exports
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "EXPORTS",
                    ("Symbol", "name", target),
                )
            elif rel_type in ["MODULE_INIT", "MODULE_EXIT"]:
                # Handle module init/exit functions
                func_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    rel_type,
                    ("Function", "qualified_name", func_qn),
                )
            elif rel_type == "IMPLEMENTS_SYSCALL":
                # Handle syscall implementations
                func_qn = f"{module_qn}.{source}"
                syscall_qn = f"{module_qn}.sys_{target}"
                self.ingestor.ensure_relationship_batch(
                    ("Function", "qualified_name", func_qn),
                    "IMPLEMENTS_SYSCALL",
                    ("Syscall", "qualified_name", syscall_qn),
                )

    def _process_function_calls(self) -> None:
        """Third pass: Process function calls using the cached ASTs."""
        for file_path, (root_node, language) in self.ast_cache.items():
            self._process_calls_in_file(file_path, root_node, language)

    def _process_calls_in_file(
        self, file_path: Path, root_node: Node, language: str
    ) -> None:
        """Process function calls in a specific file using its cached AST."""
        relative_path = file_path.relative_to(self.repo_path)
        logger.debug(f"Processing calls in cached AST for: {relative_path}")

        try:
            module_qn = ".".join(
                [self.project_name] + list(relative_path.with_suffix("").parts)
            )
            if file_path.name == "__init__.py":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )

            self._process_calls_in_functions(root_node, module_qn, language)
            self._process_calls_in_classes(root_node, module_qn, language)

        except Exception as e:
            logger.error(f"Failed to process calls in {file_path}: {e}")

    def _process_calls_in_functions(
        self, root_node: Node, module_qn: str, language: str
    ) -> None:
        lang_queries = self.queries[language]
        lang_config: LanguageConfig = lang_queries["config"]

        captures = lang_queries["functions"].captures(root_node)
        func_nodes = captures.get("function", [])
        for func_node in func_nodes:
            if not isinstance(func_node, Node):
                continue
            if self._is_method(func_node, lang_config):
                continue

            name_node = func_node.child_by_field_name("name")
            if not name_node:
                continue
            text = name_node.text
            if text is None:
                continue
            func_name = text.decode("utf8")
            func_qn = self._build_nested_qualified_name(
                func_node, module_qn, func_name, lang_config
            )

            if func_qn:
                self._ingest_function_calls(
                    func_node, func_qn, "Function", module_qn, language
                )

    def _process_calls_in_classes(
        self, root_node: Node, module_qn: str, language: str
    ) -> None:
        lang_queries = self.queries[language]

        class_captures = lang_queries["classes"].captures(root_node)
        class_nodes = class_captures.get("class", [])
        for class_node in class_nodes:
            if not isinstance(class_node, Node):
                continue
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                continue
            text = name_node.text
            if text is None:
                continue
            class_name = text.decode("utf8")
            class_qn = f"{module_qn}.{class_name}"

            body_node = class_node.child_by_field_name("body")
            if not body_node:
                continue

            method_captures = lang_queries["functions"].captures(body_node)
            method_nodes = method_captures.get("function", [])
            for method_node in method_nodes:
                if not isinstance(method_node, Node):
                    continue
                method_name_node = method_node.child_by_field_name("name")
                if not method_name_node:
                    continue
                text = method_name_node.text
                if text is None:
                    continue
                method_name = text.decode("utf8")
                method_qn = f"{class_qn}.{method_name}"

                self._ingest_function_calls(
                    method_node, method_qn, "Method", module_qn, language
                )

    def _get_call_target_name(self, call_node: Node) -> str | None:
        """Extracts the name of the function or method being called."""
        # For 'call' in Python and 'call_expression' in JS/TS
        if func_child := call_node.child_by_field_name("function"):
            if func_child.type == "identifier":
                text = func_child.text
                if text is not None:
                    return text.decode("utf8")  # type: ignore[no-any-return]
            # Python: obj.method() -> attribute
            elif func_child.type == "attribute":
                if attr_child := func_child.child_by_field_name("attribute"):
                    text = attr_child.text
                    if text is not None:
                        return text.decode("utf8")  # type: ignore[no-any-return]
            # JS/TS: obj.method() -> member_expression
            elif func_child.type == "member_expression":
                if prop_child := func_child.child_by_field_name("property"):
                    text = prop_child.text
                    if text is not None:
                        return text.decode("utf8")  # type: ignore[no-any-return]

        # For 'method_invocation' in Java
        if name_node := call_node.child_by_field_name("name"):
            text = name_node.text
            if text is not None:
                return text.decode("utf8")  # type: ignore[no-any-return]

        return None

    def _ingest_function_calls(
        self,
        caller_node: Node,
        caller_qn: str,
        caller_type: str,
        module_qn: str,
        language: str,
    ) -> None:
        calls_query = self.queries[language].get("calls")
        if not calls_query:
            return

        call_captures = calls_query.captures(caller_node)
        call_nodes = call_captures.get("call", [])
        for call_node in call_nodes:
            if not isinstance(call_node, Node):
                continue
            call_name = self._get_call_target_name(call_node)
            if not call_name:
                continue

            callee_info = self._resolve_function_call(call_name, module_qn)
            if not callee_info:
                continue

            callee_type, callee_qn = callee_info
            logger.debug(
                f"      Found call from {caller_qn} to {call_name} (resolved as {callee_type}:{callee_qn})"
            )

            self.ingestor.ensure_relationship_batch(
                (caller_type, "qualified_name", caller_qn),
                "CALLS",
                (callee_type, "qualified_name", callee_qn),
            )

    def _resolve_function_call(
        self, call_name: str, module_qn: str
    ) -> tuple[str, str] | None:
        # First, try to resolve with fully qualified names
        possible_qns = [
            f"{module_qn}.{call_name}",
            f"{self.project_name}.{call_name}",
            (
                f"{'.'.join(module_qn.split('.')[:-1])}.{call_name}"
                if "." in module_qn
                else None
            ),
        ]
        possible_qns = [qn for qn in possible_qns if qn]

        for qn in possible_qns:
            if qn in self.function_registry:
                return self.function_registry[qn], qn

        # If not found, use the simple name lookup as a fallback
        if call_name in self.simple_name_lookup:
            # This is a simplification.
            for registered_qn in self.simple_name_lookup[call_name]:
                if self._is_likely_same_function(call_name, registered_qn, module_qn):
                    return self.function_registry[registered_qn], registered_qn

        return None

    # TODO: (VA) This is a hack to resolve function calls. We need to improve this.
    def _is_likely_same_function(
        self, call_name: str, registered_qn: str, caller_module_qn: str
    ) -> bool:
        if len(call_name) > 10 or "_" in call_name:
            return True

        caller_parts = caller_module_qn.split(".")
        registered_parts = registered_qn.split(".")

        if len(caller_parts) >= 2 and len(registered_parts) >= 2:
            if caller_parts[:2] == registered_parts[:2]:
                return True

        return False

    def _ingest_test_file(self, file_path: Path, content: str, module_qn: str, language: str) -> None:
        """Ingest test file with test-specific parsing."""
        logger.info(f"  Processing test file: {file_path}")
        
        # Create test parser
        test_parser = TestParser(self.parsers[language], self.queries[language], language)
        nodes, relationships = test_parser.parse_test_file(str(file_path), content)
        
        # Ingest test nodes
        for node in nodes:
            if node.node_type == "test_suite":
                suite_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "TestSuite",
                    {
                        "qualified_name": suite_qn,
                        "name": node.name,
                        "framework": node.properties.get("framework", ""),
                        "start_line": node.start_line,
                        "end_line": node.end_line,
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "CONTAINS_TEST_SUITE",
                    ("TestSuite", "qualified_name", suite_qn),
                )
                
            elif node.node_type == "test_case":
                test_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "TestCase",
                    {
                        "qualified_name": test_qn,
                        "name": node.name,
                        "framework": node.properties.get("framework", ""),
                        "start_line": node.start_line,
                        "end_line": node.end_line,
                    }
                )
                parent_suite = node.properties.get("parent_suite")
                if parent_suite:
                    parent_qn = f"{module_qn}.{parent_suite}"
                    self.ingestor.ensure_relationship_batch(
                        ("TestSuite", "qualified_name", parent_qn),
                        "CONTAINS_TEST",
                        ("TestCase", "qualified_name", test_qn),
                    )
                else:
                    self.ingestor.ensure_relationship_batch(
                        ("Module", "qualified_name", module_qn),
                        "CONTAINS_TEST",
                        ("TestCase", "qualified_name", test_qn),
                    )
                    
            elif node.node_type == "test_function":
                test_qn = f"{module_qn}.{node.name}"
                self.ingestor.ensure_node_batch(
                    "TestFunction",
                    {
                        "qualified_name": test_qn,
                        "name": node.name,
                        "framework": node.properties.get("framework", ""),
                        "start_line": node.start_line,
                        "end_line": node.end_line,
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "CONTAINS_TEST",
                    ("TestFunction", "qualified_name", test_qn),
                )
                
        # Ingest test relationships
        for source, rel_type, target_type, target in relationships:
            if rel_type == "CONTAINS_TEST":
                source_qn = f"{module_qn}.{source}"
                target_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("TestSuite", "qualified_name", source_qn),
                    "CONTAINS_TEST",
                    ("TestCase", "qualified_name", target_qn),
                )
            elif rel_type == "CONTAINS_SUITE":
                source_qn = f"{module_qn}.{source}"
                target_qn = f"{module_qn}.{target}"
                self.ingestor.ensure_relationship_batch(
                    ("TestSuite", "qualified_name", source_qn),
                    "CONTAINS_SUITE",
                    ("TestSuite", "qualified_name", target_qn),
                )
            elif rel_type == "ASSERTS":
                source_qn = f"{module_qn}.{source}"
                # Create assertion node inline
                self.ingestor.ensure_node_batch(
                    "Assertion",
                    {
                        "text": target,
                        "module": module_qn,
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("TestCase", "qualified_name", source_qn),
                    "ASSERTS",
                    ("Assertion", "text", target),
                )
                
        # Also parse for regular functions to find what's being tested
        self._ingest_top_level_functions(
            self.ast_cache[file_path][0], module_qn, language
        )
        self._ingest_classes_and_methods(
            self.ast_cache[file_path][0], module_qn, language
        )
        
    def _parse_bdd_file(self, file_path: Path) -> None:
        """Parse BDD feature files."""
        logger.info(f"  Parsing BDD feature file: {file_path}")
        
        try:
            content = file_path.read_text()
            relative_path = file_path.relative_to(self.repo_path)
            
            # Create BDD parser
            bdd_parser = BDDParser()
            feature = bdd_parser.parse_feature_file(str(file_path), content)
            
            # Create feature node
            feature_qn = f"{self.project_name}.features.{feature.name.replace(' ', '_')}"
            self.ingestor.ensure_node_batch(
                "BDDFeature",
                {
                    "qualified_name": feature_qn,
                    "name": feature.name,
                    "description": feature.description,
                    "tags": feature.tags,
                    "path": str(relative_path),
                }
            )
            
            # Link to project
            self.ingestor.ensure_relationship_batch(
                ("Project", "name", self.project_name),
                "CONTAINS_FEATURE",
                ("BDDFeature", "qualified_name", feature_qn),
            )
            
            # Create scenario nodes
            for scenario in feature.scenarios:
                scenario_qn = f"{feature_qn}.{scenario.name.replace(' ', '_')}"
                self.ingestor.ensure_node_batch(
                    "BDDScenario",
                    {
                        "qualified_name": scenario_qn,
                        "name": scenario.name,
                        "tags": scenario.tags,
                        "step_count": len(scenario.steps),
                    }
                )
                self.ingestor.ensure_relationship_batch(
                    ("BDDFeature", "qualified_name", feature_qn),
                    "CONTAINS_SCENARIO",
                    ("BDDScenario", "qualified_name", scenario_qn),
                )
                
                # Create step nodes
                for i, step in enumerate(scenario.steps):
                    step_id = f"{scenario_qn}.step_{i}"
                    self.ingestor.ensure_node_batch(
                        "BDDStep",
                        {
                            "qualified_name": step_id,
                            "keyword": step.keyword,
                            "text": step.text,
                            "parameters": step.parameters,
                        }
                    )
                    self.ingestor.ensure_relationship_batch(
                        ("BDDScenario", "qualified_name", scenario_qn),
                        "HAS_STEP",
                        ("BDDStep", "qualified_name", step_id),
                    )
                    
        except Exception as e:
            logger.error(f"Failed to parse BDD file {file_path}: {e}")
    
    def _analyze_data_flow(self, file_path: Path, content: str, module_qn: str, language: str) -> None:
        """Perform data flow analysis on a file (REQ-DF-1, REQ-DF-2)."""
        logger.info(f"  Analyzing data flow in: {file_path}")
        
        try:
            # Create data flow analyzer
            analyzer = DataFlowAnalyzer(self.parsers[language], self.queries[language], language)
            variables, flows = analyzer.analyze_file(str(file_path), content, module_qn)
            
            # Ingest variable nodes
            for var in variables:
                self.ingestor.ensure_node_batch(
                    "Variable",
                    var.to_dict()
                )
                
                # Link variable to its scope
                if var.scope:
                    if "." in var.scope:
                        # Function or class scope
                        scope_parts = var.scope.split(".")
                        if scope_parts[-1].startswith(module_qn):
                            # It's a function
                            self.ingestor.ensure_relationship_batch(
                                ("Function", "qualified_name", var.scope),
                                "DECLARES_VARIABLE",
                                ("Variable", "qualified_name", var.qualified_name)
                            )
                        else:
                            # It's a class
                            self.ingestor.ensure_relationship_batch(
                                ("Class", "qualified_name", var.scope),
                                "HAS_FIELD" if var.var_type == "field" else "DECLARES_VARIABLE",
                                ("Variable", "qualified_name", var.qualified_name)
                            )
                    else:
                        # Module scope
                        self.ingestor.ensure_relationship_batch(
                            ("Module", "qualified_name", var.scope),
                            "DECLARES_VARIABLE",
                            ("Variable", "qualified_name", var.qualified_name)
                        )
            
            # Ingest flow edges
            for flow in flows:
                # Create FLOWS_TO relationships
                source_type = self._determine_node_type(flow.source)
                target_type = self._determine_node_type(flow.target)
                
                if source_type and target_type:
                    self.ingestor.ensure_relationship_batch(
                        (source_type, "qualified_name", flow.source),
                        "FLOWS_TO",
                        (target_type, "qualified_name", flow.target),
                        properties=flow.to_dict()
                    )
                    
                    # Create specific flow type edges
                    if flow.flow_type == "modifies":
                        self.ingestor.ensure_relationship_batch(
                            (source_type, "qualified_name", flow.source),
                            "MODIFIES",
                            (target_type, "qualified_name", flow.target),
                            properties={"line_number": flow.line_number}
                        )
                    elif flow.flow_type == "passes_to":
                        self.ingestor.ensure_relationship_batch(
                            (source_type, "qualified_name", flow.source),
                            "PASSES_TO",
                            (target_type, "qualified_name", flow.target),
                            properties={"line_number": flow.line_number}
                        )
                        
            logger.info(f"  Found {len(variables)} variables and {len(flows)} data flows")
            
        except Exception as e:
            logger.error(f"Failed to analyze data flow in {file_path}: {e}")
    
    def _analyze_dependencies(self, file_path: Path, content: str, module_qn: str, language: str) -> None:
        """Analyze module dependencies and exports."""
        logger.info(f"  Analyzing dependencies in: {file_path}")
        
        try:
            # Create dependency analyzer
            analyzer = DependencyAnalyzer(self.parsers[language], self.queries[language], language)
            exports, imports = analyzer.analyze_file(str(file_path), content, module_qn)
            
            # Store exports for this module
            self.module_exports[module_qn] = exports
            
            # Track dependencies
            for imp in imports:
                # Resolve the import to a module qualified name
                dep_module = self._resolve_import_to_module(imp.source_module, module_qn, language)
                if dep_module:
                    self.module_dependencies[module_qn].add(dep_module)
                    
                    # Create IMPORTS relationship
                    self.ingestor.ensure_relationship_batch(
                        (("Module", "qualified_name", module_qn),
                         "IMPORTS",
                         ("Module", "qualified_name", dep_module),
                         {"symbol": imp.symbol, "line_number": imp.line_number})
                    )
                    
                    # If importing specific symbol, create REQUIRES relationship
                    if imp.symbol != "*" and imp.import_type == "named":
                        # Try to find the target symbol
                        target_qn = f"{dep_module}.{imp.symbol}"
                        self.ingestor.ensure_relationship_batch(
                            (("Module", "qualified_name", module_qn),
                             "REQUIRES",
                             ("", "qualified_name", target_qn),  # Could be function, class, or variable
                             {"line_number": imp.line_number})
                        )
            
            # Create EXPORTS relationships for this module's exports
            for export in exports:
                # Create relationship from module to exported symbol
                symbol_qn = f"{module_qn}.{export.symbol}"
                symbol_label = self._determine_export_node_type(export.export_type)
                
                self.ingestor.ensure_relationship_batch(
                    (("Module", "qualified_name", module_qn),
                     "EXPORTS",
                     (symbol_label, "qualified_name", symbol_qn),
                     {"line_number": export.line_number, "is_default": export.is_default})
                )
            
            logger.info(f"  Found {len(exports)} exports and {len(imports)} imports")
            
        except Exception as e:
            logger.error(f"Failed to analyze dependencies in {file_path}: {e}")
    
    def _resolve_import_to_module(self, import_path: str, current_module: str, language: str) -> Optional[str]:
        """Resolve an import path to a module qualified name."""
        if language == "python":
            # Handle relative imports
            if import_path.startswith("."):
                # Count dots for relative level
                level = len(import_path) - len(import_path.lstrip("."))
                relative_path = import_path[level:]
                
                # Go up 'level' directories from current module
                parts = current_module.split(".")
                if level < len(parts):
                    base = ".".join(parts[:-level])
                    if relative_path:
                        return f"{base}.{relative_path}"
                    else:
                        return base
            else:
                # Absolute import - return as is
                return import_path
        
        # For other languages, return the import path as is
        return import_path
    
    def _determine_export_node_type(self, export_type: str) -> str:
        """Determine the graph node label based on export type."""
        type_mapping = {
            "function": "Function",
            "class": "Class", 
            "variable": "Variable",
            "namespace": "Module",
            "default": "Module"
        }
        return type_mapping.get(export_type, "Module")
    
    def _determine_node_type(self, qualified_name: str) -> Optional[str]:
        """Determine the node type from a qualified name."""
        if qualified_name.startswith("return_of_"):
            return "Function"
        elif qualified_name.startswith("param_of_"):
            return "Function"
        else:
            # Check if it's a known variable
            if "." in qualified_name:
                return "Variable"
            return None
    
    def _detect_and_report_circular_dependencies(self) -> None:
        """Detect and report circular dependencies in the module graph."""
        try:
            # Create a dependency analyzer to use its circular detection
            analyzer = DependencyAnalyzer(None, {}, "")
            cycles = analyzer.detect_circular_dependencies(self.module_dependencies)
            
            if cycles:
                logger.warning(f"  Found {len(cycles)} circular dependencies:")
                for i, cycle in enumerate(cycles, 1):
                    logger.warning(f"    Cycle {i}: {' -> '.join(cycle)}")
                    
                    # Create CIRCULAR_DEPENDENCY relationships in the graph
                    for j in range(len(cycle) - 1):
                        self.ingestor.ensure_relationship_batch(
                            (("Module", "qualified_name", cycle[j]),
                             "CIRCULAR_DEPENDENCY",
                             ("Module", "qualified_name", cycle[j + 1]),
                             {"cycle_id": i})
                        )
            else:
                logger.info("  No circular dependencies detected")
                
        except Exception as e:
            logger.error(f"Failed to detect circular dependencies: {e}")
    
    def _analyze_security(self, file_path: Path, content: str, module_qn: str, language: str) -> None:
        """Analyze security vulnerabilities in the file."""
        try:
            # Get parser and queries for the language
            if language not in self.parsers or language not in self.queries:
                logger.warning(f"No parser available for {language}, skipping security analysis")
                return
                
            parser = self.parsers[language]
            queries = self.queries[language]
            
            # Create security analyzer
            analyzer = SecurityAnalyzer(parser, queries, language)
            
            # Analyze for vulnerabilities
            vulnerabilities = analyzer.analyze_file(str(file_path), content, module_qn)
            
            # Create Vulnerability nodes and relationships
            for vuln in vulnerabilities:
                # Create vulnerability node
                vuln_id = f"{module_qn}:{vuln.vuln_type}:{vuln.line_number}"
                self.ingestor.ensure_node(
                    "Vulnerability",
                    {
                        "id": vuln_id,
                        "type": vuln.vuln_type,
                        "severity": vuln.severity,
                        "description": vuln.description,
                        "line_number": vuln.line_number,
                        "code_snippet": vuln.code_snippet[:500],  # Limit snippet size
                        "cwe_id": vuln.cwe_id or "",
                        "recommendation": vuln.recommendation or "",
                        "confidence": vuln.confidence
                    }
                )
                
                # Link vulnerability to module
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "HAS_VULNERABILITY",
                    ("Vulnerability", "id", vuln_id),
                    {"file_path": str(file_path)}
                )
                
            # Get data flows for taint analysis
            data_flows = []
            if hasattr(self, "_last_data_flows"):
                data_flows = self._last_data_flows
                
            # Analyze taint flows
            taint_flows = analyzer.analyze_taint_flow(str(file_path), content, data_flows)
            
            # Create taint flow relationships
            for taint in taint_flows:
                # Create TAINT_FLOW edges
                self.ingestor.ensure_relationship_batch(
                    ("Module", "qualified_name", module_qn),
                    "TAINT_FLOW",
                    ("Module", "qualified_name", module_qn),
                    {
                        "source_type": taint.source_type,
                        "source_line": taint.source_location[1],
                        "sink_type": taint.sink_type,
                        "sink_line": taint.sink_location[1],
                        "is_validated": taint.is_validated,
                        "flow_length": len(taint.flow_path)
                    }
                )
                
                # If unvalidated taint to dangerous sink, create high severity vulnerability
                if not taint.is_validated and taint.sink_type in ["exec", "sql", "kernel"]:
                    vuln_id = f"{module_qn}:taint_flow:{taint.source_location[1]}_to_{taint.sink_location[1]}"
                    self.ingestor.ensure_node(
                        "Vulnerability",
                        {
                            "id": vuln_id,
                            "type": f"{taint.source_type}_to_{taint.sink_type}",
                            "severity": "high",
                            "description": f"Unvalidated {taint.source_type} flows to {taint.sink_type}",
                            "line_number": taint.sink_location[1],
                            "code_snippet": f"Taint from line {taint.source_location[1]} to line {taint.sink_location[1]}",
                            "cwe_id": "CWE-20",  # Improper Input Validation
                            "recommendation": "Validate and sanitize input before use",
                            "confidence": 0.9
                        }
                    )
                    
                    self.ingestor.ensure_relationship_batch(
                        ("Module", "qualified_name", module_qn),
                        "HAS_VULNERABILITY",
                        ("Vulnerability", "id", vuln_id),
                        {"file_path": str(file_path)}
                    )
                    
            if vulnerabilities:
                logger.info(f"  Found {len(vulnerabilities)} vulnerabilities in {file_path.name}")
                    
        except Exception as e:
            logger.error(f"Failed to perform security analysis on {file_path}: {e}")
