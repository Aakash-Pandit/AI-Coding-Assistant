"""Integration tests for the RAG retriever (requires a built index)."""
import pytest
import numpy as np

from sage.indexing.parser import Chunk
from sage.rag.store import FAISSStore
from sage.rag.retriever import Retriever
from sage.rag.embedder import Embedder


def _build_temp_index(tmp_path, chunks_data: list[dict]) -> None:
    embedder = Embedder()
    store = FAISSStore()

    chunks = [
        Chunk(
            content=d["content"],
            file_path=d.get("file_path", "test.py"),
            language="python",
            start_line=i * 10 + 1,
            end_line=i * 10 + 5,
            chunk_type="function",
            symbol_name=d.get("name", f"fn_{i}"),
        )
        for i, d in enumerate(chunks_data)
    ]

    texts = [c.content for c in chunks]
    vecs = embedder.embed(texts)
    store.add(chunks, vecs)
    store.save(tmp_path)


def test_retriever_finds_relevant_chunk(tmp_path, monkeypatch):
    _build_temp_index(tmp_path, [
        {"content": "def authenticate_user(token): ...", "name": "authenticate_user"},
        {"content": "def calculate_tax(amount, rate): return amount * rate", "name": "calculate_tax"},
        {"content": "def send_email(to, subject, body): ...", "name": "send_email"},
    ])

    from sage.config.settings import Settings
    monkeypatch.setattr("sage.rag.retriever.get_settings", lambda: Settings(index_dir=tmp_path))

    retriever = Retriever()
    retriever._index_dir = tmp_path

    results = retriever.retrieve("user authentication token", k=3)
    assert len(results) >= 1
    assert results[0].chunk.symbol_name == "authenticate_user"


def test_retriever_reranks_by_keyword(tmp_path, monkeypatch):
    _build_temp_index(tmp_path, [
        {"content": "def process_payment(card_number): ...", "name": "process_payment"},
        {"content": "def validate_jwt_token(token): decode and verify jwt", "name": "validate_jwt"},
    ])

    retriever = Retriever()
    retriever._index_dir = tmp_path

    results = retriever.retrieve("jwt token validation", k=2)
    names = [r.chunk.symbol_name for r in results]
    assert names[0] == "validate_jwt"


def test_compress_respects_budget(tmp_path):
    embedder = Embedder()
    store = FAISSStore()

    chunks = [
        Chunk(
            content="x" * 5000,  # large chunk
            file_path="big.py",
            language="python",
            start_line=1,
            end_line=100,
            chunk_type="function",
            symbol_name="big_fn",
        )
        for _ in range(5)
    ]
    vecs = embedder.embed([c.content for c in chunks])
    store.add(chunks, vecs)

    from sage.rag.store import SearchResult, ChunkMetadata
    results = [SearchResult(chunk=ChunkMetadata(**c.model_dump()), score=0.9) for c in chunks]

    retriever = Retriever()
    compressed = retriever.compress(results, max_chars=3000)
    assert len(compressed) <= 3200  # small buffer for truncation marker
