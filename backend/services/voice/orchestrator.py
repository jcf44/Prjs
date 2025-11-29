import asyncio
import structlog
import numpy as np
import threading
import time
from backend.services.voice.audio import get_audio_service, AudioService
from backend.services.voice.wakeword import get_wakeword_service, WakeWordService
from backend.services.voice.stt import get_stt_service, STTService
from backend.services.voice.tts import get_tts_service, TTSService
from backend.services.voice.event_broadcaster import get_broadcaster
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
        self.is_speaking = False
        self.is_processing = False  # New flag for STT/LLM phase
        self.audio_buffer = []
        self.silence_count = 0
        self.max_silence_chunks = 20
        self.min_audio_chunks = 10
        self.last_speech_time = 0

    async def start(self):
        """Start the voice loop"""
        try:
            if self.is_running:
                logger.info("Voice orchestrator already running, skipping start")
                return
                
            logger.info("Starting voice orchestrator...")
            self.is_running = True
            
            # Reset state
            self.listening_for_command = False
            self.is_speaking = False
            self.is_processing = False
            self.audio_buffer = []
            self.silence_count = 0
            
            # Start listening without a direct callback (we'll poll the queue)
            logger.info("Starting audio service...")
            try:
                self.audio_service.start_listening()
                logger.info("Audio service started successfully")
            except Exception as audio_error:
                logger.error("FATAL: Failed to start audio service", error=str(audio_error), exc_info=True)
                self.is_running = False
                raise
            
            # Start the processing loop in a separate thread to avoid blocking the event loop
            logger.info("Starting processing thread...")
            self.processing_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self.processing_thread.start()
            
            # Give thread a moment to start
            await asyncio.sleep(0.1)
            
            if not self.processing_thread.is_alive():
                logger.error("FATAL: Processing thread failed to start!")
                self.is_running = False
                self.audio_service.stop_listening()
                raise RuntimeError("Processing thread failed to start")
            
            logger.info("Processing thread started", thread_alive=self.processing_thread.is_alive())
            logger.info("Voice Orchestrator started - say 'Hey Wendy' to activate")
            
        except Exception as e:
            logger.error("Failed to start voice orchestrator", error=str(e), exc_info=True)
            self.is_running = False
            raise

    def stop(self):
        """Stop the voice loop"""
        self.is_running = False
        self.audio_service.stop_listening()
        if hasattr(self, 'processing_thread'):
            self.processing_thread.join(timeout=1.0)
        logger.info("Voice Orchestrator stopped")

    def _process_audio_loop(self):
        """Main loop for processing audio chunks"""
        logger.info("Audio processing loop started")
        chunks_received = 0
        
        while self.is_running:
            # Get chunk from audio service (non-blocking or with timeout)
            chunk = self.audio_service.get_audio_chunk()
            
            if chunk is None:
                # Sleep briefly to avoid busy wait
                time.sleep(0.01)
                continue
            
            chunks_received += 1
            if chunks_received % 50 == 0:
                logger.info("Processing loop heartbeat", chunks_received=chunks_received)
                
            self._process_chunk(chunk)

    def _process_chunk(self, chunk: np.ndarray):
        """Process a single audio chunk"""
        # Heartbeat log every 100 chunks (~8s) to confirm life
        if np.random.random() < 0.01: # 1% chance per chunk
             logger.info("Voice Heartbeat", is_running=self.is_running, listening=self.listening_for_command, speaking=self.is_speaking, processing=self.is_processing)

        # If speaking or processing, ignore input to prevent self-hearing and backlog
        if self.is_speaking or self.is_processing:
            return

        # Convert to float32 for processing if not already
        if chunk.dtype == np.int16:
            chunk_float = chunk.astype(np.float32) / 32768.0
        else:
            chunk_float = chunk

        # Gain factor (30.0 = +30dB) - Massive gain for very weak mic
        gain = 30.0 
        chunk_float = chunk_float * gain
        
        # Clip to avoid distortion
        chunk_float = np.clip(chunk_float, -1.0, 1.0)
        
        # Re-convert to int16 for consistency
        chunk_boosted = (chunk_float * 32767).astype(np.int16)

        if not self.listening_for_command:
            # Phase 1: Listen for Wake Word
            
            # DEBUG: Log energy level
            self.silence_count += 1
            
            # Calculate energy on boosted signal for monitoring
            energy = np.sqrt(np.mean(chunk_boosted.astype(np.float32)**2))
            
            if self.silence_count % 20 == 0:
                logger.info("Audio Input Check (Boosted)", energy=energy, status="waiting_for_wakeword")
            
            # DEBUG: Log before wake word detection
            if self.silence_count % 50 == 0:
                logger.info("Attempting wake word detection", chunk_shape=chunk_boosted.shape, energy=energy)

            if self.wakeword_service.detect(chunk_boosted):
                logger.info("Wake word detected! Listening for command...")
                self._enter_listening_mode()
        else:
            # Phase 2: Record command until silence or max duration
            self.audio_buffer.append(chunk_boosted.copy())
            
            # Simple energy-based silence detection
            if self._is_silence(chunk):
                self.silence_count += 1
            else:
                self.silence_count = 0
                self.last_speech_time = time.time()
            
            # Check for end conditions
            buffer_duration = len(self.audio_buffer) * 0.08  # 80ms per chunk
            
            # Timeout check for continuous mode (if no speech for 8 seconds)
            if buffer_duration > 8.0 and (time.time() - self.last_speech_time > 5.0) and len(self.audio_buffer) < 20:
                 # If buffer is small (mostly silence) and time passed, give up
                 logger.info("Listening timeout. Returning to wake word detection.")
                 self.listening_for_command = False
                 self.audio_buffer = []
                 # Reset wake word stream to ensure clean state
                 if self.wakeword_service:
                     self.wakeword_service.reset()
                 return

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
                
                # Start processing in a separate thread to avoid blocking audio loop
                self.is_processing = True
                threading.Thread(target=self._process_command, args=(audio_data,), daemon=True).start()

    def _enter_listening_mode(self):
        """Transition to listening mode"""
        self.listening_for_command = True
        self.audio_buffer = []
        self.silence_count = 0
        self.last_speech_time = time.time()
        
        # Reset KWS stream to clear state
        if self.wakeword_service:
            self.wakeword_service.reset()
            
        # Play sound in a separate thread
        threading.Thread(target=self._play_listening_sound, daemon=True).start()

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

    def _process_command(self, audio_data: np.ndarray):
        """Process the recorded voice command (Sync, runs in thread)"""
        try:
            broadcaster = get_broadcaster()
            
            # Step 1: Speech-to-Text
            logger.info("Transcribing audio...")
            text = self.stt_service.transcribe(audio_data)
            logger.info("Transcribed", text=text)
            
            if not text or not text.strip():
                logger.info("No speech detected")
                self.is_processing = False
                return
            
            # Emit transcription event (user message)
            broadcaster.emit_sync("transcription", {
                "role": "user",
                "content": text
            })

            # Step 2: LLM Processing
            logger.info("Getting response from LLM...")
            response = self.llm_service.chat_sync(
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
            
            # Emit response event (assistant message)
            broadcaster.emit_sync("response", {
                "role": "assistant",
                "content": response_text
            })

            # Step 3: Text-to-Speech
            logger.info("Synthesizing speech...")
            audio_bytes = self.tts_service.synthesize(response_text)
            
            # Step 4: Play response
            logger.info("Playing response...")
            self.is_speaking = True
            self.is_processing = False  # CRITICAL: Reset processing flag before speaking
            self.audio_service.play_audio(audio_bytes)
            self.is_speaking = False
            
            logger.info("Voice interaction complete. Returning to wake word detection.")
            
            # Return to wake word detection mode (user must say "Hey Wendy" again)
            # This ensures reliable, consistent detection
            self.listening_for_command = False
            if self.wakeword_service:
                self.wakeword_service.reset()
            
        except Exception as e:
            logger.error("Error processing voice command", error=str(e))
            self.is_processing = False
            self.is_speaking = False
            # Try to speak an error message
            try:
                error_audio = self.tts_service.synthesize("Sorry, I encountered an error.")
                self.audio_service.play_audio(error_audio)
            except:
                pass

    def get_status(self) -> dict:
        """Get current status of the voice orchestrator"""
        return {
            "is_running": self.is_running,
            "listening_for_command": self.listening_for_command,
            "is_speaking": self.is_speaking,
            "buffer_size": len(self.audio_buffer),
            "keywords_file": self.wakeword_service.keywords_file if self.wakeword_service else None
        }


_orchestrator: VoiceOrchestrator | None = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VoiceOrchestrator()
    return _orchestrator
