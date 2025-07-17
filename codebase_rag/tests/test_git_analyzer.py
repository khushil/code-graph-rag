"""Test Git analyzer functionality."""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from codebase_rag.version_control.git_analyzer import (
    CommitInfo,
    GitAnalyzer,
)


class TestGitAnalyzer:
    """Test Git repository analysis."""

    @pytest.fixture
    def git_repo(self):
        """Create a temporary Git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

            # Create and commit a test file
            test_file = repo_path / "test.py"
            test_file.write_text("def hello():\n    print('Hello')\n")
            subprocess.run(["git", "add", "test.py"], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

            # Add more content and commit
            test_file.write_text("def hello():\n    print('Hello')\n\ndef world():\n    print('World')\n")
            subprocess.run(["git", "add", "test.py"], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "Add world function"], cwd=repo_path, check=True)

            yield repo_path

    def test_git_analyzer_init(self, git_repo):
        """Test GitAnalyzer initialization."""
        analyzer = GitAnalyzer(git_repo)
        assert analyzer.repo_path == git_repo

    def test_get_recent_commits(self, git_repo):
        """Test getting recent commits."""
        analyzer = GitAnalyzer(git_repo)
        commits = analyzer.get_recent_commits(max_commits=10)

        assert len(commits) == 2
        assert commits[0].message == "Add world function"
        assert commits[1].message == "Initial commit"
        assert commits[0].author == "Test User"
        assert commits[0].author_email == "test@example.com"

    def test_get_file_history(self, git_repo):
        """Test getting file history."""
        analyzer = GitAnalyzer(git_repo)
        test_file = git_repo / "test.py"

        history = analyzer.get_file_history(str(test_file))

        assert history is not None
        assert history.total_commits == 2
        assert len(history.commits) == 2
        assert history.commits[0].message == "Add world function"
        assert len(history.contributors) == 1
        assert history.contributors[0][0].startswith("Test User")
        assert history.contributors[0][1] == 2  # 2 commits

    def test_get_blame_info(self, git_repo):
        """Test getting blame information."""
        analyzer = GitAnalyzer(git_repo)
        test_file = git_repo / "test.py"

        blame_info = analyzer.get_blame_info(str(test_file))

        assert len(blame_info) > 0
        assert blame_info[0].author == "Test User"
        assert blame_info[0].line_content == "def hello():"

        # Check that different lines might have different commits
        world_lines = [b for b in blame_info if "world" in b.line_content]
        assert len(world_lines) > 0

    def test_get_contributors(self, git_repo):
        """Test getting repository contributors."""
        analyzer = GitAnalyzer(git_repo)
        contributors = analyzer.get_contributors()

        assert len(contributors) == 1
        assert contributors[0][0].startswith("Test User")
        assert contributors[0][1] == 2  # 2 commits

    def test_non_git_directory(self):
        """Test handling of non-git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            analyzer = GitAnalyzer(Path(temp_dir))

            # Should handle gracefully
            commits = analyzer.get_recent_commits()
            assert commits == [] or commits is None

            contributors = analyzer.get_contributors()
            assert contributors == []

    def test_complex_history(self, git_repo):
        """Test with more complex commit history."""
        # Add another contributor
        subprocess.run(["git", "config", "user.name", "Another User"], cwd=git_repo, check=True)
        subprocess.run(["git", "config", "user.email", "another@example.com"], cwd=git_repo, check=True)

        # Create another file
        another_file = git_repo / "another.py"
        another_file.write_text("# Another file\n")
        subprocess.run(["git", "add", "another.py"], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add another file"], cwd=git_repo, check=True)

        analyzer = GitAnalyzer(git_repo)

        # Check commits
        commits = analyzer.get_recent_commits()
        assert len(commits) == 3

        # Check contributors
        contributors = analyzer.get_contributors()
        assert len(contributors) == 2

        # Check file-specific history
        test_file = git_repo / "test.py"
        history = analyzer.get_file_history(str(test_file))
        assert history.total_commits == 2  # Only 2 commits touched test.py

    def test_commit_info_structure(self, git_repo):
        """Test CommitInfo dataclass structure."""
        analyzer = GitAnalyzer(git_repo)
        commits = analyzer.get_recent_commits()

        commit = commits[0]
        assert isinstance(commit, CommitInfo)
        assert hasattr(commit, 'sha')
        assert hasattr(commit, 'author')
        assert hasattr(commit, 'author_email')
        assert hasattr(commit, 'message')
        assert hasattr(commit, 'date')
        assert isinstance(commit.date, datetime)
        assert hasattr(commit, 'files_changed')
        assert isinstance(commit.files_changed, list)
