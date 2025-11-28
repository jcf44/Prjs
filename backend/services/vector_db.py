import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.config import get_settings
import structlog
from typing import List, Dict, Any, Optional
from ollama import AsyncClient

logger = structlog.get_logger()

class VectorDBService:
    def __init__(self):
        self.settings = get_settings()
        self.client = chromadb.PersistentClient(path=self.settings.CHROMA_DB_PATH)
        self.embedding_model = self.settings.EMBEDDING_MODEL
        self.collection_name = "wendy_documents"
        self.ollama_client = AsyncClient(host=self.settings.OLLAMA_BASE_URL)
        
        # Initialize collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama AsyncClient with parallel execution"""
        import asyncio
        
        async def get_single_embedding(text):
            try:
                response = await self.ollama_client.embeddings(model=self.embedding_model, prompt=text)
                return response["embedding"]
            except Exception as e:
                logger.error("Failed to generate embedding", error=str(e), text_preview=text[:50])
                raise

        # Create tasks for all texts
        tasks = [get_single_embedding(text) for text in texts]
        embeddings = await asyncio.gather(*tasks)
        return embeddings

    async def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Add documents to the vector database"""
        logger.info("Adding documents to vector DB", count=len(documents))
        
        try:
            embeddings = await self._get_embeddings(documents)
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
            query_embeddings = await self._get_embeddings([query])
            query_embedding = query_embeddings[0]
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

    async def list_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List unique documents in the vector DB"""
        try:
            # ChromaDB doesn't have a direct "SELECT DISTINCT" for metadata.
            # We have to fetch all (or limit) and aggregate.
            # This is not efficient for large datasets but works for small/medium.
            # Ideally, we would maintain a separate "documents" collection or SQL table.
            
            # Fetch metadatas only
            result = self.collection.get(include=["metadatas"])
            metadatas = result["metadatas"]
            
            unique_docs = {}
            for meta in metadatas:
                source_id = meta.get("source_id")
                if source_id and source_id not in unique_docs:
                    unique_docs[source_id] = {
                        "source_id": source_id,
                        "filename": meta.get("filename", "unknown"),
                        "source": meta.get("source", "unknown"),
                        "user_profile": meta.get("user_profile", "default"),
                        "created_at": meta.get("created_at", None) # If we added this
                    }
            
            return list(unique_docs.values())[:limit]
        except Exception as e:
            logger.error("Failed to list documents", error=str(e))
            return []

_vector_db_service: VectorDBService | None = None

def get_vector_db_service():
    global _vector_db_service
    if _vector_db_service is None:
        _vector_db_service = VectorDBService()
    return _vector_db_service
