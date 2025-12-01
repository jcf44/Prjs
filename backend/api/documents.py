from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
import shutil
import os

from backend.services.ingestion import get_ingestion_service, IngestionService
from backend.services.converter import get_converter_service, DocumentConverter
import structlog

router = APIRouter(prefix="/v1/documents", tags=["documents"])
logger = structlog.get_logger()

@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    user_profile: str = Form("default"),
    project_id: str = Form("default"),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    try:
        # Ensure persistence directory exists
        documents_dir = os.path.join(os.path.expanduser("~"), ".wendy", "documents")
        os.makedirs(documents_dir, exist_ok=True)
        
        # Create a unique filename to avoid collisions
        import uuid
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        persistent_path = os.path.join(documents_dir, unique_filename)
        
        # Save uploaded file to persistent location
        with open(persistent_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        try:
            source_id = await ingestion_service.process_file(
                file_path=persistent_path,
                user_profile=user_profile,
                project_id=project_id,
                metadata={"original_filename": file.filename}
            )
            return {"status": "success", "source_id": source_id, "filename": file.filename, "project_id": project_id}
        except Exception as e:
            # Cleanup if ingestion fails
            if os.path.exists(persistent_path):
                os.remove(persistent_path)
            raise e
                
    except Exception as e:
        logger.error("Document ingestion failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from backend.services.rag import get_rag_service, RAGService

class RAGQueryRequest(BaseModel):
    query: str
    limit: int = 5
    model: Optional[str] = None
    project_id: str = "default"

@router.post("/query")
async def rag_query(
    request: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        results = await rag_service.query(request.query, project_id=request.project_id, model=request.model)
        return results
    except Exception as e:
        logger.error("RAG query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

from backend.services.vector_db import get_vector_db_service, VectorDBService

@router.get("/")
async def list_documents(
    limit: int = 20,
    project_id: str = "default",
    vector_db: VectorDBService = Depends(get_vector_db_service)
):
    """List ingested documents"""
    return await vector_db.list_documents(project_id=project_id, limit=limit)

@router.delete("/{source_id}")
async def delete_document(
    source_id: str,
    vector_db: VectorDBService = Depends(get_vector_db_service)
):
    """Delete a document by source_id"""
    # Try to get the file path first to clean up physical file
    file_path = await vector_db.get_document_path(source_id)
    
    # Delete from Vector DB
    await vector_db.delete_document(source_id)
    
    # Delete physical file if it exists and is in our managed directory
    if file_path and os.path.exists(file_path):
        # basic safety check to only delete files in .wendy
        if ".wendy" in file_path: 
            try:
                os.remove(file_path)
                logger.info("Deleted physical file", path=file_path)
            except Exception as e:
                logger.error("Failed to delete physical file", path=file_path, error=str(e))
                
    return {"status": "deleted", "source_id": source_id}

@router.post("/{source_id}/convert")
async def convert_document(
    source_id: str,
    project_id: str = "default",
    vector_db: VectorDBService = Depends(get_vector_db_service),
    converter: DocumentConverter = Depends(get_converter_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """Convert a PDF document to Markdown"""
    # 1. Get original file path
    file_path = await vector_db.get_document_path(source_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original document file not found")
        
    if not file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents can be converted")

    try:
        # 2. Define output paths
        # We'll save the markdown in the same persistent directory as the documents
        documents_dir = os.path.dirname(file_path)
        
        # Image output directory: frontend/public/doc_images
        # Assuming backend is at c:\Work\Projects\Wendy\Prjs\backend
        # We need to go up one level to Prjs, then into frontend/public
        # This path calculation relies on the project structure
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        image_output_dir = os.path.join(project_root, "frontend", "public", "doc_images")
        
        # Public URL path for images (relative to frontend root)
        public_image_path = "/doc_images"
        
        # Retrieve original metadata to get the user-facing filename
        # FIX: Use where={"source_id": ...} because source_id is metadata, not the chunk ID
        original_doc = vector_db.collection.get(where={"source_id": source_id}, include=["metadatas"])
        logger.info("Original Doc Metadata", metadata=original_doc)
        
        original_user_filename = None
        
        # Try to get filename from metadata
        if original_doc and original_doc["metadatas"]:
            meta_list = original_doc["metadatas"]
            if meta_list and len(meta_list) > 0:
                # Check for 'original_filename' first, then 'filename'
                original_user_filename = meta_list[0].get("original_filename")
                if not original_user_filename:
                    original_user_filename = meta_list[0].get("filename")
                    
        # Fallback: Use the basename of the source file path if metadata failed
        if not original_user_filename:
            original_user_filename = os.path.basename(file_path)
            
        # Final fallback just in case
        if not original_user_filename:
            original_user_filename = "document.pdf"
        
        logger.info("Using filename for conversion", original=original_user_filename)
            
        # Create new filename: Original Name.md
        new_filename = os.path.splitext(original_user_filename)[0] + ".md"
        
        # 3. Perform conversion
        md_path = converter.convert_pdf_to_markdown(
            pdf_path=file_path,
            output_dir=documents_dir,
            image_output_dir=image_output_dir,
            public_image_path=public_image_path,
            custom_filename=new_filename
        )
        
        # 4. Ingest the new Markdown file
        new_source_id = await ingestion_service.process_file(
            file_path=md_path,
            user_profile="default", # Should ideally get from request/context
            project_id=project_id,
            metadata={"original_filename": new_filename, "converted_from": source_id}
        )
        
        return {
            "status": "success", 
            "source_id": new_source_id, 
            "filename": new_filename,
            "project_id": project_id
        }
        
    except Exception as e:
        logger.error("Conversion failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{source_id}/download")
async def download_document(
    source_id: str,
    vector_db: VectorDBService = Depends(get_vector_db_service)
):
    """Download a document"""
    file_path = await vector_db.get_document_path(source_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found")
        
    filename = os.path.basename(file_path)
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
