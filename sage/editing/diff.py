"""
Generate unified diffs from LLM output.

The LLM is prompted to output raw unified diff blocks. This module:
1. Sends the prompt and collects the full streamed response
2. Parses out all `--- a/... +++ b/...` diff blocks
3. Applies each diff to the original file content to produce the new content
"""
from __future__ import annotations

import re
import difflib
from pathlib import Path

from pydantic import BaseModel

from sage.agent.prompts import SYSTEM_EDIT
from sage.llm.manager import get_provider
from sage.rag.retriever import Retriever
from sage.rag.store import SearchResult


class FileDiff(BaseModel):
    file_path: Path
    original_content: str
    new_content: str
    diff_text: str


DIFF_BLOCK_RE = re.compile(
    r"---\s+a/(.+?)\n\+\+\+\s+b/(.+?)\n((?:[@+\- ][^\n]*\n?)*)",
    re.MULTILINE,
)


class DiffGenerator:
    def __init__(self, project_root: Path | None = None) -> None:
        self._root = project_root or Path.cwd()
        self._provider = get_provider()
        self._retriever = Retriever()

    async def generate(self, task: str, k: int = 8) -> list[FileDiff]:
        results = self._retriever.retrieve(task, k=k)
        context = self._retriever.compress(results)

        user_content = (
            f"Here is relevant code from the repository:\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"Task: {task}\n\n"
            f"Generate unified diffs to accomplish this task. "
            f"Output ONLY the diff blocks, nothing else."
        )

        messages = [
            {"role": "system", "content": SYSTEM_EDIT},
            {"role": "user", "content": user_content},
        ]

        # Collect full streamed response
        raw = ""
        async for chunk in self._provider.chat(messages, stream=True):
            raw += chunk

        return self._parse_diffs(raw)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_diffs(self, llm_output: str) -> list[FileDiff]:
        diffs: list[FileDiff] = []

        for match in DIFF_BLOCK_RE.finditer(llm_output):
            file_a = match.group(1).strip()
            diff_body = match.group(3)

            # Reconstruct the full diff text
            diff_text = f"--- a/{file_a}\n+++ b/{file_a}\n{diff_body}"

            file_path = self._root / file_a
            if not file_path.exists():
                continue

            original = file_path.read_text(errors="replace")
            new_content = self._apply_patch(original, diff_text, file_path)
            if new_content is None:
                continue

            diffs.append(
                FileDiff(
                    file_path=file_path,
                    original_content=original,
                    new_content=new_content,
                    diff_text=diff_text,
                )
            )

        return diffs

    def _apply_patch(self, original: str, diff_text: str, file_path: Path) -> str | None:
        """Apply a unified diff to original content, return new content or None on failure."""
        try:
            import patch_ng as patch_lib

            pset = patch_lib.fromstring(diff_text.encode())
            if not pset:
                return None

            orig_lines = original.splitlines(keepends=True)
            result = pset.apply(orig_lines)
            if result is False:
                return None
            return "".join(result) if isinstance(result, list) else result
        except Exception:
            # Fallback: unified_diff reconstruction when patch-ng fails
            return self._naive_apply(original, diff_text)

    def _naive_apply(self, original: str, diff_text: str) -> str | None:
        """
        Naive line-by-line diff application as fallback.
        Works for simple single-hunk diffs.
        """
        lines = original.splitlines(keepends=True)
        output: list[str] = list(lines)
        offset = 0

        hunk_re = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
        diff_lines = diff_text.splitlines(keepends=True)

        i = 0
        while i < len(diff_lines):
            m = hunk_re.match(diff_lines[i])
            if m:
                src_start = int(m.group(1)) - 1
                hunk_lines = []
                i += 1
                while i < len(diff_lines) and not hunk_re.match(diff_lines[i]) and not diff_lines[i].startswith("--- ") and not diff_lines[i].startswith("+++ "):
                    hunk_lines.append(diff_lines[i])
                    i += 1

                # Apply hunk
                pos = src_start + offset
                removes = [ln[1:] for ln in hunk_lines if ln.startswith("-")]
                adds = [ln[1:] for ln in hunk_lines if ln.startswith("+")]

                # Find and remove old lines, keep context lines
                new_output = output[:pos]
                j = pos
                for rem in removes:
                    while j < len(output) and output[j].rstrip("\n") != rem.rstrip("\n"):
                        new_output.append(output[j])
                        j += 1
                    if j < len(output):
                        j += 1  # skip the removed line
                new_output.extend(adds)
                new_output.extend(output[j:])
                offset += len(adds) - len(removes)
                output = new_output
            else:
                i += 1

        return "".join(output)


def make_diff_text(original: str, new: str, file_path: str) -> str:
    """Generate a unified diff string from two file contents."""
    orig_lines = original.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )
    return "\n".join(diff)
