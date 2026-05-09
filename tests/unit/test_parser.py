"""Unit tests for the Tree-sitter code parser."""
from pathlib import Path

import pytest

from sage.indexing.parser import CodeParser
from sage.indexing.scanner import FileRecord


def make_record(tmp_path: Path, filename: str, content: str) -> FileRecord:
    p = tmp_path / filename
    p.write_text(content)
    ext = Path(filename).suffix
    lang_map = {".py": "python", ".js": "javascript", ".md": "markdown"}
    return FileRecord(
        path=p,
        language=lang_map[ext],
        size=len(content.encode()),
        relative_path=filename,
    )


PYTHON_SRC = """\
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""

JS_SRC = """\
function greet(name) {
  return `Hello, ${name}`;
}

class Greeter {
  constructor(name) {
    this.name = name;
  }
}
"""

MD_SRC = "# Hello\n\nThis is a test document with some content.\n" * 20


def test_python_chunks_by_function(tmp_path):
    parser = CodeParser()
    record = make_record(tmp_path, "calc.py", PYTHON_SRC)
    chunks = parser.parse(record)
    names = [c.symbol_name for c in chunks]
    types = [c.chunk_type for c in chunks]
    assert "add" in names
    assert "Calculator" in names
    assert "function" in types
    assert "class" in types


def test_python_chunk_has_line_numbers(tmp_path):
    parser = CodeParser()
    record = make_record(tmp_path, "calc.py", PYTHON_SRC)
    chunks = parser.parse(record)
    for chunk in chunks:
        assert chunk.start_line >= 1
        assert chunk.end_line >= chunk.start_line


def test_js_chunks_extracted(tmp_path):
    parser = CodeParser()
    record = make_record(tmp_path, "greet.js", JS_SRC)
    chunks = parser.parse(record)
    assert len(chunks) >= 1


def test_markdown_uses_sliding_window(tmp_path):
    parser = CodeParser()
    record = make_record(tmp_path, "README.md", MD_SRC)
    chunks = parser.parse(record)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.chunk_type == "prose"


def test_chunk_content_non_empty(tmp_path):
    parser = CodeParser()
    record = make_record(tmp_path, "calc.py", PYTHON_SRC)
    chunks = parser.parse(record)
    for chunk in chunks:
        assert chunk.content.strip() != ""
