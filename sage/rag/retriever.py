"""
Retriever: embed query → FAISS search → rerank → compress into LLM context.
"""
from __future__ import annotations

from sage.config.settings import get_settings
from sage.rag.embedder import Embedder
from sage.rag.store import FAISSStore, SearchResult

MAX_CONTEXT_CHARS = 12_000   # ~3k tokens at 4 chars/token
RERANK_KEYWORD_WEIGHT = 0.15  # blend keyword overlap into semantic score


class Retriever:
    def __init__(self) -> None:
        settings = get_settings()
        self._store: FAISSStore | None = None
        self._embedder = Embedder()
        self._index_dir = settings.index_dir

    def _get_store(self) -> FAISSStore:
        if self._store is None:
            self._store = FAISSStore.load(self._index_dir)
        return self._store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(self, query: str, k: int = 10) -> list[SearchResult]:
        store = self._get_store()
        vec = self._embedder.embed_one(query)
        results = store.search(vec, k=k)
        return self._rerank(results, query)

    def compress(self, results: list[SearchResult], max_chars: int = MAX_CONTEXT_CHARS) -> str:
        """
        Concatenate top chunks into a single context string, trimmed to budget.
        Each chunk gets a header showing file path and line range.
        """
        sections: list[str] = []
        used = 0

        for r in results:
            c = r.chunk
            header = f"### {c.file_path} (lines {c.start_line}-{c.end_line})"
            body = c.content.strip()
            block = f"{header}\n```{c.language}\n{body}\n```"

            if used + len(block) > max_chars:
                # Trim the last block to fit the budget
                remaining = max_chars - used
                if remaining > 200:
                    block = block[:remaining] + "\n... (truncated)"
                    sections.append(block)
                break

            sections.append(block)
            used += len(block)

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rerank(self, results: list[SearchResult], query: str) -> list[SearchResult]:
        """Boost chunks that contain query keywords on top of semantic score."""
        query_tokens = set(query.lower().split())

        def score(r: SearchResult) -> float:
            text = r.chunk.content.lower()
            keyword_hits = sum(1 for t in query_tokens if t in text)
            overlap = keyword_hits / max(len(query_tokens), 1)
            return r.score + RERANK_KEYWORD_WEIGHT * overlap

        return sorted(results, key=score, reverse=True)
