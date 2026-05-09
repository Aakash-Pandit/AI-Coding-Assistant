"""Unit tests for FAISSStore."""
import numpy as np
import pytest

from sage.indexing.parser import Chunk
from sage.rag.store import FAISSStore


def _make_chunk(name: str, line: int = 1) -> Chunk:
    return Chunk(
        content=f"def {name}(): pass",
        file_path="test.py",
        language="python",
        start_line=line,
        end_line=line + 2,
        chunk_type="function",
        symbol_name=name,
    )


def _rand_vecs(n: int, dim: int = 384) -> np.ndarray:
    vecs = np.random.randn(n, dim).astype(np.float32)
    # L2-normalise to mimic embedder output
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


def test_add_and_search():
    store = FAISSStore()
    chunks = [_make_chunk("foo"), _make_chunk("bar")]
    vecs = _rand_vecs(2)
    store.add(chunks, vecs)

    results = store.search(vecs[0], k=1)
    assert len(results) == 1
    assert results[0].chunk.symbol_name == "foo"
    assert results[0].score > 0.99  # exact match → cosine ≈ 1.0


def test_total_count():
    store = FAISSStore()
    store.add([_make_chunk("a"), _make_chunk("b")], _rand_vecs(2))
    assert store.total == 2


def test_save_and_load(tmp_path):
    store = FAISSStore()
    chunks = [_make_chunk("save_me")]
    vecs = _rand_vecs(1)
    store.add(chunks, vecs)
    store.save(tmp_path)

    loaded = FAISSStore.load(tmp_path)
    assert loaded.total == 1
    results = loaded.search(vecs[0], k=1)
    assert results[0].chunk.symbol_name == "save_me"


def test_search_empty_store():
    store = FAISSStore()
    results = store.search(_rand_vecs(1)[0], k=5)
    assert results == []


def test_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        FAISSStore.load(tmp_path / "nonexistent")
