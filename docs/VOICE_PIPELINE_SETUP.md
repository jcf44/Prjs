# Wendy Voice Pipeline Setup Guide

This document describes the voice pipeline configuration for Wendy, including wake word detection, speech-to-text (STT), and text-to-speech (TTS).

## Overview

The voice pipeline uses the following stack:

| Component | Technology | Purpose |
|-----------|------------|---------|
| Wake Word | sherpa-onnx KWS | Detects "Hey Wendy" trigger phrase |
| STT | faster-whisper | Converts speech to text |
| TTS | sherpa-onnx VITS | Converts text to speech |
| Audio I/O | sounddevice | Microphone input and speaker output |

All components run **locally and offline** - no cloud APIs required.

---

## Dependencies

### Python Packages

```toml
# In pyproject.toml
"sherpa-onnx>=1.10.0"
"faster-whisper>=1.0.0"
"sounddevice>=0.5.0"
"numpy>=1.26.0"
```

### System Requirements

- Python 3.12+
- Working microphone
- Working speakers/headphones
- ~2GB disk space for models

---

## Directory Structure

Models are stored in the user's home directory:

```
~/.wendy/
└── models/
    ├── sherpa_kws/
    │   └── sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/
    │       ├── encoder-epoch-12-avg-2-chunk-16-left-64.onnx
    │       ├── decoder-epoch-12-avg-2-chunk-16-left-64.onnx
    │       ├── joiner-epoch-12-avg-2-chunk-16-left-64.onnx
    │       ├── tokens.txt
    │       ├── keywords.txt              # Default keywords
    │       ├── keywords_wendy.txt        # "Hey Wendy" (balanced)
    │       ├── keywords_wendy_sensitive.txt  # More sensitive
    │       └── keywords_wendy_strict.txt     # Fewer false positives
    │
    └── sherpa_tts/
        └── vits-piper-en_US-lessac-medium/
            ├── en_US-lessac-medium.onnx
            ├── tokens.txt
            └── espeak-ng-data/
```

**Note:** Models are downloaded automatically on first run.

---

## Configuration

### Settings (backend/config.py)

```python
# Voice settings
SHERPA_KWS_MODEL_PATH: str = ""  # Auto-download to ~/.wendy/models
SHERPA_TTS_MODEL_PATH: str = ""  # Auto-download to ~/.wendy/models
STT_MODEL_SIZE: str = "base.en"  # Options: tiny, base, small, medium, large
AUDIO_DEVICE_INDEX: Optional[int] = None  # None = default device
```

### STT Model Sizes

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny.en | ~75MB | Fastest | Lower |
| base.en | ~150MB | Fast | Good |
| small.en | ~500MB | Medium | Better |
| medium.en | ~1.5GB | Slow | High |
| large-v3 | ~3GB | Slowest | Highest |

For most use cases, `base.en` provides a good balance.

---

## Wake Word Configuration

### How "Hey Wendy" Works

The KWS (Keyword Spotting) model uses BPE (Byte Pair Encoding) tokens. "Hey Wendy" is tokenized as:

```
"HEY"   → ▁HE + Y
"WENDY" → ▁WE + ND + Y

Final: ▁HE Y ▁WE ND Y @0.5
```

The `▁` character (U+2581) represents a word boundary.

### Creating the Keywords File

Run the configuration script:

```bash
uv run python scripts/create_wakeword.py
```

**Output:**
```
============================================================
       HEY WENDY WAKE WORD CONFIGURATION
============================================================

Step 1: Loading tokens...
  Loaded 500 tokens

Step 2: Searching for relevant tokens...
  '▁HE' -> ID 49
  '▁WE' -> ID 41
  'ND' -> ID 148
  'Y' -> ID 17

Step 3: Building token sequence for 'Hey Wendy'...
  Token sequence: ['▁HE', 'Y', '▁WE', 'ND', 'Y']

Step 4: Creating keywords files...
  Created: keywords_wendy.txt (threshold 0.5)
  Created: keywords_wendy_sensitive.txt (threshold 0.3)
  Created: keywords_wendy_strict.txt (threshold 0.8)
```

### Threshold Tuning

| File | Threshold | Use Case |
|------|-----------|----------|
| `keywords_wendy.txt` | 0.5 | **Default** - Balanced detection |
| `keywords_wendy_sensitive.txt` | 0.3 | If "Hey Wendy" is often missed |
| `keywords_wendy_strict.txt` | 0.8 | If too many false activations |

To change threshold, rename the desired file to `keywords_wendy.txt`.

### Custom Wake Words

To add different wake words, edit `scripts/create_wakeword.py`:

```python
# Change this line:
tokens = find_token_sequence("Hey Wendy", token_to_id)

# To your desired phrase:
tokens = find_token_sequence("Hello Assistant", token_to_id)
```

---

## Voice Services

### WakeWordService (`backend/services/voice/wakeword.py`)

- Automatically downloads the KWS model on first use
- Prefers `keywords_wendy.txt` if it exists
- Falls back to default `keywords.txt`
- Processes 80ms audio chunks (1280 samples at 16kHz)

```python
from backend.services.voice import get_wakeword_service

ww = get_wakeword_service()
detected = ww.detect(audio_chunk)  # Returns True if "Hey Wendy" detected
```

### STTService (`backend/services/voice/stt.py`)

- Uses faster-whisper with CPU inference
- Expects 16kHz audio
- Handles int16 or float32 input

```python
from backend.services.voice import get_stt_service

stt = get_stt_service()
text = stt.transcribe(audio_numpy_array)
```

### TTSService (`backend/services/voice/tts.py`)

- Uses sherpa-onnx VITS (Piper voice)
- Returns WAV bytes
- Default voice: `en_US-lessac-medium`

```python
from backend.services.voice import get_tts_service

tts = get_tts_service()
wav_bytes = tts.synthesize("Hello, how can I help?")
```

### AudioService (`backend/services/voice/audio.py`)

- Manages microphone input stream
- Handles speaker playback
- Queue-based chunk processing

```python
from backend.services.voice import get_audio_service

audio = get_audio_service()
audio.start_listening(callback_function)
audio.play_audio(wav_bytes)
audio.stop_listening()
```

### VoiceOrchestrator (`backend/services/voice/orchestrator.py`)

Coordinates the full voice interaction flow:

1. **Listen** for wake word ("Hey Wendy")
2. **Record** user's command (with silence detection)
3. **Transcribe** audio to text (STT)
4. **Process** with LLM
5. **Synthesize** response (TTS)
6. **Play** audio response

```python
from backend.services.voice import get_orchestrator

orchestrator = get_orchestrator()
await orchestrator.start()  # Starts listening loop
orchestrator.stop()         # Stops listening
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/voice/status` | GET | Get voice pipeline status |
| `/v1/voice/start` | POST | Start wake word listening |
| `/v1/voice/stop` | POST | Stop voice pipeline |
| `/v1/voice/test/tts` | POST | Test TTS with custom text |
| `/v1/voice/test/wakeword` | POST | Get wake word configuration |

### Example Usage

```bash
# Start voice listening
curl -X POST http://localhost:8181/v1/voice/start

# Check status
curl http://localhost:8181/v1/voice/status

# Test TTS
curl -X POST "http://localhost:8181/v1/voice/test/tts?text=Hello%20World"

# Stop voice
curl -X POST http://localhost:8181/v1/voice/stop
```

---

## Verification

Run the verification script to test all components:

```bash
uv run python scripts/verify_voice.py
```

**Expected Output:**
```
============================================================
       WENDY VOICE PIPELINE VERIFICATION
============================================================

Testing TTS (Sherpa-ONNX VITS)...
  ✅ TTS generation successful (175,636 bytes)

Testing STT (faster-whisper)...
  ✅ STT initialized
  ✅ STT transcription: "Hello, I am Wendy..."

Testing Wake Word (sherpa-onnx KWS)...
  ✅ Using custom 'Hey Wendy' keywords!
  ✅ No false positives on silence
  ✅ 'Hey Wendy' keywords file exists

Testing Audio I/O (sounddevice)...
  ✅ Audio playback complete

Testing Full Voice Pipeline...
  ✅ Voice pipeline initialized

============================================================
                    SUMMARY
============================================================
  TTS             ✅ PASS
  STT             ✅ PASS
  Wake Word       ✅ PASS
  Audio           ✅ PASS
  Pipeline        ✅ PASS
============================================================
🎉 All voice pipeline tests passed!
```

---

## Troubleshooting

### "Model not found" errors

Models are downloaded automatically. If download fails:

1. Check internet connection
2. Manually download from:
   - KWS: https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models
   - TTS: https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models
3. Extract to `~/.wendy/models/`

### Wake word not detecting

1. Verify keywords file exists:
   ```bash
   cat ~/.wendy/models/sherpa_kws/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/keywords_wendy.txt
   ```

2. Try the sensitive threshold:
   ```bash
   cd ~/.wendy/models/sherpa_kws/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/
   cp keywords_wendy_sensitive.txt keywords_wendy.txt
   ```

3. Speak clearly and at normal volume

### Too many false activations

Use the strict threshold:
```bash
cd ~/.wendy/models/sherpa_kws/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/
cp keywords_wendy_strict.txt keywords_wendy.txt
```

### No audio playback

1. Check default audio device:
   ```python
   import sounddevice as sd
   print(sd.query_devices())
   ```

2. Set specific device in `.env`:
   ```
   AUDIO_DEVICE_INDEX=1
   ```

### STT transcription poor quality

1. Ensure 16kHz sample rate
2. Try a larger model:
   ```
   STT_MODEL_SIZE=small.en
   ```

### pkg_resources warning

This warning is harmless and comes from ctranslate2:
```
UserWarning: pkg_resources is deprecated as an API...
```

It will be fixed in a future version of the dependency.

---

## Model Sources

| Component | Model | Source |
|-----------|-------|--------|
| KWS | sherpa-onnx-kws-zipformer-gigaspeech-3.3M | [k2-fsa/sherpa-onnx releases](https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models) |
| TTS | vits-piper-en_US-lessac-medium | [k2-fsa/sherpa-onnx releases](https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models) |
| STT | faster-whisper (auto-download) | [Hugging Face](https://huggingface.co/guillaumekln/faster-whisper-base.en) |

---

## Quick Reference

```bash
# Verify voice pipeline
uv run python scripts/verify_voice.py

# Create "Hey Wendy" wake word
uv run python scripts/create_wakeword.py

# Start API server
uv run uvicorn backend.main:app --reload

# Start voice listening (after API is running)
curl -X POST http://localhost:8181/v1/voice/start

# Say "Hey Wendy" followed by your question!
```

---

*Document created: November 2025*
*Last updated: November 2025*
