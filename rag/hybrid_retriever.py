"""
rag/hybrid_retriever.py

Hybrid retrieval combining:
- Vector similarity (FAISS)
- Keyword matching (BM25)
- Emotion-aware filtering
- Cross-encoder reranking
"""

import asyncio
import numpy as np
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi
from pathlib import Path
import logging

from rag.model_cache import get_model
from rag.emotion_detector import EmotionDetector, Emotion
from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Advanced retriever with hybrid search and reranking.
    """
    
    def __init__(
        self,
        vector_store,
        metadata: List[Dict],
        use_reranking: bool = True,
        alpha: float = 0.7  # Weight: 0.7 vector, 0.3 keyword
    ):
        self.vector_store = vector_store
        self.metadata = metadata
        self.use_reranking = use_reranking
        self.alpha = alpha
        
        # Build BM25 index (skip if no metadata, e.g., Qdrant mode)
        self.corpus = []
        self.bm25 = None
        if metadata:
            self.corpus = [record["input"] for record in metadata]
            tokenized_corpus = [doc.lower().split() for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
            logger.info(f"BM25 index built with {len(self.corpus)} documents")
        else:
            logger.warning("No metadata provided - BM25 search disabled (vector-only mode)")
        
        # Emotion detector
        self.emotion_detector = EmotionDetector()
        
        # Reranker model (lightweight cross-encoder)
        self.reranker = None
        if use_reranking:
            try:
                from sentence_transformers import CrossEncoder
                self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("Reranker loaded")
            except Exception as e:
                logger.warning(f"Reranker loading failed: {e}")
                self.use_reranking = False
    
    async def search_async(
        self,
        query: str,
        k: int = 5,
        top_k_candidates: int = 20,
        min_score: float = 0.3
    ) -> List[Dict]:
        """
        Async hybrid search with emotion awareness.
        
        Args:
            query: User query
            k: Final number of results
            top_k_candidates: Initial candidates before reranking
            min_score: Minimum similarity threshold
            
        Returns:
            List of {input, response, score, emotion} dicts
        """
        # Detect query emotion
        query_emotion = self.emotion_detector.detect(query)
        logger.info(f"Query emotion: {query_emotion.value}")
        
        # 1. Vector search (run in thread pool to avoid blocking)
        loop = asyncio.get_event_loop()
        vector_results = await loop.run_in_executor(
            None,
            self._vector_search,
            query,
            top_k_candidates
        )
        
        # 2. BM25 keyword search
        bm25_results = self._bm25_search(query, top_k_candidates)
        
        # 3. Fuse scores
        fused_results = self._fuse_scores(
            vector_results,
            bm25_results,
            query_emotion
        )
        
        # Filter by minimum score
        fused_results = [r for r in fused_results if r["score"] >= min_score]
        
        if not fused_results:
            logger.warning(f"No results above threshold {min_score}")
            return []
        
        # 4. Rerank top candidates
        if self.use_reranking and self.reranker and len(fused_results) > k:
            reranked = await loop.run_in_executor(
                None,
                self._rerank,
                query,
                fused_results[:top_k_candidates]
            )
            return reranked[:k]
        
        return fused_results[:k]
    
    def _vector_search(self, query: str, k: int) -> List[Dict]:
        """Vector similarity search."""
        try:
            results = self.vector_store.search(
                query,
                k=k,
                model_name=EMBEDDING_MODEL
            )
            return results
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _bm25_search(self, query: str, k: int) -> Dict[str, float]:
        """BM25 keyword search."""
        if not self.bm25:
            # BM25 disabled (e.g., Qdrant mode)
            return {}
        
        try:
            tokenized_query = query.lower().split()
            scores = self.bm25.get_scores(tokenized_query)
            
            # Normalize scores to [0, 1]
            max_score = max(scores) if max(scores) > 0 else 1.0
            normalized = {
                self.corpus[i]: score / max_score
                for i, score in enumerate(scores)
            }
            return normalized
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return {}
    
    def _fuse_scores(
        self,
        vector_results: List[Dict],
        bm25_scores: Dict[str, float],
        query_emotion: Emotion
    ) -> List[Dict]:
        """
        Fuse vector and BM25 scores with emotion boosting.
        """
        fused = {}
        
        # Process vector results
        for result in vector_results:
            input_text = result["input"]
            vec_score = result["score"]
            bm25_score = bm25_scores.get(input_text, 0.0)
            
            # Weighted fusion
            combined_score = self.alpha * vec_score + (1 - self.alpha) * bm25_score
            
            # Emotion boost
            doc_emotion = result.get("emotion", Emotion.NEUTRAL)
            if isinstance(doc_emotion, str):
                try:
                    doc_emotion = Emotion(doc_emotion)
                except ValueError:
                    doc_emotion = Emotion.NEUTRAL
            
            boost = self.emotion_detector.get_boost_factor(query_emotion, doc_emotion)
            combined_score *= boost
            
            fused[input_text] = {
                **result,
                "score": combined_score,
                "vec_score": vec_score,
                "bm25_score": bm25_score,
                "emotion_boost": boost
            }
        
        # Sort by fused score
        sorted_results = sorted(
            fused.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        return sorted_results
    
    def _rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """Rerank candidates using cross-encoder."""
        if not self.reranker or not candidates:
            return candidates
        
        try:
            # Prepare query-candidate pairs
            pairs = [(query, c["input"]) for c in candidates]
            
            # Score with cross-encoder
            scores = self.reranker.predict(pairs)
            
            # Update scores and sort
            for candidate, score in zip(candidates, scores):
                candidate["rerank_score"] = float(score)
                # Combine original score with rerank score
                candidate["final_score"] = 0.6 * candidate["score"] + 0.4 * float(score)
            
            reranked = sorted(
                candidates,
                key=lambda x: x.get("final_score", x["score"]),
                reverse=True
            )
            
            return reranked
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return candidates
    
    # Sync wrapper
    def search(self, query: str, k: int = 5, **kwargs) -> List[Dict]:
        """Synchronous search wrapper."""
        return asyncio.run(self.search_async(query, k, **kwargs))
