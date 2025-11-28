from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import base64
from backend.services.vision import get_vision_service, VisionService
import structlog

router = APIRouter(prefix="/v1/vision", tags=["vision"])
logger = structlog.get_logger()

class VisionAnalysisRequest(BaseModel):
    image: str # Base64 encoded
    prompt: str = "Describe this image"

@router.post("/analyze")
async def analyze_image(
    request: VisionAnalysisRequest,
    vision_service: VisionService = Depends(get_vision_service)
):
    try:
        description = await vision_service.analyze_image(request.image, request.prompt)
        return {"description": description}
    except Exception as e:
        logger.error("Vision analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/file")
async def analyze_image_file(
    file: UploadFile = File(...),
    prompt: str = Form("Describe this image"),
    vision_service: VisionService = Depends(get_vision_service)
):
    try:
        contents = await file.read()
        image_base64 = base64.b64encode(contents).decode("utf-8")
        
        description = await vision_service.analyze_image(image_base64, prompt)
        return {"description": description}
    except Exception as e:
        logger.error("Vision analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
