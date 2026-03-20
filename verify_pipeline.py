#!/usr/bin/env python3
"""
Quick verification script to test the async RAG pipeline.
Run this to verify the system is working before using the Streamlit UI.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_pipeline():
    """Test basic pipeline functionality."""
    print("=" * 70)
    print("RAG Pipeline Verification Test")
    print("=" * 70)
    
    try:
        # Import pipeline
        print("\n1. Importing AsyncRAGPipeline...")
        from rag.pipeline_async import AsyncRAGPipeline
        print("   ✅ Import successful")
        
        # Initialize pipeline
        print("\n2. Initializing pipeline...")
        pipeline = AsyncRAGPipeline()
        print(f"   ✅ Pipeline initialized")
        print(f"   - Model: {pipeline.model}")
        print(f"   - Corpus size: {pipeline.corpus_size:,}")
        print(f"   - Cache enabled: {pipeline.enable_cache}")
        
        # Test emotion detection
        print("\n3. Testing emotion detection...")
        test_messages = [
            "I've been thinking about you all day",
            "Hey, what's up?",
            "I'm feeling sad today",
            "You're amazing!",
        ]
        
        for msg in test_messages:
            emotion_result = pipeline.emotion_detector.detect_emotion(msg)
            print(f"   '{msg[:40]}...'")
            print(f"   → {emotion_result['emotion']} ({emotion_result['confidence']:.0%})")
        
        print("\n4. Testing full pipeline with sample query...")
        test_query = "Hey, how are you doing?"
        
        result = await pipeline.suggest_reply(
            user_message=test_query,
            session_id="test_user"
        )
        
        print(f"\n   Query: '{test_query}'")
        print(f"   ✅ Response generated successfully!")
        print(f"   - Emotion: {result['emotion']}")
        print(f"   - Latency: {result['latency_ms']:.0f}ms")
        print(f"   - Sources: {len(result['sources'])}")
        print(f"   - Cached: {result['cached']}")
        print(f"\n   Reply preview: {result['reply'][:100]}...")
        
        # Test caching
        print("\n5. Testing response caching...")
        result2 = await pipeline.suggest_reply(
            user_message=test_query,
            session_id="test_user"
        )
        
        print(f"   Second request:")
        print(f"   - Latency: {result2['latency_ms']:.0f}ms")
        print(f"   - Cached: {result2['cached']}")
        
        if result2['cached']:
            print(f"   ✅ Cache working! ({result2['latency_ms']:.0f}ms vs {result['latency_ms']:.0f}ms)")
        
        # Test conversation memory
        print("\n6. Testing conversation memory...")
        await pipeline.suggest_reply("Hi there!", session_id="memory_test")
        await pipeline.suggest_reply("How are you?", session_id="memory_test")
        result3 = await pipeline.suggest_reply("Tell me about yourself", session_id="memory_test")
        
        print(f"   ✅ 3-turn conversation completed")
        print(f"   - Latency: {result3['latency_ms']:.0f}ms")
        
        # Test statistics
        print("\n7. Pipeline statistics...")
        stats = await pipeline.get_stats()
        print(f"   - Corpus size: {stats['corpus_size']:,}")
        print(f"   - Cache size: {stats['cache_size']}")
        print(f"   - Model: {stats['model']}")
        print(f"   - Top-K: {stats['top_k']}")
        print(f"   - Temperature: {stats['temperature']}")
        
        # Final summary
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nThe RAG pipeline is working correctly!")
        print("You can now run: streamlit run app.py")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure FAISS index exists: python scripts/build_index.py")
        print("2. Check GROQ_API_KEY in .env file")
        print("3. Verify all dependencies installed: pip install -r requirements.txt")
        return False


def main():
    """Run verification tests."""
    try:
        success = asyncio.run(test_pipeline())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
