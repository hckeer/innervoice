"""
rag/qdrant_vector_store.py

Async Qdrant vector store - drop-in replacement for AsyncVectorStore.
Compatible with existing pipeline architecture.
"""

import asyncio
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from rag.model_cache import get_model

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """
    Async Qdrant vector store with drop-in compatibility for FAISS-based AsyncVectorStore.
    Uses Qdrant Cloud for fully managed, persistent vector storage.
    """
    
    def __init__(
        self,
        url: str,
        api_key: str,
        collection_name: str = "conversations",
        embedding_dim: int = 384  # all-MiniLM-L6-v2 dimension
    ):
        """
        Initialize Qdrant client.
        
        Args:
            url: Qdrant cluster URL (e.g., https://xxx.gcp.cloud.qdrant.io:6333)
            api_key: Qdrant API key
            collection_name: Name of the collection
            embedding_dim: Embedding dimension (384 for all-MiniLM-L6-v2)
        """
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self._lock = asyncio.Lock()
        
        # Initialize client
        self.client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=60
        )
        
        # Cache for metadata (for backward compatibility)
        self.metadata: List[Dict] = []
        self._metadata_loaded = False
        
        logger.info(f"Qdrant client initialized: {url}")
    
    # ── Collection Management ─────────────────────────────────────────────────
    
    async def create_collection_if_not_exists(self) -> None:
        """Create collection if it doesn't exist."""
        loop = asyncio.get_event_loop()
        
        def _create():
            try:
                collections = self.client.get_collections().collections
                if any(c.name == self.collection_name for c in collections):
                    logger.info(f"Collection '{self.collection_name}' already exists")
                    return
                
                # Create collection with cosine distance (equivalent to FAISS IndexFlatIP)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection '{self.collection_name}'")
            except Exception as e:
                logger.error(f"Failed to create collection: {e}")
                raise
        
        await loop.run_in_executor(None, _create)
    
    # ── Loading / Compatibility ───────────────────────────────────────────────
    
    async def load(self, index_path: Path, metadata_path: Path) -> None:
        """
        Load metadata for backward compatibility.
        In Qdrant mode, this just ensures collection exists and loads metadata count.
        """
        async with self._lock:
            await self.create_collection_if_not_exists()
            
            # Get collection info
            loop = asyncio.get_event_loop()
            
            def _get_count():
                collection_info = self.client.get_collection(self.collection_name)
                return collection_info.points_count
            
            count = await loop.run_in_executor(None, _get_count)
            logger.info(f"Qdrant collection loaded: {count:,} points")
            self._metadata_loaded = True
    
    async def save(self, index_path: Path, metadata_path: Path) -> None:
        """
        No-op for Qdrant (data is already persisted in cloud).
        Kept for API compatibility.
        """
        logger.info("Save called (no-op for Qdrant - data already persisted)")
    
    def is_loaded(self) -> bool:
        """Check if store is ready."""
        return self._metadata_loaded
    
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
        model_name: str = "all-MiniLM-L6-v2",
        emotion_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Async semantic search using Qdrant.
        
        Args:
            query: Search query
            k: Number of results
            model_name: Embedding model name
            emotion_filter: Optional emotion filter (e.g., "romantic", "playful")
            
        Returns:
            List of {input, response, score, metadata} dicts
        """
        if not self.is_loaded():
            raise RuntimeError("Qdrant store not loaded. Call load() first.")
        
        # Embed query
        query_vec = await self.embed_async([query], model_name)
        query_vector = query_vec[0].tolist()
        
        # Search in thread pool
        loop = asyncio.get_event_loop()
        
        def _search():
            # Build filter if emotion is specified
            query_filter = None
            if emotion_filter:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="emotion",
                            match=MatchValue(value=emotion_filter)
                        )
                    ]
                )
            
            # Search Qdrant
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=k,
                query_filter=query_filter,
                with_payload=True
            )
            
            # Format results to match FAISS format
            results = []
            for hit in search_result:
                payload = hit.payload
                results.append({
                    "input": payload.get("input", ""),
                    "response": payload.get("response", ""),
                    "score": float(hit.score),
                    "metadata": payload.get("metadata", {}),
                    "emotion": payload.get("metadata", {}).get("emotion", "neutral")
                })
            
            return results
        
        results = await loop.run_in_executor(None, _search)
        return results
    
    # ── Adding Records ────────────────────────────────────────────────────────
    
    async def add_texts_async(
        self,
        records: List[Dict],
        model_name: str = "all-MiniLM-L6-v2",
        batch_size: int = 100
    ) -> None:
        """
        Add new records to Qdrant asynchronously.
        
        Args:
            records: List of {input, response, metadata} dicts
            model_name: Embedding model name
            batch_size: Upload batch size
        """
        async with self._lock:
            await self.create_collection_if_not_exists()
            
            # Extract texts and generate embeddings
            texts = [r["input"] for r in records]
            embeddings = await self.embed_async(texts, model_name)
            
            loop = asyncio.get_event_loop()
            
            def _upload_batch(start_idx: int, end_idx: int):
                points = []
                for i in range(start_idx, end_idx):
                    record = records[i]
                    vector = embeddings[i].tolist()
                    
                    # Create point with payload
                    point = PointStruct(
                        id=start_idx + i,  # Use sequential IDs
                        vector=vector,
                        payload={
                            "input": record.get("input", ""),
                            "response": record.get("response", ""),
                            "metadata": record.get("metadata", {})
                        }
                    )
                    points.append(point)
                
                # Upload batch
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                
                return len(points)
            
            # Upload in batches
            total = len(records)
            for start in range(0, total, batch_size):
                end = min(start + batch_size, total)
                uploaded = await loop.run_in_executor(None, _upload_batch, start, end)
                logger.info(f"Uploaded batch {start}-{end} ({uploaded} points)")
            
            logger.info(f"Successfully uploaded {total:,} records to Qdrant")
    
    @property
    def size(self) -> int:
        """Get number of vectors in collection."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return collection_info.points_count
        except:
            return 0
    
    # ── Utility Methods ───────────────────────────────────────────────────────
    
    async def clear_collection(self) -> None:
        """Delete and recreate collection (for re-indexing)."""
        loop = asyncio.get_event_loop()
        
        def _clear():
            try:
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted collection '{self.collection_name}'")
            except:
                pass
        
        await loop.run_in_executor(None, _clear)
        await self.create_collection_if_not_exists()
    
    # ── Sync wrappers for backward compatibility ──────────────────────────────
    
    def load_sync(self, index_path: Path, metadata_path: Path) -> None:
        """Synchronous load wrapper."""
        asyncio.run(self.load(index_path, metadata_path))
    
    def search(self, query: str, k: int = 5, model_name: str = "all-MiniLM-L6-v2") -> List[Dict]:
        """Synchronous search wrapper."""
        return asyncio.run(self.search_async(query, k, model_name))
