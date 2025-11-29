#!/usr/bin/env python
"""Quick microphone test to check if audio is being captured"""
import sounddevice as sd
import numpy as np
import time

def test_microphone():
    print("Available audio devices:")
    print(sd.query_devices())
    print("\n" + "="*60)
    
    device = None  # Use default
    sample_rate = 16000
    block_size = 1280  # 80ms chunks
    
    print(f"\nListening on default device...")
    print(f"Sample rate: {sample_rate}, Block size: {block_size}")
    print("Say something into your microphone!\n")
    
    chunk_count = 0
    
    def callback(indata, frames, time_info, status):
        nonlocal chunk_count
        if status:
            print(f"Status: {status}")
        
        # Calculate energy
        audio = indata.copy().flatten()
        energy = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
        
        chunk_count += 1
        if chunk_count % 10 == 0:  # Every ~800ms
            print(f"Chunk {chunk_count}: Energy = {energy:.2f}")
    
    with sd.InputStream(
        device=device,
        channels=1,
        samplerate=sample_rate,
        dtype='int16',
        blocksize=block_size,
        callback=callback
    ):
        print("Recording for 10 seconds...")
        time.sleep(10)
    
    print(f"\nTest complete! Captured {chunk_count} chunks.")
    if chunk_count == 0:
        print("ERROR: No audio captured! Check microphone permissions and device.")
    elif chunk_count < 100:
        print("WARNING: Very few chunks captured. Audio might be dropping.")
    else:
        print("SUCCESS: Audio is being captured.")

if __name__ == "__main__":
    test_microphone()
