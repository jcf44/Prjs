import wave
import numpy as np
import os

filename = "debug_voice_input.wav"

if not os.path.exists(filename):
    print(f"File {filename} not found.")
    exit(1)

try:
    with wave.open(filename, 'rb') as wf:
        params = wf.getparams()
        print(f"Channels: {params.nchannels}")
        print(f"Sample Width: {params.sampwidth}")
        print(f"Frame Rate: {params.framerate}")
        print(f"Frames: {params.nframes}")
        duration = params.nframes / params.framerate
        print(f"Duration: {duration:.2f}s")
        
        frames = wf.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16)
        
        if len(data) == 0:
            print("Error: Audio data is empty.")
        else:
            max_amp = np.max(np.abs(data))
            mean_amp = np.mean(np.abs(data))
            print(f"Max Amplitude: {max_amp}")
            print(f"Mean Amplitude: {mean_amp:.2f}")
            
            if max_amp == 0:
                print("WARNING: Audio is completely silent.")
            elif max_amp < 500:
                print("WARNING: Audio is very quiet.")
            else:
                print("Audio levels look okay.")
                
except Exception as e:
    print(f"Error analyzing file: {e}")
