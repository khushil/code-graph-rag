"""Version control integration for code analysis."""

from .git_analyzer import GitAnalyzer, CommitInfo, BlameInfo, FileHistory

__all__ = ["GitAnalyzer", "CommitInfo", "BlameInfo", "FileHistory"]