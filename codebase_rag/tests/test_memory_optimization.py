"""Tests for memory optimization functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from codebase_rag.memory_optimizer import (
    BatchProcessor,
    MemoryOptimizedParser,
    MemoryStats,
    StreamingFileReader,
    memory_guard,
    optimize_memory_settings,
)


class TestMemoryStats:
    """Test memory statistics functionality."""

    def test_memory_stats_creation(self):
        """Test creating memory statistics."""
        stats = MemoryStats.current()

        assert stats.total_memory > 0
        assert stats.available_memory > 0
        assert stats.used_memory > 0
        assert 0 <= stats.percent_used <= 100
        assert stats.process_memory > 0

    def test_memory_stats_logging(self, caplog):
        """Test memory stats logging."""
        stats = MemoryStats.current()
        stats.log_stats("test context")

        assert "Memory stats test context" in caplog.text
        assert "Process:" in caplog.text
        assert "MB" in caplog.text


class TestStreamingFileReader:
    """Test streaming file reader functionality."""

    def test_read_file_chunks(self):
        """Test reading file in chunks."""
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("A" * 5000)  # 5KB of data
            temp_path = Path(f.name)

        try:
            reader = StreamingFileReader(chunk_size=1024)
            chunks = list(reader.read_file_chunks(temp_path))

            # Should have 5 chunks (5KB / 1KB)
            assert len(chunks) == 5
            assert all(len(chunk) == 1024 for chunk in chunks[:-1])
            assert len(chunks[-1]) == 5000 - 4096

            # Reconstruct and verify
            reconstructed = b''.join(chunks)
            assert reconstructed == b"A" * 5000
        finally:
            temp_path.unlink()

    def test_read_file_lines(self):
        """Test reading file line by line."""
        content = "Line 1\nLine 2\nLine 3\n"

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            reader = StreamingFileReader()
            lines = list(reader.read_file_lines(temp_path))

            assert lines == ["Line 1", "Line 2", "Line 3"]
        finally:
            temp_path.unlink()

    def test_mmap_file(self):
        """Test memory-mapped file reading."""
        content = b"Memory mapped content"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            reader = StreamingFileReader()
            with reader.mmap_file(temp_path) as mmapped:
                assert mmapped[:6] == b"Memory"
                assert len(mmapped) == len(content)
        finally:
            temp_path.unlink()

    def test_mmap_empty_file(self):
        """Test memory-mapping an empty file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            reader = StreamingFileReader()
            with reader.mmap_file(temp_path) as mmapped:
                assert mmapped == b''
        finally:
            temp_path.unlink()


class TestMemoryOptimizedParser:
    """Test memory-optimized parser functionality."""

    def test_should_use_streaming(self):
        """Test streaming decision based on file size."""
        parser = MemoryOptimizedParser(max_file_size=1024 * 1024)  # 1MB

        # Create small file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Small content")
            small_file = Path(f.name)

        # Create large file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("X" * (2 * 1024 * 1024))  # 2MB
            large_file = Path(f.name)

        try:
            assert not parser.should_use_streaming(small_file)
            assert parser.should_use_streaming(large_file)
        finally:
            small_file.unlink()
            large_file.unlink()

    @patch('codebase_rag.memory_optimizer.gc.collect')
    def test_memory_gc_trigger(self, mock_gc):
        """Test garbage collection trigger on high memory."""
        parser = MemoryOptimizedParser(gc_threshold=80.0)

        # Mock high memory usage
        with patch.object(MemoryStats, 'current') as mock_stats:
            mock_stats.return_value = MemoryStats(
                total_memory=8 * 1024 * 1024 * 1024,  # 8GB
                available_memory=1 * 1024 * 1024 * 1024,  # 1GB
                used_memory=7 * 1024 * 1024 * 1024,  # 7GB
                percent_used=87.5,  # Above threshold
                process_memory=500 * 1024 * 1024  # 500MB
            )

            parser._check_memory_and_gc()
            mock_gc.assert_called_once()


class TestBatchProcessor:
    """Test batch processor functionality."""

    def test_batch_processing(self):
        """Test batch processing logic."""
        processor = BatchProcessor(batch_size=3)

        # Add items
        assert not processor.add_item("item1")
        assert not processor.add_item("item2")
        assert processor.add_item("item3")  # Batch full

        # Get batch
        batch = processor.get_batch()
        assert batch == ["item1", "item2", "item3"]
        assert not processor.has_items()

        # Add more items
        processor.add_item("item4")
        assert processor.has_items()

        batch = processor.get_batch()
        assert batch == ["item4"]


class TestMemoryGuard:
    """Test memory guard context manager."""

    def test_memory_guard_normal(self):
        """Test memory guard under normal conditions."""
        with memory_guard(max_memory_mb=10000) as check_memory:  # 10GB limit
            # Should not raise
            check_memory()

    def test_memory_guard_exceeded(self):
        """Test memory guard when limit exceeded."""
        with pytest.raises(MemoryError):
            with memory_guard(max_memory_mb=1) as check_memory:  # 1MB limit
                # Current process likely uses more than 1MB
                check_memory()


class TestOptimizeMemorySettings:
    """Test memory optimization settings."""

    @patch('codebase_rag.memory_optimizer.gc.set_threshold')
    def test_optimize_settings(self, mock_set_threshold):
        """Test applying optimization settings."""
        optimize_memory_settings()
        mock_set_threshold.assert_called_once_with(700, 10, 10)
