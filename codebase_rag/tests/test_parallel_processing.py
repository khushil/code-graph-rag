"""Tests for parallel processing functionality (REQ-SCL-2)."""

import multiprocessing as mp
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codebase_rag.parallel_processor import FileTask, ParallelProcessor, ParseResult
from codebase_rag.progress_reporter import ProgressReporter, ProgressStats


class TestParallelProcessor:
    """Test the parallel processing functionality."""
    
    @pytest.fixture
    def mock_ingestor(self):
        """Create a mock ingestor."""
        ingestor = MagicMock()
        ingestor.ensure_node_batch = MagicMock()
        ingestor.ensure_relationship_batch = MagicMock()
        ingestor.flush_all = MagicMock()
        return ingestor
    
    @pytest.fixture
    def sample_repo(self):
        """Create a sample repository structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            
            # Create some sample files
            (repo_path / "main.py").write_text("def main():\n    pass\n")
            (repo_path / "utils.py").write_text("def helper():\n    return 42\n")
            
            # Create a subdirectory
            (repo_path / "src").mkdir()
            (repo_path / "src" / "module.py").write_text("class MyClass:\n    pass\n")
            
            # Create test files
            (repo_path / "test_main.py").write_text("def test_main():\n    assert True\n")
            (repo_path / "tests").mkdir()
            (repo_path / "tests" / "test_utils.py").write_text("def test_helper():\n    pass\n")
            
            yield repo_path
    
    def test_parallel_processor_initialization(self, mock_ingestor, sample_repo):
        """Test ParallelProcessor initialization."""
        processor = ParallelProcessor(
            mock_ingestor, sample_repo, {}, {}, max_workers=4
        )
        
        assert processor.max_workers == 4
        assert processor.batch_size == 100
        assert processor.total_files == 0
        assert processor.processed_files == 0
    
    def test_auto_worker_count(self, mock_ingestor, sample_repo):
        """Test automatic worker count determination."""
        processor = ParallelProcessor(
            mock_ingestor, sample_repo, {}, {}
        )
        
        # Should be 80% of CPU cores
        expected_workers = max(1, int(mp.cpu_count() * 0.8))
        assert processor.max_workers == expected_workers
    
    @patch('codebase_rag.parallel_processor.load_parsers')
    def test_collect_files(self, mock_load_parsers, mock_ingestor, sample_repo):
        """Test file collection."""
        # Mock parsers for Python
        mock_parsers = {"python": MagicMock()}
        mock_queries = {"python": {"config": MagicMock()}}
        mock_load_parsers.return_value = (mock_parsers, mock_queries)
        
        processor = ParallelProcessor(
            mock_ingestor, sample_repo, mock_parsers, mock_queries
        )
        
        # Collect all Python files
        files = processor.collect_files()
        
        # Should find all .py files
        assert len(files) == 5
        file_names = {f.file_path.name for f in files}
        assert "main.py" in file_names
        assert "utils.py" in file_names
        assert "module.py" in file_names
        assert "test_main.py" in file_names
        assert "test_utils.py" in file_names
    
    @patch('codebase_rag.parallel_processor.load_parsers')
    def test_collect_files_with_filters(self, mock_load_parsers, mock_ingestor, sample_repo):
        """Test file collection with filters."""
        mock_parsers = {"python": MagicMock()}
        mock_queries = {"python": {"config": MagicMock()}}
        mock_load_parsers.return_value = (mock_parsers, mock_queries)
        
        processor = ParallelProcessor(
            mock_ingestor, sample_repo, mock_parsers, mock_queries
        )
        
        # Test folder filter
        files = processor.collect_files(folder_filter="src")
        assert len(files) == 1
        assert files[0].file_path.name == "module.py"
        
        # Test file pattern
        files = processor.collect_files(file_pattern="test_*.py")
        assert len(files) == 2
        file_names = {f.file_path.name for f in files}
        assert "test_main.py" in file_names
        assert "test_utils.py" in file_names
        
        # Test skip tests
        files = processor.collect_files(skip_tests=True)
        assert len(files) == 3
        file_names = {f.file_path.name for f in files}
        assert "main.py" in file_names
        assert "utils.py" in file_names
        assert "module.py" in file_names
        assert "test_main.py" not in file_names
        assert "test_utils.py" not in file_names
    
    def test_parse_result_dataclass(self):
        """Test ParseResult dataclass."""
        result = ParseResult(
            file_path=Path("test.py"),
            language="python",
            nodes=[{"label": "Function", "name": "test"}],
            relationships=[],
            functions={"test": "Function"},
            simple_names={"test": {"test"}},
            error=None
        )
        
        assert result.file_path == Path("test.py")
        assert result.language == "python"
        assert len(result.nodes) == 1
        assert result.error is None
    
    @patch('codebase_rag.parallel_processor.load_parsers')
    def test_parse_file_worker(self, mock_load_parsers):
        """Test the file parsing worker function."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def hello():\n    print('Hello')\n\nclass MyClass:\n    def method(self):\n        pass\n")
            temp_path = Path(f.name)
        
        try:
            # Mock parsers
            from codebase_rag.parser_loader import load_parsers
            parsers, queries = load_parsers()
            
            if "python" in parsers:
                # Test the worker function
                result = ParallelProcessor._parse_file_worker(
                    temp_path, "python", "test.py"
                )
                
                assert result.error is None
                assert result.language == "python"
                assert len(result.nodes) >= 3  # Module, Function, Class
                
                # Check for function
                func_nodes = [n for n in result.nodes if n.get("label") == "Function"]
                assert len(func_nodes) >= 1
                assert any(n.get("name") == "hello" for n in func_nodes)
                
                # Check for class
                class_nodes = [n for n in result.nodes if n.get("label") == "Class"]
                assert len(class_nodes) >= 1
                assert any(n.get("name") == "MyClass" for n in class_nodes)
        finally:
            temp_path.unlink()


class TestProgressReporter:
    """Test the progress reporting functionality."""
    
    def test_progress_reporter_initialization(self):
        """Test ProgressReporter initialization."""
        reporter = ProgressReporter(100, update_interval=0.5)
        
        assert reporter.total_items == 100
        assert reporter.processed_items == 0
        assert reporter.failed_items == 0
        assert reporter.update_interval == 0.5
        assert reporter.current_phase == "Initializing"
    
    def test_progress_update(self):
        """Test progress updates."""
        reporter = ProgressReporter(100)
        
        # Update progress
        reporter.update(processed=10)
        assert reporter.processed_items == 10
        
        reporter.update(processed=5, failed=2)
        assert reporter.processed_items == 15
        assert reporter.failed_items == 2
        
        # Set phase
        reporter.set_phase("Processing files")
        assert reporter.current_phase == "Processing files"
    
    def test_progress_stats(self):
        """Test progress statistics calculation."""
        reporter = ProgressReporter(100)
        reporter.update(processed=50, failed=5)
        
        stats = reporter.get_stats()
        
        assert isinstance(stats, ProgressStats)
        assert stats.total_items == 100
        assert stats.processed_items == 50
        assert stats.failed_items == 5
        assert stats.items_per_second >= 0
        
        # With 50% complete, there should be an ETA
        if stats.items_per_second > 0:
            assert stats.estimated_time_remaining is not None
    
    def test_timedelta_formatting(self):
        """Test timedelta formatting."""
        from datetime import timedelta
        
        # Test seconds only
        td = timedelta(seconds=45)
        formatted = ProgressReporter._format_timedelta(td)
        assert formatted == "45s"
        
        # Test minutes and seconds
        td = timedelta(minutes=3, seconds=30)
        formatted = ProgressReporter._format_timedelta(td)
        assert formatted == "3m 30s"
        
        # Test hours, minutes and seconds
        td = timedelta(hours=2, minutes=15, seconds=45)
        formatted = ProgressReporter._format_timedelta(td)
        assert formatted == "2h 15m 45s"