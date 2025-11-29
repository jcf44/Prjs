"""
Real-time diagnostic for wake word detection
Checks what's happening during detection attempts
"""
import requests
import time
import json

print("Wake Word Detection Diagnostic")
print("="*60)

# Check if voice mode is running
try:
    status = requests.get("http://localhost:8181/v1/voice/status").json()
    print(f"\n✓ Voice Status:")
    print(f"  is_running: {status['is_running']}")
    print(f"  listening_for_command: {status['listening_for_command']}")
    print(f"  is_speaking: {status['is_speaking']}")
    print(f"  buffer_size: {status['buffer_size']}")
    
    if not status['is_running']:
        print("\n❌ Voice mode is NOT running!")
        print("   Please activate voice mode in the UI first.")
        exit(1)
    
    print("\n✓ Voice mode is active")
    print("\n" + "="*60)
    print("Monitoring for 30 seconds...")
    print("SAY 'HEY WENDY' NOW!")
    print("="*60)
    
    # Monitor for 30 seconds
    for i in range(30):
        time.sleep(1)
        status = requests.get("http://localhost:8181/v1/voice/status").json()
        
        if status['listening_for_command']:
            print(f"\n🎉 WAKE WORD DETECTED at {i} seconds!")
            print("   Status changed to listening_for_command=True")
            break
        
        if i % 5 == 0:
            print(f"  {i}s - Still waiting for wake word...")
    
    else:
        print("\n❌ No wake word detected in 30 seconds")
        print("\nThis suggests the wake word model is not triggering.")
        print("Check the backend logs for:")
        print("  - 'Attempting wake word detection' messages")
        print("  - 'Audio Input Check' energy levels")
        print("  - Any 'KWS Result Raw' messages")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
