"""
app.py – Streamlit UI for the RAG Conversation Assistant (Production v2.0)

PRODUCTION ENHANCEMENTS:
- Async pipeline integration with emotion-aware retrieval
- Hybrid search (vector + BM25 + reranking)
- Personality-driven romantic responses
- Real-time emotion detection display
- Enhanced retrieval scoring and context display
- Conversation memory management
- Performance metrics display

Tabs:
  1. 💬 Chat Assistant  – personality-driven romantic replies with emotion awareness
  2. 📸 OCR Input       – upload a screenshot, extract & feed to pipeline
  3. ⚙️ Settings        – model, top-k, temperature, advanced options
  4. 📊 Index Info      – corpus stats, emotion distribution, and re-index

Run:
    streamlit run app.py
"""

import sys
import os
import asyncio
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InnerVoice",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS - Claude Dark Mode Style ──────────────────────────────────────
st.markdown("""
<style>
  /* Import Fonts - Playfair Display (serif) + Inter (sans-serif) */
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

  * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }

  /* Claude Dark Mode Background */
  .stApp {
    background: #1E1E1E !important;
    color: #E5E5E5 !important;
  }

  /* Hide Streamlit elements */
  section[data-testid="stSidebar"] { display: none !important; }
  [data-testid="collapsedControl"] { display: none !important; }
  [data-testid="stSidebarCollapsedControl"] { display: none !important; }
  [data-testid="stDeployButton"] { display: none !important; }
  [data-testid="stToolbar"] { display: none !important; }
  #MainMenu { display: none !important; }
  header[data-testid="stHeader"] { display: none !important; }
  footer { display: none !important; }

  /* Main content - centered, elegant spacing */
  .block-container {
    padding-top: 1rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
  }

  /* Top Badge */
  .top-badge {
    text-align: center;
    padding: 1rem 0 0.5rem;
  }
  .badge-pill {
    display: inline-block;
    background: #2A2A2A;
    border: 1px solid #333333;
    border-radius: 20px;
    padding: 0.4rem 1rem;
    font-size: 0.85rem;
    color: #999999;
    font-weight: 400;
  }
  .badge-pill a {
    color: #E8A87C;
    text-decoration: none;
    font-weight: 500;
  }
  .badge-pill a:hover {
    color: #F4B991;
  }

  /* Hero Section - Centered */
  .hero-section {
    text-align: center;
    padding: 3rem 0 2rem;
    max-width: 900px;
    margin: 0 auto;
  }
  
  /* Logo with Heart Icon */
  .logo-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }
  .heart-icon {
    font-size: 2.5rem;
    color: #E8A87C;
  }
  .brand-name {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 3rem;
    font-weight: 600;
    color: #F5F5F5;
    letter-spacing: -0.5px;
  }
  
  /* Main Heading */
  .main-heading {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 2rem;
    font-weight: 500;
    color: #E5E5E5;
    margin: 0.5rem 0 0.75rem;
  }
  
  /* Subtitle */
  .subtitle-text {
    font-size: 0.9rem;
    color: #888888;
    font-weight: 400;
    margin-bottom: 2.5rem;
  }

  /* Central Input Bar - Claude Style */
  .central-input {
    background: #2A2A2A;
    border: 1px solid #333333;
    border-radius: 12px;
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    transition: border-color 0.2s;
  }
  .central-input:hover {
    border-color: #444444;
  }
  .input-icon {
    color: #666666;
    font-size: 1.1rem;
  }

  /* Header styling */
  .main-header {
    text-align: center;
    padding: 2rem 0 1.5rem;
  }
  .main-title {
    font-size: 2.5rem;
    font-weight: 600;
    color: #E5E5E5 !important;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    font-family: 'Playfair Display', serif;
  }
  .title-icon {
    font-size: 2rem;
    color: #E8A87C;
  }
  .subtitle {
    font-size: 0.9rem;
    color: #888888;
    margin-top: 0.5rem;
    font-weight: 400;
  }

  /* Search bar container */
  .search-container {
    max-width: 900px;
    margin: 2rem auto;
    background: #2A2A2A;
    border: 1px solid #333333;
    border-radius: 12px;
    display: flex;
    align-items: center;
    padding: 0;
    transition: border-color 0.2s;
  }
  .search-container:hover {
    border-color: #444444;
  }
  
  /* Discovery tags - Claude style pills */
  .discover-section {
    text-align: center;
    margin: 1.5rem 0 3rem;
  }
  .discover-tags {
    display: flex;
    justify-content: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-top: 0.75rem;
  }
  .discover-label {
    color: #888888;
    font-weight: 500;
    margin-right: 0.5rem;
  }
  .tag {
    background: #2A2A2A;
    border: 1px solid #333333;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.85rem;
    color: #CCCCCC;
    font-weight: 400;
    cursor: pointer;
    transition: all 0.2s;
  }
  .tag:hover {
    background: #333333;
    border-color: #444444;
    color: #E5E5E5;
  }

  /* Tab styling - Dark mode */
  .stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #333333 !important;
    gap: 2rem !important;
    padding: 0 !important;
    margin-bottom: 2rem !important;
  }
  .stTabs [data-baseweb="tab"] {
    color: #888888 !important;
    font-weight: 500 !important;
    border: none !important;
    padding: 0.75rem 0 !important;
    background: transparent !important;
    font-size: 1rem !important;
  }
  .stTabs [data-baseweb="tab"] svg {
    margin-right: 0.5rem;
  }
  .stTabs [aria-selected="true"] {
    color: #E5E5E5 !important;
    border-bottom: 2px solid #E8A87C !important;
    font-weight: 600 !important;
  }
  .stTabs [data-baseweb="tab-panel"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
  }

  /* Two-panel layout - Dark cards */
  .two-panel {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
    margin-top: 2rem;
  }
  .panel {
    background: #2A2A2A;
    border: 1px solid #333333;
    border-radius: 12px;
    padding: 1.5rem;
    min-height: 500px;
  }
  .panel-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: #E5E5E5;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #333333;
  }
  .panel-icon {
    font-size: 1.2rem;
    color: #E8A87C;
  }

  /* Message input */
  .message-input-container {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: auto;
    padding-top: 1rem;
    border-top: 1px solid #333333;
  }
  
  /* Streamlit input overrides - Dark mode */
  .stTextInput input, .stTextArea textarea {
    background: #2A2A2A !important;
    border: 1px solid #333333 !important;
    border-radius: 8px !important;
    color: #E5E5E5 !important;
    font-size: 0.95rem !important;
  }
  .stTextInput input::placeholder, .stTextArea textarea::placeholder {
    color: #666666 !important;
  }
  .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #444444 !important;
    box-shadow: none !important;
  }

  /* Button styling - Dark mode */
  .stButton > button {
    background: #E8A87C !important;
    color: #1E1E1E !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    transition: all 0.2s !important;
  }
  .stButton > button:hover {
    background: #F4B991 !important;
  }

  /* Context panel empty state */
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #666666;
    font-size: 0.95rem;
    text-align: center;
    padding: 3rem 2rem;
  }

  /* Chat messages - Dark mode */
  [data-testid="stChatMessage"] {
    background: #2A2A2A !important;
    border: 1px solid #333333 !important;
    border-radius: 12px !important;
    color: #E5E5E5 !important;
  }
  [data-testid="stChatMessage"] p {
    color: #E5E5E5 !important;
  }

  /* Expander - Dark mode */
  .streamlit-expanderHeader {
    background: #2A2A2A !important;
    border: 1px solid #333333 !important;
    border-radius: 8px !important;
    color: #E5E5E5 !important;
  }
  
  /* Info boxes - Dark mode */
  .stAlert {
    background: #2A2A2A !important;
    border: 1px solid #333333 !important;
    color: #E5E5E5 !important;
  }

  /* Remove extra spacing */
  .stMarkdown { margin: 0 !important; }
  .stMarkdown p, .stMarkdown li {
    color: #CCCCCC !important;
  }
  
  /* Selectbox styling - Dark mode */
  .stSelectbox {
    background: #2A2A2A;
  }
  .stSelectbox > div > div {
    background: #2A2A2A !important;
    border: 1px solid #333333 !important;
    border-radius: 8px !important;
    color: #E5E5E5 !important;
  }
  .stSelectbox [data-baseweb="select"] {
    color: #E5E5E5 !important;
  }
  .stSelectbox [data-baseweb="select"] > div {
    color: #E5E5E5 !important;
  }

  /* Captions - muted text */
  .stCaption {
    color: #888888 !important;
  }

  /* Hide Streamlit badges */
  .viewerBadge_container__1QSob {
    display: none !important;
  }
  
  /* Headings - Dark mode */
  h1, h2, h3, h4, h5, h6 {
    color: #E5E5E5 !important;
  }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults ────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "pipeline": None,
        "session_id": "default",  # For conversation memory
        "history": [],        # list of {"role": "user"|"assistant", "content": str}
        "settings": {
            "model": "openai/gpt-oss-120b",
            "top_k": 5,
            "temperature": 0.7,
            "max_tokens": 512,
            "tone": "romantic",  # Default personality mode
            "stream": False,  # Disable streaming for now (needs Groq streaming API)
            "enable_cache": True,
            "enable_emotions": True,
        },
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    # Migration: Update deprecated model to new default
    if "settings" in st.session_state and st.session_state.settings.get("model") == "llama3-8b-8192":
        st.session_state.settings["model"] = "openai/gpt-oss-120b"

_init_state()


# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading production RAG pipeline …")
def get_async_pipeline(model, top_k, temperature, max_tokens, enable_cache):
    """Initialize the async pipeline (cached for reuse)."""
    from rag.pipeline_async import AsyncRAGPipeline
    return AsyncRAGPipeline(
        model=model,
        top_k=top_k,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_cache=enable_cache,
    )


def get_or_create_async_pipeline():
    """Get or create the async pipeline based on current settings."""
    s = st.session_state.settings
    return get_async_pipeline(
        s["model"],
        s["top_k"],
        s["temperature"],
        s["max_tokens"],
        s["enable_cache"],
    )


async def async_suggest_reply(pipeline, user_message, session_id, k):
    """Wrapper for async suggest_reply."""
    return await pipeline.suggest_reply(
        user_message=user_message,
        session_id=session_id,
        k=k,
    )


def sync_suggest_reply(pipeline, user_message, session_id, k):
    """Synchronous wrapper for async pipeline (for Streamlit compatibility)."""
    import concurrent.futures
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"sync_suggest_reply called with message: {user_message[:50]}")
    
    def run_async():
        logger.info("Running async function in thread")
        result = asyncio.run(async_suggest_reply(pipeline, user_message, session_id, k))
        logger.info("Async function completed")
        return result
    
    # Run in a thread pool to avoid event loop conflicts
    logger.info("Starting ThreadPoolExecutor")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_async)
        result = future.result(timeout=30)  # 30 second timeout
        logger.info("Got result from future")
        return result


def llm_status():
    # Placeholder for Groq API status
    return True, ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]


def index_exists() -> bool:
    from config import FAISS_INDEX_PATH
    return FAISS_INDEX_PATH.exists()


def show_index_missing_error():
    """Show helpful error when index is missing (should never happen in production)."""
    from config import FAISS_INDEX_PATH, METADATA_PATH, SAMPLE_CONVERSATIONS_PATH, DATA_DIR, BASE_DIR
    
    st.error("🚨 **FAISS Index Not Found**")
    
    # Show diagnostic information
    with st.expander("🔍 Click here for diagnostic information"):
        st.markdown("### File System Diagnostic")
        st.write(f"**BASE_DIR:** `{BASE_DIR}`")
        st.write(f"**DATA_DIR:** `{DATA_DIR}`")
        st.write(f"**Expected index path:** `{FAISS_INDEX_PATH}`")
        st.write(f"**Expected metadata path:** `{METADATA_PATH}`")
        st.write(f"**Sample data path:** `{SAMPLE_CONVERSATIONS_PATH}`")
        
        st.markdown("### File Existence Check")
        st.write(f"- Index exists: **{FAISS_INDEX_PATH.exists()}**")
        st.write(f"- Metadata exists: **{METADATA_PATH.exists()}**")
        st.write(f"- Sample data exists: **{SAMPLE_CONVERSATIONS_PATH.exists()}**")
        st.write(f"- Data directory exists: **{DATA_DIR.exists()}**")
        
        if DATA_DIR.exists():
            st.markdown("### Contents of data/ directory:")
            try:
                items = list(DATA_DIR.iterdir())
                if items:
                    for item in items:
                        size = item.stat().st_size / (1024 * 1024) if item.is_file() else 0
                        st.write(f"- `{item.name}` {f'({size:.2f} MB)' if item.is_file() else '(dir)'}")
                else:
                    st.write("*(Directory is empty)*")
            except Exception as e:
                st.write(f"Error reading directory: {e}")
        
        st.markdown("### Current Working Directory")
        st.write(f"`{Path.cwd()}`")
        
        try:
            st.markdown("### Contents of current directory:")
            for item in sorted(Path.cwd().iterdir())[:20]:  # Show first 20 items
                st.write(f"- `{item.name}`")
        except:
            pass
    
    st.markdown("""
    ---
    ### What This Means
    
    The search index is missing. This usually means the deployment failed.
    
    **For Production (Render):**
    - The index should be built automatically during deployment
    - Check build logs for errors in `build_index_production.py`
    - Look for "BUILD SUCCESSFUL" message in logs
    
    **For Local Development:**
    ```bash
    python build_index_production.py
    ```
    
    **Contact Support:** If this error persists in production, please report it with the diagnostic info above.
    """)
    st.stop()


def history_to_text(history: list[dict]) -> str:
    lines = []
    for h in history[-6:]:  # last 3 turns
        label = "User" if h["role"] == "user" else "Assistant"
        lines.append(f"{label}: {h['content']}")
    return "\n".join(lines)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:0.6rem;padding:0.5rem 0 1rem;">
      <span style="font-size:2rem;">🧠</span>
      <div>
        <div style="font-size:1rem;font-weight:800;color:#0f172a;letter-spacing:0.5px;text-transform:uppercase;">InnerVoice</div>
        <div style="font-size:0.65rem;font-weight:600;color:#0BA37F;letter-spacing:2px;text-transform:uppercase;">AI TOOL</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # LLM status
    llm_ok, models = llm_status()
    status_chip = (
        '<span class="chip-green">● Groq API Online</span>'
        if llm_ok
        else '<span class="chip-red">✕ Groq API Offline</span>'
    )
    st.markdown(status_chip, unsafe_allow_html=True)

    # Index status
    idx_ok = index_exists()
    idx_chip = (
        '<span class="chip-green">● Index Ready</span>'
        if idx_ok
        else '<span class="chip-yellow">⚠ No Index – build it first</span>'
    )
    st.markdown(idx_chip, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Quick Setup")
    st.code("""\
# 1. Install
pip install -r requirements.txt

# 2. Build index
python scripts/build_index.py

# 3. Add GROQ_API_KEY to .env

# 4. Run app
streamlit run app.py""", language="bash")


# ── Claude-Inspired Dark Mode Header ──────────────────────────────────────────
# Top badge
st.markdown("""
<div class="top-badge">
  <span class="badge-pill">Free plan · <a href="#">Upgrade</a></span>
</div>
""", unsafe_allow_html=True)

# Hero Section with Heart Icon
st.markdown("""
<div class="hero-section">
  <div class="logo-container">
    <span class="heart-icon">♥</span>
    <h1 class="brand-name">InnerVoice</h1>
  </div>
  <p class="main-heading">Find Your Perfect AI Reply</p>
  <p class="subtitle-text">Local AI · sentence-transformers · FAISS · Groq LLaMA3</p>
</div>
""", unsafe_allow_html=True)

# ── Central Input Bar (Claude Style) ──────────────────────────────────────────
col_search, col_model, col_btn = st.columns([5, 2, 1])
with col_search:
    search_query = st.text_input("Search", placeholder="Search by topic, keyword, or context...", label_visibility="collapsed")
with col_model:
    current_model = st.session_state.settings.get("model", "openai/gpt-oss-120b")
    model_display_name = f"Model: {current_model.split('/')[-1]} · Groq"
    model_display = st.selectbox("Model", [model_display_name], label_visibility="collapsed")
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    search_btn = st.button("Search", use_container_width=True)

# ── Suggestion Chips ──────────────────────────────────────────────────────────
st.markdown("""
<div class="discover-section">
  <div class="discover-tags">
    <span class="discover-label">Discover:</span>
    <span class="tag">💬 Chat Replies</span>
    <span class="tag">🎨 Tone Adjustment</span>
    <span class="tag">📸 OCR Extraction</span>
    <span class="tag">🔍 Context Retrieval</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_ocr, tab_settings, tab_index = st.tabs(
    ["💬 Chat Assistant", "📸 OCR Input", "⚙️ Settings", "📊 Index Info dev"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: Chat Assistant
# ═══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    # Two-panel layout matching the design
    col_chat, col_ctx = st.columns([1, 1], gap="medium")

    with col_chat:
        st.markdown("""
        <div class="panel-header">
            <span class="panel-icon">💬</span>
            <span>Conversation</span>
        </div>
        """, unsafe_allow_html=True)

        # Render history
        for msg in st.session_state.history:
            with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                st.write(msg["content"])

        # Chat input at the bottom (properly triggers on Enter)
        user_input = st.chat_input("Type your message here...", key="chat_input")

        # Process input when user submits
        if user_input:
            st.write(f"DEBUG: Processing input: {user_input[:50]}")  # Debug log
            if not index_exists():
                show_index_missing_error()
            else:
                try:
                    # Add user message to history
                    st.session_state.history.append({"role": "user", "content": user_input})

                    st.write("DEBUG: Getting pipeline...")  # Debug log
                    pipeline = get_or_create_async_pipeline()
                    session_id = st.session_state.get("session_id", "default")

                    # Generate assistant response
                    s = st.session_state.settings
                    
                    # Use async pipeline
                    st.write("DEBUG: Calling sync_suggest_reply...")  # Debug log
                    start_time = time.time()
                    with st.spinner("Generating personality-driven reply …"):
                        result = sync_suggest_reply(
                            pipeline=pipeline,
                            user_message=user_input,
                            session_id=session_id,
                            k=s["top_k"],
                        )
                    
                    st.write("DEBUG: Got result")  # Debug log
                    latency_ms = (time.time() - start_time) * 1000
                    
                    reply = result["reply"]
                    emotion = result.get("emotion", "neutral")
                    confidence = result.get("confidence", 0.0)
                    sources = result["sources"]
                    cached = result.get("cached", False)

                    # Add assistant response to history
                    st.session_state.history.append({"role": "assistant", "content": reply})

                    # Store for context panel
                    st.session_state["_last_context"] = result.get("context", "")
                    st.session_state["_last_sources"] = sources
                    st.session_state["_last_emotion"] = emotion
                    st.session_state["_last_confidence"] = confidence
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {type(e).__name__}: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

        # Clear history button
        if st.session_state.history:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Clear Chat", key="clear_chat"):
                st.session_state.history = []
                st.session_state.pop("_last_context", None)
                st.session_state.pop("_last_sources", None)
                st.rerun()

    with col_ctx:
        st.markdown("""
        <div class="panel-header">
            <span class="panel-icon">🔍</span>
            <span>Retrieved Context</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Show content or empty state
        if "_last_sources" in st.session_state and st.session_state["_last_sources"]:
            # Show emotion if available
            if "_last_emotion" in st.session_state:
                emotion = st.session_state["_last_emotion"]
                confidence = st.session_state.get("_last_confidence", 0.0)
                
                emotion_emoji = {
                    "romantic": "💕",
                    "flirty": "😘",
                    "playful": "😄",
                    "sad": "😢",
                    "serious": "🧐",
                    "curious": "🤔",
                    "supportive": "🤗",
                    "neutral": "😐",
                }.get(emotion, "💬")
                
                st.info(f"{emotion_emoji} **Detected Emotion:** {emotion.title()} ({confidence:.0%} confidence)")
            
            # Show retrieved sources
            for i, src in enumerate(st.session_state["_last_sources"], 1):
                score = src.get("score", 0.0)
                emotion_tag = src.get("metadata", {}).get("emotion", "neutral")
                
                with st.expander(f"Example {i} · {score*100:.1f}% match · {emotion_tag}"):
                    st.markdown(f"**💬 Similar message:**")
                    st.info(src["input"])
                    st.markdown(f"**🤖 Original response:**")
                    st.success(src["response"])
                    
                    # Show metadata if available
                    metadata = src.get("metadata", {})
                    if metadata:
                        st.caption(f"🏷️ Emotion: {metadata.get('emotion', 'N/A')} | "
                                 f"Confidence: {metadata.get('emotion_confidence', 0):.2f}")
        else:
            st.markdown("""
            <div class="empty-state">
                Send a message to see retrieved context here.
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: OCR Input
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ocr:
    st.markdown("### 📸 Chat Screenshot → AI Reply")
    st.markdown("Upload a screenshot of a chat conversation. OCR will extract the text and feed it to the assistant.")

    from ocr.screenshot_reader import ScreenshotReader
    ocr_available = ScreenshotReader.is_available()

    if not ocr_available:
        st.warning(
            "**Tesseract OCR is not installed.**\n\n"
            "Install it with:\n```bash\nsudo apt install tesseract-ocr\n```\n\n"
            "You can still paste text manually below."
        )

    col_up, col_paste = st.columns(2)

    extracted_text = ""
    parsed_turns = []

    with col_up:
        st.markdown("#### 📁 Upload Screenshot")
        uploaded = st.file_uploader(
            "Upload image (PNG, JPG, JPEG)",
            type=["png", "jpg", "jpeg"],
            disabled=not ocr_available,
        )
        if uploaded and ocr_available:
            from PIL import Image
            img = Image.open(uploaded)
            st.image(img, caption="Uploaded Screenshot", use_column_width=True)
            reader = ScreenshotReader()
            with st.spinner("Running OCR …"):
                try:
                    extracted_text = reader.read_image(img)
                    parsed_turns = reader.parse_chat_lines(extracted_text)
                    st.success(f"✅ Extracted {len(parsed_turns)} conversation turns")
                except Exception as e:
                    st.error(f"OCR failed: {e}")

    with col_paste:
        st.markdown("#### ✏️ Or Paste Text Manually")
        manual_text = st.text_area(
            "Paste chat text here",
            placeholder="Alice: Hey, how are you?\nBob: I'm good! You?",
            height=200,
        )
        if manual_text.strip():
            reader = ScreenshotReader()
            parsed_turns = reader.parse_chat_lines(manual_text)
            extracted_text = manual_text

    if parsed_turns:
        st.markdown("---")
        st.markdown("#### 🗣️ Parsed Conversation")
        for turn in parsed_turns:
            role_icon = "🧑" if turn["speaker"].lower() not in ["bot", "ai", "assistant"] else "🤖"
            st.markdown(f"**{role_icon} {turn['speaker']}:** {turn['message']}")

        st.markdown("---")
        latest_msg = parsed_turns[-1]["message"] if parsed_turns else ""
        st.text_input("Latest message to reply to:", value=latest_msg, key="ocr_query")

        if st.button("🤖 Suggest Reply for this Conversation"):
            if not index_exists():
                st.error("⚠️ Build the FAISS index first: `python scripts/build_index.py`")
            else:
                query = st.session_state.get("ocr_query", latest_msg)
                pipeline = get_or_create_async_pipeline()
                session_id = st.session_state.get("session_id", "default")
                
                with st.spinner("Retrieving context and generating reply …"):
                    result = sync_suggest_reply(
                        pipeline=pipeline,
                        user_message=query,
                        session_id=session_id,
                        k=st.session_state.settings["top_k"],
                    )
                
                st.markdown("#### 💡 Suggested Reply")
                st.markdown(f'<div class="reply-box">{result["reply"]}</div>', unsafe_allow_html=True)
                
                # Show emotion
                emotion = result.get("emotion", "neutral")
                confidence = result.get("confidence", 0.0)
                st.info(f"💭 Detected emotion: {emotion.title()} ({confidence:.0%} confidence)")

                with st.expander("📚 Retrieved Context"):
                    st.text(result.get("context", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: Settings
# ═══════════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("### ⚙️ Production Pipeline Settings")
    st.markdown("Changes take effect on the next message. Sliders update instantly.")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 🦙 LLM Settings")
        _, avail_models = llm_status()
        model_options = avail_models if avail_models else ["openai/gpt-oss-120b"]
        new_model = st.selectbox(
            "Groq Model",
            model_options,
            index=0,
        )
        new_tokens = st.slider("Max Tokens", 64, 1024, st.session_state.settings["max_tokens"], 32)
        new_temp = st.slider("Temperature", 0.0, 1.5, st.session_state.settings["temperature"], 0.05)
        
        st.markdown("#### 🎭 Personality Settings")
        new_enable_emotions = st.toggle(
            "Enable Emotion Detection",
            value=st.session_state.settings.get("enable_emotions", True),
            help="Detect and use emotions for better retrieval and responses"
        )
        new_enable_cache = st.toggle(
            "Enable Response Cache",
            value=st.session_state.settings.get("enable_cache", True),
            help="Cache responses for faster repeated queries"
        )

    with col_b:
        st.markdown("#### 🔍 Retrieval Settings")
        new_k = st.slider("Top-K Examples", 1, 10, st.session_state.settings["top_k"])
        
        st.markdown("#### 📊 Production Features")
        st.success("✅ Hybrid Search (Vector + BM25)")
        st.success("✅ Cross-encoder Reranking")
        st.success("✅ Emotion-aware Retrieval")
        st.success("✅ Conversation Memory (5 turns)")
        st.success("✅ Personality-driven Responses")

    if st.button("💾 Save Settings", key="save_settings"):
        st.session_state.settings.update({
            "model": new_model,
            "max_tokens": new_tokens,
            "temperature": new_temp,
            "top_k": new_k,
            "enable_emotions": new_enable_emotions,
            "enable_cache": new_enable_cache,
        })
        # Clear cached pipeline so it rebuilds with new settings
        get_async_pipeline.clear()
        st.success("✅ Settings saved! Pipeline will reload on next message.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: Index Info
# ═══════════════════════════════════════════════════════════════════════════════
with tab_index:
    st.markdown("### 📊 Vector Index Information")

    from config import FAISS_INDEX_PATH, METADATA_PATH, CONVERSATIONS_PATH, SAMPLE_CONVERSATIONS_PATH

    # File status
    def file_chip(path: Path) -> str:
        if path.exists():
            size_kb = path.stat().st_size / 1024
            return f"✅ `{path.name}` ({size_kb:.1f} KB)"
        return f"❌ `{path.name}` – not found"

    col_info, col_action = st.columns([2, 1])

    with col_info:
        st.markdown("#### File Status")
        st.markdown(file_chip(FAISS_INDEX_PATH))
        st.markdown(file_chip(METADATA_PATH))
        st.markdown(file_chip(CONVERSATIONS_PATH))
        st.markdown(file_chip(SAMPLE_CONVERSATIONS_PATH))

        st.markdown("---")
        if index_exists():
            try:
                pipeline = get_or_create_async_pipeline()
                
                # Get async stats
                stats = asyncio.run(pipeline.get_stats())
                
                st.markdown("#### 📈 Pipeline Statistics")
                col1, col2, col3 = st.columns(3)
                col1.metric("📄 Vectors", f"{stats['corpus_size']:,}")
                col2.metric("💾 Cache Size", f"{stats['cache_size']:,}")
                col3.metric("🧠 Embed Model", "all-MiniLM-L6-v2")
                
                col4, col5, col6 = st.columns(3)
                col4.metric("📐 Index Type", "Hybrid")
                col5.metric("🎯 Top-K", stats['top_k'])
                col6.metric("🌡️ Temperature", stats['temperature'])
                
                # Show emotion distribution if available
                try:
                    import pickle
                    with open(METADATA_PATH, "rb") as f:
                        metadata = pickle.load(f)
                    
                    emotions = {}
                    for record in metadata:
                        emotion = record.get("metadata", {}).get("emotion", "neutral")
                        emotions[emotion] = emotions.get(emotion, 0) + 1
                    
                    if emotions:
                        st.markdown("---")
                        st.markdown("#### 🎭 Emotion Distribution in Corpus")
                        
                        emotion_emoji = {
                            "romantic": "💕",
                            "flirty": "😘",
                            "playful": "😄",
                            "sad": "😢",
                            "serious": "🧐",
                            "curious": "🤔",
                            "supportive": "🤗",
                            "neutral": "😐",
                        }
                        
                        for emotion, count in sorted(emotions.items(), key=lambda x: x[1], reverse=True):
                            emoji = emotion_emoji.get(emotion, "💬")
                            percentage = (count / len(metadata)) * 100
                            st.progress(percentage / 100, text=f"{emoji} {emotion.title()}: {count:,} ({percentage:.1f}%)")
                
                except Exception as e:
                    st.caption(f"No emotion metadata available ({e})")
                    
            except Exception as e:
                st.warning(f"Could not load index stats: {e}")
        else:
            st.info("No index built yet. Build one to see stats.")

    with col_action:
        st.markdown("#### Actions")

        if st.button("🔨 Build Index\n(seed data)", key="build_seed"):
            import subprocess
            with st.spinner("Building index from seed dataset …"):
                result = subprocess.run(
                    [sys.executable, "scripts/build_index.py",
                     "--src", str(SAMPLE_CONVERSATIONS_PATH)],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent)
                )
            if result.returncode == 0:
                get_pipeline.clear()
                st.success("✅ Index built successfully!")
                st.rerun()
            else:
                st.error(f"Build failed:\n```\n{result.stderr}\n```")

        if st.button("🔄 Build Index\n(full corpus)", key="build_full"):
            import subprocess
            with st.spinner("Building index from full conversations dataset …"):
                result = subprocess.run(
                    [sys.executable, "scripts/build_index.py"],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent)
                )
            if result.returncode == 0:
                get_pipeline.clear()
                st.success("✅ Full index built successfully!")
                st.rerun()
            else:
                st.error(f"Build failed:\n```\n{result.stderr}\n```")

        if index_exists():
            if st.button("🗑️ Delete Index", key="del_idx"):
                FAISS_INDEX_PATH.unlink(missing_ok=True)
                METADATA_PATH.unlink(missing_ok=True)
                get_pipeline.clear()
                st.warning("Index deleted.")
                st.rerun()

        st.markdown("---")
        st.markdown("#### Download Datasets")
        if st.button("📥 Download\nDailyDialog + BST", key="dl_datasets"):
            import subprocess
            with st.spinner("Downloading datasets (may take a while) …"):
                r1 = subprocess.run(
                    [sys.executable, "scripts/collect_datasets.py"],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent)
                )
                r2 = subprocess.run(
                    [sys.executable, "scripts/process_dataset.py"],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent)
                )
            if r1.returncode == 0 and r2.returncode == 0:
                st.success("✅ Datasets downloaded and processed!")
            else:
                st.error("Download/process failed. Check network and HuggingFace access.")
