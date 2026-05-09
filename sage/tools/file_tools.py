"""File system tools — all operations are restricted to the project root."""
from __future__ import annotations

from pathlib import Path

from sage.config.settings import get_settings
from sage.tools.registry import REGISTRY


def _safe_path(path_str: str) -> Path:
    root = get_settings().project_root
    p = (root / path_str).resolve()
    if not str(p).startswith(str(root)):
        raise PermissionError(f"Access denied: {path_str} is outside the project root")
    return p


@REGISTRY.tool
def read_file(path: str) -> str:
    """Read the contents of a file. Path is relative to the project root."""
    p = _safe_path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        return p.read_text(errors="replace")
    except OSError as e:
        return f"Error reading file: {e}"


@REGISTRY.tool
def list_files(directory: str = ".") -> str:
    """List files in a directory. Path is relative to the project root."""
    p = _safe_path(directory)
    if not p.exists():
        return f"Error: directory not found: {directory}"
    if not p.is_dir():
        return f"Error: not a directory: {directory}"

    lines = []
    for item in sorted(p.iterdir()):
        size = item.stat().st_size if item.is_file() else 0
        kind = "file" if item.is_file() else "dir"
        lines.append(f"{kind:4}  {size:8,}  {item.name}")
    return "\n".join(lines) if lines else "(empty directory)"


@REGISTRY.tool
def search_in_files(pattern: str, directory: str = ".") -> str:
    """Search for a pattern (substring) across all source files in a directory."""

    p = _safe_path(directory)
    supported = {".py", ".js", ".ts", ".go", ".md", ".yaml", ".yml", ".json"}
    matches: list[str] = []

    for file in p.rglob("*"):
        if not file.is_file() or file.suffix not in supported:
            continue
        try:
            text = file.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.lower() in line.lower():
                rel = file.relative_to(get_settings().project_root)
                matches.append(f"{rel}:{i}: {line.strip()}")

    if not matches:
        return f"No matches found for '{pattern}'"
    return "\n".join(matches[:50]) + (f"\n… ({len(matches)} total)" if len(matches) > 50 else "")
