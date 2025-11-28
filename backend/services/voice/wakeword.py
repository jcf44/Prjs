import sherpa_onnx
import numpy as np
import structlog
from backend.config import get_settings
import os
import urllib.request
import tarfile

logger = structlog.get_logger()


class WakeWordService:
    def __init__(self):
        self.settings = get_settings()
        self.model_dir = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Ensure model is downloaded
        self._ensure_model()
        
        # Model paths
        model_path = os.path.join(self.model_dir, "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01")
        encoder = os.path.join(model_path, "encoder-epoch-12-avg-2-chunk-16-left-64.onnx")
        decoder = os.path.join(model_path, "decoder-epoch-12-avg-2-chunk-16-left-64.onnx")
        joiner = os.path.join(model_path, "joiner-epoch-12-avg-2-chunk-16-left-64.onnx")
        tokens = os.path.join(model_path, "tokens.txt")
        
        # Keywords file - prefer custom "Hey Wendy" if it exists
        custom_keywords = os.path.join(model_path, "keywords_wendy.txt")
        default_keywords = os.path.join(model_path, "keywords.txt")
        
        if os.path.exists(custom_keywords):
            self.keywords_file = custom_keywords
            logger.info("Using custom 'Hey Wendy' keywords")
        else:
            self.keywords_file = default_keywords
            logger.warning(
                "Custom keywords not found, using default. "
                "Run 'python scripts/create_wakeword.py' to create 'Hey Wendy' keywords."
            )
        
        try:
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
            logger.info("Sherpa-ONNX KWS initialized", keywords_file=self.keywords_file)
        except Exception as e:
            logger.error("Failed to initialize KWS", error=str(e))
            raise

    def _ensure_model(self):
        """Download KWS model if missing"""
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
        Process audio chunk (float32 or int16, 16kHz).
        Returns True if keyword detected.
        """
        # Ensure float32
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
        
        # Flatten if needed (sounddevice returns shape (N, 1) for mono)
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.flatten()
        
        self.stream.accept_waveform(16000, audio_chunk)
        
        while self.spotter.is_ready(self.stream):
            self.spotter.decode(self.stream)
            result = self.spotter.get_result(self.stream)
            if result.keyword:
                logger.info("Wake word detected!", keyword=result.keyword)
                return True
        
        return False

    def reset(self):
        """Reset the stream for a fresh detection cycle"""
        self.stream = self.spotter.create_stream()


_wakeword_service: WakeWordService | None = None


def get_wakeword_service():
    global _wakeword_service
    if _wakeword_service is None:
        _wakeword_service = WakeWordService()
    return _wakeword_service
