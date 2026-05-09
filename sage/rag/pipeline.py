"""
RAG pipeline: retrieve relevant chunks → build prompt → stream LLM answer.
"""
from __future__ import annotations

from typing import AsyncIterator

from sage.agent.prompts import SYSTEM_ASK
from sage.llm.manager import get_provider
from sage.rag.retriever import Retriever


class RAGPipeline:
    def __init__(self, model: str | None = None) -> None:
        self._retriever = Retriever()
        self._provider = get_provider()
        self._model = model

    async def answer(self, query: str, k: int = 10) -> AsyncIterator[str]:
        results = self._retriever.retrieve(query, k=k)
        context = self._retriever.compress(results)

        if context:
            user_content = (
                f"Here is relevant code from the repository:\n\n"
                f"{context}\n\n"
                f"---\n\n"
                f"Question: {query}"
            )
        else:
            user_content = query

        messages = [
            {"role": "system", "content": SYSTEM_ASK},
            {"role": "user", "content": user_content},
        ]

        async for chunk in self._provider.chat(messages, stream=True, model=self._model):
            yield chunk

    def get_sources(self, query: str, k: int = 10) -> list[dict]:
        """Return source metadata for a query (used by tests and UI)."""
        results = self._retriever.retrieve(query, k=k)
        return [
            {
                "file": r.chunk.file_path,
                "lines": f"{r.chunk.start_line}-{r.chunk.end_line}",
                "score": round(r.score, 3),
                "symbol": r.chunk.symbol_name,
            }
            for r in results
        ]
