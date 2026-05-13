import frida
import time
import sys

# Load the SSL bypass script
with open(r"C:\Users\31760\frida_ssl_bypass.js", "r", encoding="utf-8") as f:
    ssl_script_code = f.read()

print("[*] Connecting to device...")
device = frida.get_usb_device()
print(f"[*] Device: {device}")

# Spawn Doubao with Frida injected
print("[*] Spawning com.larus.nova...")
pid = device.spawn(["com.larus.nova"])
print(f"[*] Spawned PID: {pid}")

session = device.attach(pid)
print("[*] Session attached")

# Load SSL bypass script
script = session.create_script(ssl_script_code)
script.on("message", lambda msg, data: print(f"[Frida] {msg}"))
script.load()
print("[*] SSL bypass script loaded")

# Resume the app
device.resume(pid)
print("[*] App resumed — SSL pinning should be bypassed!")
print("[*] Now send a message in Doubao and check mitmproxy logs.")

# Keep alive for 120 seconds
try:
    time.sleep(120)
except KeyboardInterrupt:
    pass

print("[*] Done.")
