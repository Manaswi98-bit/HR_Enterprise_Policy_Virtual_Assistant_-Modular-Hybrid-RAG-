# 🧠 HR Enterprise Policy Assistant (Cortex AI)

> An AI assistant that reads your company's HR policy documents and answers employee questions in plain English — **only** from what the documents actually say, with a source citation for every answer.

**Difficulty:** Intermediate · **Skills demonstrated:** Retrieval-Augmented Generation (RAG), Hybrid Search, Cross-Encoder Re-ranking, Answer-quality evaluation · **Status:** ✅ Working

---

## 👋 For everyone (the 30-second version)

Imagine a new employee asks: *"How many paid leave days do I get, and can I carry them over?"*

Instead of digging through a 60-page PDF, they ask this assistant. It:

1. **Finds** the exact passages in the HR documents that relate to the question.
2. **Reads** only those passages — it is **not allowed** to make things up or use outside knowledge.
3. **Answers** clearly and **shows its sources** (which document and page), so the answer can be trusted and verified.
4. **Scores itself** on how well the answer is backed by the documents, and how fast it responded.

If the answer isn't in the documents, it honestly says so instead of guessing. That honesty is what makes it safe for real HR and compliance use.

---

## 💼 Why this project matters (for recruiters & hiring managers)

This is a **production-style RAG system**, not a toy chatbot. It demonstrates the concerns that matter in real enterprise AI work:

| Concern | How it's handled here |
|---|---|
| **Trust & accuracy** | Answers are grounded strictly in source documents; the model refuses when it doesn't know. |
| **Traceability** | Every answer cites the source file and page number. |
| **Search quality** | Uses **hybrid search** (keyword + semantic) plus a **neural re-ranker** — the pattern serious enterprise search tools rely on. |
| **Measurability** | Ships a built-in scoring system (relevance, groundedness, latency) so quality is a number, not a guess. |
| **Multiple formats** | Ingests PDF, Word, text, CSV, and Markdown. |
| **Two interfaces** | A polished web app **and** a command-line tool. |

---

## 🛠️ For engineers (the technical version)

### Architecture

```
Documents (PDF / DOCX / TXT / CSV / MD)
        │
        ▼
[ Loader ] → clean text + attach source & page metadata     (data_loader.py)
        │
        ▼
[ Splitter ] → chunks (size 600, overlap 120)               (data_loader.py)
        │
        ▼
[ Embed + Index ] ── ChromaDB (dense vectors)
                 └── BM25 (sparse keywords)                  (llm_service.py)
        │
   user query
        │
        ▼
[ Hybrid Retrieval ] → dense top-k  ∪  BM25 top-k → de-dup
        │
        ▼
[ Cross-Encoder Re-rank ] → FlashRank (ms-marco-MiniLM) → top-n
        │
        ▼
[ Generate ] → Mistral LLM, context-only prompt, cited      (llm_service.py)
        │
        ▼
[ Evaluate ] → relevance + groundedness + latency scores
```

### Stack

- **Python** 3.12+
- **LLM & embeddings:** Mistral (`mistral-large-latest`, `mistral-embed`) via `langchain-mistralai`
- **Vector store:** ChromaDB (persistent)
- **Keyword search:** BM25 (`langchain-community`)
- **Re-ranker:** FlashRank cross-encoder (`ms-marco-MiniLM-L-12-v2`)
- **Framework:** LangChain
- **Web UI:** Streamlit
- **Config:** `python-dotenv`

### Key design decisions

- **Hybrid retrieval** — dense vectors catch *meaning* ("time off" ≈ "leave"), BM25 catches *exact terms* (policy codes, section numbers, internal acronyms). Results are merged and de-duplicated.
- **Cross-encoder re-ranking** — re-scores the merged candidates so only the *most* relevant 2 chunks reach the LLM, keeping the prompt small, cheap, and precise.
- **Grounded prompting** — the system prompt forbids outside knowledge and mandates an exact refusal string when the context lacks the answer.
- **Self-evaluation** — `calculate_accuracy_matrix()` blends retrieval relevance (cosine similarity) with groundedness (lexical + semantic overlap between answer and context).

---

## 🚀 Why this architecture wins

Standard "naive" RAG uses a single dense-vector search. This pipeline adds **hybrid search + cross-encoder re-ranking**, which improves accuracy, cuts token cost, and suppresses hallucination:

| Dimension | Naive vector RAG | This hybrid + re-ranker | Gain |
|---|---|---|---|
| **Retrieval accuracy** | ~60–70% (misses acronyms, policy IDs, jargon) | ~85–95% (meaning **and** exact keywords) | **+35% precision** |
| **Context sent to LLM** | 4–8 bloated chunks | Top 2 highest-quality chunks | **~50% fewer tokens** |
| **Hallucination risk** | High — invents answers on no match | Strict context-only prompt + explicit refusal | **~90% fewer false outputs** |

*(Figures are indicative of the design's expected behavior on HR-policy documents, not a formal benchmark run.)*

---

## 📂 Project structure

```
HR_Enterprise_Policy/
├── README.md              # this file
├── main.py                # command-line chat interface
├── app.py                 # Streamlit web interface (Cortex AI UI)
├── data_loader.py         # multi-format loading + semantic chunking
├── llm_service.py         # embeddings, hybrid search, re-rank, generate, evaluate
├── pyproject.toml         # dependencies
├── data/                  # your source documents (e.g. HR-Policy.pdf)
├── chroma_db_storage/     # persisted vector index (auto-generated)
└── .env                   # API keys (not committed)
```

---

## ⚡ Getting started

### 1. Prerequisites

- Python 3.12+
- A **Mistral API key** (required). Google / HuggingFace keys are optional.

### 2. Install

Using [`uv`](https://github.com/astral-sh/uv):

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

### 3. Configure keys

Create a `.env` file in the project root:

```env
MISTRAL_API_KEY=your_key_here

# Optional overrides (sensible defaults already set)
PERSIST_DIR=./chroma_db_storage
EMBED_MODEL=mistral-embed
LLM_MODEL=mistral-large-latest
RERANK_MODEL=ms-marco-MiniLM-L-12-v2
```

### 4. Add documents

Drop your HR files into the `data/` folder (PDF, DOCX, TXT, CSV, or MD).

### 5. Run

**Web app (recommended):**

```bash
streamlit run app.py
```

**Command line:**

```bash
python main.py
```

Then ask questions like *"What is the notice period for resignation?"* — the assistant replies with cited sources and quality metrics.

---

## 📊 What the metrics mean

Every answer reports four numbers, so quality is measurable rather than assumed:

- **Accuracy Score** — overall confidence, blending the two scores below.
- **Retrieval Relevance** — how well the retrieved passages match the question.
- **Groundedness** — how much of the answer is actually supported by those passages (this is the hallucination check).
- **Latency** — response time in seconds.

---

## 🧭 Example

```
Ask a Question: What is the maternity leave policy?

========================= ANSWER =========================
Eligible employees are entitled to 26 weeks of paid maternity
leave... [Reference #1]

==================== METRICS ====================
Accuracy Score      : 87.4%
Retrieval Relevance : 91.2%
Groundedness        : 83.6%
Latency             : 1.9 seconds

==================== REFERENCES ====================
[Reference #1] Source: HR-Policy.pdf (Page: 12) | Score: 91.2%
Snippet: Maternity leave shall be granted for a period of...
```

---

## 🔒 Production notes

- **No hallucination by design:** the model refuses when the answer isn't in the documents.
- **Secrets safe:** API keys live in `.env` and are git-ignored.
- **Persistent index:** documents are embedded once and reused across sessions.
- **Graceful degradation:** if the re-ranker fails to load, the system falls back to top hybrid results instead of crashing.

---

*Portfolio project demonstrating enterprise-grade Retrieval-Augmented Generation with hybrid search, cross-encoder re-ranking, grounded generation, and built-in answer evaluation.*
