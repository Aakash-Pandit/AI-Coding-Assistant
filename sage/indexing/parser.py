"""
Parse source files into semantic chunks.

For code files (.py, .js, .ts, .go): use Tree-sitter to extract
function/class/method boundaries so each chunk is a complete logical unit.

For prose/config files (.md, .yaml, .json): fall back to a sliding-window
character splitter since there are no meaningful AST boundaries.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from sage.indexing.scanner import FileRecord

ChunkType = Literal["function", "class", "method", "block", "prose"]

# Maximum characters per chunk for prose/config files
PROSE_CHUNK_SIZE = 1500
PROSE_OVERLAP = 200


class Chunk(BaseModel):
    content: str
    file_path: str          # relative path shown to the user
    language: str
    start_line: int
    end_line: int
    chunk_type: ChunkType
    symbol_name: str = ""   # function/class name when available


class CodeParser:
    def __init__(self) -> None:
        self._parsers: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, record: FileRecord) -> list[Chunk]:
        text = record.path.read_text(errors="replace")
        lang = record.language

        if lang in ("python", "javascript", "typescript", "go"):
            chunks = self._parse_with_treesitter(text, record)
            if chunks:
                return chunks
            # Fallback if tree-sitter grammar unavailable
        return self._sliding_window(text, record)

    # ------------------------------------------------------------------
    # Tree-sitter parsing
    # ------------------------------------------------------------------

    def _get_parser(self, language: str):
        if language in self._parsers:
            return self._parsers[language]

        try:
            import tree_sitter_python as tspython
            import tree_sitter_javascript as tsjavascript
            import tree_sitter_go as tsgo
            from tree_sitter import Language, Parser

            lang_map = {
                "python": tspython.language(),
                "javascript": tsjavascript.language(),
                "typescript": tsjavascript.language(),  # close enough for chunking
                "go": tsgo.language(),
            }
            if language not in lang_map:
                return None

            parser = Parser(Language(lang_map[language]))
            self._parsers[language] = parser
            return parser
        except Exception:
            return None

    def _parse_with_treesitter(self, text: str, record: FileRecord) -> list[Chunk]:
        parser = self._get_parser(record.language)
        if parser is None:
            return []

        tree = parser.parse(text.encode())
        lines = text.splitlines()
        chunks: list[Chunk] = []

        # Node types that represent logical top-level units
        target_types = {
            "function_definition",      # Python
            "async_function_definition",
            "class_definition",         # Python
            "function_declaration",     # JS/TS/Go
            "method_definition",        # JS/TS class methods
            "lexical_declaration",      # JS/TS const fn = ...
            "type_declaration",         # Go
        }

        for node in self._walk(tree.root_node):
            if node.type not in target_types:
                continue
            start = node.start_point[0]   # 0-indexed line
            end = node.end_point[0]

            content = "\n".join(lines[start : end + 1])
            if len(content.strip()) < 20:
                continue

            symbol = self._extract_name(node, text)
            chunk_type = self._node_to_chunk_type(node.type)

            chunks.append(
                Chunk(
                    content=content,
                    file_path=record.relative_path,
                    language=record.language,
                    start_line=start + 1,   # 1-indexed for display
                    end_line=end + 1,
                    chunk_type=chunk_type,
                    symbol_name=symbol,
                )
            )

        return chunks

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)

    def _extract_name(self, node, text: str) -> str:
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                start = child.start_byte
                end = child.end_byte
                return text[start:end]
        return ""

    def _node_to_chunk_type(self, node_type: str) -> ChunkType:
        if "class" in node_type:
            return "class"
        if "method" in node_type:
            return "method"
        if "function" in node_type or "declaration" in node_type:
            return "function"
        return "block"

    # ------------------------------------------------------------------
    # Sliding-window fallback (markdown, yaml, json, etc.)
    # ------------------------------------------------------------------

    def _sliding_window(self, text: str, record: FileRecord) -> list[Chunk]:
        chunks: list[Chunk] = []
        lines = text.splitlines()
        full_text = "\n".join(lines)

        step = PROSE_CHUNK_SIZE - PROSE_OVERLAP
        pos = 0
        while pos < len(full_text):
            slice_text = full_text[pos : pos + PROSE_CHUNK_SIZE]
            if not slice_text.strip():
                pos += step
                continue

            # Approximate line numbers for the slice
            start_line = full_text[:pos].count("\n") + 1
            end_line = start_line + slice_text.count("\n")

            chunks.append(
                Chunk(
                    content=slice_text,
                    file_path=record.relative_path,
                    language=record.language,
                    start_line=start_line,
                    end_line=end_line,
                    chunk_type="prose",
                )
            )
            pos += step

        return chunks
