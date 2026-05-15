#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
doubao_qa.py — 一键向豆包提问，自动抓取回答 + 参考文献
用法: python doubao_qa.py "你的问题"
输出: 桌面 doubao_qa_result_{timestamp}.json
"""

import subprocess, time, sys, os, json, threading, signal, re
from datetime import datetime
from collections import Counter

# ===== 配置 =====
ADB_PATH = r"C:\Users\31760\platform-tools\platform-tools\adb.exe"
FRIDA_SERVER_PATH = "/data/local/tmp/frida-server"
DOUBAO_PACKAGE = "com.larus.nova"
MITMDUMP = r"C:\Users\31760\AppData\Local\Programs\Python\Python313\Scripts\mitmdump"
PYTHON = r"C:\Users\31760\AppData\Local\Programs\Python\Python313\python.exe"
ADB_HOST = "127.0.0.1:5555"
PROXY_HOST = "10.0.2.2"
PROXY_PORT = "8080"

# SSL bypass JS (inline, no file dependency)
SSL_BYPASS_JS = """
Java.perform(function() {
    var TrustManager = Java.registerClass({
        name: "com.frida.PinningBypass",
        implements: [Java.use("javax.net.ssl.X509TrustManager")],
        methods: {
            checkClientTrusted: function(chain, authType) {},
            checkServerTrusted: function(chain, authType) {},
            getAcceptedIssuers: function() { return []; }
        }
    });
    var TMArray = Java.array("javax.net.ssl.TrustManager", [TrustManager.$new()]);

    try {
        var SSLContext = Java.use("javax.net.ssl.SSLContext");
        SSLContext.init.overload("[Ljavax.net.ssl.KeyManager;", "[Ljavax.net.ssl.TrustManager;", "java.security.SecureRandom").implementation = function(kmf, tm, sr) {
            this.init(kmf, TMArray, sr);
        };
    } catch(e) { console.log("[Frida] SSLContext hook failed: " + e); }

    try {
        var CertificatePinner = Java.use("okhttp3.CertificatePinner");
        CertificatePinner.check.overload("java.lang.String", "java.util.List").implementation = function(hostname, peerCertificates) {
            return;
        };
        CertificatePinner.check.overload("java.lang.String", "java.security.cert.Certificate").implementation = function(hostname, peerCertificate) {
            return;
        };
    } catch(e) { console.log("[Frida] CertificatePinner not found: " + e); }

    console.log("[Frida] SSL bypass active");
});
"""

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["MSYS_NO_PATHCONV"] = "1"


def log(msg, level="INFO"):
    prefix = {"INFO": "[*]", "OK": "[+]", "WARN": "[!]", "ERR": "[X]"}
    print(f"{prefix.get(level, '[*]')} {msg}")


def adb(cmd, timeout=15):
    """Run an ADB command, return stdout."""
    full = [ADB_PATH, "-s", ADB_HOST] + cmd.split()
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def adb_shell(cmd, timeout=15):
    """Run adb shell command."""
    return adb(f"shell {cmd}", timeout=timeout)


def connect_adb():
    """Ensure ADB is connected."""
    log("Connecting ADB...")
    out = subprocess.run([ADB_PATH, "connect", ADB_HOST], capture_output=True, text=True).stdout
    if "connected" not in out and "already" not in out:
        log(f"ADB connection failed: {out}", "ERR")
        return False
    status = adb_shell("echo ok")
    if "ok" not in status:
        log("ADB shell check failed", "ERR")
        return False
    log("ADB connected", "OK")
    return True


def setup_frida():
    """Start frida-server and inject SSL bypass."""
    # Start frida-server as root
    log("Starting frida-server...")
    subprocess.run([ADB_PATH, "-s", ADB_HOST, "root"], capture_output=True, text=True)
    time.sleep(1)
    adb_shell("killall frida-server", timeout=5)
    time.sleep(1)

    adb_shell(f"nohup {FRIDA_SERVER_PATH} > /dev/null 2>&1 &")
    time.sleep(3)

    pid = adb_shell("pidof frida-server")
    if not pid:
        log("frida-server failed to start!", "ERR")
        return None
    log(f"frida-server running (PID: {pid})", "OK")

    # Inject SSL bypass via Frida Python API
    try:
        import frida
        log("Injecting SSL bypass...")
        device = frida.get_usb_device()
        session = device.attach(DOUBAO_PACKAGE)
        script = session.create_script(SSL_BYPASS_JS)
        script.on("message", lambda msg, data: None)  # silent
        script.load()
        log("SSL bypass injected", "OK")
        return session
    except Exception as e:
        log(f"Frida injection failed: {e}", "WARN")
        log("Continuing anyway (check if Doubao is open)", "WARN")
        return None


def set_proxy(enable=True):
    """Set/clear global proxy on emulator."""
    if enable:
        adb_shell(f"settings put global http_proxy {PROXY_HOST}:{PROXY_PORT}")
        log(f"Proxy set: {PROXY_HOST}:{PROXY_PORT}", "OK")
    else:
        adb_shell("settings put global http_proxy :0")
        log("Proxy cleared", "OK")


def ensure_doubao_open():
    """Make sure Doubao is in the foreground."""
    # Check if Doubao is running
    pkg = adb_shell("pidof com.larus.nova")
    if not pkg:
        log("Doubao not running, launching...", "WARN")
        adb_shell("monkey -p com.larus.nova -c android.intent.category.LAUNCHER 1")
        time.sleep(5)
        log("Doubao launched", "OK")
    else:
        # Bring to foreground
        adb_shell("monkey -p com.larus.nova -c android.intent.category.LAUNCHER 1")
        time.sleep(2)
        log("Doubao in foreground", "OK")


def find_input_coordinates():
    """Try to find the chat input field using uiautomator."""
    try:
        adb_shell("rm /sdcard/ui.xml", timeout=5)
        adb_shell("uiautomator dump /sdcard/ui.xml", timeout=10)
        time.sleep(2)
        # Pull and parse
        out = adb_shell("cat /sdcard/ui.xml", timeout=5)
        if not out:
            return None

        # Look for EditText (input field)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(out)
        for node in root.iter():
            cls = node.attrib.get("class", "")
            if "EditText" in cls:
                bounds = node.attrib.get("bounds", "")
                # Parse bounds: [left,top][right,bottom]
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if m:
                    x = (int(m.group(1)) + int(m.group(3))) // 2
                    y = (int(m.group(2)) + int(m.group(4))) // 2
                    log(f"Found input field at ({x}, {y})")
                    return (x, y)
            # Look for send button (ImageView/Button near bottom-right)
        return None
    except Exception as e:
        log(f"UI dump failed: {e}", "WARN")
        return None


def send_question(text):
    """Type question and send via ADB UI automation."""
    log(f"Sending: {text[:50]}...")

    # Try to find input coordinates dynamically
    coords = find_input_coordinates()
    if coords:
        input_x, input_y = coords
        # Send button is usually 100-150px to the right of input center
        send_x, send_y = min(input_x + 150, 850), input_y
    else:
        # Fallback: center-bottom for input, right-bottom for send
        # Resolution 900x1600, input at ~(450, 1480), send at ~(830, 1480)
        input_x, input_y = 450, 1480
        send_x, send_y = 830, 1480
        log("Using fallback coordinates", "WARN")

    # Tap input field
    adb_shell(f"input tap {input_x} {input_y}")
    time.sleep(0.5)

    # Clear any existing text (select all + delete)
    adb_shell("input keyevent 29 --longpress")  # Ctrl+A equivalent
    time.sleep(0.2)

    # Type via clipboard for reliable Chinese support
    # Escape special characters for shell
    safe_text = text.replace("'", "'\\''").replace('"', '\\"')

    # Use Android clipboard API
    escaped = text.replace("'", "\\'").replace('"', '\\"').replace("\\", "\\\\")
    adb_shell(f"cmd clipboard set \"{escaped}\"", timeout=5)
    time.sleep(0.3)
    # Paste
    adb_shell("input keyevent 279")  # KEYCODE_PASTE
    time.sleep(0.5)

    # Tap send button
    adb_shell(f"input tap {send_x} {send_y}")
    time.sleep(1)
    log("Question sent", "OK")
    return True


def run_capture(capture_file, stop_event):
    """Run mitmdump in background until stop_event is set."""
    subprocess.run(
        [MITMDUMP, "-w", capture_file, "--set", "block_global=false"],
        capture_output=True,
        timeout=120
    )


def extract_answer_from_capture(capture_file):
    """Extract QA data from mitmdump binary capture."""
    log("Extracting data from capture...")

    # Convert .mitm to text
    txt_file = capture_file.replace(".mitm", ".txt")
    try:
        r = subprocess.run(
            [MITMDUMP, "-r", capture_file, "--no-http2"],
            capture_output=True, text=True, timeout=30
        )
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(r.stdout)
    except Exception as e:
        log(f"mitmdump extraction failed: {e}", "ERR")
        return None

    # Parse SSE events (same logic as extract_references.py)
    msg_refs = {}
    msg_queries = {}
    msg_answers = {}
    msg_mode = {}
    msg_conv = {}
    msg_question = {}

    with open(txt_file, "r", encoding="utf-8") as f:
        content = f.read()

    for line in content.split("\n"):
        s = line.strip()
        if not s.startswith("data: {"):
            continue
        try:
            obj = json.loads(s[6:])
        except json.JSONDecodeError:
            continue

        cmd = obj.get("cmd")

        if cmd == 50200:
            try:
                n = obj["downlink_body"]["bot_reply_loading_update_notify"]
                ext = n["ext"]
                mid = ext.get("message_id", "")
                cid = n.get("conversation_id", "")
                if not mid:
                    continue
                msg_conv[mid] = cid
                ai = ext.get("agent_intention", "")
                msg_mode[mid] = "browsing" if "browsing" in ai else "chat"

                rs = ext.get("search_references", "")
                if rs and len(rs) > 5:
                    try:
                        refs = json.loads(rs)
                    except json.JSONDecodeError:
                        continue
                    if mid not in msg_refs:
                        msg_refs[mid] = []
                    for r in refs:
                        tc = r["text_card"]
                        msg_refs[mid].append({
                            "title": tc.get("title", ""),
                            "url": tc.get("url", ""),
                            "sitename": tc.get("sitename", ""),
                            "summary": tc.get("summary", "")[:500]
                        })

                qs = ext.get("search_queries", "")
                if qs and mid not in msg_queries:
                    try:
                        msg_queries[mid] = json.loads(qs)
                    except json.JSONDecodeError:
                        pass
            except (KeyError, TypeError):
                continue

        elif cmd == 300:
            try:
                body = obj["downlink_body"].get("fetch_chunk_message_downlink_body", {})
                mid = body.get("message_id", "")
                if not mid:
                    continue
                inner = json.loads(body.get("content", "{}"))
                text = inner.get("text", "").replace("\\n", "\n").replace("\\t", "\t")
                msg_answers[mid] = msg_answers.get(mid, "") + text

                mq = body.get("ext", {}).get("mult_query", "")
                if mq and mid not in msg_question:
                    msg_question[mid] = mq
                    if mid not in msg_queries:
                        msg_queries[mid] = [mq]
            except (KeyError, TypeError, json.JSONDecodeError):
                continue

    if not msg_answers:
        log("No answers found in capture!", "ERR")
        return None

    # Build result
    results = []
    for mid in sorted(msg_answers.keys()):
        refs_raw = msg_refs.get(mid, [])
        seen = set()
        refs = []
        for r in refs_raw:
            if r["url"] not in seen:
                seen.add(r["url"])
                refs.append(r)

        queries = msg_queries.get(mid, [])
        question = msg_question.get(mid, queries[0] if queries else "")

        sc = dict(Counter(r["sitename"] for r in refs))

        results.append({
            "task_id": mid,
            "question": question,
            "mode": msg_mode.get(mid, "chat"),
            "search_keywords": queries,
            "search_sources": refs,
            "search_summary": f"搜索 {len(queries)} 个关键词，参考 {len(refs)} 篇资料",
            "answer": msg_answers.get(mid, ""),
            "total_references": len(refs),
            "statistics": {
                "sitename_counts": sc,
                "brands": [],
                "token_usage": {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
            }
        })

    # Cleanup temp txt
    try:
        os.remove(txt_file)
    except OSError:
        pass

    return results


def main():
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    if not question:
        print("用法: python doubao_qa.py \"你的问题\"")
        print("示例: python doubao_qa.py \"iPhone 17什么时候发布\"")
        sys.exit(1)

    log(f"Question: {question}")

    # Step 1: Connect ADB
    if not connect_adb():
        sys.exit(1)

    # Step 2: Check Doubao
    ensure_doubao_open()

    # Step 3: Setup Frida
    session = setup_frida()

    # Step 4: Set proxy
    set_proxy(True)

    # Step 5: Start capture
    capture_file = os.path.expanduser(f"~/Desktop/doubao_qa_capture_{int(time.time())}.mitm")
    log(f"Capture file: {capture_file}")

    capture_proc = subprocess.Popen(
        [MITMDUMP, "-w", capture_file, "--set", "block_global=false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    log(f"mitmdump running (PID: {capture_proc.pid})", "OK")

    # Step 6: Send question via UI automation
    send_question(question)

    # Step 7: Wait for response
    log("Waiting for Doubao to answer...")
    time.sleep(5)  # Initial wait

    # Monitor - wait for answer completion
    max_wait = 120
    waited = 5
    while waited < max_wait:
        # Check if we've received some data
        if os.path.exists(capture_file) and os.path.getsize(capture_file) > 1000:
            # Quick check: see if response seems complete
            log(f"Got data ({os.path.getsize(capture_file)} bytes), waiting more...")
            time.sleep(5)
            waited += 5
        else:
            time.sleep(2)
            waited += 2

    # Step 8: Stop capture
    log("Stopping capture...")
    capture_proc.terminate()
    time.sleep(2)
    if capture_proc.poll() is None:
        capture_proc.kill()

    # Step 9: Clear proxy
    set_proxy(False)

    # Step 10: Extract and output
    results = extract_answer_from_capture(capture_file)

    if not results:
        log("No results extracted. Check if capture was successful.", "ERR")
        log(f"Capture file saved at: {capture_file}", "INFO")
        sys.exit(1)

    # Write output
    output_file = os.path.expanduser(f"~/Desktop/doubao_qa_result_{int(time.time())}.json")
    output = {
        "code": 0,
        "msg": "success",
        "data": {
            "question": question,
            "generated_at": datetime.now().isoformat(),
            "results": results
        }
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log(f"Done! Result saved to: {output_file}", "OK")

    # Print summary
    for r in results:
        print(f"\n  Q: {r['question'][:80]}")
        print(f"  Mode: {r['mode']} | Refs: {r['total_references']} | Answer: {len(r['answer'])} chars")
        if r['statistics']['sitename_counts']:
            print(f"  Sources: {dict(list(r['statistics']['sitename_counts'].items())[:5])}")

    # Cleanup capture if successful
    try:
        os.remove(capture_file)
    except OSError:
        pass

    # Keep Frida alive a bit
    if session:
        time.sleep(2)


if __name__ == "__main__":
    main()
