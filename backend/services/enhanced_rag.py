"""
Enhanced RAG Service with Traceability Matrix Integration

This service combines:
1. Semantic search (existing RAG via ChromaDB)
2. Deterministic lookup (traceability matrix)

When a query mentions a requirement ID or related keywords,
it pulls the exact documents from the trace links first,
then supplements with semantic search.
"""

import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from backend.services.vector_db import get_vector_db_service, VectorDBService
from backend.services.llm import get_llm_service, LLMService
from backend.services.traceability import get_traceability_service, TraceabilityService
from backend.domain.traceability import TraceType, Requirement, TraceLink
from backend.config import get_settings
import structlog

logger = structlog.get_logger()


@dataclass
class RetrievedContext:
    """A piece of context retrieved for the LLM"""
    content: str
    source: str
    retrieval_method: str  # 'traceability' or 'semantic'
    trace_type: Optional[str] = None  # If from traceability
    requirement_id: Optional[str] = None
    relevance_score: Optional[float] = None


class EnhancedRAGService:
    """
    RAG service that combines traceability matrix lookup with semantic search.
    """
    
    # Regex pattern to detect requirement IDs (e.g., REQ-001, FR-3.1.2, etc.)
    REQUIREMENT_ID_PATTERN = re.compile(
        r'\b(REQ|FR|NFR|UC|SR|BR|TR)[-_]?(\d+(?:\.\d+)*)\b',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.vector_db = get_vector_db_service()
        self.llm = get_llm_service()
        self.traceability = get_traceability_service()
        self.settings = get_settings()
    
    async def query(
        self,
        query: str,
        project_id: str = "default",
        model: str = None,
        use_traceability: bool = True,
        use_semantic: bool = True,
        trace_types: Optional[List[TraceType]] = None,
        max_trace_docs: int = 5,
        max_semantic_docs: int = 10
    ) -> Dict[str, Any]:
        """
        Enhanced RAG query that combines traceability and semantic search.
        
        Args:
            query: User's question
            project_id: Project to search within
            model: LLM model to use
            use_traceability: Whether to use traceability matrix lookup
            use_semantic: Whether to use semantic vector search
            trace_types: Filter trace links by type (e.g., only design docs)
            max_trace_docs: Maximum documents to retrieve from traceability
            max_semantic_docs: Maximum chunks from semantic search
        
        Returns:
            Answer with sources and retrieval metadata
        """
        logger.info(
            "Processing enhanced RAG query",
            query=query,
            project_id=project_id,
            use_traceability=use_traceability,
            use_semantic=use_semantic
        )
        
        contexts: List[RetrievedContext] = []
        trace_metadata = {
            "requirement_ids_detected": [],
            "trace_documents_found": 0,
            "semantic_chunks_found": 0
        }
        
        # =================================================================
        # Step 1: Traceability Matrix Lookup
        # =================================================================
        if use_traceability:
            trace_contexts, detected_reqs = await self._retrieve_from_traceability(
                query=query,
                project_id=project_id,
                trace_types=trace_types,
                max_docs=max_trace_docs
            )
            contexts.extend(trace_contexts)
            trace_metadata["requirement_ids_detected"] = detected_reqs
            trace_metadata["trace_documents_found"] = len(trace_contexts)
        
        # =================================================================
        # Step 2: Semantic Search (fills gaps)
        # =================================================================
        if use_semantic:
            # Get paths already covered by traceability to avoid duplication
            covered_paths = {ctx.source for ctx in contexts}
            
            semantic_contexts = await self._retrieve_from_semantic(
                query=query,
                project_id=project_id,
                exclude_paths=covered_paths,
                max_chunks=max_semantic_docs
            )
            contexts.extend(semantic_contexts)
            trace_metadata["semantic_chunks_found"] = len(semantic_contexts)
        
        # =================================================================
        # Step 3: Build Context and Call LLM
        # =================================================================
        if not contexts:
            logger.warning("No context found for query", query=query)
            return {
                "answer": "I couldn't find any relevant documents for this query.",
                "sources": [],
                "retrieval_metadata": trace_metadata
            }
        
        # Build the context string with source attribution
        context_parts = []
        for i, ctx in enumerate(contexts, 1):
            source_label = f"[Source {i}: {ctx.source}]"
            if ctx.requirement_id:
                source_label = f"[Source {i}: {ctx.source} (linked to {ctx.requirement_id})]"
            context_parts.append(f"{source_label}\n{ctx.content}")
        
        full_context = "\n\n---\n\n".join(context_parts)
        
        # Build the prompt
        system_prompt = self._build_system_prompt(full_context, trace_metadata)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        # Call LLM
        selected_model = model or self.settings.DOC_BRAIN_MODEL
        response = await self.llm.chat(model=selected_model, messages=messages)
        
        # Build sources list
        sources = [
            {
                "source": ctx.source,
                "retrieval_method": ctx.retrieval_method,
                "trace_type": ctx.trace_type,
                "requirement_id": ctx.requirement_id,
                "relevance_score": ctx.relevance_score
            }
            for ctx in contexts
        ]
        
        return {
            "answer": response['message']['content'],
            "sources": sources,
            "retrieval_metadata": trace_metadata
        }
    
    async def _retrieve_from_traceability(
        self,
        query: str,
        project_id: str,
        trace_types: Optional[List[TraceType]],
        max_docs: int
    ) -> tuple[List[RetrievedContext], List[str]]:
        """
        Retrieve documents from traceability matrix based on requirement IDs in query.
        """
        contexts = []
        detected_req_ids = []
        
        # Detect requirement IDs in the query
        matches = self.REQUIREMENT_ID_PATTERN.findall(query)
        for prefix, number in matches:
            req_id = f"{prefix.upper()}-{number}"
            detected_req_ids.append(req_id)
        
        # Also try searching by keywords if no explicit IDs found
        if not detected_req_ids:
            # Search requirements by query text
            matching_reqs = await self.traceability.search_requirements(
                project_id=project_id,
                query=query
            )
            detected_req_ids = [req.requirement_id for req in matching_reqs[:3]]
        
        # Get trace links for detected requirements
        for req_id in detected_req_ids[:max_docs]:
            links = await self.traceability.get_documents_for_requirement(
                project_id=project_id,
                requirement_id=req_id,
                trace_types=trace_types
            )
            
            for link in links:
                content = await self._load_document_content(link.document_path)
                if content:
                    contexts.append(RetrievedContext(
                        content=content,
                        source=link.document_path,
                        retrieval_method='traceability',
                        trace_type=link.trace_type.value,
                        requirement_id=req_id
                    ))
        
        logger.info(
            "Traceability retrieval complete",
            detected_req_ids=detected_req_ids,
            documents_found=len(contexts)
        )
        
        return contexts, detected_req_ids
    
    async def _retrieve_from_semantic(
        self,
        query: str,
        project_id: str,
        exclude_paths: set,
        max_chunks: int
    ) -> List[RetrievedContext]:
        """
        Retrieve chunks via semantic search, excluding already-covered paths.
        """
        results = await self.vector_db.search(
            query=query,
            project_id=project_id,
            n_results=max_chunks + len(exclude_paths)  # Get extra to account for filtering
        )
        
        contexts = []
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results.get('distances', [[]])[0]
        
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            source_path = meta.get('source', meta.get('filename', 'unknown'))
            
            # Skip if already covered by traceability
            if source_path in exclude_paths:
                continue
            
            # Calculate relevance score from distance
            distance = distances[i] if i < len(distances) else None
            relevance = 1.0 - distance if distance is not None else None
            
            contexts.append(RetrievedContext(
                content=doc,
                source=source_path,
                retrieval_method='semantic',
                relevance_score=relevance
            ))
            
            if len(contexts) >= max_chunks:
                break
        
        return contexts
    
    async def _load_document_content(self, document_path: str) -> Optional[str]:
        """
        Load the full content of a document for traceability context.
        
        For now, this tries to read the file directly.
        Could be enhanced to:
        - Pull from vector DB if already indexed
        - Summarize long documents
        - Extract specific sections
        """
        try:
            # Normalize path
            if not os.path.isabs(document_path):
                # Try relative to corpus directory
                corpus_base = self.settings.CORPUS_DIRECTORY
                document_path = os.path.join(corpus_base, document_path)
            
            if not os.path.exists(document_path):
                logger.warning("Document not found", path=document_path)
                return None
            
            ext = os.path.splitext(document_path)[1].lower()
            
            if ext in ['.txt', '.md']:
                with open(document_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif ext == '.docx':
                import docx
                doc = docx.Document(document_path)
                content = "\n".join([para.text for para in doc.paragraphs])
            elif ext == '.pdf':
                import pymupdf
                content = ""
                with pymupdf.open(document_path) as doc:
                    for page in doc:
                        content += page.get_text()
            else:
                logger.warning("Unsupported file type for direct load", ext=ext)
                return None
            
            # Truncate very long documents
            max_chars = 10000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[... document truncated ...]"
            
            return content
            
        except Exception as e:
            logger.error("Failed to load document", path=document_path, error=str(e))
            return None
    
    def _build_system_prompt(self, context: str, trace_metadata: Dict) -> str:
        """Build the system prompt with context and retrieval info."""
        
        trace_info = ""
        if trace_metadata["requirement_ids_detected"]:
            req_ids = ", ".join(trace_metadata["requirement_ids_detected"])
            trace_info = f"""
Note: The query references the following requirement(s): {req_ids}
Documents have been retrieved based on the traceability matrix for these requirements.
"""
        
        return f"""You are a helpful assistant with access to project documentation.
Use the following context to answer the user's question accurately.
{trace_info}
If the answer is not fully covered in the context, acknowledge what you found
and indicate what additional information might be needed.

When citing information, reference the source document.

Context:
{context}
"""


# =============================================================================
# Query by Requirement endpoint (direct requirement lookup)
# =============================================================================

    async def query_requirement(
        self,
        requirement_id: str,
        project_id: str,
        question: Optional[str] = None,
        trace_types: Optional[List[TraceType]] = None,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Query specifically about a requirement.
        
        If no question is provided, returns a summary of the requirement
        and its traced documents.
        """
        # Find the requirement
        req = await self.traceability.find_requirement(project_id, requirement_id)
        if not req:
            return {
                "answer": f"Requirement {requirement_id} not found in project.",
                "sources": [],
                "requirement": None
            }
        
        # Get trace links
        links = req.trace_links
        if trace_types:
            links = [l for l in links if l.trace_type in trace_types]
        
        # If no specific question, provide a summary
        if not question:
            return await self._summarize_requirement(req, links)
        
        # Otherwise, answer the question using traced documents
        contexts = []
        for link in links:
            content = await self._load_document_content(link.document_path)
            if content:
                contexts.append(RetrievedContext(
                    content=content,
                    source=link.document_path,
                    retrieval_method='traceability',
                    trace_type=link.trace_type.value,
                    requirement_id=requirement_id
                ))
        
        # Build context
        context_parts = []
        for i, ctx in enumerate(contexts, 1):
            context_parts.append(
                f"[{ctx.trace_type.upper()}: {ctx.source}]\n{ctx.content}"
            )
        
        full_context = "\n\n---\n\n".join(context_parts)
        
        system_prompt = f"""You are a helpful assistant answering questions about requirement {requirement_id}.

Requirement: {req.title}
Description: {req.description}
Status: {req.status.value}
Priority: {req.priority.value}

Use the following traced documentation to answer the question:

{full_context}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        selected_model = model or self.settings.DOC_BRAIN_MODEL
        response = await self.llm.chat(model=selected_model, messages=messages)
        
        return {
            "answer": response['message']['content'],
            "sources": [
                {
                    "source": ctx.source,
                    "trace_type": ctx.trace_type
                }
                for ctx in contexts
            ],
            "requirement": {
                "id": req.requirement_id,
                "title": req.title,
                "status": req.status.value,
                "priority": req.priority.value
            }
        }
    
    async def _summarize_requirement(
        self, 
        req: Requirement, 
        links: List[TraceLink]
    ) -> Dict[str, Any]:
        """Generate a summary of a requirement and its traces."""
        coverage = req.coverage_summary()
        
        summary = f"""**Requirement {req.requirement_id}: {req.title}**

**Description:** {req.description}

**Status:** {req.status.value}
**Priority:** {req.priority.value}
**Category:** {req.category or 'Uncategorized'}

**Traceability Coverage:**
- Source documents: {coverage['source']}
- Design documents: {coverage['design']}
- Implementation docs: {coverage['implementation']}
- Verification docs: {coverage['verification']}
- Reference docs: {coverage['reference']}

**Traced Documents:**
"""
        for link in links:
            summary += f"- [{link.trace_type.value.upper()}] {link.document_path}"
            if link.section:
                summary += f" (Section: {link.section})"
            summary += "\n"
        
        return {
            "answer": summary,
            "sources": [
                {"source": link.document_path, "trace_type": link.trace_type.value}
                for link in links
            ],
            "requirement": {
                "id": req.requirement_id,
                "title": req.title,
                "description": req.description,
                "status": req.status.value,
                "priority": req.priority.value,
                "category": req.category,
                "coverage": coverage
            }
        }


# Singleton
_enhanced_rag_service: EnhancedRAGService | None = None

def get_enhanced_rag_service() -> EnhancedRAGService:
    global _enhanced_rag_service
    if _enhanced_rag_service is None:
        _enhanced_rag_service = EnhancedRAGService()
    return _enhanced_rag_service
