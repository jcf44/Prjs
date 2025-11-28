"""
Voice Pipeline Verification Script

Tests all voice components:
1. TTS (sherpa-onnx VITS)
2. STT (faster-whisper)
3. Wake Word (sherpa-onnx KWS)
4. Audio I/O (sounddevice)
5. Full pipeline integration
"""

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


async def verify_tts():
    """Test TTS (Sherpa-ONNX VITS)"""
    logger.info("=" * 50)
    logger.info("Testing TTS (Sherpa-ONNX VITS)...")
    
    try:
        from backend.services.voice.tts import get_tts_service
        
        tts = get_tts_service()
        test_text = "Hello! I am Wendy, your local AI assistant. How can I help you today?"
        
        logger.info("Generating speech...", text=test_text)
        audio_bytes = tts.synthesize(test_text)
        
        if len(audio_bytes) > 0:
            logger.info("✅ TTS generation successful", size_bytes=len(audio_bytes))
            
            # Save to file for manual verification
            output_file = "test_tts_output.wav"
            with open(output_file, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"   Saved to {output_file} for manual listening")
            return True
        else:
            logger.error("❌ TTS returned empty audio")
            return False
            
    except Exception as e:
        logger.error("❌ TTS test failed", error=str(e))
        return False


async def verify_stt():
    """Test STT (faster-whisper)"""
    logger.info("=" * 50)
    logger.info("Testing STT (faster-whisper)...")
    
    try:
        from backend.services.voice.stt import get_stt_service
        
        stt = get_stt_service()
        
        # Test with silence
        silence = np.zeros(16000 * 2, dtype=np.float32)  # 2 seconds
        logger.info("Transcribing silence...")
        text = stt.transcribe(silence)
        logger.info("✅ STT transcription (silence)", text=repr(text))
        
        # Test with TTS output if available
        if os.path.exists("test_tts_output.wav"):
            logger.info("Transcribing TTS output...")
            with wave.open("test_tts_output.wav", "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Resample if needed (TTS might be 22050Hz, Whisper needs 16000Hz)
                if wf.getframerate() != 16000:
                    from scipy import signal
                    audio = signal.resample(audio, int(len(audio) * 16000 / wf.getframerate()))
                
            text = stt.transcribe(audio)
            logger.info("✅ STT transcription (TTS output)", text=text)
        
        return True
        
    except Exception as e:
        logger.error("❌ STT test failed", error=str(e))
        return False


async def verify_wakeword():
    """Test Wake Word Detection (sherpa-onnx KWS)"""
    logger.info("=" * 50)
    logger.info("Testing Wake Word (sherpa-onnx KWS)...")
    
    try:
        from backend.services.voice.wakeword import get_wakeword_service
        
        ww = get_wakeword_service()
        
        logger.info("Keywords file", path=ww.keywords_file)
        
        # Read and display keywords
        if os.path.exists(ww.keywords_file):
            with open(ww.keywords_file, "r", encoding="utf-8") as f:
                keywords = f.read().strip()
            logger.info("Configured keywords", content=keywords)
        
        # Test with silence (should NOT detect)
        silence = np.zeros(1280, dtype=np.float32)  # 80ms chunk
        
        false_positives = 0
        for _ in range(100):  # Test 100 chunks of silence
            if ww.detect(silence):
                false_positives += 1
        
        if false_positives == 0:
            logger.info("✅ No false positives on silence")
        else:
            logger.warning(f"⚠️ {false_positives} false positives on silence")
        
        # Check if "Hey Wendy" keywords exist
        model_dir = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
        wendy_keywords = os.path.join(model_dir, "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01", "keywords_wendy.txt")
        
        if os.path.exists(wendy_keywords):
            logger.info("✅ 'Hey Wendy' keywords file exists")
        else:
            logger.warning("⚠️ 'Hey Wendy' keywords not configured")
            logger.info("   Run: python scripts/create_wakeword.py")
        
        return True
        
    except Exception as e:
        logger.error("❌ Wake Word test failed", error=str(e))
        return False


async def verify_audio():
    """Test Audio I/O (sounddevice)"""
    logger.info("=" * 50)
    logger.info("Testing Audio I/O (sounddevice)...")
    
    try:
        import sounddevice as sd
        
        # List devices
        devices = sd.query_devices()
        logger.info("Audio devices found", count=len(devices))
        
        # Find default input/output
        default_input = sd.query_devices(kind='input')
        default_output = sd.query_devices(kind='output')
        
        logger.info("Default input", device=default_input['name'])
        logger.info("Default output", device=default_output['name'])
        
        # Test audio playback if TTS output exists
        if os.path.exists("test_tts_output.wav"):
            logger.info("Playing TTS output...")
            from backend.services.voice.audio import get_audio_service
            audio_service = get_audio_service()
            
            with open("test_tts_output.wav", "rb") as f:
                audio_bytes = f.read()
            
            audio_service.play_audio(audio_bytes)
            logger.info("✅ Audio playback complete")
        
        return True
        
    except Exception as e:
        logger.error("❌ Audio test failed", error=str(e))
        return False


async def verify_full_pipeline():
    """Test the full voice pipeline orchestration"""
    logger.info("=" * 50)
    logger.info("Testing Full Voice Pipeline...")
    
    try:
        from backend.services.voice import get_orchestrator
        
        orchestrator = get_orchestrator()
        status = orchestrator.get_status()
        
        logger.info("Orchestrator status", **status)
        logger.info("✅ Voice pipeline initialized")
        
        logger.info("\nTo test the full pipeline interactively:")
        logger.info("1. Start the API server: uvicorn backend.main:app --reload")
        logger.info("2. POST to /v1/voice/start")
        logger.info("3. Say 'Hey Wendy' (or configured wake word)")
        logger.info("4. Speak your command")
        logger.info("5. Listen for Wendy's response")
        
        return True
        
    except Exception as e:
        logger.error("❌ Full pipeline test failed", error=str(e))
        return False


async def main():
    logger.info("=" * 60)
    logger.info("       WENDY VOICE PIPELINE VERIFICATION")
    logger.info("=" * 60)
    
    results = {}
    
    # Run all tests
    results['TTS'] = await verify_tts()
    results['STT'] = await verify_stt()
    results['Wake Word'] = await verify_wakeword()
    results['Audio'] = await verify_audio()
    results['Pipeline'] = await verify_full_pipeline()
    
    # Summary
    logger.info("=" * 60)
    logger.info("                    SUMMARY")
    logger.info("=" * 60)
    
    all_passed = True
    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {component:15} {status}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("🎉 All voice pipeline tests passed!")
    else:
        logger.warning("⚠️ Some tests failed. Check the output above.")
    
    # Cleanup
    if os.path.exists("test_tts_output.wav"):
        logger.info("\nNote: test_tts_output.wav preserved for manual listening")


if __name__ == "__main__":
    asyncio.run(main())
