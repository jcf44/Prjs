import asyncio
import structlog
import numpy as np
from backend.services.voice.audio import get_audio_service, AudioService
from backend.services.voice.wakeword import get_wakeword_service, WakeWordService
from backend.services.voice.stt import get_stt_service, STTService
from backend.services.voice.tts import get_tts_service, TTSService
from backend.services.llm import get_llm_service, LLMService
from backend.config import get_settings

logger = structlog.get_logger()


class VoiceOrchestrator:
    def __init__(self):
        self.settings = get_settings()
        self.audio_service = get_audio_service()
        self.wakeword_service = get_wakeword_service()
        self.stt_service = get_stt_service()
        self.tts_service = get_tts_service()
        self.llm_service = get_llm_service()
        
        self.is_running = False
        self.listening_for_command = False
        self.audio_buffer = []
        self.silence_count = 0
        self.max_silence_chunks = 20  # ~1.6 seconds of silence to end recording
        self.min_audio_chunks = 10    # Minimum ~0.8 seconds before allowing silence detection

    async def start(self):
        """Start the voice loop"""
        self.is_running = True
        self.audio_service.start_listening(self._on_audio_chunk)
        logger.info("Voice Orchestrator started - say 'Hey Wendy' to activate")
        
        while self.is_running:
            await asyncio.sleep(0.1)

    def stop(self):
        """Stop the voice loop"""
        self.is_running = False
        self.audio_service.stop_listening()
        logger.info("Voice Orchestrator stopped")

    def _on_audio_chunk(self, chunk: np.ndarray):
        """Callback for audio chunks (called from audio thread)"""
        if not self.is_running:
            return

        if not self.listening_for_command:
            # Phase 1: Listen for Wake Word
            if self.wakeword_service.detect(chunk):
                logger.info("Wake word detected! Listening for command...")
                self.listening_for_command = True
                self.audio_buffer = []
                self.silence_count = 0
                # TODO: Play confirmation sound
                self._play_listening_sound()
        else:
            # Phase 2: Record command until silence or max duration
            self.audio_buffer.append(chunk.copy())
            
            # Simple energy-based silence detection
            if self._is_silence(chunk):
                self.silence_count += 1
            else:
                self.silence_count = 0
            
            # Check for end conditions
            buffer_duration = len(self.audio_buffer) * 0.08  # 80ms per chunk
            
            # End if: enough silence after minimum recording, or max duration reached
            should_process = False
            if len(self.audio_buffer) >= self.min_audio_chunks and self.silence_count >= self.max_silence_chunks:
                logger.info("Silence detected, processing command...")
                should_process = True
            elif buffer_duration >= 10.0:  # Max 10 seconds
                logger.info("Max duration reached, processing command...")
                should_process = True
            
            if should_process:
                self.listening_for_command = False
                audio_data = np.concatenate(self.audio_buffer)
                self.audio_buffer = []
                
                # Process in background (schedule on event loop)
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._process_command(audio_data))
                except RuntimeError:
                    # No event loop running, create one
                    asyncio.run(self._process_command(audio_data))

    def _is_silence(self, chunk: np.ndarray, threshold: float = 500) -> bool:
        """Check if audio chunk is silence based on energy"""
        # Convert to float for calculation
        if chunk.dtype == np.int16:
            audio = chunk.astype(np.float32)
        else:
            audio = chunk * 32768.0  # Scale float32 to int16 range
        
        energy = np.sqrt(np.mean(audio ** 2))
        return energy < threshold

    def _play_listening_sound(self):
        """Play a short sound to indicate Wendy is listening"""
        # Generate a simple beep (440Hz for 200ms)
        try:
            duration = 0.2
            sample_rate = 22050
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            tone = np.sin(2 * np.pi * 440 * t) * 0.3
            tone_int16 = (tone * 32767).astype(np.int16)
            
            import wave
            import io
            
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(tone_int16.tobytes())
                audio_bytes = wav_buffer.getvalue()
            
            self.audio_service.play_audio(audio_bytes)
        except Exception as e:
            logger.debug("Could not play listening sound", error=str(e))

    async def _process_command(self, audio_data: np.ndarray):
        """Process the recorded voice command"""
        try:
            # Step 1: Speech-to-Text
            logger.info("Transcribing audio...")
            text = self.stt_service.transcribe(audio_data)
            logger.info("Transcribed", text=text)
            
            if not text or not text.strip():
                logger.info("No speech detected")
                return

            # Step 2: LLM Processing
            logger.info("Getting response from LLM...")
            response = await self.llm_service.chat(
                model=self.settings.FAST_BRAIN_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are Wendy, a helpful voice assistant. Keep responses concise and conversational since they will be spoken aloud."
                    },
                    {"role": "user", "content": text}
                ],
                stream=False
            )
            
            response_text = response['message']['content']
            logger.info("LLM response", response=response_text[:100] + "..." if len(response_text) > 100 else response_text)

            # Step 3: Text-to-Speech
            logger.info("Synthesizing speech...")
            audio_bytes = self.tts_service.synthesize(response_text)
            
            # Step 4: Play response
            logger.info("Playing response...")
            self.audio_service.play_audio(audio_bytes)
            
            logger.info("Voice interaction complete")
            
        except Exception as e:
            logger.error("Error processing voice command", error=str(e))
            # Try to speak an error message
            try:
                error_audio = self.tts_service.synthesize("Sorry, I encountered an error processing your request.")
                self.audio_service.play_audio(error_audio)
            except:
                pass

    def get_status(self) -> dict:
        """Get current status of the voice orchestrator"""
        return {
            "is_running": self.is_running,
            "listening_for_command": self.listening_for_command,
            "buffer_size": len(self.audio_buffer),
            "keywords_file": self.wakeword_service.keywords_file if self.wakeword_service else None
        }


_orchestrator: VoiceOrchestrator | None = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VoiceOrchestrator()
    return _orchestrator
