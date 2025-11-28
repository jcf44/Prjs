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
