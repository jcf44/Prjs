from backend.services.llm import get_llm_service, LLMService
import structlog

from backend.config import get_settings

logger = structlog.get_logger()

class VisionService:
    def __init__(self):
        settings = get_settings()
        self.model = settings.VISION_MODEL
        self.llm_service = get_llm_service()

    async def analyze_image(self, image_data: str, prompt: str = "Describe this image") -> str:
        """
        Analyze an image using the vision model.
        image_data: Base64 encoded image or path to image file.
        """
        logger.info("Analyzing image", model=self.model)
        
        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": [image_data]
            }
        ]
        
        try:
            response = await self.llm_service.chat(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response['message']['content']
        except Exception as e:
            logger.error("Vision analysis failed", error=str(e))
            raise

_vision_service: VisionService | None = None

def get_vision_service():
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
