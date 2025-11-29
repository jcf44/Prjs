from faster_whisper import WhisperModel
import structlog
from backend.config import get_settings
import os
import numpy as np

logger = structlog.get_logger()

class STTService:
    def __init__(self):
        self.settings = get_settings()
        model_size = self.settings.STT_MODEL_SIZE
        logger.info("Loading STT Model", size=model_size)
        
        # Run on CPU with INT8 for compatibility, or CUDA if available
        # faster-whisper handles this reasonably well.
        device = "cpu" # Default to CPU for safety on local windows dev without assuming CUDA
        compute_type = "int8"
        
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio data (numpy array float32 or int16).
        """
        try:
            # Ensure float32
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            
            # Ensure 1D array
            if audio_data.ndim > 1:
                audio_data = audio_data.flatten()
            
            logger.info("Starting Whisper transcription", samples=len(audio_data))
            
            # Explicitly set language and VAD to help
            segments, info = self.model.transcribe(
                audio_data, 
                beam_size=5, 
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            text = ""
            count = 0
            for segment in segments:
                count += 1
                logger.debug("Segment found", text=segment.text)
                text += segment.text
                
            logger.info("Transcription finished", segments_count=count, text_len=len(text))
            return text.strip()
        except Exception as e:
            logger.error("Transcription failed", error=str(e))
            return ""

_stt_service: STTService | None = None

def get_stt_service():
    global _stt_service
    if _stt_service is None:
        _stt_service = STTService()
    return _stt_service
