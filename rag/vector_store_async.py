"""
rag/vector_store_async.py

Async FAISS wrapper with global model cache and non-blocking operations.
"""

import pickle
import numpy as np
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional

from rag.model_cache import get_model

logger = logging.getLogger(__name__)


class AsyncVectorStore:
    """Async FAISS vector store with global model caching."""
    
    def __init__(self) -> None:
        self.index = None
        self.metadata: List[Dict] = []
        self._lock = asyncio.Lock()
    
    # ── Loading / Saving ──────────────────────────────────────────────────────
    
    async def load(self, index_path: Path, metadata_path: Path) -> None:
        """Load FAISS index and metadata asynchronously."""
        async with self._lock:
            loop = asyncio.get_event_loop()
            
            # Load in thread pool to avoid blocking
            def _load():
                import faiss
                index = faiss.read_index(str(index_path))
                with open(metadata_path, "rb") as f:
                    metadata = pickle.load(f)
                return index, metadata
            
            self.index, self.metadata = await loop.run_in_executor(None, _load)
            logger.info(f"Loaded {self.index.ntotal:,} vectors + {len(self.metadata):,} metadata")
    
    async def save(self, index_path: Path, metadata_path: Path) -> None:
        """Save FAISS index and metadata asynchronously."""
        async with self._lock:
            loop = asyncio.get_event_loop()
            
            def _save():
                import faiss
                faiss.write_index(self.index, str(index_path))
                with open(metadata_path, "wb") as f:
                    pickle.dump(self.metadata, f)
            
            await loop.run_in_executor(None, _save)
            logger.info("Saved index and metadata")
    
    def is_loaded(self) -> bool:
        """Check if index is loaded."""
        return self.index is not None and len(self.metadata) > 0
    
    # ── Embedding ──────────────────────────────────────────────────────────────
    
    async def embed_async(
        self,
        texts: List[str],
        model_name: str = "all-MiniLM-L6-v2"
    ) -> np.ndarray:
        """
        Async embedding using global model cache.
        Runs in thread pool to avoid blocking event loop.
        """
        loop = asyncio.get_event_loop()
        
        def _embed():
            model = get_model(model_name)
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embeddings.astype(np.float32)
        
        return await loop.run_in_executor(None, _embed)
    
    # ── Search ────────────────────────────────────────────────────────────────
    
    async def search_async(
        self,
        query: str,
        k: int = 5,
        model_name: str = "all-MiniLM-L6-v2"
    ) -> List[Dict]:
        """
        Async semantic search.
        
        Returns:
            List of {input, response, score, ...} dicts
        """
        if not self.is_loaded():
            raise RuntimeError("Vector store not loaded. Call load() first.")
        
        # Embed query
        query_vec = await self.embed_async([query], model_name)
        
        # Search in thread pool (FAISS is CPU-bound)
        loop = asyncio.get_event_loop()
        
        def _search():
            k_actual = min(k, self.index.ntotal)
            scores, indices = self.index.search(query_vec, k_actual)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                record = dict(self.metadata[idx])
                record["score"] = float(score)
                results.append(record)
            
            return results
        
        results = await loop.run_in_executor(None, _search)
        return results
    
    # ── Adding records ────────────────────────────────────────────────────────
    
    async def add_texts_async(
        self,
        records: List[Dict],
        model_name: str = "all-MiniLM-L6-v2"
    ) -> None:
        """Add new records to index asynchronously."""
        async with self._lock:
            texts = [r["input"] for r in records]
            embeddings = await self.embed_async(texts, model_name)
            
            loop = asyncio.get_event_loop()
            
            def _add():
                import faiss
                if self.index is None:
                    dim = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dim)
                
                self.index.add(embeddings)
                self.metadata.extend(records)
            
            await loop.run_in_executor(None, _add)
            logger.info(f"Added {len(records)} records to index")
    
    @property
    def size(self) -> int:
        """Get number of vectors in index."""
        return self.index.ntotal if self.index is not None else 0
    
    # ── Sync wrappers for backward compatibility ──────────────────────────────
    
    def load_sync(self, index_path: Path, metadata_path: Path) -> None:
        """Synchronous load wrapper."""
        asyncio.run(self.load(index_path, metadata_path))
    
    def search(self, query: str, k: int = 5, model_name: str = "all-MiniLM-L6-v2") -> List[Dict]:
        """Synchronous search wrapper."""
        return asyncio.run(self.search_async(query, k, model_name))
