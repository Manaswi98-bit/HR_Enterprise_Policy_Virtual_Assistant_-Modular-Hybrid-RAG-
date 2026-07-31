import os
import time
from dotenv import load_dotenv
from data_loader import UniversalDocumentLoader, DocumentSplitter
from llm_service import (
    get_embedding_model,
    setup_hybrid_search,
    get_llm,
    run_reranked_search,
    generate_answer,
    calculate_accuracy_matrix
)

load_dotenv()

DATA_DIRECTORY = "./data"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 120
TOP_K_CANDIDATES = 4
TOP_N_RERANKED = 2
LLM_TEMPERATURE = 0.2


def main():
    print("=" * 60)
    print("ENTERPRISE MULTI-FORMAT RAG CLI")
    print("=" * 60)

    embedding_model = get_embedding_model()

    all_documents = []
    if os.path.exists(DATA_DIRECTORY):
        files = [f for f in os.listdir(DATA_DIRECTORY) if f.lower().endswith(('.pdf', '.txt', '.docx', '.csv', '.md'))]
        for f in files:
            all_documents.extend(UniversalDocumentLoader.load_from_path(os.path.join(DATA_DIRECTORY, f)))

    chunks = DocumentSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP).split(all_documents) if all_documents else []

    print("Initializing Database...")
    vector_db, keyword_db, stored_docs = setup_hybrid_search(chunks, embedding_model, clear_existing=False)

    print(f"Ready. Loaded {len(stored_docs)} chunks from memory.")
    
    llm = get_llm(temperature=LLM_TEMPERATURE)
    chat_history = []

    while True:
        print("\n" + "-" * 60)
        query = input("Ask a Question (type 'exit' to quit): ").strip()

        if not query or query.lower() == 'exit':
            print("Shutting down. Goodbye.")
            break

        chat_history.append({"role": "user", "content": query})
        start_time = time.time()

        retrieved_docs = run_reranked_search(
            query=query,
            vector_db=vector_db,
            keyword_db=keyword_db,
            top_k=TOP_K_CANDIDATES,
            top_n=TOP_N_RERANKED
        )

        answer = generate_answer(query, retrieved_docs, llm, chat_history)
        latency = time.time() - start_time

        metrics = calculate_accuracy_matrix(
            query=query,
            response_text=answer,
            context_docs=retrieved_docs,
            embedding_model=embedding_model,
            latency=latency
        )

        chat_history.append({"role": "assistant", "content": answer})

        print("\n" + "=" * 25 + " ANSWER " + "=" * 25)
        print(answer.strip())

        print("\n" + "=" * 20 + " METRICS " + "=" * 20)
        print(f"Accuracy Score      : {metrics['overall_accuracy']}%")
        print(f"Retrieval Relevance : {metrics['retrieval_relevance']}%")
        print(f"Groundedness        : {metrics['groundedness_score']}%")
        print(f"Latency             : {metrics['latency_sec']} seconds")

        print("\n" + "=" * 20 + " REFERENCES " + "=" * 20)
        for idx, (doc, score) in enumerate(zip(retrieved_docs, metrics["match_scores"]), start=1):
            src = doc.metadata.get("source_name", "Unknown File")
            page = doc.metadata.get("page", "N/A")
            print(f"\n[Reference #{idx}] Source: {src} (Page: {page}) | Score: {score}%")
            print(f"Snippet: {doc.page_content[:200]}...")


if __name__ == "__main__":
    main()
