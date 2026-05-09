"""Git-aware tools for the agent."""
from __future__ import annotations

from sage.tools.registry import REGISTRY


def _repo():
    from git import InvalidGitRepositoryError, Repo

    from sage.config.settings import get_settings
    try:
        return Repo(get_settings().project_root, search_parent_directories=True)
    except InvalidGitRepositoryError:
        return None


@REGISTRY.tool
def git_status() -> str:
    """Return the current git working tree status (staged and unstaged changes)."""
    repo = _repo()
    if repo is None:
        return "Error: not a git repository"
    diff_staged = repo.git.diff("--cached", "--stat")
    diff_unstaged = repo.git.diff("--stat")
    untracked = repo.git.ls_files("--others", "--exclude-standard")
    parts = []
    if diff_staged:
        parts.append(f"Staged:\n{diff_staged}")
    if diff_unstaged:
        parts.append(f"Unstaged:\n{diff_unstaged}")
    if untracked:
        parts.append(f"Untracked:\n{untracked}")
    return "\n\n".join(parts) if parts else "Working tree clean"


@REGISTRY.tool
def git_diff(staged: bool = False) -> str:
    """
    Show the current git diff.
    Set staged=true to see only staged changes, false for unstaged.
    """
    repo = _repo()
    if repo is None:
        return "Error: not a git repository"
    args = ["--cached"] if staged else []
    diff = repo.git.diff(*args)
    if not diff:
        return "No changes" + (" staged" if staged else " in working tree")
    # Truncate if very large
    if len(diff) > 6000:
        diff = diff[:6000] + "\n… (diff truncated)"
    return diff


@REGISTRY.tool
def git_log(n: int = 10) -> str:
    """Show the last N git commits with author, date, and message."""
    repo = _repo()
    if repo is None:
        return "Error: not a git repository"
    log = repo.git.log(f"-{n}", "--oneline", "--decorate")
    return log if log else "No commits found"


@REGISTRY.tool
def git_blame(file_path: str, start_line: int = 1, end_line: int = 20) -> str:
    """Show who last modified each line in a file (git blame)."""
    repo = _repo()
    if repo is None:
        return "Error: not a git repository"
    try:
        result = repo.git.blame(
            f"-L{start_line},{end_line}", "--porcelain", file_path
        )
        return result[:3000] if len(result) > 3000 else result
    except Exception as e:
        return f"Error: {e}"
