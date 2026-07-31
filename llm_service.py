import os
import shutil
import numpy as np
from dotenv import load_dotenv

from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from flashrank import Ranker

load_dotenv()

# Read settings from environment variables
PERSIST_DIR = os.getenv("PERSIST_DIR", "./chroma_db_storage")
EMBED_MODEL = os.getenv("EMBED_MODEL", "mistral-embed")
LLM_MODEL = os.getenv("LLM_MODEL", "mistral-large-latest")
RERANK_MODEL = os.getenv("RERANK_MODEL", "ms-marco-MiniLM-L-12-v2")

RERANK_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flashrank_cache")


def check_api_key():
    if not os.getenv("MISTRAL_API_KEY"):
        raise ValueError("MISTRAL_API_KEY missing. Please add it to your .env file.")


def get_embedding_model() -> MistralAIEmbeddings:
    check_api_key()
    return MistralAIEmbeddings(model=EMBED_MODEL, max_retries=5)


def get_llm(temperature: float = 0.2) -> ChatMistralAI:
    check_api_key()
    return ChatMistralAI(model=LLM_MODEL, temperature=temperature, max_tokens=512, max_retries=5)


def setup_hybrid_search(chunks, embedding_model, clear_existing: bool = False):
    if clear_existing and os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    if chunks:
        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_model,
            persist_directory=PERSIST_DIR,
        )
    else:
        vector_db = Chroma(
            persist_directory=PERSIST_DIR,
            embedding_function=embedding_model,
        )

    stored = vector_db.get()
    all_docs = []
    if stored and stored.get("documents"):
        for text, meta in zip(stored["documents"], stored["metadatas"]):
            all_docs.append(Document(page_content=text, metadata=meta or {}))

    keyword_db = BM25Retriever.from_documents(all_docs) if all_docs else None
    return vector_db, keyword_db, all_docs


def clear_vector_store(vector_db) -> int:
    if vector_db is None:
        return 0
    data = vector_db.get()
    ids = data.get("ids", []) if data else []
    if ids:
        vector_db.delete(ids=ids)
    return len(ids)


def _dedup(docs):
    seen, unique = set(), []
    for doc in docs:
        key = doc.page_content.strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(doc)
    return unique


def run_reranked_search(query: str, vector_db, keyword_db, top_k: int = 4, top_n: int = 2) -> list:
    v_results = vector_db.similarity_search(query, k=top_k) if vector_db else []
    k_results = keyword_db.invoke(query)[:top_k] if keyword_db else []

    candidates = _dedup(v_results + k_results)
    if not candidates:
        return []

    try:
        os.makedirs(RERANK_CACHE, exist_ok=True)
        ranker = Ranker(model_name=RERANK_MODEL, cache_dir=RERANK_CACHE)
        compressor = FlashrankRerank(client=ranker, top_n=min(top_n, len(candidates)))
        return compressor.compress_documents(documents=candidates, query=query)
    except Exception as exc:
        print(f"Reranker skipped: {exc}")
        return candidates[:top_n]


SYSTEM_PROMPT = """You are the HR Enterprise Policy Assistant.

STRICT RULES:
1. Answer ONLY from the DOCUMENT CONTEXT below. Never use outside knowledge.
2. If the context does not contain the answer, reply exactly:
   "I cannot find the answer in the provided HR policy documents."
3. Be precise and concise.
4. Cite sources like [Reference #1] when relevant."""


def generate_answer(query: str, context_documents: list, llm_model, chat_history: list = None) -> str:
    if not context_documents:
        return "I cannot find the answer in the provided HR policy documents."

    context_blocks = []
    for idx, doc in enumerate(context_documents, start=1):
        src = doc.metadata.get("source_name", "Document")
        page = doc.metadata.get("page", "N/A")
        context_blocks.append(f"[Reference #{idx}] (Source: {src}, Page: {page})\n{doc.page_content}")
    context_text = "\n\n".join(context_blocks)

    formatted_history = "No prior history."
    if chat_history:
        recent = chat_history[-6:]
        formatted_history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)

    prompt = f"""{SYSTEM_PROMPT}

RECENT CONVERSATION:
{formatted_history}

DOCUMENT CONTEXT:
{context_text}

USER QUESTION: {query}

ANSWER:"""

    response = llm_model.invoke(prompt)
    return response.content


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def calculate_accuracy_matrix(query: str, response_text: str, context_docs: list, embedding_model, latency: float) -> dict:
    if not context_docs:
        return {
            "retrieval_relevance": 0.0,
            "groundedness_score": 0.0,
            "overall_accuracy": 0.0,
            "latency_sec": round(latency, 2),
            "match_scores": [],
            "status": "No Context Found",
        }

    chunk_texts = [d.page_content for d in context_docs]
    q_vec = np.array(embedding_model.embed_query(query))
    chunk_vecs = [np.array(v) for v in embedding_model.embed_documents(chunk_texts)]

    match_scores = [round(max(0.0, _cosine(q_vec, c) * 100), 2) for c in chunk_vecs]
    avg_relevance = float(np.mean(match_scores)) if match_scores else 0.0

    context_combined = " ".join(t.lower() for t in chunk_texts)
    resp_words = [w.lower() for w in response_text.split() if len(w) > 3]
    lexical = (sum(1 for w in resp_words if w in context_combined) / len(resp_words) * 100) if resp_words else 100.0

    ans_vec = np.array(embedding_model.embed_query(response_text))
    ctx_vec = np.array(embedding_model.embed_query(context_combined[:8000]))
    semantic = max(0.0, _cosine(ans_vec, ctx_vec) * 100)

    groundedness = round(0.5 * lexical + 0.5 * semantic, 2)
    overall = round(0.5 * avg_relevance + 0.5 * groundedness, 2)

    return {
        "retrieval_relevance": round(avg_relevance, 2),
        "groundedness_score": groundedness,
        "overall_accuracy": overall,
        "latency_sec": round(latency, 2),
        "match_scores": match_scores,
        "status": "High Precision" if overall >= 75 else "Moderate Precision" if overall >= 50 else "Low Precision",
    }
