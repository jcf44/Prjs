# import openwakeword
# from openwakeword.model import Model
import numpy as np
import structlog
from backend.config import get_settings
import os

logger = structlog.get_logger()

class WakeWordService:
    def __init__(self):
        self.settings = get_settings()
        logger.warning("Wake Word Service is running in MOCK mode due to Python 3.12 incompatibility with openwakeword.")
        # self.model = Model(wakeword_models=[self.model_name], inference_framework="onnx")

    def detect(self, audio_chunk: np.ndarray) -> bool:
        """
        Mock detection. Returns False always unless we simulate it.
        """
        # prediction = self.model.predict(audio_chunk)
        return False

_wakeword_service: WakeWordService | None = None

def get_wakeword_service():
    global _wakeword_service
    if _wakeword_service is None:
        _wakeword_service = WakeWordService()
    return _wakeword_service
