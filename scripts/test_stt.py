import os
import sys
import numpy as np
import wave
from faster_whisper import WhisperModel

# Mock settings
MODEL_SIZE = "base.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

def main():
    filename = "debug_voice_input.wav"
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return

    print(f"Loading model {MODEL_SIZE} on {DEVICE}...")
    try:
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("Model loaded.")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    print(f"Reading {filename}...")
    with wave.open(filename, 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
        audio_int16 = np.frombuffer(frames, dtype=np.int16)
        # Convert to float32
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

    print("Transcribing...")
    try:
        segments, info = model.transcribe(audio_float32, beam_size=5)
        
        text = ""
        for segment in segments:
            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            text += segment.text
            
        print(f"Full text: '{text.strip()}'")
        
    except Exception as e:
        print(f"Transcription failed: {e}")

if __name__ == "__main__":
    main()
