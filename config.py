"""
Central configuration for the RAG Conversation Assistant.
Values are loaded from environment variables with sensible defaults.

PRODUCTION NOTES:
- Paths are relative to BASE_DIR for portability
- FAISS index should be built during deployment (build phase)
- All required files live in /opt/render/project/src/data on Render
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present (not used in production, only local dev)
load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"

# FAISS index and metadata paths (created during build phase)
FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", str(DATA_DIR / "index.faiss")))
METADATA_PATH = Path(os.getenv("METADATA_PATH", str(DATA_DIR / "metadata.pkl")))
CONVERSATIONS_PATH = Path(os.getenv("CONVERSATIONS_PATH", str(DATA_DIR / "conversations.jsonl")))
SAMPLE_CONVERSATIONS_PATH = DATA_DIR / "sample_conversations.jsonl"

# ── Embedding model ──────────────────────────────────────────────────────────
# Using smaller model for 512MB RAM constraint
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))  # Reduced for limited memory

# ── Retrieval ────────────────────────────────────────────────────────────────
TOP_K = int(os.getenv("TOP_K", "5"))

# ── Groq / LLM ─────────────────────────────────────────────────────────────
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# ── Qdrant Cloud Configuration ───────────────────────────────────────────────
USE_QDRANT = os.getenv("USE_QDRANT", "false").lower() == "true"
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "conversations")

# Ensure data directories exist at import time
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Production readiness check
def check_production_ready() -> bool:
    """Check if required files exist for production deployment."""
    if USE_QDRANT:
        # For Qdrant mode, only need credentials
        return bool(QDRANT_URL and QDRANT_API_KEY)
    else:
        # For FAISS mode, need local index files
        return (
            FAISS_INDEX_PATH.exists() and 
            METADATA_PATH.exists() and 
            SAMPLE_CONVERSATIONS_PATH.exists()
        )
