"""Check backend logs by making a quick test"""
import requests
import json

# Check if voice mode is running
try:
    response = requests.get("http://localhost:8181/v1/voice/status")
    status = response.json()
    print("Voice Status:")
    print(json.dumps(status, indent=2))
    
    print("\n" + "="*60)
    if status.get("is_running"):
        print("✅ Voice mode IS RUNNING")
        print(f"   - Listening for command: {status.get('listening_for_command')}")
        print(f"   - Is speaking: {status.get('is_speaking')}")
        print(f"   - Buffer size: {status.get('buffer_size')}")
    else:
        print("❌ Voice mode is NOT running")
        
except Exception as e:
    print(f"Error: {e}")
