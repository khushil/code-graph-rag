"""Tests for VCS (Git) analysis functionality."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from codebase_rag.analysis.vcs import (
    AuthorInfo,
    CommitInfo,
    FileHistory,
    VCSAnalyzer,
)


class TestVCSAnalyzer:
    """Test the VCS analysis functionality."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock Git repository."""
        mock = MagicMock()
        mock.git = MagicMock()
        return mock

    @pytest.fixture
    def analyzer(self, mock_repo):
        """Create a VCS analyzer with mocked repo."""
        with patch("codebase_rag.analysis.vcs.Repo", return_value=mock_repo):
            return VCSAnalyzer("/fake/repo")

    def test_commit_info_dataclass(self):
        """Test CommitInfo dataclass."""
        commit = CommitInfo(
            commit_hash="abc123",
            author_name="John Doe",
            author_email="john@example.com",
            committer_name="Jane Doe",
            committer_email="jane@example.com",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            message="Initial commit",
            parent_hashes=["def456"],
            modified_files=["main.py"],
            added_files=["README.md"],
            removed_files=[],
            line_stats={"additions": 100, "deletions": 20},
        )

        assert commit.commit_hash == "abc123"
        assert commit.author_name == "John Doe"
        assert commit.author_email == "john@example.com"
        assert len(commit.parent_hashes) == 1
        assert len(commit.modified_files) == 1
        assert len(commit.added_files) == 1
        assert commit.line_stats["additions"] == 100

    def test_author_info_dataclass(self):
        """Test AuthorInfo dataclass."""
        author = AuthorInfo(
            name="John Doe",
            email="john@example.com",
            commit_count=50,
            lines_added=1000,
            lines_removed=200,
            first_commit_date=datetime(2023, 1, 1, tzinfo=UTC),
            last_commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            primary_languages=["python", "javascript"],
        )

        assert author.name == "John Doe"
        assert author.email == "john@example.com"
        assert author.commit_count == 50
        assert author.lines_added == 1000
        assert author.lines_removed == 200
        assert len(author.primary_languages) == 2

    def test_file_history_dataclass(self):
        """Test FileHistory dataclass."""
        commit1 = CommitInfo(
            commit_hash="abc123",
            author_name="John Doe",
            author_email="john@example.com",
            committer_name="John Doe",
            committer_email="john@example.com",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            message="Update file",
            parent_hashes=[],
            modified_files=["file.py"],
            added_files=[],
            removed_files=[],
            line_stats={},
        )

        author1 = AuthorInfo(
            name="John Doe",
            email="john@example.com",
            commit_count=1,
        )

        history = FileHistory(
            file_path="file.py",
            commits=[commit1],
            total_commits=1,
            authors=[author1],
            creation_date=datetime(2023, 1, 1, tzinfo=UTC),
            last_modified_date=datetime(2024, 1, 1, tzinfo=UTC),
            is_test_file=False,
        )

        assert history.file_path == "file.py"
        assert history.total_commits == 1
        assert len(history.commits) == 1
        assert len(history.authors) == 1
        assert not history.is_test_file

    def test_is_test_file_detection(self, analyzer):
        """Test detection of test files."""
        # Test files
        assert analyzer._is_test_file("test_module.py")
        assert analyzer._is_test_file("module_test.py")
        assert analyzer._is_test_file("tests/test_feature.py")
        assert analyzer._is_test_file("spec/feature_spec.js")
        assert analyzer._is_test_file("__tests__/component.test.js")

        # Non-test files
        assert not analyzer._is_test_file("main.py")
        assert not analyzer._is_test_file("module.py")
        assert not analyzer._is_test_file("src/feature.py")

    def test_build_vcs_graph(self, analyzer):
        """Test building VCS graph nodes and relationships."""
        commits = [
            CommitInfo(
                commit_hash="abc123",
                author_name="John Doe",
                author_email="john@example.com",
                committer_name="John Doe",
                committer_email="john@example.com",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                message="Initial commit",
                parent_hashes=[],
                modified_files=[],
                added_files=["main.py", "README.md"],
                removed_files=[],
                line_stats={"additions": 100, "deletions": 0},
            ),
            CommitInfo(
                commit_hash="def456",
                author_name="Jane Doe",
                author_email="jane@example.com",
                committer_name="Jane Doe",
                committer_email="jane@example.com",
                timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                message="Update main.py",
                parent_hashes=["abc123"],
                modified_files=["main.py"],
                added_files=[],
                removed_files=[],
                line_stats={"additions": 20, "deletions": 5},
            ),
        ]

        authors = [
            AuthorInfo(
                name="John Doe",
                email="john@example.com",
                commit_count=1,
                lines_added=100,
                lines_removed=0,
            ),
            AuthorInfo(
                name="Jane Doe",
                email="jane@example.com",
                commit_count=1,
                lines_added=20,
                lines_removed=5,
            ),
        ]

        nodes, relationships = analyzer.build_vcs_graph(commits, authors)

        # Check Author nodes
        author_nodes = [n for n in nodes if n["label"] == "Author"]
        assert len(author_nodes) == 2
        john_node = next(
            n for n in author_nodes if n["properties"]["email"] == "john@example.com"
        )
        assert john_node["properties"]["name"] == "John Doe"
        assert john_node["properties"]["commit_count"] == 1

        # Check Commit nodes
        commit_nodes = [n for n in nodes if n["label"] == "Commit"]
        assert len(commit_nodes) == 2
        initial_commit = next(
            n for n in commit_nodes if n["properties"]["hash"] == "abc123"
        )
        assert initial_commit["properties"]["additions"] == 100
        assert initial_commit["properties"]["files_changed"] == 2

        # Check AUTHORED_BY relationships
        authored_rels = [r for r in relationships if r["rel_type"] == "AUTHORED_BY"]
        assert len(authored_rels) == 2
        assert authored_rels[0]["start_value"] == "abc123"
        assert authored_rels[0]["end_value"] == "john@example.com"

        # Check PARENT_OF relationships
        parent_rels = [r for r in relationships if r["rel_type"] == "PARENT_OF"]
        assert len(parent_rels) == 1
        assert parent_rels[0]["start_value"] == "abc123"
        assert parent_rels[0]["end_value"] == "def456"

        # Check file modification relationships
        added_rels = [r for r in relationships if r["rel_type"] == "ADDED_IN"]
        assert len(added_rels) == 2  # main.py and README.md

        modified_rels = [r for r in relationships if r["rel_type"] == "MODIFIED_IN"]
        assert len(modified_rels) == 1  # main.py in second commit
        assert modified_rels[0]["start_value"] == "main.py"
        assert modified_rels[0]["end_value"] == "def456"

    def test_generate_vcs_report(self, analyzer):
        """Test generating VCS analysis report."""
        commits = [
            CommitInfo(
                commit_hash=f"commit{i}",
                author_name="John Doe" if i % 2 == 0 else "Jane Doe",
                author_email="john@example.com" if i % 2 == 0 else "jane@example.com",
                committer_name="John Doe" if i % 2 == 0 else "Jane Doe",
                committer_email="john@example.com"
                if i % 2 == 0
                else "jane@example.com",
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                message=f"Commit {i}",
                parent_hashes=[f"commit{i - 1}"] if i > 0 else [],
                modified_files=["main.py"] if i > 0 else [],
                added_files=["main.py", "test.py"] if i == 0 else [],
                removed_files=[],
                line_stats={"additions": 10 * (i + 1), "deletions": 5 * i},
            )
            for i in range(5)
        ]

        authors = [
            AuthorInfo(
                name="John Doe",
                email="john@example.com",
                commit_count=3,
                lines_added=90,
                lines_removed=30,
                first_commit_date=datetime(2024, 1, 1, tzinfo=UTC),
                last_commit_date=datetime(2024, 1, 5, tzinfo=UTC),
            ),
            AuthorInfo(
                name="Jane Doe",
                email="jane@example.com",
                commit_count=2,
                lines_added=60,
                lines_removed=25,
                first_commit_date=datetime(2024, 1, 2, tzinfo=UTC),
                last_commit_date=datetime(2024, 1, 4, tzinfo=UTC),
            ),
        ]

        report = analyzer.generate_vcs_report(commits, authors)

        # Check basic statistics
        assert report["total_commits"] == 5
        assert report["total_authors"] == 2

        # Check date range
        assert (
            report["date_range"]["first_commit"]
            == datetime(2024, 1, 1, tzinfo=UTC).isoformat()
        )
        assert (
            report["date_range"]["last_commit"]
            == datetime(2024, 1, 5, tzinfo=UTC).isoformat()
        )

        # Check top contributors
        assert len(report["top_contributors"]) == 2
        assert report["top_contributors"][0]["name"] == "John Doe"
        assert report["top_contributors"][0]["commits"] == 3

        # Check commit frequency
        assert "2024-01" in report["commit_frequency"]
        assert report["commit_frequency"]["2024-01"] == 5

        # Check file churn
        assert "main.py" in report["file_churn"]
        assert report["file_churn"]["main.py"] == 4  # Modified in commits 1-4

    @patch("codebase_rag.analysis.vcs.Repo")
    def test_analyze_repository(self, mock_repo_class, analyzer):
        """Test repository analysis with mock commits."""
        # Create mock commits
        mock_commit1 = MagicMock()
        mock_commit1.hexsha = "abc123"
        mock_commit1.author.name = "John Doe"
        mock_commit1.author.email = "john@example.com"
        mock_commit1.committer.name = "John Doe"
        mock_commit1.committer.email = "john@example.com"
        mock_commit1.committed_date = 1704067200  # 2024-01-01 00:00:00
        mock_commit1.message = "Initial commit"
        mock_commit1.parents = []
        mock_commit1.stats.total = {"insertions": 100, "deletions": 0, "files": 2}

        # Mock diff for added files
        mock_diff1 = MagicMock()
        mock_diff1.new_file = True
        mock_diff1.deleted_file = False
        mock_diff1.b_path = "main.py"

        mock_commit1.diff.return_value = [mock_diff1]

        # Mock tree traversal for first commit
        mock_blob = MagicMock()
        mock_blob.type = "blob"
        mock_blob.path = "main.py"
        mock_commit1.tree.traverse.return_value = [mock_blob]

        # Set up mock repo
        analyzer.repo.iter_commits.return_value = [mock_commit1]

        # Analyze
        commits, authors = analyzer.analyze_repository()

        # Verify results
        assert len(commits) == 1
        assert commits[0].commit_hash == "abc123"
        assert commits[0].author_name == "John Doe"
        assert len(commits[0].added_files) == 1
        assert commits[0].added_files[0] == "main.py"

        assert len(authors) == 1
        assert authors[0].name == "John Doe"
        assert authors[0].email == "john@example.com"
