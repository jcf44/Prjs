import sounddevice as sd

print("Available Audio Devices:")
print(sd.query_devices())

print("\nDefault Input Device:")
try:
    print(sd.query_devices(kind='input'))
except:
    print("None")
