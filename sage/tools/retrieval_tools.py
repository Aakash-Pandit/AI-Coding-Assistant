"""Codebase semantic search tool (wraps the RAG retriever)."""
from __future__ import annotations

from sage.tools.registry import REGISTRY


@REGISTRY.tool
def search_codebase(query: str, k: int = 5) -> str:
    """
    Semantically search the indexed codebase and return relevant code snippets.
    Use this to find functions, classes, or patterns related to a topic.
    Requires the codebase to be indexed first with `sage index`.
    """
    from sage.config.settings import get_settings
    from sage.rag.store import FAISSStore
    from sage.rag.embedder import Embedder

    settings = get_settings()
    index_path = settings.index_dir / "repo.faiss"

    if not index_path.exists():
        return "Error: no index found. Run `sage index` first."

    try:
        embedder = Embedder()
        store = FAISSStore.load(settings.index_dir)
        vec = embedder.embed_one(query)
        results = store.search(vec, k=k)

        if not results:
            return f"No results found for: {query}"

        lines = [f"Search results for: '{query}'\n"]
        for i, r in enumerate(results, 1):
            c = r.chunk
            lines.append(
                f"{i}. [{c.language}] {c.file_path} lines {c.start_line}-{c.end_line}"
                + (f" ({c.symbol_name})" if c.symbol_name else "")
                + f"  score={r.score:.3f}"
            )
            lines.append(f"```{c.language}")
            snippet = c.content[:400] + ("…" if len(c.content) > 400 else "")
            lines.append(snippet)
            lines.append("```\n")

        return "\n".join(lines)
    except Exception as e:
        return f"Error during codebase search: {e}"
