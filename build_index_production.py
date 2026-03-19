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

# CRITICAL: Get absolute path to script directory
SCRIPT_DIR = Path(__file__).parent.resolve()
print(f"\n🔍 Script directory: {SCRIPT_DIR}")
print(f"🔍 Current working directory: {Path.cwd()}")

# Set up paths - use absolute paths
DATA_DIR = SCRIPT_DIR / "data"
SAMPLE_DATA = DATA_DIR / "sample_conversations.jsonl"
INDEX_PATH = DATA_DIR / "index.faiss"
METADATA_PATH = DATA_DIR / "metadata.pkl"

# Ensure data dir exists
print(f"\n📂 Creating data directory if needed...")
DATA_DIR.mkdir(parents=True, exist_ok=True)
print(f"   ✅ Data directory: {DATA_DIR}")
print(f"   ✅ Exists: {DATA_DIR.exists()}")

print(f"\n📋 Expected file paths:")
print(f"   Sample data: {SAMPLE_DATA}")
print(f"   Index output: {INDEX_PATH}")
print(f"   Metadata output: {METADATA_PATH}")

# Check if sample data exists
print(f"\n🔍 Checking for sample data...")
if not SAMPLE_DATA.exists():
    print(f"❌ ERROR: Sample data not found at {SAMPLE_DATA}")
    print(f"\n📂 Contents of {DATA_DIR}:")
    if DATA_DIR.exists():
        for item in DATA_DIR.iterdir():
            print(f"   - {item.name}")
    else:
        print("   Directory does not exist!")
    
    print(f"\n📂 Contents of {SCRIPT_DIR}:")
    for item in SCRIPT_DIR.iterdir():
        print(f"   - {item.name}")
    
    sys.exit(1)

print(f"   ✅ Sample data found!")

# Load sample conversations
print(f"\n📚 Loading sample conversations...")
records = []
line_count = 0
error_count = 0

with open(SAMPLE_DATA, "r", encoding="utf-8") as f:
    for line in f:
        line_count += 1
        line = line.strip()
        if line:
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                error_count += 1
                print(f"   Warning: Line {line_count} - Invalid JSON: {e}")
                continue

if error_count > 0:
    print(f"   ⚠️  Skipped {error_count} invalid lines")

if not records:
    print("\n❌ ERROR: No valid records found in sample data")
    sys.exit(1)

print(f"   ✅ Loaded {len(records):,} conversations from {line_count} lines")

# Import heavy dependencies only when needed
print("\n🔧 Loading embedding model (this may take 1-2 minutes)...")
try:
    import numpy as np
    import faiss
    from sentence_transformers import SentenceTransformer
    print("   ✅ Dependencies imported successfully")
except ImportError as e:
    print(f"\n❌ ERROR: Required dependencies not installed: {e}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Use smaller, faster model for production
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
print(f"   Model: {EMBEDDING_MODEL}")

try:
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("   ✅ Model loaded successfully")
except Exception as e:
    print(f"\n❌ ERROR: Failed to load embedding model: {e}")
    sys.exit(1)

# Extract texts
texts = [r["input"] for r in records]
print(f"\n📝 Extracted {len(texts)} text inputs")

# Generate embeddings
print(f"\n🧮 Generating embeddings for {len(texts):,} texts...")
print("   (This may take 2-3 minutes on limited resources)")

try:
    embeddings = model.encode(
        texts,
        batch_size=32,  # Smaller batch for limited memory
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    print(f"   ✅ Embeddings generated: shape={embeddings.shape}")
except Exception as e:
    print(f"\n❌ ERROR: Failed to generate embeddings: {e}")
    sys.exit(1)

# Build FAISS index
dim = embeddings.shape[1]
print(f"\n🏗️  Building FAISS index (dimension={dim})...")

try:
    index = faiss.IndexFlatIP(dim)  # Inner product (cosine similarity)
    index.add(embeddings.astype(np.float32))
    print(f"   ✅ Index built: {index.ntotal:,} vectors")
except Exception as e:
    print(f"\n❌ ERROR: Failed to build FAISS index: {e}")
    sys.exit(1)

# Save index
print(f"\n💾 Saving index to {INDEX_PATH}...")
try:
    faiss.write_index(index, str(INDEX_PATH))
    
    if not INDEX_PATH.exists():
        print(f"   ❌ ERROR: Index file was not created at {INDEX_PATH}")
        sys.exit(1)
    
    index_size_mb = INDEX_PATH.stat().st_size / (1024 * 1024)
    print(f"   ✅ Index saved successfully ({index_size_mb:.2f} MB)")
    print(f"   ✅ File exists: {INDEX_PATH}")
except Exception as e:
    print(f"\n❌ ERROR: Failed to save index: {e}")
    sys.exit(1)

# Save metadata
print(f"\n📋 Saving metadata to {METADATA_PATH}...")
try:
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(records, f)
    
    if not METADATA_PATH.exists():
        print(f"   ❌ ERROR: Metadata file was not created at {METADATA_PATH}")
        sys.exit(1)
    
    metadata_size_mb = METADATA_PATH.stat().st_size / (1024 * 1024)
    print(f"   ✅ Metadata saved successfully ({metadata_size_mb:.2f} MB)")
    print(f"   ✅ File exists: {METADATA_PATH}")
except Exception as e:
    print(f"\n❌ ERROR: Failed to save metadata: {e}")
    sys.exit(1)

# Verify files exist
print("\n🔍 Final verification...")
print(f"   Index file: {INDEX_PATH}")
print(f"   - Exists: {INDEX_PATH.exists()}")
print(f"   - Size: {INDEX_PATH.stat().st_size / (1024 * 1024):.2f} MB")
print(f"   Metadata file: {METADATA_PATH}")
print(f"   - Exists: {METADATA_PATH.exists()}")
print(f"   - Size: {METADATA_PATH.stat().st_size / (1024 * 1024):.2f} MB")

if INDEX_PATH.exists() and METADATA_PATH.exists():
    print("\n" + "=" * 80)
    print("✅ BUILD SUCCESSFUL - Index ready for production")
    print("=" * 80)
    print(f"\n📂 Files created in: {DATA_DIR}")
    print(f"   - index.faiss ({index_size_mb:.2f} MB)")
    print(f"   - metadata.pkl ({metadata_size_mb:.2f} MB)")
    sys.exit(0)
else:
    print("\n❌ ERROR: Files not created properly")
    sys.exit(1)
