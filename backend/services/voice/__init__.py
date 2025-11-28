"""
Wendy Voice Pipeline

Components:
- AudioService: Microphone input and speaker output via sounddevice
- WakeWordService: "Hey Wendy" detection via sherpa-onnx KWS
- STTService: Speech-to-text via faster-whisper
- TTSService: Text-to-speech via sherpa-onnx VITS
- VoiceOrchestrator: Coordinates the full voice interaction flow
"""

from .audio import get_audio_service, AudioService
from .stt import get_stt_service, STTService
from .tts import get_tts_service, TTSService
from .wakeword import get_wakeword_service, WakeWordService
from .orchestrator import get_orchestrator, VoiceOrchestrator

__all__ = [
    # Audio
    "get_audio_service",
    "AudioService",
    # STT
    "get_stt_service", 
    "STTService",
    # TTS
    "get_tts_service",
    "TTSService",
    # Wake Word
    "get_wakeword_service",
    "WakeWordService",
    # Orchestrator
    "get_orchestrator",
    "VoiceOrchestrator",
]
