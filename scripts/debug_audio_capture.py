import sounddevice as sd
import numpy as np
import wave
import time

def debug_audio():
    print("Listing Audio Devices:")
    print(sd.query_devices())
    
    try:
        default_input = sd.query_devices(kind='input')
        print(f"\nDefault Input Device: {default_input['name']}")
    except Exception as e:
        print(f"\nError querying default input: {e}")
    
    fs = 16000  # Sample rate
    seconds = 5  # Duration of recording
    
    print(f"\nRecording {seconds} seconds... SPEAK NOW!")
    try:
        myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()  # Wait until recording is finished
        print("Recording finished.")
        
        # Analyze
        max_amp = np.max(np.abs(myrecording))
        rms = np.sqrt(np.mean(myrecording.astype(np.float32)**2))
        
        print(f"\nAnalysis:")
        print(f"Max Amplitude: {max_amp} (Range: 0-32767)")
        print(f"RMS Energy: {rms:.2f}")
        
        if max_amp < 100:
            print("RESULT: SILENCE DETECTED. Check microphone selection or mute switch.")
        elif max_amp < 1000:
            print("RESULT: VERY QUIET. Gain boost needed.")
        else:
            print("RESULT: AUDIO DETECTED. Microphone is working.")
            
        with wave.open('debug_capture.wav', 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(fs)
            wav_file.writeframes(myrecording.tobytes())
        print("\nSaved to debug_capture.wav")
        
    except Exception as e:
        print(f"Recording failed: {e}")

if __name__ == "__main__":
    debug_audio()
