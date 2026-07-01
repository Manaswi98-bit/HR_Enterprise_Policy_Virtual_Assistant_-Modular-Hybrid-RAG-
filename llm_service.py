import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_compressors import FlashrankRerank
from flashrank import Ranker  

# Automatically read variables out of your .env file
load_dotenv()

def get_embedding_model():
    """Initializes the official Mistral AI embedding model."""
    if not os.environ.get("MISTRAL_API_KEY"):
        raise ValueError("❌ MISTRAL_API_KEY missing from environment or .env file.")
        
    print("🤖 Loading the Mistral AI embedding model...")
    return MistralAIEmbeddings(model="mistral-embed")

def setup_hybrid_search(chunks, embedding_model):
    """Sets up basic Vector (Chroma) and Keyword (BM25) databases."""
    print("📦 Building Hybrid search indexes...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory="./my_local_db"
    )
    keyword_db = BM25Retriever.from_documents(chunks)
    return vector_db, keyword_db

def get_llm():
    """Initializes a direct connection to Mistral AI using your MISTRAL_API_KEY."""
    if not os.environ.get("MISTRAL_API_KEY"):
        raise ValueError("❌ MISTRAL_API_KEY missing from environment or .env file.")

    print("🤖 Connecting directly to Mistral AI API...")
    # Pure direct API connection to Mistral - does not use Hugging Face
    llm = ChatMistralAI(
        model="mistral-large-latest",
        temperature=0.2,
        max_tokens=512
    )
    return llm

def run_reranked_search(query: str, vector_db, keyword_db) -> list:
    """Gathers raw results from both DBs, merges them, and uses FlashRank to pick the top 2."""
    v_results = vector_db.similarity_search(query, k=4)
    k_results = keyword_db.invoke(query)[:4]
    
    candidates = []
    for doc in (v_results + k_results):
        if doc not in candidates:
            candidates.append(doc)
            
    # Initialize the core Flashrank engine client manually 
    # to completely bypass Pydantic model validation issues
    flashrank_client = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    
    # Pass the pre-warmed client directly into the compressor
    compressor = FlashrankRerank(client=flashrank_client, top_n=2)
    
    reranked_docs = compressor.compress_documents(documents=candidates, query=query)
    return reranked_docs

def generate_answer(query: str, context_documents: list, llm_model) -> str:
    """Combines the query and text fragments into a structured prompt template."""
    context_text = "\n\n".join([doc.page_content for doc in context_documents])
    
    prompt = f"""You are an expert HR Virtual Assistant. Answer the user's question accurately using ONLY the provided HR Policy contexts below. 
If the context does not contain the answer, say "I cannot find the answer in the official policy document." Do not try to make up rules.

---
HR CONTEXT AVAILABLE:
{context_text}
---

USER QUESTION: {query}

HR ASSISTANT ANSWER:"""
    
    response = llm_model.invoke(prompt)
    # ChatMistralAI returns a Message object, so we extract text using .content
    return response.content