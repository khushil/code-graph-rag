"""Parallel processing implementation for scalable code ingestion."""

import multiprocessing as mp
import queue
import threading
import time

# Suppress pickle warnings for multiprocessing
import warnings
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from tree_sitter import Node, Parser

warnings.filterwarnings("ignore", category=FutureWarning)

from ..analysis.dependencies import DependencyAnalyzer
from ..language_config import get_language_config
from ..memory_optimizer import memory_monitor
from ..parsers.c_parser import CParser
from ..parsers.config_parser import ConfigParser
from ..parsers.test_detector import TestDetector
from ..parsers.test_parser import TestParser


@dataclass
class FileTask:
    """Represents a file to be processed."""

    filepath: Path
    relative_filepath: str
    parent_label: str
    parent_key: str
    parent_val: str
    language_config: Any | None = None


@dataclass
class ProcessingResult:
    """Result from processing a single file."""

    filepath: Path
    relative_filepath: str
    nodes: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    ast_data: tuple[Node, str] | None
    functions: dict[str, str]  # {qualified_name: type}
    simple_names: dict[str, set[str]]  # {simple_name: {qualified_names}}
    module_qn: str | None
    exports: list[Any]
    dependencies: set[str]
    error: str | None = None


class FileProcessor:
    """Process individual files in worker processes."""

    def __init__(
        self,
        repo_path: Path,
        parsers: dict[str, Parser],
        queries: dict[str, Any],
        project_name: str,
    ):
        self.repo_path = repo_path
        self.parsers = parsers
        self.queries = queries
        self.project_name = project_name

    def process_file(self, task: FileTask) -> ProcessingResult:
        """Process a single file and return results."""
        filepath = task.filepath
        relative_filepath = task.relative_filepath

        # Initialize result
        result = ProcessingResult(
            filepath=filepath,
            relative_filepath=relative_filepath,
            nodes=[],
            relationships=[],
            ast_data=None,
            functions={},
            simple_names=defaultdict(set),
            module_qn=None,
            exports=[],
            dependencies=set(),
        )

        # Monitor memory usage for large files
        with memory_monitor(f"Processing {filepath.name}"):
            try:
                # Determine language and get config
                language_config = get_language_config(
                    filepath, self.parsers, self.queries
                )
                if not language_config:
                    return result

                # Read file content
                try:
                    content = filepath.read_text(encoding="utf-8")
                except Exception as e:
                    logger.error(f"Error reading {filepath}: {e}")
                    result.error = str(e)
                    return result

                # Parse file
                parser = self.parsers[language_config.language]
                tree = parser.parse(content.encode("utf-8"))
                root_node = tree.root_node

                # Cache AST data
                result.ast_data = (root_node, content)

                # Create file node
                file_node = {
                    "label": "File",
                    "properties": {
                        "path": relative_filepath,
                        "name": filepath.name,
                        "language": language_config.language,
                        "size": len(content),
                        "lines": content.count("\n") + 1,
                    },
                }
                result.nodes.append(file_node)

                # Create relationship to parent
                result.relationships.append(
                    {
                        "start_label": task.parent_label,
                        "start_key": task.parent_key,
                        "start_value": task.parent_val,
                        "rel_type": "HAS_FILE",
                        "end_label": "File",
                        "end_key": "path",
                        "end_value": relative_filepath,
                    }
                )

                # Determine module qualified name
                module_qn = self._determine_module_qn(
                    filepath, language_config.language
                )
                result.module_qn = module_qn

                # Process based on file type
                if ConfigParser.is_config_file(filepath):
                    # Process configuration file
                    config_parser = ConfigParser(
                        parser, queries, language_config.language
                    )
                    config_nodes, config_rels = config_parser.parse_config_file(
                        filepath, content, module_qn
                    )
                    result.nodes.extend(config_nodes)
                    result.relationships.extend(config_rels)
                else:
                    # Process source code file
                    nodes, rels, funcs, exports, deps = self._process_source_file(
                        filepath,
                        relative_filepath,
                        content,
                        root_node,
                        language_config,
                        module_qn,
                    )
                    result.nodes.extend(nodes)
                    result.relationships.extend(rels)
                    result.functions.update(funcs)
                    result.exports.extend(exports)
                    result.dependencies.update(deps)

                    # Update simple name lookup
                    for qname, ftype in funcs.items():
                        simple_name = qname.split(".")[-1]
                        result.simple_names[simple_name].add(qname)

            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")
                result.error = str(e)

        return result

    def _determine_module_qn(self, filepath: Path, language: str) -> str | None:
        """Determine the module qualified name for a file."""
        if language == "python":
            parts = filepath.relative_to(self.repo_path).with_suffix("").parts
            return ".".join(parts)
        # Add other language-specific logic as needed
        return None

    def _process_source_file(
        self,
        filepath: Path,
        relative_filepath: str,
        content: str,
        root_node: Node,
        language_config: Any,
        module_qn: str | None,
    ) -> tuple[list[dict], list[dict], dict[str, str], list, set[str]]:
        """Process a source code file and extract nodes/relationships."""
        nodes = []
        relationships = []
        functions = {}
        exports = []
        dependencies = set()

        # Detect if it's a test file
        test_detector = TestDetector()
        is_test, test_framework = test_detector.detect_test_file(
            str(filepath), content, language_config.language
        )

        if is_test:
            # Process as test file
            test_parser = TestParser(
                self.parsers[language_config.language],
                self.queries[language_config.language],
                language_config.language,
            )
            test_nodes, test_rels = test_parser.parse_test_file(
                filepath, content, module_qn, test_framework
            )
            nodes.extend(test_nodes)
            relationships.extend(test_rels)
        else:
            # Process as regular source file
            # Extract language-specific nodes
            if language_config.language == "c":
                c_parser = CParser(
                    self.parsers[language_config.language],
                    self.queries[language_config.language],
                )
                c_nodes, c_rels = c_parser.parse_c_file(
                    str(filepath), content, module_qn or ""
                )
                nodes.extend(c_nodes)
                relationships.extend(c_rels)
            else:
                # Use generic language processing
                extracted_nodes, extracted_rels = self._extract_language_nodes(
                    root_node, language_config, module_qn, relative_filepath
                )
                nodes.extend(extracted_nodes)
                relationships.extend(extracted_rels)

            # Collect function definitions
            for node in nodes:
                if node["label"] in ["Function", "Method"]:
                    qname = node["properties"]["qualified_name"]
                    functions[qname] = node["label"].lower()

            # Analyze dependencies
            dep_analyzer = DependencyAnalyzer(
                self.parsers[language_config.language],
                self.queries[language_config.language],
                language_config.language,
            )
            imports, deps_extracted, exports_extracted = dep_analyzer.analyze_file(
                root_node, relative_filepath, module_qn
            )

            # Create import nodes
            for imp in imports:
                import_node = {
                    "label": "Import",
                    "properties": {
                        "module": imp.module_path,
                        "alias": imp.alias,
                        "is_relative": imp.is_relative,
                        "import_type": imp.import_type,
                        "line_number": imp.line_number,
                    },
                }
                nodes.append(import_node)

                # Link to file
                relationships.append(
                    {
                        "start_label": "File",
                        "start_key": "path",
                        "start_value": relative_filepath,
                        "rel_type": "IMPORTS",
                        "end_label": "Import",
                        "end_key": "module",
                        "end_value": imp.module_path,
                    }
                )

                dependencies.add(imp.module_path)

            exports.extend(exports_extracted)

        return nodes, relationships, functions, exports, dependencies

    def _extract_language_nodes(
        self,
        root_node: Node,
        language_config: Any,
        module_qn: str | None,
        filepath: str,
    ) -> tuple[list[dict], list[dict]]:
        """Extract nodes and relationships for a given language."""
        nodes = []
        relationships = []

        # This is a simplified version - the actual implementation would
        # use the language-specific queries to extract nodes
        # For now, just return empty lists
        return nodes, relationships


class ParallelProcessor:
    """Manages parallel processing of files."""

    def __init__(
        self,
        repo_path: Path,
        parsers: dict[str, Parser],
        queries: dict[str, Any],
        project_name: str,
        num_workers: int | None = None,
    ):
        self.repo_path = repo_path
        self.parsers = parsers
        self.queries = queries
        self.project_name = project_name

        # Determine number of workers
        if num_workers is None:
            # Use 80% of CPU cores by default
            cpu_count = mp.cpu_count()
            self.num_workers = max(1, int(cpu_count * 0.8))
        else:
            self.num_workers = max(1, num_workers)

        logger.info(f"Initializing parallel processor with {self.num_workers} workers")

    def process_files_parallel(
        self, file_tasks: list[FileTask], progress_callback=None
    ) -> tuple[list[ProcessingResult], float]:
        """Process files in parallel and return results."""
        start_time = time.time()
        total_files = len(file_tasks)
        completed = 0
        results = []

        # Create a queue for tasks
        task_queue: mp.Queue[FileTask | None] = mp.Queue()
        result_queue: mp.Queue[ProcessingResult] = mp.Queue()

        # Add all tasks to queue
        for task in file_tasks:
            task_queue.put(task)

        # Add sentinel values to signal workers to stop
        for _ in range(self.num_workers):
            task_queue.put(None)

        # Start worker processes
        workers = []
        for i in range(self.num_workers):
            worker = mp.Process(
                target=self._worker,
                args=(i, task_queue, result_queue),
            )
            worker.start()
            workers.append(worker)

        # Collect results
        while completed < total_files:
            try:
                result = result_queue.get(timeout=0.1)
                results.append(result)
                completed += 1

                if progress_callback:
                    progress_callback(completed, total_files)

                if completed % 100 == 0:
                    logger.info(f"Processed {completed}/{total_files} files")

            except queue.Empty:
                continue

        # Wait for all workers to finish
        for worker in workers:
            worker.join()

        elapsed_time = time.time() - start_time
        logger.info(
            f"Processed {total_files} files in {elapsed_time:.2f}s "
            f"({total_files / elapsed_time:.1f} files/sec)"
        )

        return results, elapsed_time

    def _worker(self, worker_id: int, task_queue: mp.Queue, result_queue: mp.Queue):
        """Worker process that processes files."""
        # Create processor for this worker
        processor = FileProcessor(
            self.repo_path, self.parsers, self.queries, self.project_name
        )

        while True:
            task = task_queue.get()
            if task is None:
                break

            try:
                result = processor.process_file(task)
                result_queue.put(result)
            except Exception as e:
                logger.error(
                    f"Worker {worker_id} error processing {task.filepath}: {e}"
                )
                # Put error result
                error_result = ProcessingResult(
                    filepath=task.filepath,
                    relative_filepath=task.relative_filepath,
                    nodes=[],
                    relationships=[],
                    ast_data=None,
                    functions={},
                    simple_names={},
                    module_qn=None,
                    exports=[],
                    dependencies=set(),
                    error=str(e),
                )
                result_queue.put(error_result)


class ThreadSafeIngestor:
    """Thread-safe wrapper around MemgraphIngestor for parallel updates."""

    def __init__(self, ingestor):
        self.ingestor = ingestor
        self._lock = threading.Lock()
        self._node_buffer = []
        self._relationship_buffer = []
        self._buffer_size = 1000  # Flush when buffer reaches this size

    def add_nodes(self, nodes: list[dict[str, Any]]):
        """Add nodes to buffer (thread-safe)."""
        with self._lock:
            self._node_buffer.extend(nodes)
            if len(self._node_buffer) >= self._buffer_size:
                self._flush_nodes()

    def add_relationships(self, relationships: list[dict[str, Any]]):
        """Add relationships to buffer (thread-safe)."""
        with self._lock:
            self._relationship_buffer.extend(relationships)
            if len(self._relationship_buffer) >= self._buffer_size:
                self._flush_relationships()

    def _flush_nodes(self):
        """Flush node buffer to database (must be called with lock held)."""
        if not self._node_buffer:
            return

        # Group nodes by label
        nodes_by_label = defaultdict(list)
        for node in self._node_buffer:
            nodes_by_label[node["label"]].append(node["properties"])

        # Batch insert by label
        for label, properties_list in nodes_by_label.items():
            self.ingestor.ensure_node_batch(label, properties_list)

        self._node_buffer.clear()

    def _flush_relationships(self):
        """Flush relationship buffer to database (must be called with lock held)."""
        if not self._relationship_buffer:
            return

        # Group relationships by type
        rels_by_type = defaultdict(list)
        for rel in self._relationship_buffer:
            key = (
                rel["start_label"],
                rel["rel_type"],
                rel["end_label"],
            )
            rels_by_type[key].append(rel)

        # Batch insert by type
        for (start_label, rel_type, end_label), rels in rels_by_type.items():
            for rel in rels:
                self.ingestor.ensure_relationship(
                    start_label=start_label,
                    start_key=rel["start_key"],
                    start_value=rel["start_value"],
                    rel_type=rel_type,
                    end_label=end_label,
                    end_key=rel["end_key"],
                    end_value=rel["end_value"],
                    properties=rel.get("properties", {}),
                )

        self._relationship_buffer.clear()

    def flush_all(self):
        """Flush all buffers to database."""
        with self._lock:
            self._flush_nodes()
            self._flush_relationships()
            self.ingestor.flush_all()
