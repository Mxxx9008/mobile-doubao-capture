#!/bin/bash
# ============================================================
#  豆包抓包一键启动脚本
#  用法: bash start_capture.sh
# ============================================================

set -e

# ---- config ----
ADB_HOST="127.0.0.1:5555"
PROXY_HOST="10.0.2.2"
PROXY_PORT="8080"
MITM_FILE="$HOME/Desktop/doubao_capture_$(date +%Y%m%d_%H%M%S).mitm"
TXT_FILE="${MITM_FILE%.mitm}.txt"
SCRIPT_DIR="$HOME"

# Python 编码（Windows 必须）
export PYTHONIOENCODING=utf-8

# ---- colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

step()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
info()  { echo -e "${CYAN}[*]${NC} $1"; }
error() { echo -e "${RED}[X]${NC} $1"; }

cleanup() {
    echo ""
    warn "Stopping capture..."
    # 恢复代理
    adb -s "$ADB_HOST" shell settings put global http_proxy :0 2>/dev/null || true
    # 杀掉 mitmdump
    if [ -n "$MITM_PID" ]; then
        kill "$MITM_PID" 2>/dev/null && info "mitmdump stopped" || true
    fi
    # 杀掉 frida 注入
    if [ -n "$FRIDA_PID" ]; then
        kill "$FRIDA_PID" 2>/dev/null && info "frida injection stopped" || true
    fi
    echo ""
    info "Capture file: $MITM_FILE"
    info "Run extract when ready:"
    echo "  mitmdump -r \"$MITM_FILE\" --no-http2 > \"$TXT_FILE\""
    echo "  PYTHONIOENCODING=utf-8 python \"$SCRIPT_DIR/extract_references.py\""
    echo ""
    exit 0
}

trap cleanup INT

# ============================================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   豆包抓包工具 v1.0${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ---- Step 1: Connect ADB ----
step "Connecting to emulator ($ADB_HOST)..."
adb connect "$ADB_HOST" 2>&1 | grep -v "^$" || true
sleep 1

if ! adb -s "$ADB_HOST" shell echo ok > /dev/null 2>&1; then
    error "ADB connection failed! Is the emulator running?"
    exit 1
fi
info "ADB connected"

# ---- Step 2: Frida-server ----
step "Starting frida-server as root..."
adb -s "$ADB_HOST" root 2>&1 | grep -v "^$" || true
sleep 1

# Kill old frida-server if any
adb -s "$ADB_HOST" shell "killall frida-server" 2>/dev/null || true
sleep 1

adb -s "$ADB_HOST" shell "/data/local/tmp/frida-server &" 2>&1 | grep -v "^$" || true
sleep 2

if adb -s "$ADB_HOST" shell "pidof frida-server" > /dev/null 2>&1; then
    info "frida-server is running"
else
    error "frida-server failed to start! Push it first:"
    echo "  adb push frida-server /data/local/tmp/"
    echo "  adb shell chmod 755 /data/local/tmp/frida-server"
    exit 1
fi

# ---- Step 3: mitmproxy ----
step "Starting mitmproxy..."
mitmdump -w "$MITM_FILE" &
MITM_PID=$!
sleep 2

if kill -0 "$MITM_PID" 2>/dev/null; then
    info "mitmdump running (PID: $MITM_PID)"
else
    error "mitmdump failed to start!"
    exit 1
fi

# ---- Step 4: Set proxy ----
step "Setting emulator proxy ($PROXY_HOST:$PROXY_PORT)..."
adb -s "$ADB_HOST" shell settings put global http_proxy "${PROXY_HOST}:${PROXY_PORT}"
info "Proxy set"

# ---- Step 5: Frida inject ----
step "Injecting SSL bypass into Doubao..."
python "$SCRIPT_DIR/frida_keepalive.py" &
FRIDA_PID=$!
sleep 3

if kill -0 "$FRIDA_PID" 2>/dev/null; then
    info "Frida injection active (PID: $FRIDA_PID)"
else
    warn "Frida injection may have failed. Is Doubao open?"
    warn "Open Doubao and re-run: python frida_keepalive.py"
fi

# ---- Done ----
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   ALL SET - Go chat in Doubao!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
info "Capture file: $MITM_FILE"
echo -e "${YELLOW}Press Enter when you're done chatting to extract data...${NC}"
read -r

# ---- Stop & extract ----
echo ""
step "Stopping Frida injection..."
kill "$FRIDA_PID" 2>/dev/null || true
sleep 1

step "Stopping mitmdump..."
kill "$MITM_PID" 2>/dev/null || true
sleep 2

step "Restoring emulator proxy..."
adb -s "$ADB_HOST" shell settings put global http_proxy :0
info "Proxy restored"

# ---- Extract ----
step "Converting .mitm to text..."
PYTHONIOENCODING=utf-8 mitmdump -r "$MITM_FILE" --no-http2 > "$TXT_FILE"
info "Text dump: $TXT_FILE"

step "Extracting references..."
PYTHONIOENCODING=utf-8 python "$SCRIPT_DIR/extract_references.py" "$TXT_FILE"
info "Done!"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Capture complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
info "Output: $TXT_FILE"
info "JSON files are on your Desktop"
