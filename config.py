"""
Central configuration for the RAG Conversation Assistant.
Values are loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"

FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", str(DATA_DIR / "index.faiss")))
METADATA_PATH = Path(os.getenv("METADATA_PATH", str(DATA_DIR / "metadata.pkl")))
CONVERSATIONS_PATH = Path(os.getenv("CONVERSATIONS_PATH", str(DATA_DIR / "conversations.jsonl")))
SAMPLE_CONVERSATIONS_PATH = DATA_DIR / "sample_conversations.jsonl"

# ── Embedding model ──────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))

# ── Retrieval ────────────────────────────────────────────────────────────────
TOP_K = int(os.getenv("TOP_K", "5"))

# ── Groq / LLM ─────────────────────────────────────────────────────────────
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# Ensure data directories exist at import time
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
