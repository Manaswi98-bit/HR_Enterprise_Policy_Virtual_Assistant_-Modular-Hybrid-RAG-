import os
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class Load_PDF:
    def __init__(self, file_path: str):
        self.file_path = file_path
      
    def load(self) -> List[Document]:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Target PDF file not found at: {self.file_path}")
        
        print(f"Loading document: {self.file_path}...")
        loader = PyPDFLoader(self.file_path)
        return loader.load()
    
class DocumentSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def split(self, documents: List[Document]) -> List[Document]:
        print(f"Splitting documents into smaller semantic chunks...")
        return self.splitter.split_documents(documents)