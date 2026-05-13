import frida
import time
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load SSL bypass script
js_path = os.path.join(SCRIPT_DIR, "frida_ssl_bypass.js")
if not os.path.exists(js_path):
    # Fallback: same dir as this script or current dir
    js_path = r"C:\Users\31760\frida_ssl_bypass.js"

with open(js_path, "r", encoding="utf-8") as f:
    ssl_script_code = f.read()

print("[*] Connecting to device via USB...")
device = frida.get_usb_device()
print(f"[*] Device: {device}")

print("[*] Attaching to Doubao (com.larus.nova)...")
try:
    session = device.attach("com.larus.nova")
except frida.ProcessNotFoundError:
    print("[!] Doubao is not running! Open Doubao first, then re-run.")
    sys.exit(1)

print(f"[*] Session attached")

script = session.create_script(ssl_script_code)
script.on("message", lambda msg, data: print(f"[Frida] {msg}"))
script.load()
print("[*] SSL bypass injected — all HTTPS traffic is now decryptable!")
print("[*] Keep this window open while chatting in Doubao.")
print("[*] Press Ctrl+C when done.\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

print("\n[*] Frida injection detached.")
