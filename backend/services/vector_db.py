import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.config import get_settings
import structlog
from typing import List, Dict, Any, Optional
import ollama

logger = structlog.get_logger()

class VectorDBService:
    def __init__(self):
        self.settings = get_settings()
        self.client = chromadb.PersistentClient(path=self.settings.CHROMA_DB_PATH)
        self.embedding_model = self.settings.EMBEDDING_MODEL
        self.collection_name = "wendy_documents"
        
        # Initialize collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama"""
        embeddings = []
        for text in texts:
            try:
                response = ollama.embeddings(model=self.embedding_model, prompt=text)
                embeddings.append(response["embedding"])
            except Exception as e:
                logger.error("Failed to generate embedding", error=str(e), text_preview=text[:50])
                raise
        return embeddings

    async def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Add documents to the vector database"""
        logger.info("Adding documents to vector DB", count=len(documents))
        
        try:
            embeddings = self._get_embeddings(documents)
            self.collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info("Successfully added documents")
        except Exception as e:
            logger.error("Failed to add documents to ChromaDB", error=str(e))
            raise

    async def search(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Search for relevant documents"""
        logger.info("Searching vector DB", query=query)
        
        try:
            query_embedding = self._get_embeddings([query])[0]
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error("Search failed", error=str(e))
            raise

    async def delete_document(self, doc_id: str):
        """Delete a document by ID (or ID prefix for chunks)"""
        # Note: This deletes by exact ID. If chunks have IDs like "doc_id_chunk_1", 
        # we might need a where clause.
        # For now, let's assume we delete by metadata "source_id" if we want to delete a whole file.
        try:
            self.collection.delete(where={"source_id": doc_id})
            logger.info("Deleted document chunks", source_id=doc_id)
        except Exception as e:
            logger.error("Failed to delete document", error=str(e))
            raise

_vector_db_service: VectorDBService | None = None

def get_vector_db_service():
    global _vector_db_service
    if _vector_db_service is None:
        _vector_db_service = VectorDBService()
    return _vector_db_service
