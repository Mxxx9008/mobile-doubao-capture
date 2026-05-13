import frida
import time
import sys

# Load the SSL bypass script
with open(r"C:\Users\31760\frida_ssl_bypass.js", "r", encoding="utf-8") as f:
    ssl_script_code = f.read()

print("[*] Connecting to device...")
device = frida.get_usb_device()
print(f"[*] Device: {device}")

# Attach to running Doubao process
print("[*] Attaching to com.larus.nova...")
session = device.attach("com.larus.nova")
print(f"[*] Session attached")

# Load SSL bypass script
script = session.create_script(ssl_script_code)
script.on("message", lambda msg, data: print(f"[Frida] {msg}"))
script.load()
print("[*] SSL bypass script loaded — all connections will be trusted!")
print("[*] NOW send a message in Doubao that will trigger references.")
print("[*] I'll stay alive for 180 seconds...")

# Keep alive for 180 seconds
try:
    time.sleep(180)
except KeyboardInterrupt:
    pass

print("[*] Done.")
