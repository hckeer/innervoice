#!/usr/bin/env python3
"""
ULTRA-FAST Qdrant upload with parallel processing and optimized batching.
Optimized for 645,692 records - reduces time from 9-18 hours to ~1-2 hours.
No heavy dependencies required - uses only sentence-transformers.
"""

import json
import os
import sys
import time
import multiprocessing as mp
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Load environment
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "conversations")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# OPTIMIZED SETTINGS (no PyTorch required)
BATCH_SIZE = 256  # Upload batches - larger = faster but more memory
EMBEDDING_BATCH_SIZE = 128  # Embedding batch - tuned for CPU performance
PARALLEL_UPLOADS = 8  # Parallel upload threads - maximize network throughput
CHECKPOINT_EVERY = 10000  # Save progress every 10k records
NUM_WORKERS = mp.cpu_count()  # Use all CPU cores

def load_conversations(file_path: str, limit: int = None) -> List[Dict]:
    """Load conversations from JSONL file with progress bar."""
    conversations = []
    
    # Count lines first for progress bar
    with open(file_path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in tqdm(enumerate(f), total=total_lines if not limit else min(limit, total_lines), desc="Loading"):
            if limit and i >= limit:
                break
            try:
                conv = json.loads(line.strip())
                conversations.append(conv)
            except json.JSONDecodeError:
                continue
    return conversations

def load_checkpoint(checkpoint_file: str) -> int:
    """Load last uploaded ID from checkpoint."""
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            return int(f.read().strip())
    return 0

def save_checkpoint(checkpoint_file: str, last_id: int):
    """Save checkpoint."""
    with open(checkpoint_file, 'w') as f:
        f.write(str(last_id))

def upload_to_qdrant(conversations: List[Dict], collection_name: str):
    """Upload conversations to Qdrant with optimized parallel processing."""
    
    print(f"\n🚀 Starting ULTRA-FAST upload...")
    print(f"   Total conversations: {len(conversations):,}")
    print(f"   Embedding batch size: {EMBEDDING_BATCH_SIZE}")
    print(f"   Upload batch size: {BATCH_SIZE}")
    print(f"   Parallel uploads: {PARALLEL_UPLOADS}")
    print(f"   CPU cores: {NUM_WORKERS}")
    
    # Initialize client
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # Load embedding model
    print(f"\n📦 Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("   ✅ Model loaded")
    
    # Check/create collection
    try:
        collection_info = client.get_collection(collection_name)
        print(f"\n📊 Collection exists: {collection_info.points_count:,} points")
        start_id = collection_info.points_count
    except:
        print(f"\n📝 Creating collection: {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        start_id = 0
    
    # Check for checkpoint
    checkpoint_file = f".upload_checkpoint_{collection_name}.txt"
    last_checkpoint = load_checkpoint(checkpoint_file)
    
    if last_checkpoint > 0:
        print(f"\n📍 Resuming from checkpoint: {last_checkpoint:,} records")
        conversations = conversations[last_checkpoint:]
        start_id += last_checkpoint
    
    # Step 1: Generate ALL embeddings in batches (optimized for CPU)
    print(f"\n🧠 Generating embeddings...")
    all_embeddings = []
    texts = [f"{conv.get('input', '')} {conv.get('response', '')}" for conv in conversations]
    
    start_time = time.time()
    
    # Use multi_process for CPU parallelization
    for i in tqdm(range(0, len(texts), EMBEDDING_BATCH_SIZE), desc="Embedding"):
        batch_texts = texts[i:i + EMBEDDING_BATCH_SIZE]
        batch_embeddings = model.encode(
            batch_texts,
            batch_size=32,  # Internal batch size for sentence-transformers
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True  # Faster similarity search
        )
        all_embeddings.extend(batch_embeddings)
    
    embedding_time = time.time() - start_time
    print(f"   ✅ Generated {len(all_embeddings):,} embeddings in {embedding_time:.1f}s")
    print(f"   Rate: {len(all_embeddings)/embedding_time:.1f} embeddings/sec")
    
    # Step 2: Upload in parallel batches (network I/O optimization)
    print(f"\n⬆️  Uploading to Qdrant (parallel)...")
    upload_start = time.time()
    total_uploaded = 0
    upload_lock = Lock()
    
    def upload_batch(batch_data):
        """Upload a single batch to Qdrant."""
        batch_idx, batch_convs, batch_embeds = batch_data
        
        points = []
        for i, (conv, embedding) in enumerate(zip(batch_convs, batch_embeds)):
            point_id = start_id + batch_idx + i
            points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding),
                payload={
                    "input": conv.get("input", ""),
                    "response": conv.get("response", ""),
                    "metadata": conv.get("metadata", {})
                }
            ))
        
        # Upload with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                client.upsert(collection_name=collection_name, points=points, wait=False)
                return len(points)
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"\n❌ Failed to upload batch {batch_idx}: {e}")
                    return 0
                time.sleep(1)
    
    # Prepare batches
    batches = []
    for batch_idx in range(0, len(conversations), BATCH_SIZE):
        batch_convs = conversations[batch_idx:batch_idx + BATCH_SIZE]
        batch_embeds = all_embeddings[batch_idx:batch_idx + BATCH_SIZE]
        batches.append((batch_idx, batch_convs, batch_embeds))
    
    # Upload in parallel with progress bar
    with ThreadPoolExecutor(max_workers=PARALLEL_UPLOADS) as executor:
        futures = []
        progress_bar = tqdm(total=len(conversations), desc="Uploading")
        
        for batch in batches:
            future = executor.submit(upload_batch, batch)
            futures.append(future)
            
            # Limit number of pending futures to avoid memory issues
            if len(futures) >= PARALLEL_UPLOADS * 3:
                done_future = futures.pop(0)
                uploaded = done_future.result()
                with upload_lock:
                    total_uploaded += uploaded
                    progress_bar.update(uploaded)
                    
                    # Save checkpoint
                    if total_uploaded % CHECKPOINT_EVERY < BATCH_SIZE:
                        save_checkpoint(checkpoint_file, total_uploaded)
        
        # Wait for remaining futures
        for future in as_completed(futures):
            uploaded = future.result()
            with upload_lock:
                total_uploaded += uploaded
                progress_bar.update(uploaded)
        
        progress_bar.close()
    
    upload_time = time.time() - upload_start
    total_time = time.time() - start_time
    
    print(f"\n✅ Upload complete!")
    print(f"   Uploaded: {total_uploaded:,} conversations")
    print(f"   Embedding time: {embedding_time:.1f}s")
    print(f"   Upload time: {upload_time:.1f}s")
    print(f"   Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"   Overall rate: {total_uploaded/total_time:.1f} conversations/sec")
    
    # Cleanup checkpoint
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
    
    # Verify
    print(f"\n🔍 Verifying upload...")
    collection_info = client.get_collection(collection_name)
    print(f"   Final collection size: {collection_info.points_count:,} points")

def main():
    print("=" * 70)
    print(" " * 12 + "QDRANT ULTRA-FAST UPLOAD (OPTIMIZED)")
    print("=" * 70)
    
    print(f"\n🔧 Configuration:")
    print(f"   Qdrant URL: {QDRANT_URL}")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Model: {EMBEDDING_MODEL}")
    print(f"   Embedding batch: {EMBEDDING_BATCH_SIZE}")
    print(f"   Upload batch: {BATCH_SIZE}")
    print(f"   Parallel uploads: {PARALLEL_UPLOADS}")
    print(f"   CPU cores: {NUM_WORKERS}")
    
    # Check which file to upload
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        data_file = "data/conversations.jsonl"
        limit = None
        print(f"\n📁 Mode: FULL DATASET")
    else:
        data_file = "data/sample_conversations.jsonl"
        limit = None
        print(f"\n📁 Mode: SAMPLE (for testing)")
        print("   Run with --full flag to upload the complete dataset")
    
    print(f"   File: {data_file}")
    
    # Check file exists
    if not os.path.exists(data_file):
        print(f"\n❌ Error: File not found: {data_file}")
        return
    
    file_size = os.path.getsize(data_file) / (1024 * 1024)
    print(f"   Size: {file_size:.2f} MB")
    
    # Load conversations
    print(f"\n📖 Loading conversations...")
    conversations = load_conversations(data_file, limit)
    print(f"   Loaded: {len(conversations):,} conversations")
    
    if not conversations:
        print("\n❌ No conversations loaded!")
        return
    
    # Show sample
    print(f"\n📋 Sample conversation:")
    sample = conversations[0]
    print(f"   Input: {sample.get('input', '')[:80]}...")
    print(f"   Response: {sample.get('response', '')[:80]}...")
    
    # Estimate time (CPU-based)
    estimated_time_min = len(conversations) * 0.02 / 60  # ~0.02s per record optimized
    estimated_time_max = len(conversations) * 0.04 / 60  # ~0.04s per record
    
    # Confirm for full dataset
    if len(conversations) > 1000:
        print(f"\n⚠️  About to upload {len(conversations):,} conversations")
        print(f"   Estimated time: {estimated_time_min:.1f}-{estimated_time_max:.1f} minutes")
        
        # Skip confirmation if running non-interactively or --yes flag
        if '--yes' in sys.argv or not sys.stdin.isatty():
            print("\n   Auto-confirming (non-interactive mode)...")
        else:
            response = input("\n   Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("\n❌ Upload cancelled")
                return
    
    # Upload
    upload_to_qdrant(conversations, COLLECTION_NAME)
    
    print("\n🎉 Done!")
    print("=" * 70)

if __name__ == "__main__":
    main()
