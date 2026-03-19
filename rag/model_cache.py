"""
rag/model_cache.py

Global singleton model cache for embedding and reranking models.
Ensures models load only once across all instances.
"""

import threading
from typing import Optional, Dict
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)


class ModelCache:
    """Thread-safe singleton model cache."""
    
    _instance: Optional['ModelCache'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._models: Dict[str, SentenceTransformer] = {}
                    cls._instance._initialized = True
        return cls._instance
    
    def get_model(self, model_name: str) -> SentenceTransformer:
        """Get or load a model from cache."""
        if model_name not in self._models:
            with self._lock:
                if model_name not in self._models:
                    logger.info(f"Loading model: {model_name}")
                    self._models[model_name] = SentenceTransformer(model_name)
                    logger.info(f"Model loaded: {model_name}")
        return self._models[model_name]
    
    def clear(self):
        """Clear all cached models (for testing)."""
        with self._lock:
            self._models.clear()


# Global instance
_model_cache = ModelCache()


def get_model(model_name: str) -> SentenceTransformer:
    """Get model from global cache."""
    return _model_cache.get_model(model_name)
