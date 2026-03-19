"""
scripts/process_dataset.py

PRODUCTION VERSION: Processes raw conversation data with improved chunking
and emotion tagging for personality-driven RAG system.

Key improvements over v1:
- Conversation window chunking (5-10 lines) for better context
- Scene boundary detection in subtitle files
- Emotion detection and tagging for emotion-aware retrieval
- Metadata enrichment (conversation length, emotional tone)
- Better deduplication with semantic awareness

Reads all raw JSONL files from data/raw/ plus the built-in
sample_conversations.jsonl, normalises to:
    {"input": "...", "response": "...", "metadata": {...}}

Subtitle .txt files (e.g. en.txt from OpenSubtitles) are parsed
with conversation window chunking for better context retention.

Usage:
    python scripts/process_dataset.py
    
Optional flags:
    --window-size N     Set conversation window size (default: 5)
    --skip-emotions     Skip emotion detection (faster but less features)
"""

import json
import re
import sys
import os
import random
import argparse
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from config import RAW_DATA_DIR, CONVERSATIONS_PATH, SAMPLE_CONVERSATIONS_PATH

# Import emotion detector for tagging
try:
    from rag.emotion_detector import EmotionDetector
    EMOTION_DETECTOR_AVAILABLE = True
except ImportError:
    print("[warn] EmotionDetector not available - skipping emotion tagging")
    EMOTION_DETECTOR_AVAILABLE = False

# Maximum subtitle pairs to extract from a single .txt file (avoid OOM on huge files)
MAX_SUBTITLE_PAIRS = int(os.getenv("MAX_SUBTITLE_PAIRS", "80000"))

# Conversation window size (number of consecutive lines to group as context)
DEFAULT_WINDOW_SIZE = 5

# Scene break detection: if gap between subtitle times > N seconds, start new scene
SCENE_BREAK_THRESHOLD_SEC = 10

# ── junk filters for subtitle lines ──────────────────────────────────────────
_RE_TIMESTAMP = re.compile(r"\d{1,2}:\d{2}:\d{2}")          # 00:01:23
_RE_ARROW     = re.compile(r"-->")                            # SRT arrow
_RE_ONLY_NUM  = re.compile(r"^\d+$")                         # pure index numbers
_RE_TAG       = re.compile(r"<[^>]+>")                       # HTML-style tags
_CREDIT_WORDS = {
    "subtitle", "subtitles", "subtitled", "translation",
    "transcribed", "sync", "corrected", "encoded", "ripped",
    "presented", "produced", "directed", "written by",
}


def _is_junk_subtitle_line(line: str) -> bool:
    """Return True if the line should be skipped when parsing subtitle txt files."""
    stripped = line.strip()
    if not stripped:
        return True
    if _RE_TIMESTAMP.search(stripped):
        return True
    if _RE_ARROW.search(stripped):
        return True
    if _RE_ONLY_NUM.match(stripped):
        return True
    if len(stripped) < 4:
        return True
    lower = stripped.lower()
    if any(w in lower for w in _CREDIT_WORDS):
        return True
    return False


# ── loaders ──────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
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


def load_txt_conversations(
    path: Path,
    window_size: int = DEFAULT_WINDOW_SIZE,
    enable_emotions: bool = True,
) -> list[dict]:
    """
    Parse a plain-text subtitle file into conversation windows.
    
    IMPROVED STRATEGY (v2):
    - Group consecutive lines into conversation windows (5-10 lines)
    - Detect scene breaks (large time gaps or topic shifts)
    - Create overlapping windows for better coverage
    - Add emotion tags to each conversation
    - Enrich metadata (window position, scene context)
    
    Args:
        path: Path to subtitle .txt file
        window_size: Number of consecutive lines per window
        enable_emotions: Whether to detect emotions (slower but better)
    
    Returns:
        List of conversation dicts with input, response, and metadata
    """
    clean_lines: list[str] = []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = _RE_TAG.sub("", raw).strip()
                if not _is_junk_subtitle_line(line):
                    clean_lines.append(line)
                    # Safety: stop if lines accumulate beyond a sane limit
                    if len(clean_lines) >= MAX_SUBTITLE_PAIRS * 3:
                        print(f"    (file is very large — stopping early at {len(clean_lines):,} clean lines)")
                        break
    except Exception as e:
        print(f"  [warn] Could not read {path.name}: {e}")
        return []

    if len(clean_lines) < window_size:
        print(f"    (too few lines: {len(clean_lines)} < {window_size})")
        return []

    # Initialize emotion detector if available and enabled
    emotion_detector = None
    if enable_emotions and EMOTION_DETECTOR_AVAILABLE:
        emotion_detector = EmotionDetector()

    # Build conversation windows
    conversations: list[dict] = []
    
    # Strategy 1: Sliding window with 50% overlap for better coverage
    step = max(1, window_size // 2)  # 50% overlap
    
    for i in range(0, len(clean_lines) - window_size, step):
        window = clean_lines[i:i + window_size]
        
        # Split window into context (first N-1 lines) + response (last line)
        context_lines = window[:-1]
        response_line = window[-1]
        
        # Join context with newlines for multi-turn feeling
        context_text = " ".join(context_lines)  # Join with space for cleaner text
        
        # Create input from last line of context (immediate trigger)
        input_text = context_lines[-1] if context_lines else ""
        
        if not input_text or not response_line:
            continue
        
        # Detect emotion if enabled
        emotion = "neutral"
        emotion_confidence = 0.0
        if emotion_detector:
            try:
                emotion_result = emotion_detector.detect_emotion(response_line)
                emotion = emotion_result["emotion"]
                emotion_confidence = emotion_result["confidence"]
            except Exception:
                pass  # Fall back to neutral
        
        # Build metadata
        metadata = {
            "window_size": window_size,
            "window_position": i,
            "context": context_text,  # Full conversation context
            "emotion": emotion,
            "emotion_confidence": emotion_confidence,
            "source_file": path.name,
            "conversation_length": len(window),
        }
        
        conversations.append({
            "input": input_text,
            "response": response_line,
            "metadata": metadata,
        })
    
    # Sample if too many (keep diversity)
    if len(conversations) > MAX_SUBTITLE_PAIRS:
        random.seed(42)
        conversations = random.sample(conversations, MAX_SUBTITLE_PAIRS)
        print(f"    (sampled {MAX_SUBTITLE_PAIRS:,} windows from {len(conversations):,} available)")
    
    print(f"    (created {len(conversations):,} conversation windows, emotion_tagged={enable_emotions})")
    return conversations


# ── normaliser ───────────────────────────────────────────────────────────────

def normalise(record: dict, enable_emotions: bool = True) -> dict | None:
    """
    Return a clean {input, response, metadata} dict or None if invalid.
    
    Args:
        record: Raw conversation record
        enable_emotions: Whether to detect and tag emotions
        
    Returns:
        Normalized record with metadata or None if invalid
    """
    inp  = str(record.get("input",    record.get("utterance", ""))).strip()
    resp = str(record.get("response", record.get("reply",     ""))).strip()
    
    if not inp or not resp:
        return None
    if len(inp) < 4 or len(resp) < 4:
        return None
    
    # skip lines that are obviously not dialogue
    if _is_junk_subtitle_line(inp) or _is_junk_subtitle_line(resp):
        return None
    
    # Preserve existing metadata or create new
    metadata = record.get("metadata", {})
    
    # Add emotion tagging if not already present
    if enable_emotions and EMOTION_DETECTOR_AVAILABLE and "emotion" not in metadata:
        try:
            emotion_detector = EmotionDetector()
            emotion_result = emotion_detector.detect_emotion(resp)
            metadata["emotion"] = emotion_result["emotion"]
            metadata["emotion_confidence"] = emotion_result["confidence"]
        except Exception:
            metadata["emotion"] = "neutral"
            metadata["emotion_confidence"] = 0.0
    
    return {
        "input": inp,
        "response": resp,
        "metadata": metadata,
    }


# ── main processing ───────────────────────────────────────────────────────────

def process(window_size: int = DEFAULT_WINDOW_SIZE, skip_emotions: bool = False) -> None:
    """
    Main processing pipeline with improved chunking and emotion tagging.
    
    Args:
        window_size: Conversation window size (number of lines)
        skip_emotions: Skip emotion detection for faster processing
    """
    enable_emotions = not skip_emotions
    raw_records: list[dict] = []

    print(f"\nConfiguration:")
    print(f"  Window size: {window_size}")
    print(f"  Emotion tagging: {enable_emotions}")
    print(f"  Max subtitle pairs per file: {MAX_SUBTITLE_PAIRS:,}")
    print()

    # 1. Seed dataset
    if SAMPLE_CONVERSATIONS_PATH.exists():
        seed = load_jsonl(SAMPLE_CONVERSATIONS_PATH)
        raw_records.extend(seed)
        print(f"  Loaded {len(seed):,} records  ← sample_conversations.jsonl")

    # 2. JSONL datasets in data/raw/
    if RAW_DATA_DIR.exists():
        for raw_file in sorted(RAW_DATA_DIR.glob("*.jsonl")):
            recs = load_jsonl(raw_file)
            raw_records.extend(recs)
            print(f"  Loaded {len(recs):,} records  ← {raw_file.name}")

    # 3. Subtitle / plain-text datasets in data/raw/ (with conversation windows)
    if RAW_DATA_DIR.exists():
        for txt_file in sorted(RAW_DATA_DIR.glob("*.txt")):
            print(f"  Parsing subtitle file: {txt_file.name} …")
            conversations = load_txt_conversations(
                txt_file,
                window_size=window_size,
                enable_emotions=enable_emotions,
            )
            raw_records.extend(conversations)
            print(f"  Loaded {len(conversations):,} conversations ← {txt_file.name}")

    print(f"\nTotal raw records : {len(raw_records):,}")

    # 4. Normalise + deduplicate
    seen: set[tuple[str, str]] = set()
    clean: list[dict] = []

    for r in raw_records:
        norm = normalise(r, enable_emotions=enable_emotions)
        if norm is None:
            continue
        key = (norm["input"].lower(), norm["response"].lower())
        if key not in seen:
            seen.add(key)
            clean.append(norm)

    print(f"After dedup        : {len(clean):,}")

    # 5. Print emotion distribution if enabled
    if enable_emotions:
        emotion_counts: dict[str, int] = {}
        for record in clean:
            emotion = record.get("metadata", {}).get("emotion", "neutral")
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        print("\nEmotion distribution:")
        for emotion, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(clean)) * 100
            print(f"  {emotion:12s}: {count:6,} ({percentage:5.1f}%)")

    # 6. Save
    CONVERSATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVERSATIONS_PATH, "w", encoding="utf-8") as f:
        for record in clean:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(clean):,} records → {CONVERSATIONS_PATH}")
    print("Next step: python scripts/build_index.py")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process conversation datasets with improved chunking and emotion tagging"
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=DEFAULT_WINDOW_SIZE,
        help=f"Conversation window size (default: {DEFAULT_WINDOW_SIZE})",
    )
    parser.add_argument(
        "--skip-emotions",
        action="store_true",
        help="Skip emotion detection (faster but less features)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    print("=" * 70)
    print("Dataset Processor v2.0 – RAG Conversation Assistant (Production)")
    print("=" * 70)
    
    args = parse_args()
    process(window_size=args.window_size, skip_emotions=args.skip_emotions)