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
import os
import sys
import traceback
import numpy as np
import wave


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Simple linear interpolation resampling (no scipy needed)"""
    if orig_sr == target_sr:
        return audio
    
    duration = len(audio) / orig_sr
    target_length = int(duration * target_sr)
    
    indices = np.linspace(0, len(audio) - 1, target_length)
    resampled = np.interp(indices, np.arange(len(audio)), audio)
    
    return resampled.astype(np.float32)


def test_tts():
    """Test TTS (Sherpa-ONNX VITS)"""
    print("=" * 60)
    print("Testing TTS (Sherpa-ONNX VITS)...")
    print()
    
    try:
        from backend.services.voice.tts import get_tts_service
        
        tts = get_tts_service()
        test_text = "Hello! I am Wendy, your local AI assistant. How can I help you today?"
        
        print(f"  Generating speech for: \"{test_text}\"")
        audio_bytes = tts.synthesize(test_text)
        
        if len(audio_bytes) > 0:
            print(f"  ✅ TTS generation successful ({len(audio_bytes):,} bytes)")
            
            output_file = "test_tts_output.wav"
            with open(output_file, "wb") as f:
                f.write(audio_bytes)
            print(f"  Saved to {output_file}")
            return True
        else:
            print("  ❌ TTS returned empty audio")
            return False
            
    except Exception as e:
        print(f"  ❌ TTS test failed: {e}")
        traceback.print_exc()
        return False


def test_stt():
    """Test STT (faster-whisper)"""
    print()
    print("=" * 60)
    print("Testing STT (faster-whisper)...")
    print()
    
    try:
        from backend.services.voice.stt import get_stt_service
        
        print("  Loading STT model...")
        stt = get_stt_service()
        
        # Test with silence
        silence = np.zeros(16000 * 2, dtype=np.float32)
        print("  Transcribing silence...")
        text = stt.transcribe(silence)
        print(f"  ✅ STT initialized (silence transcribed as: '{text}')")
        
        # Test with TTS output if available
        if os.path.exists("test_tts_output.wav"):
            print("  Transcribing TTS output...")
            try:
                with wave.open("test_tts_output.wav", "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    orig_sr = wf.getframerate()
                    
                    if orig_sr != 16000:
                        print(f"    Resampling from {orig_sr}Hz to 16000Hz...")
                        audio = resample_audio(audio, orig_sr, 16000)
                
                text = stt.transcribe(audio)
                print(f"  ✅ STT transcription: \"{text}\"")
            except Exception as e:
                print(f"  ⚠️ Could not transcribe TTS output: {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ STT test failed: {e}")
        traceback.print_exc()
        return False


def test_wakeword():
    """Test Wake Word Detection (sherpa-onnx KWS)"""
    print()
    print("=" * 60)
    print("Testing Wake Word (sherpa-onnx KWS)...")
    print()
    
    try:
        from backend.services.voice.wakeword import get_wakeword_service
        
        print("  Loading wake word service...")
        ww = get_wakeword_service()
        
        print(f"  Keywords file: {ww.keywords_file}")
        
        # Check if it's the custom Hey Wendy file
        if "keywords_wendy" in ww.keywords_file:
            print("  ✅ Using custom 'Hey Wendy' keywords!")
        else:
            print("  ⚠️ Using default keywords (not 'Hey Wendy')")
        
        # Read and display keywords content
        if os.path.exists(ww.keywords_file):
            with open(ww.keywords_file, "r", encoding="utf-8") as f:
                keywords = f.read().strip()
            print(f"  Keywords content: {keywords}")
        
        # Test with silence
        print("  Testing for false positives (100 silence chunks)...")
        silence = np.zeros(1280, dtype=np.float32)
        
        false_positives = 0
        for _ in range(100):
            if ww.detect(silence):
                false_positives += 1
        
        if false_positives == 0:
            print("  ✅ No false positives on silence")
        else:
            print(f"  ⚠️ {false_positives} false positives on silence")
        
        # Check if Hey Wendy keywords exist
        model_dir = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
        wendy_keywords = os.path.join(
            model_dir, 
            "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01", 
            "keywords_wendy.txt"
        )
        
        if os.path.exists(wendy_keywords):
            print("  ✅ 'Hey Wendy' keywords file exists")
        else:
            print("  ⚠️ 'Hey Wendy' keywords not configured")
            print("     Run: python scripts/create_wakeword.py")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Wake Word test failed: {e}")
        traceback.print_exc()
        return False


def test_audio():
    """Test Audio I/O (sounddevice)"""
    print()
    print("=" * 60)
    print("Testing Audio I/O (sounddevice)...")
    print()
    
    try:
        import sounddevice as sd
        
        devices = sd.query_devices()
        print(f"  Found {len(devices)} audio devices")
        
        try:
            default_input = sd.query_devices(kind='input')
            print(f"  Default input:  {default_input['name']}")
        except Exception:
            print("  ⚠️ No default input device")
        
        try:
            default_output = sd.query_devices(kind='output')
            print(f"  Default output: {default_output['name']}")
        except Exception:
            print("  ⚠️ No default output device")
        
        # Test audio playback
        if os.path.exists("test_tts_output.wav"):
            print()
            print("  Playing TTS output...")
            from backend.services.voice.audio import get_audio_service
            audio_service = get_audio_service()
            
            with open("test_tts_output.wav", "rb") as f:
                audio_bytes = f.read()
            
            audio_service.play_audio(audio_bytes)
            print("  ✅ Audio playback complete")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Audio test failed: {e}")
        traceback.print_exc()
        return False


def test_pipeline():
    """Test the full voice pipeline"""
    print()
    print("=" * 60)
    print("Testing Full Voice Pipeline...")
    print()
    
    try:
        from backend.services.voice import get_orchestrator
        
        print("  Initializing orchestrator...")
        orchestrator = get_orchestrator()
        status = orchestrator.get_status()
        
        print(f"  Status:")
        print(f"    - is_running: {status['is_running']}")
        print(f"    - listening_for_command: {status['listening_for_command']}")
        print(f"    - keywords_file: {status['keywords_file']}")
        
        print("  ✅ Voice pipeline initialized")
        
        print()
        print("  To test interactively:")
        print("  1. Start API: uv run uvicorn backend.main:app --reload")
        print("  2. POST to http://localhost:8181/v1/voice/start")
        print("  3. Say 'Hey Wendy'")
        print("  4. Speak your command")
        print("  5. Listen for response")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Pipeline test failed: {e}")
        traceback.print_exc()
        return False


def main():
    print()
    print("=" * 60)
    print("       WENDY VOICE PIPELINE VERIFICATION")
    print("=" * 60)
    
    results = {}
    
    # Run all tests
    results['TTS'] = test_tts()
    results['STT'] = test_stt()
    results['Wake Word'] = test_wakeword()
    results['Audio'] = test_audio()
    results['Pipeline'] = test_pipeline()
    
    # Summary
    print()
    print("=" * 60)
    print("                    SUMMARY")
    print("=" * 60)
    print()
    
    all_passed = True
    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {component:15} {status}")
        if not passed:
            all_passed = False
    
    print()
    print("=" * 60)
    
    if all_passed:
        print("🎉 All voice pipeline tests passed!")
    else:
        print("⚠️ Some tests failed. Check the output above.")
    
    print()
    if os.path.exists("test_tts_output.wav"):
        print("Note: test_tts_output.wav preserved for manual listening")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print()
        print("=" * 60)
        print("                UNEXPECTED ERROR")
        print("=" * 60)
        print(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)
