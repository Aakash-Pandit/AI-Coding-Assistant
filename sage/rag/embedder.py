from __future__ import annotations

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384


# Global cache for the embedding model to avoid reloading it on every query
_GLOBAL_MODEL = None


class Embedder:
    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.model_name = model_name

    def _load(self):
        global _GLOBAL_MODEL
        if _GLOBAL_MODEL is None:
            from sage.config.settings import get_settings

            get_settings()  # This triggers the os.environ export

            from sentence_transformers import SentenceTransformer

            _GLOBAL_MODEL = SentenceTransformer(self.model_name)
        return _GLOBAL_MODEL

    def embed(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """Return L2-normalised embeddings of shape (N, EMBED_DIM)."""
        model = self._load()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-norm → cosine via inner product
        )
        return vectors.astype(np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
