import sherpa_onnx
import numpy as np
import structlog
from backend.config import get_settings
import os
import urllib.request
import tarfile
import zipfile

logger = structlog.get_logger()

class WakeWordService:
    def __init__(self):
        self.settings = get_settings()
        self.model_dir = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Check if model exists, if not download a default one
        # We will use "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01" as a base
        # It supports "hey wendy" if we can define keywords, or we use a pre-trained one.
        # Actually, for "Hey Wendy", we might need to use a model that supports open vocabulary or specific keywords.
        # Let's use "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01" which is a good KWS model.
        # We need to create a keywords file.
        
        self._ensure_model()
        
        # Initialize KWS
        # Note: We need to point to the specific model files
        model_path = os.path.join(self.model_dir, "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01")
        encoder = os.path.join(model_path, "encoder-epoch-12-avg-2-chunk-16-left-64.onnx")
        decoder = os.path.join(model_path, "decoder-epoch-12-avg-2-chunk-16-left-64.onnx")
        joiner = os.path.join(model_path, "joiner-epoch-12-avg-2-chunk-16-left-64.onnx")
        tokens = os.path.join(model_path, "tokens.txt")
        
        # Create keywords string: "keyword_phrase @ threshold"
        # "Hey Wendy" might be split into tokens.
        # For simplicity, let's try "HEY WENDY @ 2.0" (threshold needs tuning)
        keywords = "h e y w e n d y @ 0.5" # Character based? Or BPE?
        # Gigaspeech model uses BPE tokens. We might need to check tokens.txt.
        # Actually, let's use a simpler pre-trained keyword if available, or just "hey wendy" and hope BPE handles it.
        # Sherpa-ONNX KWS usually takes a text string.
        
        # Use the existing keywords.txt from the model for verification
        self.keywords_file = os.path.join(model_path, "keywords.txt")
        # with open(self.keywords_file, "w", encoding="utf-8") as f:
        #     f.write("\u2581A LE X A @ 0.5\n")
            
        try:
            # Pass arguments directly as per installed version signature
            self.spotter = sherpa_onnx.KeywordSpotter(
                tokens=tokens,
                encoder=encoder,
                decoder=decoder,
                joiner=joiner,
                num_threads=1,
                keywords_file=self.keywords_file,
                keywords_score=0.5,
                keywords_threshold=0.25,
                num_trailing_blanks=1,
                provider="cpu"
            )
            self.stream = self.spotter.create_stream()
            logger.info("Sherpa-ONNX KWS initialized")
        except Exception as e:
            logger.error("Failed to initialize KWS", error=str(e))
            raise
            self.stream = self.spotter.create_stream()
            logger.info("Sherpa-ONNX KWS initialized")
        except Exception as e:
            logger.error("Failed to initialize KWS", error=str(e))
            raise

    def _ensure_model(self):
        """Download KWS model if missing"""
        # URL for the model
        url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2"
        tar_path = os.path.join(self.model_dir, "model.tar.bz2")
        extract_path = os.path.join(self.model_dir, "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01")
        
        if not os.path.exists(extract_path):
            logger.info("Downloading KWS model...", url=url)
            urllib.request.urlretrieve(url, tar_path)
            logger.info("Extracting KWS model...")
            with tarfile.open(tar_path, "r:bz2") as tar:
                tar.extractall(self.model_dir)
            os.remove(tar_path)
            logger.info("KWS model ready")

    def detect(self, audio_chunk: np.ndarray) -> bool:
        """
        Process audio chunk (float32, 16kHz).
        Returns True if keyword detected.
        """
        # Ensure float32
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
            
        self.stream.accept_waveform(16000, audio_chunk)
        
        while self.spotter.is_ready(self.stream):
            self.spotter.decode(self.stream)
            result = self.spotter.get_result(self.stream)
            if result.keyword:
                logger.info("Wake word detected", keyword=result.keyword)
                return True
        
        return False

_wakeword_service: WakeWordService | None = None

def get_wakeword_service():
    global _wakeword_service
    if _wakeword_service is None:
        _wakeword_service = WakeWordService()
    return _wakeword_service
