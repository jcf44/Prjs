import sounddevice as sd
import numpy as np
import structlog
import wave
import io
from typing import Optional, Callable
import threading
import queue

logger = structlog.get_logger()

class AudioService:
    def __init__(self, device_index: Optional[int] = None):
        self.device_index = device_index
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = 'int16'
        self.block_size = 1280 # 80ms chunks for openWakeWord
        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.stream = None

    def start_listening(self, callback: Optional[Callable[[np.ndarray], None]] = None):
        """Start listening to microphone"""
        if self.is_listening:
            return

        logger.info("Starting audio listener", device=self.device_index)
        self.is_listening = True
        
        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning("Audio status", status=status)
            if self.is_listening:
                data = indata.copy()
                self.audio_queue.put(data)
                if callback:
                    callback(data)

        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype=self.dtype,
                blocksize=self.block_size,
                callback=audio_callback
            )
            self.stream.start()
        except Exception as e:
            logger.error("Failed to start audio stream", error=str(e))
            self.is_listening = False
            raise

    def stop_listening(self):
        """Stop listening"""
        logger.info("Stopping audio listener")
        self.is_listening = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def play_audio(self, audio_data: bytes, sample_rate: int = 22050):
        """Play audio data (wav bytes)"""
        try:
            # Parse WAV data if it has header, or assume raw PCM
            # For simplicity, let's assume standard WAV bytes from TTS
            with io.BytesIO(audio_data) as wav_file:
                with wave.open(wav_file, 'rb') as wf:
                    data = wf.readframes(wf.getnframes())
                    # Convert to numpy
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    
                    logger.info("Playing audio", frames=len(audio_np))
                    sd.play(audio_np, samplerate=wf.getframerate(), blocking=True)
                    sd.wait()
        except Exception as e:
            logger.error("Failed to play audio", error=str(e))

    def get_audio_chunk(self) -> Optional[np.ndarray]:
        """Get next chunk from queue (non-blocking)"""
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None

_audio_service: AudioService | None = None

def get_audio_service(device_index: Optional[int] = None):
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService(device_index)
    return _audio_service
