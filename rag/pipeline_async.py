"""
rag/pipeline_async.py

Production-ready async RAG pipeline that orchestrates:
  - Emotion detection
  - Hybrid retrieval (vector + BM25 + reranking)
  - Conversation memory management
  - Personality-driven response generation
  - Robust error handling with retry logic

This pipeline is designed for:
  - High concurrency (50+ users)
  - Low latency (<800ms target)
  - Personality-driven romantic responses
  - Production-grade reliability

Usage:
    import asyncio
    from rag.pipeline_async import AsyncRAGPipeline
    
    pipeline = AsyncRAGPipeline()
    result = await pipeline.suggest_reply(
        user_message="Hey, what's up?",
        session_id="user123"
    )
    print(result["reply"])
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

from config import GROQ_MODEL, TOP_K, MAX_TOKENS, TEMPERATURE
from rag.llm_client_async import AsyncLLMClient
from rag.hybrid_retriever import HybridRetriever
from rag.emotion_detector import EmotionDetector
from rag.personality_engine import PersonalityEngine
from rag.memory_manager import ConversationMemory

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result from the RAG pipeline."""
    reply: str
    context: str
    emotion: str
    confidence: float
    sources: list[dict]
    latency_ms: float
    cached: bool = False


class AsyncRAGPipeline:
    """
    High-performance async RAG pipeline for personality-driven conversation.
    
    Features:
    - Emotion-aware hybrid retrieval (vector + BM25 + reranking)
    - Conversation memory (last 5 turns)
    - Personality-driven romantic responses
    - Response caching for repeated queries
    - Full async implementation for high concurrency
    - Robust error handling with graceful fallbacks
    
    Attributes:
        model: LLM model name (default: openai/gpt-oss-120b)
        top_k: Number of results to retrieve (default: 5)
        max_tokens: Max tokens in LLM response (default: 512)
        temperature: LLM temperature (default: 0.7)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_cache: bool = True,
    ) -> None:
        """
        Initialize the async RAG pipeline.
        
        Args:
            model: LLM model name (defaults to config.GROQ_MODEL)
            top_k: Number of results to retrieve (defaults to config.TOP_K)
            max_tokens: Max tokens in response (defaults to config.MAX_TOKENS)
            temperature: LLM temperature (defaults to config.TEMPERATURE)
            enable_cache: Enable response caching (default: True)
        """
        self.model = model or GROQ_MODEL
        self.top_k = top_k or TOP_K
        self.max_tokens = max_tokens or MAX_TOKENS
        self.temperature = temperature if temperature is not None else TEMPERATURE
        self.enable_cache = enable_cache

        # Initialize basic components
        self.llm = AsyncLLMClient(model=self.model)
        self.emotion_detector = EmotionDetector()
        self.personality = PersonalityEngine()
        self.memory = ConversationMemory(max_turns=5)
        
        # Load vector store and initialize retriever
        from config import USE_QDRANT, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
        from config import FAISS_INDEX_PATH, METADATA_PATH
        
        if USE_QDRANT:
            # Use Qdrant Cloud
            logger.info("Using Qdrant Cloud vector store")
            from rag.qdrant_vector_store import QdrantVectorStore
            
            if not QDRANT_URL or not QDRANT_API_KEY:
                raise RuntimeError(
                    "Qdrant credentials missing. Set QDRANT_URL and QDRANT_API_KEY in .env"
                )
            
            self.vector_store = QdrantVectorStore(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
                collection_name=QDRANT_COLLECTION,
                embedding_dim=384
            )
            
            # Load/initialize collection
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Sync load in running loop
                    import asyncio as _asyncio
                    _asyncio.run(self.vector_store.load(FAISS_INDEX_PATH, METADATA_PATH))
                else:
                    asyncio.run(self.vector_store.load(FAISS_INDEX_PATH, METADATA_PATH))
            except RuntimeError:
                asyncio.run(self.vector_store.load(FAISS_INDEX_PATH, METADATA_PATH))
            
            logger.info(f"Qdrant collection loaded: {self.vector_store.size:,} points")
            
            # For hybrid retriever, we need metadata
            # In Qdrant mode, we'll fetch a sample for BM25 index
            # Note: This is a simplified approach - for production, consider building BM25 separately
            logger.warning("Hybrid retriever may have limited BM25 functionality in Qdrant mode")
            self.vector_store.metadata = []  # Will be populated on-demand
            
        else:
            # Use local FAISS
            logger.info("Using local FAISS vector store")
            from rag.vector_store_async import AsyncVectorStore
            
            self.vector_store = AsyncVectorStore()
            
            # Load index synchronously during initialization
            # (Streamlit cache will ensure this only happens once)
            import asyncio
            if FAISS_INDEX_PATH.exists() and METADATA_PATH.exists():
                try:
                    # Use asyncio.run if no event loop, otherwise use existing loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Can't use run() in running loop, load synchronously
                            import faiss
                            import pickle
                            self.vector_store.index = faiss.read_index(str(FAISS_INDEX_PATH))
                            with open(METADATA_PATH, "rb") as f:
                                self.vector_store.metadata = pickle.load(f)
                            logger.info(f"Loaded {self.vector_store.index.ntotal:,} vectors")
                        else:
                            asyncio.run(self.vector_store.load(FAISS_INDEX_PATH, METADATA_PATH))
                    except RuntimeError:
                        # No event loop, create one
                        asyncio.run(self.vector_store.load(FAISS_INDEX_PATH, METADATA_PATH))
                except Exception as e:
                    logger.error(f"Failed to load index: {e}")
                    raise RuntimeError(
                        f"Cannot initialize pipeline: Index loading failed. "
                        f"Please run: python scripts/build_index.py"
                    ) from e
            else:
                raise RuntimeError(
                    f"FAISS index not found at {FAISS_INDEX_PATH}. "
                    f"Please run: python scripts/build_index.py"
                )
            
            # Check if we have data
            if not self.vector_store.metadata:
                raise RuntimeError(
                    "Metadata is empty. Please rebuild the index: "
                    "python scripts/build_index.py"
                )
        
        # Initialize hybrid retriever with loaded data
        # Note: For Qdrant, metadata list may be empty - retriever will work in vector-only mode
        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            metadata=getattr(self.vector_store, 'metadata', []),
        )
        
        # Simple in-memory cache (query -> response)
        # For production, use Redis or similar
        self._response_cache: dict[str, PipelineResult] = {}
        
        corpus_size = len(getattr(self.vector_store, 'metadata', [])) or self.vector_store.size
        logger.info(
            f"AsyncRAGPipeline initialized: model={self.model}, "
            f"top_k={self.top_k}, cache_enabled={self.enable_cache}, "
            f"corpus_size={corpus_size}, use_qdrant={USE_QDRANT}"
        )

    async def suggest_reply(
        self,
        user_message: str,
        session_id: str = "default",
        k: Optional[int] = None,
        bypass_cache: bool = False,
    ) -> dict:
        """
        Generate a personality-driven reply using the full async RAG pipeline.
        
        Pipeline flow:
        1. Check cache (if enabled)
        2. Detect user emotion
        3. Retrieve conversation history from memory
        4. Hybrid retrieval (vector + BM25 + reranking + emotion boosting)
        5. Build personality-driven prompt
        6. Generate response with retry logic
        7. Update conversation memory
        8. Cache result
        
        Args:
            user_message: The user's input message
            session_id: Session identifier for memory management
            k: Number of results to retrieve (defaults to self.top_k)
            bypass_cache: Force fresh generation, skip cache check
            
        Returns:
            dict with keys:
                - reply: Generated response string
                - context: Formatted context string (for debugging/UI)
                - emotion: Detected emotion category
                - confidence: Emotion detection confidence score
                - sources: List of retrieved source documents
                - latency_ms: Total pipeline latency in milliseconds
                - cached: Whether response came from cache
                
        Example:
            result = await pipeline.suggest_reply(
                user_message="I've been thinking about you...",
                session_id="user123"
            )
            print(result["reply"])  # Romantic, personality-driven response
            print(f"Detected emotion: {result['emotion']}")
            print(f"Latency: {result['latency_ms']:.0f}ms")
        """
        start_time = time.time()
        k = k or self.top_k
        
        # Cache key (include session for personalization)
        cache_key = f"{session_id}:{user_message.strip().lower()}"
        
        # Check cache
        if self.enable_cache and not bypass_cache and cache_key in self._response_cache:
            cached_result = self._response_cache[cache_key]
            logger.info(f"Cache hit for: {user_message[:50]}...")
            return {
                "reply": cached_result.reply,
                "context": cached_result.context,
                "emotion": cached_result.emotion,
                "confidence": cached_result.confidence,
                "sources": cached_result.sources,
                "latency_ms": (time.time() - start_time) * 1000,
                "cached": True,
            }
        
        try:
            # Step 1: Detect emotion
            logger.info(f"Starting pipeline for: {user_message[:50]}...")
            detected_emotion = self.emotion_detector.detect(user_message)
            emotion = detected_emotion.value  # Get string value from enum
            confidence = 1.0  # Rule-based detector has full confidence
            
            logger.info(
                f"Emotion detected: {emotion} "
                f"(confidence: {confidence:.2f}) for: {user_message[:50]}..."
            )
            
            # Step 2: Get conversation history
            logger.info("Getting conversation history...")
            conversation_history = await self.memory.get_history()
            logger.info(f"Got {len(conversation_history)} messages in history")
            
            # Step 3: Hybrid retrieval with emotion awareness
            # Note: Retriever detects emotion internally
            logger.info("Starting hybrid retrieval...")
            sources = await self.retriever.search_async(
                query=user_message,
                k=k,
            )
            logger.info(f"Retrieved {len(sources)} sources")
            
            # Step 4: Build personality-driven prompt
            logger.info("Building prompt messages...")
            messages = self.personality.build_messages(
                user_message=user_message,
                context_examples=sources,
                conversation_history=conversation_history,
                detected_emotion=detected_emotion,  # Pass the Emotion enum object
            )
            logger.info(f"Built {len(messages)} prompt messages")
            
            # Step 5: Generate response (with retry logic built-in)
            logger.info(f"Calling LLM with model: {self.model}...")
            reply = await self.llm.generate(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            logger.info(f"LLM response received: {len(reply)} chars")
            
            # Step 6: Update conversation memory
            await self.memory.add_message("user", user_message)
            await self.memory.add_message("assistant", reply)
            logger.info("Memory updated")
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Format context for result display
            context = self._format_context(sources)
            
            # Create result
            result = PipelineResult(
                reply=reply,
                context=context,
                emotion=emotion,
                confidence=confidence,
                sources=sources,
                latency_ms=latency_ms,
                cached=False,
            )
            
            # Cache result
            if self.enable_cache:
                self._response_cache[cache_key] = result
                # Limit cache size (simple LRU-like behavior)
                if len(self._response_cache) > 1000:
                    # Remove oldest 20% of entries
                    keys_to_remove = list(self._response_cache.keys())[:200]
                    for key in keys_to_remove:
                        del self._response_cache[key]
            
            logger.info(
                f"Pipeline complete: latency={latency_ms:.0f}ms, "
                f"emotion={emotion}, sources={len(sources)}"
            )
            
            return {
                "reply": result.reply,
                "context": result.context,
                "emotion": result.emotion,
                "confidence": result.confidence,
                "sources": result.sources,
                "latency_ms": result.latency_ms,
                "cached": result.cached,
            }
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            
            # Graceful fallback: personality-based response without retrieval
            fallback_reply = self.personality.get_fallback_response(
                emotion=emotion if 'emotion' in locals() else "neutral"
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "reply": fallback_reply,
                "context": "",
                "emotion": emotion if 'emotion' in locals() else "neutral",
                "confidence": 0.0,
                "sources": [],
                "latency_ms": latency_ms,
                "cached": False,
            }

    async def stream_reply(
        self,
        user_message: str,
        session_id: str = "default",
        k: Optional[int] = None,
    ) -> tuple[AsyncGenerator[str, None], str, list[dict], str]:
        """
        Stream a reply token-by-token for real-time UI updates.
        
        Note: Current implementation returns full response at once.
        Full streaming requires Groq streaming API support.
        
        Args:
            user_message: The user's input message
            session_id: Session identifier for memory management
            k: Number of results to retrieve
            
        Returns:
            Tuple of (token_generator, context, sources, emotion)
            
        Example:
            generator, context, sources, emotion = await pipeline.stream_reply(
                user_message="Tell me something sweet",
                session_id="user123"
            )
            async for token in generator:
                print(token, end="", flush=True)
        """
        k = k or self.top_k
        
        # Detect emotion
        detected_emotion = self.emotion_detector.detect(user_message)
        
        # Get history
        conversation_history = await self.memory.get_history()
        
        # Retrieve sources
        sources = await self.retriever.search_async(
            query=user_message,
            k=k,
        )
        
        # Build prompt
        messages = self.personality.build_messages(
            user_message=user_message,
            context_examples=sources,
            conversation_history=conversation_history,
            detected_emotion=detected_emotion,  # Pass the Emotion enum object
        )
        
        # Generate full response
        # TODO: Implement true streaming when Groq streaming API is available
        reply = await self.llm.generate(
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        
        # Update memory
        await self.memory.add_message("user", user_message)
        await self.memory.add_message("assistant", reply)
        
        # Format context for return value
        context = self._format_context(sources)
        emotion = detected_emotion.value
        
        # Create async generator
        async def token_generator() -> AsyncGenerator[str, None]:
            yield reply
        
        return token_generator(), context, sources, emotion

    def _format_context(self, sources: list[dict]) -> str:
        """
        Format retrieved sources into a context string.
        
        Args:
            sources: List of source dicts with 'input', 'response', 'score'
            
        Returns:
            Formatted context string
        """
        if not sources:
            return "No relevant context found."
        
        formatted = []
        for i, source in enumerate(sources, 1):
            input_text = source.get("input", "")
            response_text = source.get("response", "")
            score = source.get("score", 0.0)
            
            formatted.append(
                f"Example {i} (relevance: {score:.2f}):\n"
                f"  Input: {input_text}\n"
                f"  Response: {response_text}"
            )
        
        return "\n\n".join(formatted)

    async def clear_memory(self, session_id: str) -> None:
        """
        Clear conversation memory for a specific session.
        
        Args:
            session_id: Session identifier
        """
        await self.memory.clear_session(session_id)
        logger.info(f"Cleared memory for session: {session_id}")

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._response_cache.clear()
        logger.info("Response cache cleared")

    async def reload_index(self) -> None:
        """Reload the retriever's index (after rebuilding)."""
        await self.retriever.reload()
        logger.info("Retriever index reloaded")

    @property
    def corpus_size(self) -> int:
        """Get the size of the indexed corpus."""
        try:
            return len(self.vector_store.metadata) if hasattr(self, 'vector_store') else 0
        except Exception:
            return 0

    async def get_stats(self) -> dict:
        """
        Get pipeline statistics.
        
        Returns:
            Dict with pipeline stats (corpus size, cache size, etc.)
        """
        return {
            "corpus_size": self.corpus_size,
            "cache_size": len(self._response_cache),
            "cache_enabled": self.enable_cache,
            "model": self.model,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


# Convenience function for simple usage
async def get_reply(user_message: str, session_id: str = "default") -> str:
    """
    Simple convenience function to get a reply without managing pipeline instance.
    
    Args:
        user_message: User's input message
        session_id: Session identifier
        
    Returns:
        Generated reply string
        
    Example:
        reply = await get_reply("Hey, what's up?")
        print(reply)
    """
    pipeline = AsyncRAGPipeline()
    result = await pipeline.suggest_reply(user_message, session_id)
    return result["reply"]
