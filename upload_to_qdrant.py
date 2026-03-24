#!/usr/bin/env python3
"""
upload_to_qdrant.py

Upload conversations.jsonl to Qdrant Cloud cluster.
Run this ONCE to populate your Qdrant collection with the full dataset.

Usage:
    python upload_to_qdrant.py
    
Environment variables required:
    QDRANT_URL - Qdrant cluster URL
    QDRANT_API_KEY - Qdrant API key
"""

import json
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 80)
print("QDRANT UPLOAD SCRIPT - InnerVoice RAG System")
print("=" * 80)

# Import after adding to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from rag.qdrant_vector_store import QdrantVectorStore
from config import DATA_DIR, CONVERSATIONS_PATH, EMBEDDING_MODEL

# Qdrant configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "conversations")

print(f"\n🔧 Configuration:")
print(f"   Qdrant URL: {QDRANT_URL}")
print(f"   Collection: {COLLECTION_NAME}")
print(f"   Embedding Model: {EMBEDDING_MODEL}")
print(f"   Data file: {CONVERSATIONS_PATH}")

# Validate configuration
if not QDRANT_URL:
    print("\n❌ ERROR: QDRANT_URL not set in environment variables")
    print("   Set it in .env file or export QDRANT_URL=<your-url>")
    sys.exit(1)

if not QDRANT_API_KEY:
    print("\n❌ ERROR: QDRANT_API_KEY not set in environment variables")
    print("   Set it in .env file or export QDRANT_API_KEY=<your-key>")
    sys.exit(1)

if not CONVERSATIONS_PATH.exists():
    print(f"\n❌ ERROR: Data file not found: {CONVERSATIONS_PATH}")
    print(f"   Looking in: {DATA_DIR}")
    print(f"   Available files:")
    if DATA_DIR.exists():
        for f in DATA_DIR.iterdir():
            print(f"     - {f.name}")
    sys.exit(1)

print(f"\n📂 Data file found: {CONVERSATIONS_PATH.stat().st_size / (1024*1024):.2f} MB")


async def main():
    """Main upload logic."""
    
    # 1. Load conversations
    print(f"\n📚 Loading conversations from {CONVERSATIONS_PATH.name}...")
    records = []
    line_count = 0
    error_count = 0
    
    with open(CONVERSATIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line_count += 1
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    
                    # Validate required fields
                    if "input" not in record or "response" not in record:
                        error_count += 1
                        print(f"   ⚠️  Line {line_count}: Missing 'input' or 'response' field")
                        continue
                    
                    # Ensure metadata exists
                    if "metadata" not in record:
                        record["metadata"] = {}
                    
                    records.append(record)
                except json.JSONDecodeError as e:
                    error_count += 1
                    print(f"   ⚠️  Line {line_count}: Invalid JSON: {e}")
                    continue
    
    if error_count > 0:
        print(f"   ⚠️  Skipped {error_count} invalid lines")
    
    if not records:
        print("\n❌ ERROR: No valid records found")
        sys.exit(1)
    
    print(f"   ✅ Loaded {len(records):,} conversations")
    
    # Show sample
    if records:
        print(f"\n📋 Sample record:")
        sample = records[0]
        print(f"   Input: {sample['input'][:100]}...")
        print(f"   Response: {sample['response'][:100]}...")
        print(f"   Metadata: {sample.get('metadata', {})}")
    
    # 2. Initialize Qdrant store
    print(f"\n🔌 Connecting to Qdrant Cloud...")
    try:
        store = QdrantVectorStore(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=COLLECTION_NAME,
            embedding_dim=384  # all-MiniLM-L6-v2
        )
        print(f"   ✅ Connected successfully")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect to Qdrant: {e}")
        sys.exit(1)
    
    # 3. Check if collection exists and has data
    try:
        existing_count = store.size
        print(f"\n📊 Collection status:")
        print(f"   Existing points: {existing_count:,}")
        
        if existing_count > 0:
            print(f"\n⚠️  WARNING: Collection already contains {existing_count:,} points")
            response = input("   Do you want to clear and re-upload? (yes/no): ").lower().strip()
            
            if response == "yes":
                print(f"\n🗑️  Clearing collection...")
                await store.clear_collection()
                print(f"   ✅ Collection cleared")
            else:
                print(f"\n✅ Keeping existing data. Upload cancelled.")
                return
    except Exception as e:
        print(f"   Note: {e}")
    
    # 4. Upload to Qdrant
    print(f"\n🚀 Starting upload to Qdrant...")
    print(f"   This will take approximately {len(records) / 100 * 5:.0f}-{len(records) / 100 * 10:.0f} seconds")
    print(f"   (Generating embeddings + uploading {len(records):,} records)")
    
    try:
        await store.add_texts_async(
            records=records,
            model_name=EMBEDDING_MODEL,
            batch_size=100
        )
        
        print(f"\n✅ Upload complete!")
        
        # Verify upload
        final_count = store.size
        print(f"\n📊 Final verification:")
        print(f"   Records uploaded: {len(records):,}")
        print(f"   Points in Qdrant: {final_count:,}")
        
        if final_count == len(records):
            print(f"   ✅ All records verified!")
        else:
            print(f"   ⚠️  Count mismatch - some records may have failed")
        
    except Exception as e:
        print(f"\n❌ ERROR: Upload failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("✅ SUCCESS - Qdrant upload complete!")
    print("=" * 80)
    print(f"\n📝 Next steps:")
    print(f"   1. Update .env with Qdrant credentials")
    print(f"   2. Set USE_QDRANT=true in .env")
    print(f"   3. Deploy to Render")
    print(f"   4. Your RAG system will now use Qdrant Cloud!")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Upload cancelled by user")
        sys.exit(1)
