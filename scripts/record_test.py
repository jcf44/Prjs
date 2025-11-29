import sounddevice as sd
import numpy as np
import wave
import time

SAMPLE_RATE = 16000
CHANNELS = 1
DURATION = 5  # seconds
OUTPUT_FILE = "test_audio.wav"

def main():
    print(f"Recording {DURATION} seconds of audio...")
    print(f"Speak 'Hey Wendy' or 'Hi Google' clearly.")
    
    try:
        recording = sd.rec(
            int(DURATION * SAMPLE_RATE), 
            samplerate=SAMPLE_RATE, 
            channels=CHANNELS, 
            dtype='int16'
        )
        sd.wait()  # Wait until recording is finished
        
        print("Recording complete.")
        
        with wave.open(OUTPUT_FILE, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2) # 2 bytes for int16
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(recording.tobytes())
            
        print(f"Saved to {OUTPUT_FILE}")
        
        # Calculate max amplitude
        max_amp = np.max(np.abs(recording))
        print(f"Max Amplitude: {max_amp} / 32768")
        
        if max_amp < 1000:
            print("WARNING: Volume seems very low.")
        elif max_amp > 32000:
            print("WARNING: Audio is clipping (too loud).")
        else:
            print("Volume levels look good.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
