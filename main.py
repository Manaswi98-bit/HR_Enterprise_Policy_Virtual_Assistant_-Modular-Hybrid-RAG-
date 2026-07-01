from data_loader import Load_PDF, DocumentSplitter
from llm_service import (
    get_embedding_model, 
    setup_hybrid_search, 
    get_llm, 
    run_reranked_search, 
    generate_answer
)

def main():
    print("==================================================")
    print("🚀 INITIALIZING COMPLETE MODULAR RAG PIPELINE")
    print("==================================================\n")
    
    # 1. LOAD THE PDF
    try:
        pdf_loader = Load_PDF("data/HR-Policy.pdf")
        docs = pdf_loader.load()
    except FileNotFoundError:
        try:
            pdf_loader = Load_PDF("HR-Policy.pdf")
            docs = pdf_loader.load()
        except Exception as e:
            print(f"❌ Could not find HR-Policy.pdf. Please verify the file path: {e}")
            return
    
    # 2. CHUNK THE DOCUMENT
    splitter = DocumentSplitter(chunk_size=600, chunk_overlap=120)
    chunks = splitter.split(docs)
    print(f"📄 Document partitioned into {len(chunks)} searchable chunks.")
    
    # 3. INITIALIZE MISTRAL EMBEDDINGS MODEL
    embedding_model = get_embedding_model()
    
    # 4. BUILD HYBRID INDEXES (Chroma Vector DB + BM25 Keyword)
    vector_db, keyword_db = setup_hybrid_search(chunks, embedding_model)
    
    # 5. INITIALIZE THE MISTRAL LLM ENGINE
    try:
        llm = get_llm()
    except Exception as e:
        print(f"❌ LLM initialization failed: {e}")
        return

    print("\n✅ System Ready! Entering User Query Phase.")
    print("==================================================")
    
    # 6. INTERACTIVE USER QUERY SECTION
    while True:
        print("\n" + "="*40)
        query = input("💬 Ask an HR Policy Question (or type 'exit' to quit): ").strip()
        
        if not query or query.lower() == 'exit':
            print("👋 Shutting down RAG pipeline. Goodbye!")
            break
            
        print("🔍 Gathering candidate chunks and reranking...")
        best_context_chunks = run_reranked_search(query, vector_db, keyword_db)
        
        print("🤖 Thinking and generating response...")
        final_answer = generate_answer(query=query, context_documents=best_context_chunks, llm_model=llm)
        
        print("\n💡 HR RESPONSE:")
        print(final_answer.strip())
        print("="*40)

if __name__ == "__main__":
    main()