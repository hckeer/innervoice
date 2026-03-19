#!/usr/bin/env python3
"""
build_index_production.py

Lightweight FAISS index builder for production deployment.
Runs during Render build phase (more resources available than runtime).

Usage:
    python build_index_production.py
"""

import json
import pickle
import sys
import os
from pathlib import Path

print("=" * 80)
print("PRODUCTION INDEX BUILDER - InnerVoice")
print("=" * 80)

# Set up paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_DATA = DATA_DIR / "sample_conversations.jsonl"
INDEX_PATH = DATA_DIR / "index.faiss"
METADATA_PATH = DATA_DIR / "metadata.pkl"

# Ensure data dir exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

print(f"\n📂 Data directory: {DATA_DIR}")
print(f"📄 Sample data: {SAMPLE_DATA}")
print(f"💾 Index output: {INDEX_PATH}")
print(f"📋 Metadata output: {METADATA_PATH}")

# Check if sample data exists
if not SAMPLE_DATA.exists():
    print(f"\n❌ ERROR: Sample data not found at {SAMPLE_DATA}")
    print("   Cannot build index without data.")
    sys.exit(1)

# Load sample conversations
print(f"\n📚 Loading sample conversations...")
records = []
with open(SAMPLE_DATA, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"   Warning: Skipping invalid JSON line: {e}")
                continue

if not records:
    print("\n❌ ERROR: No valid records found in sample data")
    sys.exit(1)

print(f"   ✅ Loaded {len(records):,} conversations")

# Import heavy dependencies only when needed
print("\n🔧 Loading embedding model (this may take 1-2 minutes)...")
try:
    import numpy as np
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"\n❌ ERROR: Required dependencies not installed: {e}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Use smaller, faster model for production
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
print(f"   Model: {EMBEDDING_MODEL}")

model = SentenceTransformer(EMBEDDING_MODEL)
print("   ✅ Model loaded")

# Extract texts
texts = [r["input"] for r in records]

# Generate embeddings
print(f"\n🧮 Generating embeddings for {len(texts):,} texts...")
print("   (This may take 2-3 minutes on limited resources)")

embeddings = model.encode(
    texts,
    batch_size=32,  # Smaller batch for limited memory
    show_progress_bar=True,
    normalize_embeddings=True,
    convert_to_numpy=True,
)

print(f"   ✅ Embeddings generated: shape={embeddings.shape}")

# Build FAISS index
dim = embeddings.shape[1]
print(f"\n🏗️  Building FAISS index (dimension={dim})...")

index = faiss.IndexFlatIP(dim)  # Inner product (cosine similarity)
index.add(embeddings.astype(np.float32))

print(f"   ✅ Index built: {index.ntotal:,} vectors")

# Save index
print(f"\n💾 Saving index to {INDEX_PATH}...")
faiss.write_index(index, str(INDEX_PATH))

index_size_mb = INDEX_PATH.stat().st_size / (1024 * 1024)
print(f"   ✅ Index saved ({index_size_mb:.2f} MB)")

# Save metadata
print(f"\n📋 Saving metadata to {METADATA_PATH}...")
with open(METADATA_PATH, "wb") as f:
    pickle.dump(records, f)

metadata_size_mb = METADATA_PATH.stat().st_size / (1024 * 1024)
print(f"   ✅ Metadata saved ({metadata_size_mb:.2f} MB)")

# Verify files exist
print("\n🔍 Verifying files...")
if INDEX_PATH.exists() and METADATA_PATH.exists():
    print("   ✅ Index file exists")
    print("   ✅ Metadata file exists")
    print("\n" + "=" * 80)
    print("✅ BUILD SUCCESSFUL - Index ready for production")
    print("=" * 80)
    sys.exit(0)
else:
    print("   ❌ ERROR: Files not created properly")
    sys.exit(1)
