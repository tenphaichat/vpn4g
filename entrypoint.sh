#!/usr/bin/env bash
set -o pipefail

cd /app || exit 1
export PYTHONUNBUFFERED=1

echo "===================================================="
echo " Xray VLESS-WS Server - Railway Lightweight Mode 1"
echo "===================================================="

cleanup() {
    echo "[*] Stopping Xray & Cloudflared..."
    if [ -n "${CHILD_PID:-}" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
        kill -INT "$CHILD_PID" 2>/dev/null || true
        pkill -TERM -P "$CHILD_PID" 2>/dev/null || true
        sleep 1
        kill -TERM "$CHILD_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup TERM INT EXIT

# Vong lap Supervisor giu Xray + Cloudflared luon song tren Railway (khong can systemd)
while true; do
    python3 -u /app/main.py 2>&1 | tee -a /app/xray-vless.log &
    CHILD_PID=$!
    wait "$CHILD_PID"
    EXIT_CODE=$?
    echo "[SUPERVISOR] main.py exited with code $EXIT_CODE. Restarting in 5s..."
    sleep 5
done
