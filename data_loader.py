import os
import tempfile
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    CSVLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter


class UniversalDocumentLoader:
    @staticmethod
    def _get_loader(file_path: str, original_filename: str = None) -> List[Document]:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif file_ext in [".txt", ".md"]:
            loader = TextLoader(file_path, encoding="utf-8")
        elif file_ext == ".docx":
            loader = Docx2txtLoader(file_path)
        elif file_ext == ".csv":
            loader = CSVLoader(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")

        docs = loader.load()
        file_name = original_filename if original_filename else os.path.basename(file_path)
        for doc in docs:
            doc.metadata["source_name"] = file_name
        return docs

    @classmethod
    def load_from_path(cls, file_path: str) -> List[Document]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        return cls._get_loader(file_path)

    @classmethod
    def load_uploaded_file(cls, uploaded_file) -> List[Document]:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            return cls._get_loader(tmp_path, original_filename=uploaded_file.name)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class DocumentSplitter:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 120):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split(self, documents: List[Document]) -> List[Document]:
        return self.splitter.split_documents(documents)