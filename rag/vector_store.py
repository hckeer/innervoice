"""
rag/vector_store.py

FAISS wrapper that manages index loading, saving, and
semantic search. Returns results with similarity scores.
"""

import pickle
import numpy as np
from pathlib import Path


class VectorStore:
    """Manages a FAISS flat inner-product index + metadata."""

    def __init__(self) -> None:
        self.index = None
        self.metadata: list[dict] = []
        self._model = None
        self._model_name: str = ""

    # ── Loading / Saving ──────────────────────────────────────────────────────

    def load(self, index_path: str | Path, metadata_path: str | Path) -> None:
        import faiss
        self.index = faiss.read_index(str(index_path))
        with open(metadata_path, "rb") as f:
            self.metadata = pickle.load(f)
        print(f"[VectorStore] Loaded {self.index.ntotal:,} vectors + {len(self.metadata):,} metadata records")

    def save(self, index_path: str | Path, metadata_path: str | Path) -> None:
        import faiss
        faiss.write_index(self.index, str(index_path))
        with open(metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)

    def is_loaded(self) -> bool:
        return self.index is not None and len(self.metadata) > 0

    # ── Embedding helper ──────────────────────────────────────────────────────

    def _get_model(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        if self._model is None or self._model_name != model_name:
            self._model = SentenceTransformer(model_name)
            self._model_name = model_name
        return self._model

    def embed(self, text: str, model_name: str) -> np.ndarray:
        model = self._get_model(model_name)
        vec = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)
        return vec.astype(np.float32)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 5, model_name: str = "all-MiniLM-L6-v2") -> list[dict]:
        """
        Semantic search over the index.

        Returns a list of dicts:
          {"input": ..., "response": ..., "score": float}
        sorted by descending similarity.
        """
        if not self.is_loaded():
            raise RuntimeError("Vector store is not loaded. Call load() first.")

        query_vec = self.embed(query, model_name)
        k = min(k, self.index.ntotal)
        scores, indices = self.index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            record = dict(self.metadata[idx])
            record["score"] = float(score)
            results.append(record)

        return results

    # ── Adding new records ────────────────────────────────────────────────────

    def add_texts(self, records: list[dict], model_name: str = "all-MiniLM-L6-v2") -> None:
        """Add new {input, response} pairs to the index at runtime."""
        import faiss

        texts = [r["input"] for r in records]
        model = self._get_model(model_name)
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

        if self.index is None:
            dim = vecs.shape[1]
            self.index = faiss.IndexFlatIP(dim)

        self.index.add(vecs.astype(np.float32))
        self.metadata.extend(records)

    @property
    def size(self) -> int:
        return self.index.ntotal if self.index is not None else 0
