from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
import shutil
import os
import tempfile
from backend.services.ingestion import get_ingestion_service, IngestionService
import structlog

router = APIRouter(prefix="/v1/documents", tags=["documents"])
logger = structlog.get_logger()

@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    user_profile: str = Form("default"),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        try:
            source_id = await ingestion_service.process_file(
                file_path=tmp_path,
                user_profile=user_profile,
                metadata={"original_filename": file.filename}
            )
            return {"status": "success", "source_id": source_id, "filename": file.filename}
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        logger.error("Document ingestion failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from backend.services.rag import get_rag_service, RAGService

class RAGQueryRequest(BaseModel):
    query: str
    limit: int = 5
    model: Optional[str] = None

@router.post("/query")
async def rag_query(
    request: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        results = await rag_service.query(request.query, model=request.model)
        return results
    except Exception as e:
        logger.error("RAG query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

from backend.services.vector_db import get_vector_db_service, VectorDBService

@router.get("/")
async def list_documents(
    limit: int = 20,
    vector_db: VectorDBService = Depends(get_vector_db_service)
):
    """List ingested documents"""
    return await vector_db.list_documents(limit=limit)

@router.delete("/{source_id}")
async def delete_document(
    source_id: str,
    vector_db: VectorDBService = Depends(get_vector_db_service)
):
    """Delete a document by source_id"""
    await vector_db.delete_document(source_id)
    return {"status": "deleted", "source_id": source_id}
