"""
Safe file patching with backup and rollback support.

Flow:
  1. Backup original → file.py.sage.bak
  2. Validate new content syntax
  3. Write atomically (tmp file → os.replace)
  4. On any failure → restore from backup
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from sage.editing.diff import FileDiff
from sage.editing.validator import SyntaxValidator

BACKUP_SUFFIX = ".sage.bak"


class FilePatcher:
    def __init__(self) -> None:
        self._validator = SyntaxValidator()
        self._applied: list[Path] = []

    def apply(self, diff: FileDiff) -> tuple[bool, str]:
        """
        Apply a single FileDiff.
        Returns (success, error_message).
        """
        path = diff.file_path
        backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)

        # 1. Backup
        shutil.copy2(path, backup)

        # 2. Syntax check
        valid, err = self._validator.validate(path, diff.new_content)
        if not valid:
            backup.unlink(missing_ok=True)
            return False, f"Syntax validation failed: {err}"

        # 3. Atomic write
        try:
            tmp = path.with_suffix(path.suffix + ".sage.tmp")
            tmp.write_text(diff.new_content, encoding="utf-8")
            os.replace(tmp, path)
            self._applied.append(path)
            return True, ""
        except OSError as e:
            self._restore(path, backup)
            return False, f"Write failed: {e}"

    def rollback(self, file_path: Path) -> bool:
        """Restore a single file from its backup."""
        backup = file_path.with_suffix(file_path.suffix + BACKUP_SUFFIX)
        return self._restore(file_path, backup)

    def rollback_all(self) -> None:
        """Restore all files that were patched this session."""
        for path in reversed(self._applied):
            self.rollback(path)
        self._applied.clear()

    def cleanup_backups(self, file_paths: list[Path]) -> None:
        """Remove backup files after a successful session."""
        for path in file_paths:
            backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
            backup.unlink(missing_ok=True)

    def _restore(self, path: Path, backup: Path) -> bool:
        if backup.exists():
            shutil.copy2(backup, path)
            backup.unlink()
            return True
        return False
