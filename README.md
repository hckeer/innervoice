# 🤖 RAG Conversation Assistant

A fully **local, offline-capable** RAG (Retrieval-Augmented Generation) pipeline that suggests replies to conversation messages.

Built with: **sentence-transformers · FAISS · Ollama llama3 · Streamlit · Tesseract OCR**

---

## 📁 Project Structure

```
rag_assistant/
├── app.py                          # Streamlit 4-tab UI
├── config.py                       # Central configuration (env-var overrides)
├── requirements.txt
├── .env.example                    # Copy to .env to configure
├── data/
│   ├── sample_conversations.jsonl  # 100-row seed corpus (included)
│   ├── conversations.jsonl         # Generated: merged + deduped corpus
│   ├── index.faiss                 # Generated: FAISS vector index
│   └── metadata.pkl                # Generated: index metadata
├── scripts/
│   ├── collect_datasets.py         # Download DailyDialog + BlendedSkillTalk
│   ├── process_dataset.py          # Merge & normalise → conversations.jsonl
│   └── build_index.py              # Embed corpus → FAISS index
├── rag/
│   ├── vector_store.py             # FAISS wrapper (load/save/search)
│   ├── retriever.py                # Top-k retrieval + context assembly
│   ├── prompt_templates.py         # Prompt templates (reply, tone, summary)
│   ├── llm_client.py               # Ollama HTTP client (streaming + sync)
│   └── pipeline.py                 # End-to-end RAG orchestration
└── ocr/
    └── screenshot_reader.py        # Tesseract OCR for chat screenshots
```

---

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Python 3.10+
python --version

# Tesseract OCR (optional, for screenshot reading)
sudo apt install tesseract-ocr

# Ollama (local LLM server)
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Install Python dependencies

```bash
cd /home/hckeer/work/antiproject1/rag_assistant

# Recommended: create a virtual environment
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure (optional)

```bash
cp .env.example .env
# Edit .env to change model, paths, or Ollama URL
```

### 4. Build the FAISS index

```bash
# Option A: Use the built-in 100-row seed dataset (instant, no download)
python scripts/build_index.py --src data/sample_conversations.jsonl

# Option B: Download large open datasets first, then build
python scripts/collect_datasets.py    # downloads DailyDialog + BlendedSkillTalk
python scripts/process_dataset.py     # merges & deduplicates
python scripts/build_index.py         # embeds and indexes
```

### 5. Start Ollama and pull the model

```bash
ollama serve          # starts Ollama server (keep running in background)
ollama pull llama3    # download llama3 (~4GB, one-time)
```

### 6. Launch the Streamlit app

```bash
streamlit run app.py
# → Opens at http://localhost:8501
```

---

## 🖥️ App Tabs

| Tab | Description |
|-----|-------------|
| **💬 Chat Assistant** | Type a message → streaming reply suggestion + retrieved context |
| **📸 OCR Input** | Upload a chat screenshot → OCR → extract conversation → suggest reply |
| **⚙️ Settings** | Adjust model, temperature, top-k, streaming mode |
| **📊 Index Info** | View corpus stats, rebuild index, download datasets |

---

## 📐 Dataset Format

All conversations are stored as JSONL, one record per line:

```jsonl
{"input": "Hey, how are you doing today?", "response": "I'm doing great, thanks for asking!"}
{"input": "Do you have any movie recommendations?", "response": "If you're into sci-fi, Interstellar is fantastic!"}
```

To add your own data, append records to `data/conversations.jsonl` then rebuild the index:

```bash
echo '{"input": "your message", "response": "ideal reply"}' >> data/conversations.jsonl
python scripts/build_index.py
```

---

## 🔍 Retrieval Pipeline

```
User Message
     │
     ▼
sentence-transformers (all-MiniLM-L6-v2)
     │  embed + L2-normalise
     ▼
FAISS IndexFlatIP (cosine similarity)
     │  top-k similar inputs
     ▼
Prompt Template  ←──── Retrieved Examples (context)
     │
     ▼
Ollama llama3 (local HTTP API)
     │
     ▼
Suggested Reply
```

---

## 🛠️ CLI / Script Usage

```bash
# Quick retrieval smoke test
python -c "
from rag.vector_store import VectorStore
vs = VectorStore()
vs.load('data/index.faiss', 'data/metadata.pkl')
for r in vs.search('How are you?', k=3):
    print(f\"[{r['score']:.3f}] {r['input'][:60]}\")
"

# End-to-end pipeline (requires Ollama running)
python -c "
from rag.pipeline import RAGPipeline
p = RAGPipeline()
result = p.suggest_reply('Hey, what are you doing tonight?')
print('Reply:', result['reply'])
"

# OCR parse (no Tesseract needed for text input)
python -c "
from ocr.screenshot_reader import ScreenshotReader
r = ScreenshotReader()
turns = r.parse_chat_lines('Alice: Hi!\nBob: Hello there, how are you?')
for t in turns: print(t)
"
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Model to use |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `TOP_K` | `5` | Retrieved examples per query |
| `MAX_TOKENS` | `512` | Max LLM output tokens |
| `TEMPERATURE` | `0.7` | LLM sampling temperature |
| `FAISS_INDEX_PATH` | `data/index.faiss` | FAISS index location |
| `METADATA_PATH` | `data/metadata.pkl` | Index metadata location |
| `CONVERSATIONS_PATH` | `data/conversations.jsonl` | Processed corpus |

---

## 🔧 Troubleshooting

**Ollama not connecting**
```bash
ollama serve          # Make sure it's running
ollama list           # Check model is pulled
```

**FAISS index not found**
```bash
python scripts/build_index.py --src data/sample_conversations.jsonl
```

**OCR not working**
```bash
sudo apt install tesseract-ocr
pip install pytesseract Pillow
```

**Slow first query**
- First query loads the embedding model (~90MB download). Subsequent queries are fast.

---

## 📦 Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `sentence-transformers` | ≥2.7 | Text embeddings |
| `faiss-cpu` | ≥1.8 | Vector similarity search |
| `datasets` | ≥2.18 | HuggingFace dataset downloads |
| `streamlit` | ≥1.32 | Web UI |
| `requests` | ≥2.31 | Ollama HTTP client |
| `pytesseract` | ≥0.3.10 | OCR (optional) |
| `Pillow` | ≥10.2 | Image processing |
| `python-dotenv` | ≥1.0 | Environment config |

---
