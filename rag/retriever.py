"""
rag/retriever.py

Wraps VectorStore and provides a clean retrieval interface
for the RAG pipeline. Assembles formatted context strings
from top-k retrieved examples.
"""

from pathlib import Path
from config import (
    FAISS_INDEX_PATH,
    METADATA_PATH,
    EMBEDDING_MODEL,
    TOP_K,
)
from rag.vector_store import VectorStore


class Retriever:
    """
    High-level retriever over the FAISS vector store.

    Usage:
        retriever = Retriever()
        context = retriever.get_context("How are you?", k=5)
    """

    def __init__(
        self,
        index_path: Path | None = None,
        metadata_path: Path | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.index_path = index_path or FAISS_INDEX_PATH
        self.metadata_path = metadata_path or METADATA_PATH
        self.embedding_model = embedding_model or EMBEDDING_MODEL
        self.store = VectorStore()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            if not self.index_path.exists():
                raise FileNotFoundError(
                    f"FAISS index not found at {self.index_path}. "
                    "Run: python scripts/build_index.py"
                )
            self.store.load(self.index_path, self.metadata_path)
            self._loaded = True

    def search(self, query: str, k: int | None = None) -> list[dict]:
        """
        Return top-k similar {input, response, score} dicts.
        """
        self._ensure_loaded()
        k = k or TOP_K
        return self.store.search(query, k=k, model_name=self.embedding_model)

    def get_context(self, query: str, k: int | None = None) -> str:
        """
        Return formatted context string ready to insert into a prompt.
        Each example is numbered and includes the input and response.
        """
        results = self.search(query, k=k)
        if not results:
            return "No relevant examples found."

        lines = ["[Similar Conversation Examples]"]
        for i, r in enumerate(results, 1):
            score_pct = r.get("score", 0) * 100
            lines.append(f"\nExample {i} (similarity: {score_pct:.1f}%):")
            lines.append(f"  User:      {r['input']}")
            lines.append(f"  Assistant: {r['response']}")
        return "\n".join(lines)

    @property
    def corpus_size(self) -> int:
        self._ensure_loaded()
        return self.store.size

    def reload(self) -> None:
        """Force a reload of the index (e.g., after re-indexing)."""
        self._loaded = False
        self.store = VectorStore()
        self._ensure_loaded()
