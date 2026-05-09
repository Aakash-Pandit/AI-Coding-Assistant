from pathlib import Path

from pydantic import BaseModel

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".go", ".js", ".ts", ".json", ".yaml", ".yml", ".md"}
)

IGNORE_DIRS: frozenset[str] = frozenset(
    {
        "venv", ".venv", "env", ".env",
        "node_modules", ".git", "dist", "build",
        "__pycache__", ".mypy_cache", ".ruff_cache",
        ".pytest_cache", "coverage", ".tox",
        ".sage",  # our own index/memory dirs
    }
)

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
}


class FileRecord(BaseModel):
    path: Path
    language: str
    size: int
    relative_path: str  # relative to scan root, for display


class RepoScanner:
    def __init__(
        self,
        extra_ignore: set[str] | None = None,
        max_file_size_kb: int = 500,
    ) -> None:
        self.ignore_dirs = IGNORE_DIRS | (extra_ignore or set())
        self.max_bytes = max_file_size_kb * 1024

    def scan(self, root: Path) -> list[FileRecord]:
        root = root.resolve()
        records: list[FileRecord] = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if self._is_ignored(path, root):
                continue
            if path.suffix not in SUPPORTED_EXTENSIONS:
                continue
            size = path.stat().st_size
            if size == 0 or size > self.max_bytes:
                continue

            records.append(
                FileRecord(
                    path=path,
                    language=LANGUAGE_MAP[path.suffix],
                    size=size,
                    relative_path=str(path.relative_to(root)),
                )
            )

        return sorted(records, key=lambda r: r.relative_path)

    def _is_ignored(self, path: Path, root: Path) -> bool:
        for part in path.relative_to(root).parts[:-1]:
            if part in self.ignore_dirs or part.startswith("."):
                return True
        return False
