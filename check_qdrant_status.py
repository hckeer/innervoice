#!/usr/bin/env python3
"""
Quick script to check Qdrant collection status.
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "conversations")

print("=" * 60)
print("Qdrant Status Check")
print("=" * 60)

try:
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=10
    )
    
    print(f"\n✅ Connected to: {QDRANT_URL}")
    
    # Get collection info
    collection_info = client.get_collection(COLLECTION_NAME)
    
    print(f"\n📊 Collection: {COLLECTION_NAME}")
    print(f"   Points count: {collection_info.points_count:,}")
    print(f"   Vector size: {collection_info.config.params.vectors.size}")
    print(f"   Status: {collection_info.status}")
    
    if collection_info.points_count == 0:
        print("\n⚠️  Collection is empty. You need to upload data.")
        print("   Run: python upload_to_qdrant.py")
    else:
        print("\n✅ Collection has data!")
        
        # Test a simple search
        print("\n🔍 Testing search...")
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=[0.1] * 384,  # dummy vector
            limit=3
        )
        print(f"   Search returned {len(results)} results")
        
        if results:
            print(f"\n   Sample result:")
            print(f"   - Score: {results[0].score:.4f}")
            print(f"   - Text: {results[0].payload.get('input', 'N/A')[:80]}...")
    
    print("\n" + "=" * 60)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check QDRANT_URL in .env")
    print("2. Check QDRANT_API_KEY in .env")
    print("3. Verify network connectivity")
