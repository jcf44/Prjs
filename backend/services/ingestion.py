import os
from typing import List, Dict, Any
import pymupdf
import docx
from backend.services.vector_db import get_vector_db_service, VectorDBService
import structlog
import uuid

logger = structlog.get_logger()

class IngestionService:
    def __init__(self):
        self.vector_db = get_vector_db_service()
        self.chunk_size = 1000
        self.chunk_overlap = 200

    async def process_file(self, file_path: str, user_profile: str, metadata: Dict[str, Any] = None):
        """Process a file and ingest it into the vector DB"""
        logger.info("Processing file", file_path=file_path)
        
        try:
            text = self._extract_text(file_path)
            chunks = self._chunk_text(text)
            
            # Prepare data for vector DB
            ids = [str(uuid.uuid4()) for _ in chunks]
            metadatas = []
            source_id = str(uuid.uuid4()) # Unique ID for the file itself
            
            base_metadata = metadata or {}
            base_metadata.update({
                "source": file_path,
                "filename": os.path.basename(file_path),
                "user_profile": user_profile,
                "source_id": source_id
            })
            
            for i, chunk in enumerate(chunks):
                meta = base_metadata.copy()
                meta["chunk_index"] = i
                metadatas.append(meta)
            
            await self.vector_db.add_documents(chunks, metadatas, ids)
            logger.info("File ingested successfully", chunk_count=len(chunks))
            return source_id
            
        except Exception as e:
            logger.error("Ingestion failed", error=str(e), file_path=file_path)
            raise

    def _extract_text(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".txt" or ext == ".md":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        elif ext == ".pdf":
            text = ""
            with pymupdf.open(file_path) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        elif ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _chunk_text(self, text: str) -> List[str]:
        """Simple recursive character splitter logic"""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + self.chunk_size
            if end >= text_len:
                chunks.append(text[start:])
                break
            
            # Try to find a natural break point (newline, period, space)
            # Look backwards from end
            break_found = False
            for char in ["\n\n", "\n", ". ", " "]:
                pos = text.rfind(char, start, end)
                if pos != -1 and pos > start + self.chunk_size // 2: # Ensure chunk isn't too small
                    end = pos + len(char)
                    break_found = True
                    break
            
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
            
        return chunks

_ingestion_service: IngestionService | None = None

def get_ingestion_service():
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service
