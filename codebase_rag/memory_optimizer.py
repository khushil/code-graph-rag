"""Memory optimization utilities for handling large files (REQ-SCL-3)."""

import gc
import mmap
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
from loguru import logger


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    total_memory: int
    available_memory: int
    used_memory: int
    percent_used: float
    process_memory: int

    @classmethod
    def current(cls) -> "MemoryStats":
        """Get current memory statistics."""
        memory = psutil.virtual_memory()
        process = psutil.Process()
        process_mem = process.memory_info().rss

        return cls(
            total_memory=memory.total,
            available_memory=memory.available,
            used_memory=memory.used,
            percent_used=memory.percent,
            process_memory=process_mem,
        )

    def log_stats(self, context: str = "") -> None:
        """Log memory statistics."""
        logger.debug(
            f"Memory stats {context}: "
            f"Process: {self.process_memory / 1024 / 1024:.1f}MB, "
            f"System: {self.percent_used:.1f}% used, "
            f"Available: {self.available_memory / 1024 / 1024:.1f}MB"
        )


class StreamingFileReader:
    """Reads large files in chunks to minimize memory usage."""

    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB chunks
        self.chunk_size = chunk_size

    def read_file_chunks(self, file_path: Path) -> Generator[bytes, None, None]:
        """Read file in chunks."""
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk

    def read_file_lines(
        self, file_path: Path, encoding: str = "utf-8"
    ) -> Generator[str, None, None]:
        """Read file line by line."""
        with open(file_path, encoding=encoding) as f:
            for line in f:
                yield line.rstrip("\n\r")

    @contextmanager
    def mmap_file(self, file_path: Path):
        """Memory-map a file for efficient random access."""
        with open(file_path, "rb") as f:
            # Empty files cannot be mmap'd
            if os.path.getsize(file_path) == 0:
                yield b""
                return

            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                yield mmapped


class MemoryOptimizedParser:
    """Parser that optimizes memory usage for large files."""

    def __init__(
        self,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        gc_threshold: float = 80.0,
    ):  # Trigger GC at 80% memory
        self.max_file_size = max_file_size
        self.gc_threshold = gc_threshold
        self.reader = StreamingFileReader()
        self._last_gc_memory = 0

    def should_use_streaming(self, file_path: Path) -> bool:
        """Determine if file should be parsed using streaming."""
        try:
            file_size = os.path.getsize(file_path)
            return file_size > self.max_file_size
        except OSError:
            return False

    def parse_file_optimized(
        self, file_path: Path, parser, language: str
    ) -> tuple[Any | None, str | None]:
        """Parse file with memory optimization."""
        stats_before = MemoryStats.current()
        stats_before.log_stats(f"before parsing {file_path.name}")

        try:
            if self.should_use_streaming(file_path):
                # For very large files, use memory mapping
                logger.info(
                    f"Using memory-mapped parsing for large file: {file_path.name}"
                )
                with self.reader.mmap_file(file_path) as mmapped_content:
                    tree = parser.parse(mmapped_content)
                    root_node = tree.root_node

                    # Process the AST immediately to avoid keeping it in memory
                    result = self._process_ast_streaming(root_node, language)

                    # Explicitly delete the tree to free memory
                    del tree
                    self._check_memory_and_gc()

                    return result, None
            else:
                # For smaller files, use regular parsing
                content = file_path.read_bytes()
                tree = parser.parse(content)
                return tree.root_node, None

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None, str(e)
        finally:
            stats_after = MemoryStats.current()
            stats_after.log_stats(f"after parsing {file_path.name}")

    def _process_ast_streaming(self, root_node, language: str) -> any:
        """Process AST in a streaming fashion to minimize memory usage."""
        # This is a placeholder - in practice, we'd extract the needed
        # information immediately and discard the AST nodes
        return root_node

    def _check_memory_and_gc(self) -> None:
        """Check memory usage and trigger garbage collection if needed."""
        stats = MemoryStats.current()

        if stats.percent_used > self.gc_threshold:
            logger.info(
                f"Memory usage high ({stats.percent_used:.1f}%), triggering garbage collection"
            )
            gc.collect()

            # Log the effect of GC
            stats_after = MemoryStats.current()
            freed = self._last_gc_memory - stats_after.process_memory
            if freed > 0:
                logger.info(f"Garbage collection freed {freed / 1024 / 1024:.1f}MB")

        self._last_gc_memory = stats.process_memory


class BatchProcessor:
    """Processes items in batches to optimize memory usage."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.current_batch = []

    def add_item(self, item: any) -> bool:
        """Add item to batch. Returns True if batch is full."""
        self.current_batch.append(item)
        return len(self.current_batch) >= self.batch_size

    def get_batch(self) -> list:
        """Get current batch and reset."""
        batch = self.current_batch
        self.current_batch = []
        return batch

    def has_items(self) -> bool:
        """Check if there are items in the current batch."""
        return len(self.current_batch) > 0


@contextmanager
def memory_guard(max_memory_mb: int = 1024):
    """Context manager to guard against excessive memory usage."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024

    def check_memory():
        current_memory = process.memory_info().rss / 1024 / 1024
        if current_memory > max_memory_mb:
            raise MemoryError(
                f"Memory usage exceeded limit: {current_memory:.1f}MB > {max_memory_mb}MB"
            )

    try:
        yield check_memory
    finally:
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        if memory_increase > 100:  # Log significant increases
            logger.warning(
                f"Significant memory increase: {memory_increase:.1f}MB "
                f"(from {initial_memory:.1f}MB to {final_memory:.1f}MB)"
            )


@contextmanager
def memory_monitor(context: str = ""):
    """Monitor memory usage during an operation."""
    stats_before = MemoryStats.current()
    stats_before.log_stats(f"before {context}")

    try:
        yield
    finally:
        stats_after = MemoryStats.current()
        stats_after.log_stats(f"after {context}")

        # Calculate memory increase
        memory_increase = stats_after.process_memory - stats_before.process_memory
        if memory_increase > 50 * 1024 * 1024:  # More than 50MB
            logger.warning(
                f"Significant memory increase during {context}: "
                f"{memory_increase / 1024 / 1024:.1f}MB"
            )


def optimize_memory_settings():
    """Optimize Python memory settings for large-scale processing."""
    # Adjust garbage collection thresholds for better performance
    # with large datasets
    gc.set_threshold(700, 10, 10)  # Default is (700, 10, 10)

    # Enable garbage collection stats in debug mode
    if logger._core.min_level <= 10:  # DEBUG level
        gc.set_debug(gc.DEBUG_STATS)

    logger.info("Memory optimization settings applied")
