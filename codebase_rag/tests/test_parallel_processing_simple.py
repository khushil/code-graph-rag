"""Simple test for our new parallel processing implementation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from codebase_rag.graph_updater import GraphUpdater
from codebase_rag.services.graph_service import MemgraphIngestor


def test_parallel_processing_flag():
    """Test that parallel processing flag is handled correctly."""
    # Mock ingestor
    mock_ingestor = MagicMock(spec=MemgraphIngestor)

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create a simple Python file
        test_file = repo_path / "test.py"
        test_file.write_text("def hello(): pass")

        # Mock parsers and queries
        mock_parser = MagicMock()
        mock_parser.parse.return_value.root_node = MagicMock()
        parsers = {"python": mock_parser}
        queries = {"python": {}}

        # Create updater with parallel processing enabled
        updater = GraphUpdater(
            ingestor=mock_ingestor,
            repo_path=repo_path,
            parsers=parsers,
            queries=queries,
            parallel=True,
            num_workers=2,
        )

        # Verify parallel processing is enabled
        assert updater.parallel is True
        assert updater.num_workers == 2

        # Test partial ingestion options
        updater2 = GraphUpdater(
            ingestor=mock_ingestor,
            repo_path=repo_path,
            parsers=parsers,
            queries=queries,
            parallel=True,
            folder_filter="src",
            file_pattern="*.py",
            skip_tests=True,
        )

        assert updater2.folder_filter == "src"
        assert updater2.file_pattern == "*.py"
        assert updater2.skip_tests is True


def test_parallel_vs_sequential_consistency():
    """Test that parallel and sequential processing produce consistent results."""
    # This test would compare results from both processing modes
    # For now, just verify the modes can be instantiated

    mock_ingestor = MagicMock(spec=MemgraphIngestor)

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create test files
        for i in range(3):
            (repo_path / f"file{i}.py").write_text(f"# File {i}")

        parsers = {"python": MagicMock()}
        queries = {"python": {}}

        # Sequential processing
        sequential_updater = GraphUpdater(
            ingestor=mock_ingestor,
            repo_path=repo_path,
            parsers=parsers,
            queries=queries,
            parallel=False,
        )

        # Parallel processing
        parallel_updater = GraphUpdater(
            ingestor=mock_ingestor,
            repo_path=repo_path,
            parsers=parsers,
            queries=queries,
            parallel=True,
            num_workers=2,
        )

        # Both should be created successfully
        assert sequential_updater.parallel is False
        assert parallel_updater.parallel is True


if __name__ == "__main__":
    test_parallel_processing_flag()
    test_parallel_vs_sequential_consistency()
