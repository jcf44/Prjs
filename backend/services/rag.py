from typing import List, Dict, Any
from backend.services.vector_db import get_vector_db_service, VectorDBService
from backend.services.llm import get_llm_service, LLMService
from backend.config import get_settings
import structlog

logger = structlog.get_logger()

class RAGService:
    def __init__(self):
        self.vector_db = get_vector_db_service()
        self.llm = get_llm_service()
        self.settings = get_settings()

    async def query(self, query: str, project_id: str = "default", model: str = None) -> Dict[str, Any]:
        """
        Answer a query using RAG.
        """
        logger.info("Processing RAG query", query=query, project_id=project_id)
        
        # 1. Retrieve relevant documents
        results = await self.vector_db.search(query, project_id=project_id, n_results=15)
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        
        # 2. Construct context
        context = "\n\n".join(documents)
        
        # 3. Construct prompt
        system_prompt = """You are a helpful assistant. Use the following context to answer the user's question.
If the answer is not in the context, say you don't know.
Context:
{context}
"""
        formatted_system_prompt = system_prompt.format(context=context)
        
        messages = [
            {"role": "system", "content": formatted_system_prompt},
            {"role": "user", "content": query}
        ]
        
        # 4. Call LLM
        selected_model = model or self.settings.DOC_BRAIN_MODEL
        response = await self.llm.chat(model=selected_model, messages=messages)
        
        return {
            "answer": response['message']['content'],
            "sources": metadatas
        }

_rag_service: RAGService | None = None

def get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
