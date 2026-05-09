"""
FAISS vector store with a JSON metadata sidecar.

Layout on disk:
  <index_dir>/repo.faiss   — FAISS binary index
  <index_dir>/repo.json    — list of ChunkMetadata dicts, index == FAISS id
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from pydantic import BaseModel

from sage.indexing.parser import Chunk


class ChunkMetadata(BaseModel):
    content: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    chunk_type: str
    symbol_name: str = ""


class SearchResult(BaseModel):
    chunk: ChunkMetadata
    score: float


class FAISSStore:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
        # IndexFlatIP = exact inner-product search.
        # Since embeddings are L2-normalised, this equals cosine similarity.
        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(dim)
        self._metadata: list[ChunkMetadata] = []

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        self._index.add(embeddings)
        for chunk in chunks:
            self._metadata.append(
                ChunkMetadata(
                    content=chunk.content,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    chunk_type=chunk.chunk_type,
                    symbol_name=chunk.symbol_name,
                )
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(self, query_vec: np.ndarray, k: int = 8) -> list[SearchResult]:
        if self._index.ntotal == 0:
            return []

        k = min(k, self._index.ntotal)
        vec = query_vec.reshape(1, -1).astype(np.float32)
        scores, ids = self._index.search(vec, k)

        results: list[SearchResult] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            results.append(SearchResult(chunk=self._metadata[idx], score=float(score)))
        return results

    @property
    def total(self) -> int:
        return self._index.ntotal

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(directory / "repo.faiss"))
        meta_path = directory / "repo.json"
        meta_path.write_text(
            json.dumps([m.model_dump() for m in self._metadata], indent=2)
        )

    @classmethod
    def load(cls, directory: Path) -> "FAISSStore":
        index_path = directory / "repo.faiss"
        meta_path = directory / "repo.json"

        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"No index found at {directory}. Run `sage index` first.")

        store = cls()
        store._index = faiss.read_index(str(index_path))
        raw: list[dict[str, Any]] = json.loads(meta_path.read_text())
        store._metadata = [ChunkMetadata(**m) for m in raw]
        return store
