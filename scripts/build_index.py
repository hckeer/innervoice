"""
scripts/build_index.py

PRODUCTION VERSION: Builds FAISS index with emotion metadata preservation
and async component support.

Key improvements over v1:
- Uses global model cache to avoid duplicate model loading
- Preserves emotion metadata from processed dataset
- Better metadata structure for hybrid retrieval
- Batch processing optimization
- Progress tracking and statistics

Reads data/conversations.jsonl, embeds each 'input' field
using sentence-transformers, and saves a FAISS index +
enhanced metadata pickle.

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --src data/conversations.jsonl
    python scripts/build_index.py --verify  # Test index after building
"""

import json
import pickle
import argparse
import sys
import os
import asyncio
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from pathlib import Path
from tqdm import tqdm
from config import (
    CONVERSATIONS_PATH,
    FAISS_INDEX_PATH,
    METADATA_PATH,
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    SAMPLE_CONVERSATIONS_PATH,
)

# Import model cache for efficient loading
try:
    from rag.model_cache import ModelCache
    MODEL_CACHE_AVAILABLE = True
except ImportError:
    print("[warn] ModelCache not available - using direct loading")
    MODEL_CACHE_AVAILABLE = False


def load_conversations(path: Path) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def build_index(src_path: Path, verify: bool = False) -> None:
    """
    Build FAISS index with emotion metadata preservation.
    
    Args:
        src_path: Path to conversations JSONL file
        verify: Run verification tests after building
    """
    import faiss
    from sentence_transformers import SentenceTransformer

    if not src_path.exists():
        # Fall back to seed dataset
        if SAMPLE_CONVERSATIONS_PATH.exists():
            print(f"[warn] {src_path} not found, using seed dataset.")
            src_path = SAMPLE_CONVERSATIONS_PATH
        else:
            print("[error] No conversation data found. Run process_dataset.py first.")
            sys.exit(1)

    print(f"Loading conversations from: {src_path}")
    records = load_conversations(src_path)
    print(f"  {len(records):,} records loaded")
    
    # Analyze emotion distribution if available
    emotions = []
    has_emotions = any("metadata" in r and "emotion" in r.get("metadata", {}) for r in records)
    
    if has_emotions:
        print("\nEmotion distribution in dataset:")
        for r in records:
            emotion = r.get("metadata", {}).get("emotion", "neutral")
            emotions.append(emotion)
        
        emotion_counts = Counter(emotions)
        for emotion, count in emotion_counts.most_common():
            percentage = (count / len(emotions)) * 100
            print(f"  {emotion:12s}: {count:6,} ({percentage:5.1f}%)")
    else:
        print("\n[info] No emotion metadata found in dataset")

    # Load embedding model (use cache if available)
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    if MODEL_CACHE_AVAILABLE:
        model = ModelCache.get_embedding_model()
        print("  (using global model cache)")
    else:
        model = SentenceTransformer(EMBEDDING_MODEL)
        print("  (direct loading)")

    texts = [r["input"] for r in records]

    print(f"\nEmbedding {len(texts):,} texts (batch_size={EMBEDDING_BATCH_SIZE}) …")
    embeddings = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,  # L2-normalise for cosine via inner-product
        convert_to_numpy=True,
    )

    dim = embeddings.shape[1]
    print(f"\nBuilding FAISS IndexFlatIP (dim={dim}) …")
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    print(f"  Indexed {index.ntotal:,} vectors")

    # Save index
    FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"  Saved FAISS index → {FAISS_INDEX_PATH}")
    
    # Calculate index size
    index_size_mb = FAISS_INDEX_PATH.stat().st_size / (1024 * 1024)
    print(f"  Index size: {index_size_mb:.2f} MB")

    # Save metadata with enriched structure
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(records, f)
    print(f"  Saved metadata    → {METADATA_PATH}")
    
    metadata_size_mb = METADATA_PATH.stat().st_size / (1024 * 1024)
    print(f"  Metadata size: {metadata_size_mb:.2f} MB")

    print("\n" + "="*70)
    print("Index built successfully!")
    print("="*70)
    print(f"Total vectors: {index.ntotal:,}")
    print(f"Dimensions: {dim}")
    print(f"Emotion-tagged: {has_emotions}")
    print(f"Total size: {index_size_mb + metadata_size_mb:.2f} MB")
    
    # Run verification if requested
    if verify:
        print("\n" + "="*70)
        print("Running verification tests...")
        print("="*70)
        verify_index(index, records, model)
    
    print("\nYou can now run:  streamlit run app.py")


def verify_index(index, records: list[dict], model) -> None:
    """
    Verify the index with test queries.
    
    Args:
        index: FAISS index
        records: Metadata records
        model: Embedding model
    """
    test_queries = [
        "Hello, how are you?",
        "I miss you",
        "What's your favorite movie?",
        "That's so funny!",
        "I'm feeling sad today",
    ]
    
    print(f"\nTesting {len(test_queries)} sample queries:\n")
    
    for i, query in enumerate(test_queries, 1):
        # Embed query
        query_embedding = model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        
        # Search
        scores, indices = index.search(query_embedding.astype(np.float32), k=3)
        
        print(f"{i}. Query: \"{query}\"")
        for j, (score, idx) in enumerate(zip(scores[0], indices[0]), 1):
            record = records[idx]
            emotion = record.get("metadata", {}).get("emotion", "N/A")
            print(f"   {j}. [{emotion:10s}] {record['input'][:60]}...")
            print(f"      Response: {record['response'][:60]}...")
            print(f"      Score: {score:.3f}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build FAISS index from conversations with emotion metadata"
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=CONVERSATIONS_PATH,
        help="Source JSONL file (default: data/conversations.jsonl)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verification tests after building index",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Index Builder v2.0 – RAG Conversation Assistant (Production)")
    print("=" * 70)
    build_index(args.src, verify=args.verify)


if __name__ == "__main__":
    main()
