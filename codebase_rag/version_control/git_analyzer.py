"""Git repository analysis for version control integration."""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
import subprocess
from loguru import logger
try:
    import git
    from git import Repo, Commit
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
    logger.warning("GitPython not installed. Git integration will be limited.")


@dataclass
class CommitInfo:
    """Information about a git commit."""
    sha: str
    author: str
    author_email: str
    committer: str
    committer_email: str
    message: str
    date: datetime
    files_changed: List[str]
    additions: int
    deletions: int
    parent_shas: List[str]


@dataclass
class BlameInfo:
    """Git blame information for a line of code."""
    line_number: int
    commit_sha: str
    author: str
    author_email: str
    date: datetime
    line_content: str
    original_line_number: int  # Line number in the original commit


@dataclass
class FileHistory:
    """History of changes to a file."""
    file_path: str
    commits: List[CommitInfo]
    renames: List[Tuple[str, str, str]]  # List of (old_path, new_path, commit_sha)
    creation_date: datetime
    last_modified: datetime
    total_commits: int
    contributors: List[Tuple[str, int]]  # List of (author, commit_count)


class GitAnalyzer:
    """Analyzes Git repository history and blame information."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.repo = None
        
        if HAS_GITPYTHON:
            try:
                self.repo = Repo(repo_path)
                if self.repo.bare:
                    logger.warning(f"Repository at {repo_path} is bare")
            except Exception as e:
                logger.error(f"Failed to open git repository at {repo_path}: {e}")
        else:
            logger.info("Using subprocess fallback for git operations")
    
    def get_blame_info(self, file_path: str) -> List[BlameInfo]:
        """Get git blame information for a file."""
        blame_info = []
        
        if self.repo and HAS_GITPYTHON:
            try:
                # Get relative path from repo root
                rel_path = Path(file_path).relative_to(self.repo_path)
                
                # Run git blame
                blame_data = self.repo.blame('HEAD', str(rel_path))
                
                line_number = 1
                for commit, lines in blame_data:
                    for line in lines:
                        blame = BlameInfo(
                            line_number=line_number,
                            commit_sha=commit.hexsha,
                            author=commit.author.name,
                            author_email=commit.author.email,
                            date=datetime.fromtimestamp(commit.authored_date),
                            line_content=line.rstrip('\n'),
                            original_line_number=line_number  # Would need more complex logic for accurate original line
                        )
                        blame_info.append(blame)
                        line_number += 1
                        
            except Exception as e:
                logger.error(f"Failed to get blame info for {file_path}: {e}")
                # Fall back to subprocess
                blame_info = self._get_blame_subprocess(file_path)
        else:
            blame_info = self._get_blame_subprocess(file_path)
            
        return blame_info
    
    def _get_blame_subprocess(self, file_path: str) -> List[BlameInfo]:
        """Get blame info using git subprocess."""
        blame_info = []
        
        try:
            # Get relative path
            rel_path = Path(file_path).relative_to(self.repo_path)
            
            # Run git blame with porcelain format for easier parsing
            cmd = ["git", "-C", str(self.repo_path), "blame", "--line-porcelain", str(rel_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            lines = result.stdout.strip().split('\n')
            i = 0
            line_number = 1
            
            while i < len(lines):
                if lines[i].startswith('author '):
                    # Parse blame entry
                    sha = lines[i-1].split()[0]
                    author = lines[i].replace('author ', '')
                    author_email = lines[i+1].replace('author-mail ', '').strip('<>')
                    timestamp = int(lines[i+3].replace('author-time ', ''))
                    
                    # Find the actual line content
                    j = i
                    while j < len(lines) and not lines[j].startswith('\t'):
                        j += 1
                    
                    if j < len(lines):
                        line_content = lines[j][1:]  # Remove leading tab
                        
                        blame = BlameInfo(
                            line_number=line_number,
                            commit_sha=sha,
                            author=author,
                            author_email=author_email,
                            date=datetime.fromtimestamp(timestamp),
                            line_content=line_content,
                            original_line_number=line_number
                        )
                        blame_info.append(blame)
                        line_number += 1
                        i = j + 1
                    else:
                        i += 1
                else:
                    i += 1
                    
        except subprocess.CalledProcessError as e:
            logger.error(f"Git blame failed for {file_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to parse blame output for {file_path}: {e}")
            
        return blame_info
    
    def get_file_history(self, file_path: str, max_commits: int = 100) -> Optional[FileHistory]:
        """Get the history of changes to a file."""
        if self.repo and HAS_GITPYTHON:
            return self._get_file_history_gitpython(file_path, max_commits)
        else:
            return self._get_file_history_subprocess(file_path, max_commits)
    
    def _get_file_history_gitpython(self, file_path: str, max_commits: int) -> Optional[FileHistory]:
        """Get file history using GitPython."""
        try:
            rel_path = Path(file_path).relative_to(self.repo_path)
            
            commits = []
            contributors = {}
            
            # Get commits that touched this file
            for commit in self.repo.iter_commits(paths=str(rel_path), max_count=max_commits):
                commit_info = CommitInfo(
                    sha=commit.hexsha,
                    author=commit.author.name,
                    author_email=commit.author.email,
                    committer=commit.committer.name,
                    committer_email=commit.committer.email,
                    message=commit.message.strip(),
                    date=datetime.fromtimestamp(commit.authored_date),
                    files_changed=[str(rel_path)],  # Simplified - would need diff for all files
                    additions=0,  # Would need to parse diff
                    deletions=0,  # Would need to parse diff
                    parent_shas=[p.hexsha for p in commit.parents]
                )
                commits.append(commit_info)
                
                # Track contributors
                author_key = f"{commit.author.name} <{commit.author.email}>"
                contributors[author_key] = contributors.get(author_key, 0) + 1
            
            if not commits:
                return None
                
            # Sort contributors by commit count
            sorted_contributors = sorted(contributors.items(), key=lambda x: x[1], reverse=True)
            
            return FileHistory(
                file_path=str(rel_path),
                commits=commits,
                renames=[],  # Would need to track renames
                creation_date=commits[-1].date if commits else datetime.now(),
                last_modified=commits[0].date if commits else datetime.now(),
                total_commits=len(commits),
                contributors=sorted_contributors
            )
            
        except Exception as e:
            logger.error(f"Failed to get file history for {file_path}: {e}")
            return None
    
    def _get_file_history_subprocess(self, file_path: str, max_commits: int) -> Optional[FileHistory]:
        """Get file history using git subprocess."""
        try:
            rel_path = Path(file_path).relative_to(self.repo_path)
            
            # Get commit history
            cmd = [
                "git", "-C", str(self.repo_path), 
                "log", f"--max-count={max_commits}",
                "--format=%H|%an|%ae|%cn|%ce|%at|%s",
                "--", str(rel_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            commits = []
            contributors = {}
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('|', 6)
                if len(parts) >= 7:
                    sha, author, author_email, committer, committer_email, timestamp, message = parts
                    
                    commit_info = CommitInfo(
                        sha=sha,
                        author=author,
                        author_email=author_email,
                        committer=committer,
                        committer_email=committer_email,
                        message=message,
                        date=datetime.fromtimestamp(int(timestamp)),
                        files_changed=[str(rel_path)],
                        additions=0,
                        deletions=0,
                        parent_shas=[]
                    )
                    commits.append(commit_info)
                    
                    # Track contributors
                    author_key = f"{author} <{author_email}>"
                    contributors[author_key] = contributors.get(author_key, 0) + 1
            
            if not commits:
                return None
                
            # Sort contributors by commit count
            sorted_contributors = sorted(contributors.items(), key=lambda x: x[1], reverse=True)
            
            return FileHistory(
                file_path=str(rel_path),
                commits=commits,
                renames=[],
                creation_date=commits[-1].date if commits else datetime.now(),
                last_modified=commits[0].date if commits else datetime.now(),
                total_commits=len(commits),
                contributors=sorted_contributors
            )
            
        except Exception as e:
            logger.error(f"Failed to get file history for {file_path}: {e}")
            return None
    
    def get_recent_commits(self, max_commits: int = 100) -> List[CommitInfo]:
        """Get recent commits in the repository."""
        if self.repo and HAS_GITPYTHON:
            return self._get_recent_commits_gitpython(max_commits)
        else:
            return self._get_recent_commits_subprocess(max_commits)
    
    def _get_recent_commits_gitpython(self, max_commits: int) -> List[CommitInfo]:
        """Get recent commits using GitPython."""
        commits = []
        
        try:
            for commit in self.repo.iter_commits(max_count=max_commits):
                # Get changed files and stats
                files_changed = []
                additions = 0
                deletions = 0
                
                for diff in commit.diff(commit.parents[0] if commit.parents else None):
                    if diff.a_path:
                        files_changed.append(diff.a_path)
                    elif diff.b_path:
                        files_changed.append(diff.b_path)
                
                commit_info = CommitInfo(
                    sha=commit.hexsha,
                    author=commit.author.name,
                    author_email=commit.author.email,
                    committer=commit.committer.name,
                    committer_email=commit.committer.email,
                    message=commit.message.strip(),
                    date=datetime.fromtimestamp(commit.authored_date),
                    files_changed=files_changed,
                    additions=additions,
                    deletions=deletions,
                    parent_shas=[p.hexsha for p in commit.parents]
                )
                commits.append(commit_info)
                
        except Exception as e:
            logger.error(f"Failed to get recent commits: {e}")
            
        return commits
    
    def _get_recent_commits_subprocess(self, max_commits: int) -> List[CommitInfo]:
        """Get recent commits using git subprocess."""
        commits = []
        
        try:
            # Get commit list
            cmd = [
                "git", "-C", str(self.repo_path),
                "log", f"--max-count={max_commits}",
                "--format=%H|%an|%ae|%cn|%ce|%at|%P|%s"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('|', 7)
                if len(parts) >= 8:
                    sha, author, author_email, committer, committer_email, timestamp, parents, message = parts
                    
                    # Get files changed for this commit
                    files_cmd = ["git", "-C", str(self.repo_path), "show", "--name-only", "--format=", sha]
                    files_result = subprocess.run(files_cmd, capture_output=True, text=True)
                    files_changed = [f for f in files_result.stdout.strip().split('\n') if f]
                    
                    commit_info = CommitInfo(
                        sha=sha,
                        author=author,
                        author_email=author_email,
                        committer=committer,
                        committer_email=committer_email,
                        message=message,
                        date=datetime.fromtimestamp(int(timestamp)),
                        files_changed=files_changed,
                        additions=0,
                        deletions=0,
                        parent_shas=parents.split() if parents else []
                    )
                    commits.append(commit_info)
                    
        except Exception as e:
            logger.error(f"Failed to get recent commits: {e}")
            
        return commits
    
    def get_contributors(self) -> List[Tuple[str, int]]:
        """Get list of contributors with their commit counts."""
        contributors = {}
        
        if self.repo and HAS_GITPYTHON:
            try:
                for commit in self.repo.iter_commits():
                    author_key = f"{commit.author.name} <{commit.author.email}>"
                    contributors[author_key] = contributors.get(author_key, 0) + 1
            except Exception as e:
                logger.error(f"Failed to get contributors: {e}")
        else:
            # Use subprocess fallback
            try:
                cmd = ["git", "-C", str(self.repo_path), "shortlog", "-sne", "HEAD"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.strip().split('\t', 1)
                        if len(parts) == 2:
                            count = int(parts[0])
                            author = parts[1]
                            contributors[author] = count
            except Exception as e:
                logger.error(f"Failed to get contributors: {e}")
        
        return sorted(contributors.items(), key=lambda x: x[1], reverse=True)