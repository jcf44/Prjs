import subprocess
import sys

# Find the backend process and get recent logs
result = subprocess.run(
    ['powershell', '-Command', 
     "Get-Process | Where-Object {$_.ProcessName -eq 'python'} | ForEach-Object { $_.Id }"],
    capture_output=True,
    text=True
)

print("Python process IDs:")
print(result.stdout)
