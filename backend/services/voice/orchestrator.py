import asyncio
import structlog
import numpy as np
from backend.services.voice.audio import get_audio_service, AudioService
from backend.services.voice.wakeword import get_wakeword_service, WakeWordService
from backend.services.voice.stt import get_stt_service, STTService
from backend.services.voice.tts import get_tts_service, TTSService
from backend.services.llm import get_llm_service
from backend.api.chat import SimpleChatRequest

logger = structlog.get_logger()

class VoiceOrchestrator:
    def __init__(self):
        self.audio_service = get_audio_service()
        self.wakeword_service = get_wakeword_service()
        self.stt_service = get_stt_service()
        self.tts_service = get_tts_service()
        self.llm_service = get_llm_service()
        
        self.is_running = False
        self.listening_for_command = False
        self.audio_buffer = []

    async def start(self):
        """Start the voice loop"""
        self.is_running = True
        self.audio_service.start_listening(self._on_audio_chunk)
        logger.info("Voice Orchestrator started")
        
        while self.is_running:
            await asyncio.sleep(0.1)

    def stop(self):
        self.is_running = False
        self.audio_service.stop_listening()

    def _on_audio_chunk(self, chunk: np.ndarray):
        """Callback for audio chunks"""
        if not self.is_running:
            return

        if not self.listening_for_command:
            # 1. Listen for Wake Word
            if self.wakeword_service.detect(chunk):
                logger.info("Wake word detected! Listening for command...")
                self.listening_for_command = True
                self.audio_buffer = [] # Clear buffer
                # Play a "ding" sound here?
        else:
            # 2. Listen for Command (VAD / Silence Detection)
            # For simplicity, let's just record for fixed 5 seconds or until silence
            self.audio_buffer.append(chunk)
            
            # Simple silence detection or fixed length
            if len(self.audio_buffer) * 0.08 > 5.0: # 5 seconds
                logger.info("Processing command...")
                self.listening_for_command = False
                
                # Process in background
                asyncio.create_task(self._process_command(np.concatenate(self.audio_buffer)))

    async def _process_command(self, audio_data: np.ndarray):
        try:
            # 3. STT
            text = self.stt_service.transcribe(audio_data)
            logger.info("Transcribed text", text=text)
            
            if not text.strip():
                return

            # 4. LLM
            # We need to call the chat flow. For now, direct LLM call.
            # Ideally we use the Chat API logic (RAG, Memory, etc.)
            # Let's mock a simple response or call LLM service directly.
            response_stream = self.llm_service.chat(
                model="qwen2.5:14b", # Use fast brain
                messages=[{"role": "user", "content": text}]
            )
            
            full_response = ""
            async for chunk in response_stream:
                if "message" in chunk:
                    full_response += chunk["message"]["content"]
            
            logger.info("LLM Response", response=full_response)

            # 5. TTS
            audio_bytes = self.tts_service.synthesize(full_response)
            
            # 6. Play Audio
            self.audio_service.play_audio(audio_bytes)
            
        except Exception as e:
            logger.error("Error processing command", error=str(e))

_orchestrator: VoiceOrchestrator | None = None

def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VoiceOrchestrator()
    return _orchestrator
