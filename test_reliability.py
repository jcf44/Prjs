"""
Test wake word detection reliability
Activates voice mode and waits for multiple wake word detections
"""
import requests
import time

print("Wake Word Reliability Test")
print("="*60)
print("This will test wake word detection 5 times")
print("Say 'HEY WENDY' each time you see the prompt")
print("="*60)

base_url = "http://localhost:8181/v1/voice"

# Check if running
status = requests.get(f"{base_url}/status").json()
if not status['is_running']:
    print("\n❌ Voice mode not running. Please activate it first.")
    exit(1)

successful_detections = 0
total_attempts = 5

for attempt in range(1, total_attempts + 1):
    print(f"\n{'='*60}")
    print(f"Attempt {attempt}/{total_attempts}")
    print(f"{'='*60}")
    print("SAY 'HEY WENDY' NOW! (Waiting 15 seconds...)")
    
    detected = False
    start_time = time.time()
    
    while time.time() - start_time < 15:
        status = requests.get(f"{base_url}/status").json()
        
        if status['listening_for_command']:
            detected = True
            detection_time = time.time() - start_time
            print(f"\n✅ DETECTED at {detection_time:.1f} seconds!")
            successful_detections += 1
            
            # Wait for it to return to wake word mode
            print("   Waiting for system to return to wake word mode...")
            time.sleep(3)
            
            # Verify it returned
            status = requests.get(f"{base_url}/status").json()
            if not status['listening_for_command']:
                print("   ✅ Confirmed: Returned to wake word detection mode")
            else:
                print("   ⚠️  Warning: Still in listening mode")
            
            break
        
        time.sleep(0.5)
    
    if not detected:
        print(f"\n❌ NOT DETECTED in 15 seconds")
    
    if attempt < total_attempts:
        print("\nWaiting 2 seconds before next attempt...")
        time.sleep(2)

print(f"\n{'='*60}")
print(f"RESULTS: {successful_detections}/{total_attempts} successful detections")
print(f"{'='*60}")

if successful_detections == total_attempts:
    print("✅ PERFECT! All detections successful!")
    print("   Wake word detection is now RELIABLE!")
elif successful_detections >= total_attempts * 0.8:
    print("✓ GOOD: Most detections successful")
    print("  May need minor tuning")
else:
    print("❌ POOR: Detection still unreliable")
    print("   Further investigation needed")
