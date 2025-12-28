"""
Vector Store Service
Handles ChromaDB initialization, embedding creation, and semantic search.

This is the "Memory" of the AI Agent - stores resume chunks as vectors
for retrieval-augmented generation (RAG).

Uses FREE embeddings via HuggingFace sentence-transformers (runs locally).
"""

import os
from typing import List, Optional
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings

settings = get_settings()


# ============================================================================
# Text Splitter Configuration
# ============================================================================

def get_text_splitter(
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> RecursiveCharacterTextSplitter:
    """
    Create a text splitter optimized for resume content.
    
    Args:
        chunk_size: Maximum characters per chunk (default 500 for resume sections)
        chunk_overlap: Overlap between chunks to maintain context
        
    Returns:
        Configured RecursiveCharacterTextSplitter
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=[
            "\n\n",  # Paragraph breaks (section separators)
            "\n",    # Line breaks
            ". ",    # Sentences
            ", ",    # Clauses
            " ",     # Words
            "",      # Characters (last resort)
        ]
    )


def chunk_text(
    text: str,
    metadata: Optional[dict] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[Document]:
    """
    Split text into chunks with metadata.
    
    Args:
        text: Raw text to chunk
        metadata: Optional metadata to attach to each chunk
        chunk_size: Maximum characters per chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of LangChain Document objects
    """
    splitter = get_text_splitter(chunk_size, chunk_overlap)
    
    # Split into raw text chunks
    text_chunks = splitter.split_text(text)
    
    # Convert to Documents with metadata
    base_metadata = metadata or {}
    documents = []
    
    for i, chunk in enumerate(text_chunks):
        doc_metadata = {
            **base_metadata,
            "chunk_index": i,
            "chunk_total": len(text_chunks),
        }
        documents.append(Document(page_content=chunk, metadata=doc_metadata))
    
    return documents


# ============================================================================
# Vector Store Management
# ============================================================================

class VectorStoreService:
    """
    Service for managing ChromaDB vector store operations.
    Handles embedding creation, storage, and retrieval.
    
    Uses FREE HuggingFace embeddings (runs locally, no API key needed).
    """
    
    _instance: Optional["VectorStoreService"] = None
    _vectorstore: Optional[Chroma] = None
    _embeddings: Optional[HuggingFaceEmbeddings] = None
    
    # Collection names
    RESUME_COLLECTION = "resume_chunks"
    
    def __new__(cls):
        """Singleton pattern - one vector store instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize embeddings and vector store."""
        if self._embeddings is None:
            self._initialize()
    
    def _initialize(self):
        """Initialize HuggingFace embeddings (FREE, local) and ChromaDB."""
        # Ensure persist directory exists
        persist_dir = Path(settings.CHROMA_PERSIST_DIRECTORY)
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize HuggingFace embeddings (FREE - runs locally)
        # all-MiniLM-L6-v2: Fast, ~80MB, good quality for semantic search
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},  # Use "cuda" if GPU available
            encode_kwargs={"normalize_embeddings": True}
        )
        
        # Initialize Chroma vector store
        self._vectorstore = Chroma(
            collection_name=self.RESUME_COLLECTION,
            embedding_function=self._embeddings,
            persist_directory=str(persist_dir),
        )
    
    @property
    def vectorstore(self) -> Chroma:
        """Get the vector store instance."""
        if self._vectorstore is None:
            self._initialize()
        return self._vectorstore
    
    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Get the embeddings instance."""
        if self._embeddings is None:
            self._initialize()
        return self._embeddings
    
    def add_documents(
        self,
        documents: List[Document],
        user_id: Optional[str] = None
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of LangChain Document objects
            user_id: Optional user ID to tag documents
            
        Returns:
            List of document IDs
        """
        # Add user_id to metadata if provided
        if user_id:
            for doc in documents:
                doc.metadata["user_id"] = user_id
        
        # Add to vector store
        ids = self.vectorstore.add_documents(documents)
        
        return ids
    
    def search(
        self,
        query: str,
        k: int = 3,
        user_id: Optional[str] = None,
        filter_dict: Optional[dict] = None
    ) -> List[Document]:
        """
        Search for relevant documents using semantic similarity.
        
        Args:
            query: Search query text
            k: Number of results to return
            user_id: Optional user ID to filter results
            filter_dict: Optional additional filters
            
        Returns:
            List of relevant Document objects
        """
        # Build filter
        search_filter = filter_dict or {}
        if user_id:
            search_filter["user_id"] = user_id
        
        # Perform similarity search
        if search_filter:
            results = self.vectorstore.similarity_search(
                query=query,
                k=k,
                filter=search_filter
            )
        else:
            results = self.vectorstore.similarity_search(
                query=query,
                k=k
            )
        
        return results
    
    def search_with_scores(
        self,
        query: str,
        k: int = 3,
        user_id: Optional[str] = None
    ) -> List[tuple[Document, float]]:
        """
        Search with relevance scores.
        
        Args:
            query: Search query text
            k: Number of results to return
            user_id: Optional user ID to filter results
            
        Returns:
            List of (Document, score) tuples
        """
        search_filter = {"user_id": user_id} if user_id else None
        
        if search_filter:
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=k,
                filter=search_filter
            )
        else:
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=k
            )
        
        return results
    
    def delete_user_documents(self, user_id: str) -> bool:
        """
        Delete all documents for a specific user.
        
        Args:
            user_id: User ID to delete documents for
            
        Returns:
            True if successful
        """
        # Get all document IDs for this user
        # Note: Chroma doesn't have a direct delete by filter, 
        # so we need to get IDs first
        try:
            collection = self.vectorstore._collection
            results = collection.get(
                where={"user_id": user_id}
            )
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
            return True
        except Exception as e:
            print(f"Error deleting documents: {e}")
            return False
    
    def get_collection_stats(self) -> dict:
        """
        Get statistics about the vector store collection.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.vectorstore._collection
            count = collection.count()
            return {
                "collection_name": self.RESUME_COLLECTION,
                "document_count": count,
                "persist_directory": settings.CHROMA_PERSIST_DIRECTORY,
            }
        except Exception as e:
            return {
                "error": str(e),
                "collection_name": self.RESUME_COLLECTION,
            }


# ============================================================================
# Module-level convenience functions
# ============================================================================

def get_vector_store() -> VectorStoreService:
    """Get the singleton vector store service instance."""
    return VectorStoreService()


def ingest_resume(
    text: str,
    filename: str,
    user_id: Optional[str] = None
) -> dict:
    """
    Ingest a resume into the vector store.
    
    Args:
        text: Cleaned resume text
        filename: Original filename
        user_id: Optional user ID
        
    Returns:
        Dictionary with ingestion results
    """
    # Chunk the text
    metadata = {
        "source": filename,
        "type": "resume",
    }
    documents = chunk_text(text, metadata=metadata)
    
    # Add to vector store
    vs = get_vector_store()
    doc_ids = vs.add_documents(documents, user_id=user_id)
    
    return {
        "chunks_created": len(documents),
        "document_ids": doc_ids,
        "metadata": metadata,
    }


def query_resume(
    query: str,
    k: int = 3,
    user_id: Optional[str] = None
) -> List[dict]:
    """
    Query the resume vector store.
    
    Args:
        query: Search query
        k: Number of results
        user_id: Optional user ID filter
        
    Returns:
        List of result dictionaries
    """
    vs = get_vector_store()
    results = vs.search_with_scores(query=query, k=k, user_id=user_id)
    
    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "relevance_score": float(score),
        }
        for doc, score in results
    ]
