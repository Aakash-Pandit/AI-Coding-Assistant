"""Unit tests for the editing subsystem."""
from pathlib import Path
import pytest

from sage.editing.validator import SyntaxValidator
from sage.editing.patcher import FilePatcher, BACKUP_SUFFIX
from sage.editing.diff import FileDiff, make_diff_text


# ---------- Validator ----------

def test_valid_python():
    v = SyntaxValidator()
    ok, err = v.validate(Path("test.py"), "def foo():\n    return 1\n")
    assert ok is True
    assert err == ""


def test_invalid_python():
    v = SyntaxValidator()
    ok, err = v.validate(Path("test.py"), "def foo(\n    return 1\n")
    assert ok is False
    assert "SyntaxError" in err


def test_non_python_always_valid():
    v = SyntaxValidator()
    ok, _ = v.validate(Path("config.yaml"), "key: !!invalid yaml {{{{")
    assert ok is True


# ---------- Patcher ----------

def test_patcher_applies_and_backs_up(tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("def hello():\n    return 'hi'\n")

    diff = FileDiff(
        file_path=f,
        original_content=f.read_text(),
        new_content="def hello():\n    return 'hello world'\n",
        diff_text="",
    )

    patcher = FilePatcher()
    ok, err = patcher.apply(diff)

    assert ok is True, err
    assert "hello world" in f.read_text()
    # backup should be cleaned up after explicit cleanup
    backup = f.with_suffix(f.suffix + BACKUP_SUFFIX)
    assert backup.exists()  # backup still there until cleanup_backups called


def test_patcher_rejects_invalid_syntax(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def ok(): pass\n")

    diff = FileDiff(
        file_path=f,
        original_content=f.read_text(),
        new_content="def broken(\n    pass\n",
        diff_text="",
    )

    patcher = FilePatcher()
    ok, err = patcher.apply(diff)

    assert ok is False
    assert "SyntaxError" in err
    # Original file must be untouched
    assert "def ok" in f.read_text()


def test_patcher_rollback(tmp_path):
    f = tmp_path / "rollback.py"
    original = "def original(): pass\n"
    f.write_text(original)

    diff = FileDiff(
        file_path=f,
        original_content=original,
        new_content="def changed(): pass\n",
        diff_text="",
    )

    patcher = FilePatcher()
    patcher.apply(diff)
    assert "changed" in f.read_text()

    patcher.rollback(f)
    assert "original" in f.read_text()


# ---------- make_diff_text ----------

def test_make_diff_text_shows_changes():
    original = "line1\nline2\nline3\n"
    new = "line1\nline2 modified\nline3\n"
    diff = make_diff_text(original, new, "test.py")
    assert "-line2" in diff
    assert "+line2 modified" in diff
