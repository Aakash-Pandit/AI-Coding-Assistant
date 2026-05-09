"""Unit tests for the repository scanner."""
import tempfile
from pathlib import Path

import pytest

from sage.indexing.scanner import RepoScanner


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text("def hello(): pass\n")
    (tmp_path / "utils.js").write_text("function greet() {}\n")
    (tmp_path / "README.md").write_text("# Hello\n")
    (tmp_path / "ignore.txt").write_text("not scanned")

    # Ignored dirs
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "lib.py").write_text("ignored")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("ignored")
    return tmp_path


def test_scan_finds_supported_files(tmp_repo):
    scanner = RepoScanner()
    records = scanner.scan(tmp_repo)
    names = [r.path.name for r in records]
    assert "main.py" in names
    assert "utils.js" in names
    assert "README.md" in names


def test_scan_excludes_unsupported(tmp_repo):
    scanner = RepoScanner()
    records = scanner.scan(tmp_repo)
    names = [r.path.name for r in records]
    assert "ignore.txt" not in names


def test_scan_ignores_venv(tmp_repo):
    scanner = RepoScanner()
    records = scanner.scan(tmp_repo)
    paths = [r.relative_path for r in records]
    assert not any("venv" in p for p in paths)


def test_scan_ignores_node_modules(tmp_repo):
    scanner = RepoScanner()
    records = scanner.scan(tmp_repo)
    paths = [r.relative_path for r in records]
    assert not any("node_modules" in p for p in paths)


def test_scan_language_detection(tmp_repo):
    scanner = RepoScanner()
    records = scanner.scan(tmp_repo)
    lang_map = {r.path.name: r.language for r in records}
    assert lang_map["main.py"] == "python"
    assert lang_map["utils.js"] == "javascript"
    assert lang_map["README.md"] == "markdown"
