"""Syntax validation before writing patched files to disk."""
from __future__ import annotations

import ast
from pathlib import Path


class SyntaxValidator:
    def validate(self, file_path: Path, content: str) -> tuple[bool, str]:
        suffix = file_path.suffix.lower()
        if suffix == ".py":
            return self._validate_python(content)
        if suffix in (".js", ".ts"):
            return self._validate_with_treesitter(content, suffix)
        # For other types we trust the diff — no validation
        return True, ""

    def _validate_python(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"

    def _validate_with_treesitter(self, code: str, suffix: str) -> tuple[bool, str]:
        try:
            import tree_sitter_javascript as tsjavascript
            from tree_sitter import Language, Parser

            lang = Language(tsjavascript.language())
            parser = Parser(lang)
            tree = parser.parse(code.encode())
            if tree.root_node.has_error:
                return False, "Syntax error detected by tree-sitter"
            return True, ""
        except Exception:
            # If tree-sitter is unavailable, skip validation
            return True, ""
