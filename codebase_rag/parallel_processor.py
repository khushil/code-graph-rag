"""Parallel processing implementation for scalable code ingestion (REQ-SCL-2)."""

import multiprocessing as mp
import os
import queue
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger
from tqdm import tqdm
from tree_sitter import Parser

from .graph_updater import GraphUpdater
from .language_config import get_language_config
from .memory_optimizer import MemoryOptimizedParser, BatchProcessor, optimize_memory_settings
from .parser_loader import load_parsers
from .services.graph_service import MemgraphIngestor


@dataclass
class FileTask:
    """Represents a file to be processed."""
    file_path: Path
    language: str
    relative_path: str
    parent_info: Tuple[str, str, str]  # (label, key, value)


@dataclass
class ParseResult:
    """Result of parsing a single file."""
    file_path: Path
    language: str
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    functions: Dict[str, str]  # qualified_name -> type
    simple_names: Dict[str, Set[str]]  # simple_name -> {qualified_names}
    error: Optional[str] = None


class ParallelProcessor:
    """Handles parallel processing of code files for scalability (REQ-SCL-2)."""
    
    def __init__(
        self,
        ingestor: MemgraphIngestor,
        repo_path: Path,
        parsers: Dict[str, Parser],
        queries: Dict[str, Any],
        max_workers: Optional[int] = None,
        batch_size: int = 100,
        enable_memory_optimization: bool = True,
    ):
        self.ingestor = ingestor
        self.repo_path = repo_path
        self.parsers = parsers
        self.queries = queries
        self.project_name = repo_path.name
        
        # Determine optimal worker count
        if max_workers is None:
            # Use 80% of CPU cores for CPU-bound parsing
            self.max_workers = max(1, int(mp.cpu_count() * 0.8))
        else:
            self.max_workers = max_workers
            
        self.batch_size = batch_size
        self.progress_lock = Lock()
        self.total_files = 0
        self.processed_files = 0
        
        # Thread-safe collections
        self.function_registry: Dict[str, str] = {}
        self.simple_name_lookup: Dict[str, Set[str]] = {}
        self.registry_lock = Lock()
        
        # Memory optimization
        self.enable_memory_optimization = enable_memory_optimization
        if enable_memory_optimization:
            optimize_memory_settings()
        
        logger.info(f"Initialized ParallelProcessor with {self.max_workers} workers")
    
    def collect_files(self, folder_filter: Optional[str] = None, 
                     file_pattern: Optional[str] = None,
                     skip_tests: bool = False) -> List[FileTask]:
        """Collect all files to be processed (REQ-SCL-1)."""
        files = []
        ignore_dirs = self.get_ignore_dirs()
        
        # Add test directories to ignore list if skip_tests is True
        if skip_tests:
            ignore_dirs.update({"test", "tests", "__tests__", "spec", "specs"})
        
        for root_str, dirs, filenames in os.walk(self.repo_path, topdown=True):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            root = Path(root_str)
            relative_root = root.relative_to(self.repo_path)
            
            # Apply folder filter if specified
            if folder_filter and not str(relative_root).startswith(folder_filter):
                dirs[:] = []  # Don't recurse into filtered directories
                continue
            
            # Determine parent container info
            parent_label, parent_key, parent_val = self._get_parent_info(relative_root)
            
            for filename in filenames:
                filepath = root / filename
                
                # Apply file pattern filter if specified
                if file_pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(filename, file_pattern):
                        continue
                
                # Skip test files if requested
                if skip_tests and self._is_test_file(filepath):
                    continue
                
                # Check if file is parseable
                lang_config = get_language_config(filepath.suffix)
                if lang_config and lang_config.name in self.parsers:
                    relative_path = str(filepath.relative_to(self.repo_path))
                    files.append(FileTask(
                        file_path=filepath,
                        language=lang_config.name,
                        relative_path=relative_path,
                        parent_info=(parent_label, parent_key, parent_val)
                    ))
        
        self.total_files = len(files)
        logger.info(f"Collected {self.total_files} files for processing")
        return files
    
    def process_files_parallel(self, files: List[FileTask]) -> None:
        """Process files in parallel using multiprocessing (REQ-SCL-2)."""
        if not files:
            logger.warning("No files to process")
            return
        
        logger.info(f"Starting parallel processing of {len(files)} files with {self.max_workers} workers")
        
        # Process files in batches
        batches = [files[i:i + self.batch_size] for i in range(0, len(files), self.batch_size)]
        
        with tqdm(total=len(files), desc="Processing files") as pbar:
            for batch in batches:
                results = self._process_batch_parallel(batch)
                
                # Process results in thread-safe manner
                for result in results:
                    if result.error:
                        logger.error(f"Error processing {result.file_path}: {result.error}")
                        pbar.update(1)
                        continue
                    
                    # Update registries in thread-safe manner
                    with self.registry_lock:
                        self.function_registry.update(result.functions)
                        for name, qns in result.simple_names.items():
                            if name not in self.simple_name_lookup:
                                self.simple_name_lookup[name] = set()
                            self.simple_name_lookup[name].update(qns)
                    
                    # Batch insert nodes and relationships
                    self._insert_parse_results(result)
                    
                    pbar.update(1)
                    with self.progress_lock:
                        self.processed_files += 1
        
        logger.info(f"Completed processing {self.processed_files} files")
    
    def _process_batch_parallel(self, batch: List[FileTask]) -> List[ParseResult]:
        """Process a batch of files in parallel."""
        results = []
        
        # Use ProcessPoolExecutor for CPU-bound parsing
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(
                    self._parse_file_worker,
                    task.file_path,
                    task.language,
                    task.relative_path,
                    self.enable_memory_optimization
                ): task
                for task in batch
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process {task.file_path}: {e}")
                    results.append(ParseResult(
                        file_path=task.file_path,
                        language=task.language,
                        nodes=[],
                        relationships=[],
                        functions={},
                        simple_names={},
                        error=str(e)
                    ))
        
        return results
    
    @staticmethod
    def _parse_file_worker(file_path: Path, language: str, relative_path: str, 
                          enable_memory_optimization: bool = True) -> ParseResult:
        """Worker function to parse a single file (runs in separate process)."""
        try:
            # Load parsers in worker process
            parsers, queries = load_parsers()
            
            if language not in parsers or language not in queries:
                return ParseResult(
                    file_path=file_path,
                    language=language,
                    nodes=[],
                    relationships=[],
                    functions={},
                    simple_names={},
                    error=f"Unsupported language: {language}"
                )
            
            parser = parsers[language]
            
            # Use memory optimization for large files
            if enable_memory_optimization:
                mem_optimizer = MemoryOptimizedParser()
                root_node, error = mem_optimizer.parse_file_optimized(file_path, parser, language)
                if error:
                    return ParseResult(
                        file_path=file_path,
                        language=language,
                        nodes=[],
                        relationships=[],
                        functions={},
                        simple_names={},
                        error=error
                    )
            else:
                # Parse the file normally
                source_bytes = file_path.read_bytes()
                tree = parser.parse(source_bytes)
                root_node = tree.root_node
            
            # Extract module information
            module_parts = list(relative_path.replace(file_path.suffix, "").split("/"))
            if file_path.name == "__init__.py" and module_parts:
                module_parts.pop()  # Remove last part for __init__.py
            
            # We need to prepend project name - but we don't have it here
            # For now, use relative path as module qualified name
            module_qn = ".".join(module_parts)
            
            nodes = []
            relationships = []
            functions = {}
            simple_names = {}
            
            # Create module node
            nodes.append({
                "label": "Module",
                "qualified_name": module_qn,
                "name": file_path.name,
                "path": relative_path,
            })
            
            # Extract functions and classes
            lang_config = queries[language]["config"]
            
            # Get functions
            func_captures = queries[language]["functions"].captures(root_node)
            for func_node in func_captures.get("function", []):
                # Check if it's a method
                is_method = False
                parent = func_node.parent
                while parent and parent.type not in lang_config.module_node_types:
                    if parent.type in lang_config.class_node_types:
                        is_method = True
                        break
                    parent = parent.parent
                
                if not is_method:
                    # Extract function name
                    name_node = func_node.child_by_field_name("name")
                    if name_node and name_node.text:
                        func_name = name_node.text.decode("utf8")
                        func_qn = f"{module_qn}.{func_name}"
                        
                        nodes.append({
                            "label": "Function",
                            "qualified_name": func_qn,
                            "name": func_name,
                            "start_line": func_node.start_point[0] + 1,
                            "end_line": func_node.end_point[0] + 1,
                        })
                        
                        functions[func_qn] = "Function"
                        if func_name not in simple_names:
                            simple_names[func_name] = set()
                        simple_names[func_name].add(func_qn)
            
            # Get classes
            class_captures = queries[language]["classes"].captures(root_node)
            for class_node in class_captures.get("class", []):
                name_node = class_node.child_by_field_name("name")
                if name_node and name_node.text:
                    class_name = name_node.text.decode("utf8")
                    class_qn = f"{module_qn}.{class_name}"
                    
                    nodes.append({
                        "label": "Class",
                        "qualified_name": class_qn,
                        "name": class_name,
                        "start_line": class_node.start_point[0] + 1,
                        "end_line": class_node.end_point[0] + 1,
                    })
                    
                    # Extract methods
                    body_node = class_node.child_by_field_name("body")
                    if body_node:
                        method_captures = queries[language]["functions"].captures(body_node)
                        for method_node in method_captures.get("function", []):
                            method_name_node = method_node.child_by_field_name("name")
                            if method_name_node and method_name_node.text:
                                method_name = method_name_node.text.decode("utf8")
                                method_qn = f"{class_qn}.{method_name}"
                                
                                nodes.append({
                                    "label": "Method",
                                    "qualified_name": method_qn,
                                    "name": method_name,
                                    "start_line": method_node.start_point[0] + 1,
                                    "end_line": method_node.end_point[0] + 1,
                                })
                                
                                functions[method_qn] = "Method"
                                if method_name not in simple_names:
                                    simple_names[method_name] = set()
                                simple_names[method_name].add(method_qn)
            
            return ParseResult(
                file_path=file_path,
                language=language,
                nodes=nodes,
                relationships=relationships,
                functions=functions,
                simple_names=simple_names
            )
            
        except Exception as e:
            return ParseResult(
                file_path=file_path,
                language=language,
                nodes=[],
                relationships=[],
                functions={},
                simple_names={},
                error=str(e)
            )
    
    def _insert_parse_results(self, result: ParseResult) -> None:
        """Insert parsing results into the graph (thread-safe)."""
        # Batch insert nodes
        for node_data in result.nodes:
            label = node_data.pop("label")
            self.ingestor.ensure_node_batch(label, node_data)
        
        # Batch insert relationships
        for rel_data in result.relationships:
            self.ingestor.ensure_relationship_batch(
                (rel_data["from_label"], rel_data["from_key"], rel_data["from_value"]),
                rel_data["rel_type"],
                (rel_data["to_label"], rel_data["to_key"], rel_data["to_value"]),
                properties=rel_data.get("properties", {})
            )
    
    def _get_parent_info(self, relative_path: Path) -> Tuple[str, str, str]:
        """Get parent container information for a path."""
        # Simplified version - in reality, we'd check for packages
        if relative_path == Path("."):
            return ("Project", "name", self.project_name)
        else:
            return ("Folder", "path", str(relative_path))
    
    def _is_test_file(self, file_path: Path) -> bool:
        """Check if a file is a test file."""
        test_patterns = ["test_", "_test", "spec_", "_spec"]
        name_lower = file_path.stem.lower()
        return any(pattern in name_lower for pattern in test_patterns)
    
    def get_progress(self) -> Tuple[int, int]:
        """Get current progress (processed, total)."""
        with self.progress_lock:
            return self.processed_files, self.total_files
    
    @staticmethod
    def get_ignore_dirs() -> Set[str]:
        """Get directories to ignore during traversal."""
        return {
            ".git", "venv", ".venv", "__pycache__", "node_modules",
            "build", "dist", ".eggs", ".pytest_cache", ".mypy_cache",
            ".ruff_cache", ".claude", ".tox", ".coverage", "htmlcov",
            ".idea", ".vscode", "__pycache__"
        }