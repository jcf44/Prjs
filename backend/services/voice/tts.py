import sherpa_onnx
import numpy as np
import structlog
from backend.config import get_settings
import os
import urllib.request
import tarfile

logger = structlog.get_logger()

class TTSService:
    def __init__(self):
        self.settings = get_settings()
        self.model_dir = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_tts")
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Download VITS model
        # Using "vits-piper-en_US-lessac-medium" (compatible with Piper voices but run via Sherpa)
        self._ensure_model()
        
        model_path = os.path.join(self.model_dir, "vits-piper-en_US-lessac-medium")
        vits_model = os.path.join(model_path, "en_US-lessac-medium.onnx")
        tokens = os.path.join(model_path, "tokens.txt")
        data_dir = os.path.join(model_path, "espeak-ng-data")
        
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=vits_model,
                    lexicon="",
                    tokens=tokens,
                    data_dir=data_dir, # espeak-ng data
                ),
                provider="cpu",
                num_threads=1,
                debug=False,
            )
        )
        
        try:
            self.tts = sherpa_onnx.OfflineTts(config=config)
            logger.info("Sherpa-ONNX TTS initialized")
        except Exception as e:
            logger.error("Failed to initialize TTS", error=str(e))
            raise

    def _ensure_model(self):
        """Download TTS model if missing"""
        url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-lessac-medium.tar.bz2"
        tar_path = os.path.join(self.model_dir, "model.tar.bz2")
        extract_path = os.path.join(self.model_dir, "vits-piper-en_US-lessac-medium")
        
        if not os.path.exists(extract_path):
            logger.info("Downloading TTS model...", url=url)
            urllib.request.urlretrieve(url, tar_path)
            logger.info("Extracting TTS model...")
            with tarfile.open(tar_path, "r:bz2") as tar:
                tar.extractall(self.model_dir)
            os.remove(tar_path)
            logger.info("TTS model ready")

    def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio (WAV bytes).
        """
        if not text:
            return b""
            
        audio = self.tts.generate(text, sid=0, speed=1.0)
        
        # Convert audio.samples (float32 list) to WAV bytes
        import wave
        import io
        
        samples = np.array(audio.samples, dtype=np.float32)
        # Convert to int16
        samples_int16 = (samples * 32767).astype(np.int16)
        
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(audio.sample_rate)
                wav_file.writeframes(samples_int16.tobytes())
            return wav_buffer.getvalue()

_tts_service: TTSService | None = None

def get_tts_service():
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
