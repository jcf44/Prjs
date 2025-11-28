from ollama import AsyncClient
from backend.config import get_settings
import structlog

logger = structlog.get_logger()

class LLMService:
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncClient(host=self.settings.OLLAMA_BASE_URL)

    async def chat(self, model: str, messages: list, stream: bool = False):
        logger.info("Sending chat request to Ollama", model=model, stream=stream)
        try:
            response = await self.client.chat(model=model, messages=messages, stream=stream)
            return response
        except Exception as e:
            logger.error("Error communicating with Ollama", error=str(e))
            raise

    async def list_models(self) -> list[str]:
        """List available models in Ollama"""
        try:
            response = await self.client.list()
            return [m['name'] for m in response.get('models', [])]
        except Exception as e:
            logger.error("Failed to list models", error=str(e))
            return []

    async def is_model_available(self, model: str) -> bool:
        """Check if a specific model is available"""
        models = await self.list_models()
        return any(model in m for m in models)

_llm_service: LLMService | None = None

def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
