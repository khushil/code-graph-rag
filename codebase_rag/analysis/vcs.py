"""Version Control System (VCS) analysis for Git integration."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from git import Repo
from loguru import logger


@dataclass
class CommitInfo:
    """Represents a Git commit."""

    commit_hash: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    timestamp: datetime
    message: str
    parent_hashes: list[str]
    modified_files: list[str]
    added_files: list[str]
    removed_files: list[str]
    line_stats: dict[str, int]  # additions, deletions


@dataclass
class AuthorInfo:
    """Represents a Git author/contributor."""

    name: str
    email: str
    commit_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    first_commit_date: datetime | None = None
    last_commit_date: datetime | None = None
    primary_languages: list[str] | None = None


@dataclass
class BlameInfo:
    """Represents blame information for a line of code."""

    file_path: str
    line_number: int
    commit_hash: str
    author_name: str
    author_email: str
    timestamp: datetime
    line_content: str


@dataclass
class FileHistory:
    """Represents the history of changes to a file."""

    file_path: str
    commits: list[CommitInfo]
    total_commits: int
    authors: list[AuthorInfo]
    creation_date: datetime
    last_modified_date: datetime
    is_test_file: bool = False


class VCSAnalyzer:
    """Analyzes version control system (Git) information."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        try:
            self.repo = Repo(repo_path)
            self.git = self.repo.git
        except Exception as e:
            logger.error(f"Failed to initialize Git repository at {repo_path}: {e}")
            raise

    def analyze_repository(
        self,
        branch: str = "HEAD",
        max_commits: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[CommitInfo], list[AuthorInfo]]:
        """Analyze the repository and extract commit and author information."""
        commits = []
        authors_map = {}

        # Build commit iterator with filters
        commit_iter = self.repo.iter_commits(branch)

        for i, commit in enumerate(commit_iter):
            if max_commits and i >= max_commits:
                break

            # Apply date filters
            commit_date = datetime.fromtimestamp(commit.committed_date, tz=UTC)
            if since and commit_date < since:
                continue
            if until and commit_date > until:
                continue

            # Extract commit info
            commit_info = self._extract_commit_info(commit)
            commits.append(commit_info)

            # Update author info
            author_key = (commit.author.name, commit.author.email)
            if author_key not in authors_map:
                authors_map[author_key] = AuthorInfo(
                    name=commit.author.name,
                    email=commit.author.email,
                    first_commit_date=commit_date,
                    last_commit_date=commit_date,
                )
            else:
                author = authors_map[author_key]
                author.commit_count += 1
                author.lines_added += commit_info.line_stats.get("additions", 0)
                author.lines_removed += commit_info.line_stats.get("deletions", 0)
                author.first_commit_date = min(author.first_commit_date, commit_date)
                author.last_commit_date = max(author.last_commit_date, commit_date)

        return commits, list(authors_map.values())

    def _extract_commit_info(self, commit) -> CommitInfo:
        """Extract information from a Git commit."""
        # Get file changes
        modified_files = []
        added_files = []
        removed_files = []

        # Get diff stats
        try:
            stats = commit.stats
            line_stats = {
                "additions": stats.total["insertions"],
                "deletions": stats.total["deletions"],
                "files_changed": stats.total["files"],
            }
        except Exception:
            line_stats = {"additions": 0, "deletions": 0, "files_changed": 0}

        # Analyze diffs
        if commit.parents:
            diffs = commit.diff(commit.parents[0])
            for diff in diffs:
                if diff.new_file:
                    added_files.append(diff.b_path)
                elif diff.deleted_file:
                    removed_files.append(diff.a_path)
                else:
                    modified_files.append(diff.b_path)
        else:
            # First commit - all files are added
            for item in commit.tree.traverse():
                if item.type == "blob":
                    added_files.append(item.path)

        return CommitInfo(
            commit_hash=commit.hexsha,
            author_name=commit.author.name,
            author_email=commit.author.email,
            committer_name=commit.committer.name,
            committer_email=commit.committer.email,
            timestamp=datetime.fromtimestamp(commit.committed_date, tz=UTC),
            message=commit.message.strip(),
            parent_hashes=[p.hexsha for p in commit.parents],
            modified_files=modified_files,
            added_files=added_files,
            removed_files=removed_files,
            line_stats=line_stats,
        )

    def get_file_history(
        self, file_path: str, follow_renames: bool = True
    ) -> FileHistory:
        """Get the complete history of a file."""
        commits = []
        authors_map = {}

        # Use git log to get file history
        log_args = ["--follow"] if follow_renames else []
        log_args.extend(["--pretty=format:%H", "--", file_path])

        try:
            commit_hashes = self.git.log(*log_args).split("\n")
            commit_hashes = [h.strip() for h in commit_hashes if h.strip()]
        except Exception:
            # File might not exist in current branch
            return FileHistory(
                file_path=file_path,
                commits=[],
                total_commits=0,
                authors=[],
                creation_date=datetime.now(tz=UTC),
                last_modified_date=datetime.now(tz=UTC),
                is_test_file=self._is_test_file(file_path),
            )

        for commit_hash in commit_hashes:
            commit = self.repo.commit(commit_hash)
            commit_info = self._extract_commit_info(commit)
            commits.append(commit_info)

            # Track authors
            author_key = (commit.author.name, commit.author.email)
            if author_key not in authors_map:
                authors_map[author_key] = AuthorInfo(
                    name=commit.author.name,
                    email=commit.author.email,
                    commit_count=1,
                )
            else:
                authors_map[author_key].commit_count += 1

        # Determine creation and last modified dates
        if commits:
            creation_date = commits[-1].timestamp  # Oldest commit
            last_modified_date = commits[0].timestamp  # Newest commit
        else:
            creation_date = datetime.now(tz=UTC)
            last_modified_date = datetime.now(tz=UTC)

        return FileHistory(
            file_path=file_path,
            commits=commits,
            total_commits=len(commits),
            authors=list(authors_map.values()),
            creation_date=creation_date,
            last_modified_date=last_modified_date,
            is_test_file=self._is_test_file(file_path),
        )

    def get_file_blame(self, file_path: str) -> list[BlameInfo]:
        """Get blame information for each line in a file."""
        blame_info = []

        try:
            # Run git blame
            blame_output = self.git.blame("--line-porcelain", file_path)

            # Parse blame output
            lines = blame_output.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue

                # First line contains commit hash and line numbers
                parts = line.split(" ")
                if len(parts) >= 3:
                    commit_hash = parts[0]
                    # original_line = int(parts[1])  # Not used currently
                    final_line = int(parts[2])

                    # Parse metadata
                    author_name = ""
                    author_email = ""
                    timestamp = None
                    line_content = ""

                    i += 1
                    while i < len(lines) and not lines[i].startswith("\t"):
                        metadata_line = lines[i].strip()
                        if metadata_line.startswith("author "):
                            author_name = metadata_line[7:]
                        elif metadata_line.startswith("author-mail "):
                            author_email = metadata_line[12:].strip("<>")
                        elif metadata_line.startswith("author-time "):
                            timestamp = datetime.fromtimestamp(
                                int(metadata_line[12:]), tz=UTC
                            )
                        i += 1

                    # Get the actual line content
                    if i < len(lines) and lines[i].startswith("\t"):
                        line_content = lines[i][1:]  # Remove tab

                    blame_info.append(
                        BlameInfo(
                            file_path=file_path,
                            line_number=final_line,
                            commit_hash=commit_hash,
                            author_name=author_name,
                            author_email=author_email,
                            timestamp=timestamp or datetime.now(tz=UTC),
                            line_content=line_content,
                        )
                    )

                i += 1

        except Exception as e:
            logger.error(f"Failed to get blame for {file_path}: {e}")

        return blame_info

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file based on naming conventions."""
        path = Path(file_path)
        name_lower = path.name.lower()

        # Common test file patterns
        test_patterns = [
            "test_",
            "_test.",
            "test.",
            ".test.",
            "spec_",
            "_spec.",
            "spec.",
            ".spec.",
            "tests/",
            "test/",
            "testing/",
            "__tests__/",
        ]

        return any(
            pattern in name_lower or pattern in str(path).lower()
            for pattern in test_patterns
        )

    def build_vcs_graph(
        self,
        commits: list[CommitInfo],
        authors: list[AuthorInfo],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build graph nodes and relationships for VCS data."""
        nodes = []
        relationships = []

        # Create Author nodes
        for author in authors:
            author_node = {
                "label": "Author",
                "properties": {
                    "email": author.email,
                    "name": author.name,
                    "commit_count": author.commit_count,
                    "lines_added": author.lines_added,
                    "lines_removed": author.lines_removed,
                    "first_commit_date": author.first_commit_date.isoformat()
                    if author.first_commit_date
                    else None,
                    "last_commit_date": author.last_commit_date.isoformat()
                    if author.last_commit_date
                    else None,
                },
            }
            nodes.append(author_node)

        # Create Commit nodes and relationships
        for commit in commits:
            commit_node = {
                "label": "Commit",
                "properties": {
                    "hash": commit.commit_hash,
                    "message": commit.message[:500],  # Truncate long messages
                    "timestamp": commit.timestamp.isoformat(),
                    "additions": commit.line_stats.get("additions", 0),
                    "deletions": commit.line_stats.get("deletions", 0),
                    "files_changed": len(commit.modified_files)
                    + len(commit.added_files)
                    + len(commit.removed_files),
                },
            }
            nodes.append(commit_node)

            # AUTHORED_BY relationship
            authored_rel = {
                "start_label": "Commit",
                "start_key": "hash",
                "start_value": commit.commit_hash,
                "rel_type": "AUTHORED_BY",
                "end_label": "Author",
                "end_key": "email",
                "end_value": commit.author_email,
                "properties": {
                    "timestamp": commit.timestamp.isoformat(),
                },
            }
            relationships.append(authored_rel)

            # PARENT_OF relationships
            for parent_hash in commit.parent_hashes:
                parent_rel = {
                    "start_label": "Commit",
                    "start_key": "hash",
                    "start_value": parent_hash,
                    "rel_type": "PARENT_OF",
                    "end_label": "Commit",
                    "end_key": "hash",
                    "end_value": commit.commit_hash,
                    "properties": {},
                }
                relationships.append(parent_rel)

            # MODIFIED_IN relationships for files
            for file_path in commit.modified_files:
                modified_rel = {
                    "start_label": "Module",
                    "start_key": "file_path",
                    "start_value": file_path,
                    "rel_type": "MODIFIED_IN",
                    "end_label": "Commit",
                    "end_key": "hash",
                    "end_value": commit.commit_hash,
                    "properties": {
                        "change_type": "modified",
                    },
                }
                relationships.append(modified_rel)

            # ADDED_IN relationships
            for file_path in commit.added_files:
                added_rel = {
                    "start_label": "Module",
                    "start_key": "file_path",
                    "start_value": file_path,
                    "rel_type": "ADDED_IN",
                    "end_label": "Commit",
                    "end_key": "hash",
                    "end_value": commit.commit_hash,
                    "properties": {},
                }
                relationships.append(added_rel)

            # REMOVED_IN relationships
            for file_path in commit.removed_files:
                removed_rel = {
                    "start_label": "Module",
                    "start_key": "file_path",
                    "start_value": file_path,
                    "rel_type": "REMOVED_IN",
                    "end_label": "Commit",
                    "end_key": "hash",
                    "end_value": commit.commit_hash,
                    "properties": {},
                }
                relationships.append(removed_rel)

        return nodes, relationships

    def generate_vcs_report(
        self,
        commits: list[CommitInfo],
        authors: list[AuthorInfo],
    ) -> dict[str, Any]:
        """Generate a comprehensive VCS analysis report."""
        report = {
            "total_commits": len(commits),
            "total_authors": len(authors),
            "date_range": {
                "first_commit": min(c.timestamp for c in commits).isoformat()
                if commits
                else None,
                "last_commit": max(c.timestamp for c in commits).isoformat()
                if commits
                else None,
            },
            "top_contributors": [],
            "commit_frequency": {},
            "file_churn": {},
            "test_coverage_evolution": {},
        }

        # Top contributors by commit count
        top_authors = sorted(authors, key=lambda a: a.commit_count, reverse=True)[:10]
        report["top_contributors"] = [
            {
                "name": a.name,
                "email": a.email,
                "commits": a.commit_count,
                "lines_added": a.lines_added,
                "lines_removed": a.lines_removed,
            }
            for a in top_authors
        ]

        # Commit frequency by month
        monthly_commits = {}
        for commit in commits:
            month_key = commit.timestamp.strftime("%Y-%m")
            monthly_commits[month_key] = monthly_commits.get(month_key, 0) + 1
        report["commit_frequency"] = monthly_commits

        # File churn (most frequently modified files)
        file_modification_count = {}
        for commit in commits:
            for file_path in commit.modified_files:
                file_modification_count[file_path] = (
                    file_modification_count.get(file_path, 0) + 1
                )

        top_churned_files = sorted(
            file_modification_count.items(), key=lambda x: x[1], reverse=True
        )[:20]
        report["file_churn"] = dict(top_churned_files)

        return report
