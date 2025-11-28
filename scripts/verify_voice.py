import asyncio
import structlog
import os
import numpy as np
import wave

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

async def verify_voice():
    logger.info("Starting Voice Pipeline Verification...")
    
    # 1. Test TTS (Sherpa-ONNX)
    try:
        from backend.services.voice.tts import get_tts_service
        # This might take a while to download models on first run
        tts = get_tts_service()
        logger.info("Testing TTS...")
        audio_bytes = tts.synthesize("Hello, I am Wendy. I am running offline.")
        if len(audio_bytes) > 0:
            logger.info("TTS generation successful", bytes=len(audio_bytes))
            # Save to file for manual check
            with open("test_tts.wav", "wb") as f:
                f.write(audio_bytes)
            logger.info("Saved test_tts.wav")
        else:
            logger.error("TTS returned empty bytes")
    except Exception as e:
        logger.error("TTS test failed", error=str(e))

    # 2. Test STT (Faster-Whisper)
    try:
        from backend.services.voice.stt import get_stt_service
        stt = get_stt_service()
        logger.info("Testing STT...")
        
        # Create a dummy WAV file with silence or noise if we don't have a real one
        # Or try to transcribe the TTS output if it wasn't silent
        # For now, let's create a dummy numpy array
        dummy_audio = np.zeros(16000 * 2, dtype=np.float32) # 2 seconds silence
        text = stt.transcribe(dummy_audio)
        logger.info("STT transcription (silence)", text=text)
        
    except Exception as e:
        logger.error("STT test failed", error=str(e))

    # 3. Test Wake Word (Sherpa-ONNX)
    try:
        from backend.services.voice.wakeword import get_wakeword_service
        ww = get_wakeword_service()
        logger.info("Testing Wake Word...")
        
        # Dummy audio chunk (80ms)
        dummy_chunk = np.zeros(1280, dtype=np.float32)
        detected = ww.detect(dummy_chunk)
        logger.info("Wake word detection (silence)", detected=detected)
        
    except Exception as e:
        logger.error("Wake Word test failed", error=str(e))

    # 4. Test Audio Service (Device Listing)
    try:
        import sounddevice as sd
        logger.info("Testing Audio Devices...")
        devices = sd.query_devices()
        logger.info("Audio devices found", count=len(devices))
        # logger.info(devices)
    except Exception as e:
        logger.error("Audio device test failed", error=str(e))

if __name__ == "__main__":
    asyncio.run(verify_voice())
