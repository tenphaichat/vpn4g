import os
import json
import base64
import time
import socket
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# --- GIAO DIỆN WEB DASHBOARD & LOGGING REALTIME ---
LOGGING_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xray VLESS Railway Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }
        .card { background: #1e293b; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); max-width: 980px; margin: 0 auto 20px auto; display: flex; flex-direction: column; }
        h2 { margin-top: 0; border-bottom: 1px solid #334155; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; color: #f8fafc; font-size: 1.2rem; flex-wrap: wrap; gap: 8px; }
        .badge { font-size: 13px; color: #4ade80; background: rgba(74, 222, 128, 0.12); padding: 4px 10px; border-radius: 999px; }
        .badge-warn { font-size: 13px; color: #fbbf24; background: rgba(251, 191, 36, 0.15); padding: 6px 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(251, 191, 36, 0.4); }
        .link-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
        .link-input { flex: 1; background: #0f172a; color: #38bdf8; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; font-family: monospace; font-size: 12px; }
        .btn { background: #0284c7; color: white; border: none; border-radius: 6px; padding: 8px 14px; cursor: pointer; font-weight: 600; font-size: 12px; white-space: nowrap; }
        .btn:hover { background: #0369a1; }
        .btn:disabled { background: #475569; cursor: not-allowed; }
        .speed-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 6px; }
        .speed-box { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center; }
        .speed-label { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
        .speed-val { font-size: 22px; font-weight: 700; color: #38bdf8; font-family: monospace; }
        #log-container { background: #090d16; color: #cbd5e1; padding: 15px; border-radius: 8px; overflow-y: auto; font-family: monospace; font-size: 12.5px; height: 420px; border: 1px solid #334155; }
        .log-entry { margin-bottom: 4px; border-bottom: 1px solid #1e293b; padding-bottom: 2px; word-break: break-all; }
        .timestamp { color: #64748b; margin-right: 8px; }
        .type-info { color: #38bdf8; font-weight: bold; }
        .type-error { color: #f87171; font-weight: bold; }
        .type-success { color: #4ade80; font-weight: bold; }
        pre { margin: 5px 0; color: #fde047; background: #1e293b; padding: 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>
            <span>⚡ Speedtest & Vị trí Máy chủ (Railway / VPS)</span>
            <button class="btn" onclick="runSpeedtest()" id="speedtest-btn">Chạy Speedtest Server</button>
        </h2>
        <div id="region-warn" style="display:none;" class="badge-warn"></div>
        <div class="speed-grid">
            <div class="speed-box">
                <div class="speed-label">Vị trí Server (Region)</div>
                <div class="speed-val" id="srv-loc" style="font-size:15px;">Đang kiểm tra...</div>
            </div>
            <div class="speed-box">
                <div class="speed-label">Ping (Cloudflare)</div>
                <div class="speed-val" id="st-ping">-- ms</div>
            </div>
            <div class="speed-box">
                <div class="speed-label">Download Server</div>
                <div class="speed-val" id="st-down">-- Mbps</div>
            </div>
            <div class="speed-box">
                <div class="speed-label">Upload Server</div>
                <div class="speed-val" id="st-up">-- Mbps</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>
            <span>🔗 Link VLESS (Quick Tunnel)</span>
            <button class="btn" onclick="copyAllLinks()" id="copy-all-btn">Copy tất cả</button>
        </h2>
        <div id="links-container">Đang khởi tạo Cloudflare Quick Tunnel...</div>
    </div>

    <div class="card">
        <h2>
            <span>📋 Log Realtime</span>
            <span class="badge">● Đang chạy</span>
        </h2>
        <div id="log-container">Đang chờ log...</div>
    </div>

    <script>
        const logContainer = document.getElementById("log-container");
        const linksContainer = document.getElementById("links-container");
        let lastLogId = 0;
        let currentLinksText = "";

        function copyText(text, btn) {
            navigator.clipboard.writeText(text);
            const old = btn.innerText;
            btn.innerText = "Đã copy!";
            setTimeout(() => btn.innerText = old, 1500);
        }

        function copyAllLinks() {
            if (!currentLinksText) return;
            copyText(currentLinksText, document.getElementById("copy-all-btn"));
        }

        async function fetchServerInfo() {
            try {
                const res = await fetch("/server_info");
                const d = await res.json();
                document.getElementById("srv-loc").innerText = `${d.city || "?"} (${d.country || "?"}) - ${d.ip || ""}`;
                if (d.country && d.country !== "SG" && d.country !== "VN" && d.country !== "HK" && d.country !== "JP" && d.country !== "TW") {
                    const w = document.getElementById("region-warn");
                    w.style.display = "block";
                    w.innerText = `⚠️ Máy chủ đang đặt tại ${d.city}, ${d.country} (khá xa Việt Nam). Trên Railway hãy vào Settings -> Deploy -> Region -> chọn Southeast Asia (Singapore) để giảm ping và tăng tốc!`;
                }
            } catch (e) {}
        }

        async function runSpeedtest() {
            const btn = document.getElementById("speedtest-btn");
            btn.disabled = true;
            btn.innerText = "Đang đo tốc độ (~8 giây)...";
            document.getElementById("st-ping").innerText = "...";
            document.getElementById("st-down").innerText = "...";
            document.getElementById("st-up").innerText = "...";
            try {
                const res = await fetch("/speedtest");
                const d = await res.json();
                document.getElementById("st-ping").innerText = `${d.ping_ms} ms`;
                document.getElementById("st-down").innerText = `${d.download_mbps} Mbps`;
                document.getElementById("st-up").innerText = `${d.upload_mbps} Mbps`;
            } catch (e) {
                document.getElementById("st-down").innerText = "Lỗi";
            } finally {
                btn.disabled = false;
                btn.innerText = "Chạy Speedtest Server";
            }
        }

        async function fetchLinks() {
            try {
                const res = await fetch("/links");
                const data = await res.json();
                if (data.links && data.links.length > 0) {
                    const joined = data.links.join("\\n");
                    if (joined !== currentLinksText) {
                        currentLinksText = joined;
                        linksContainer.innerHTML = data.links.map((l, idx) => `
                            <div class="link-row">
                                <input class="link-input" readonly value="${l.replace(/"/g, '&quot;')}" id="link-${idx}" />
                                <button class="btn" onclick="copyText(document.getElementById('link-${idx}').value, this)">Copy</button>
                            </div>
                        `).join("");
                    }
                }
            } catch (e) {}
        }

        function formatLog(item) {
            let typeClass = "type-info";
            const type = (item.type || "INFO").toUpperCase();
            if (type.includes("ERROR")) typeClass = "type-error";
            if (type.includes("SUCCESS")) typeClass = "type-success";
            let msg = typeof item.text === "object" ? `<pre>${JSON.stringify(item.text, null, 2)}</pre>` : item.text;
            return `<div class="log-entry"><span class="timestamp">[${item.time}]</span><span class="${typeClass}">[${type}]</span> ${msg}</div>`;
        }

        async function fetchLogs() {
            try {
                const res = await fetch(`/logs?last_id=${lastLogId}`);
                const data = await res.json();
                if (data.new_logs.length > 0) {
                    if (logContainer.innerText.includes("Đang chờ")) logContainer.innerHTML = "";
                    logContainer.insertAdjacentHTML('beforeend', data.new_logs.map(formatLog).join(""));
                    lastLogId = data.last_id;
                    logContainer.scrollTop = logContainer.scrollHeight;
                }
            } catch (e) {}
        }

        fetchServerInfo();
        fetchLinks();
        fetchLogs();
        setInterval(fetchLinks, 2000);
        setInterval(fetchLogs, 1000);
    </script>
</body>
</html>
"""

class RealtimeLogger:
    def __init__(self, port=8080, password="admin", max_logs=500):
        self.port = port
        self.password = password
        self.max_logs = max_logs
        self.logs = []
        self.log_sequence = 0
        self.server = None
        self.server_thread = None
        self._lock = threading.Lock()
        self._cached_info = None

    def set_password(self, password):
        self.password = password

    def set_port(self, port):
        if self.server:
            return False  # Không thể đổi port khi server đang chạy
        self.port = port
        return True

    def push_log(self, text, log_type="INFO"):
        with self._lock:
            self.log_sequence += 1
            item = {
                "id": self.log_sequence,
                "time": time.strftime("%H:%M:%S"),
                "type": log_type,
                "text": text
            }
            self.logs.append(item)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)

    def get_server_info(self):
        if self._cached_info:
            return self._cached_info
        try:
            req = urllib.request.Request("https://ipinfo.io/json", headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._cached_info = {
                    "ip": data.get("ip", ""),
                    "city": data.get("city", ""),
                    "region": data.get("region", ""),
                    "country": data.get("country", ""),
                    "org": data.get("org", "")
                }
                return self._cached_info
        except Exception:
            return {"ip": "Unknown", "city": "Unknown", "country": "?"}

    def run_server_speedtest(self):
        # 1. Measure TCP Ping to Cloudflare 1.1.1.1:443
        pings = []
        for _ in range(3):
            t0 = time.perf_counter()
            try:
                with socket.create_connection(("1.1.1.1", 443), timeout=2):
                    pings.append((time.perf_counter() - t0) * 1000.0)
            except Exception:
                pass
        ping_ms = round(min(pings), 1) if pings else 0.0

        # 2. Multi-stream Download test (8 threads, 4 seconds max)
        stop_dl = time.perf_counter() + 4.0
        dl_bytes = [0]
        dl_lock = threading.Lock()

        def dl_worker():
            url = "https://speed.cloudflare.com/__down?bytes=50000000"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            while time.perf_counter() < stop_dl:
                try:
                    with urllib.request.urlopen(req, timeout=4) as r:
                        while time.perf_counter() < stop_dl:
                            chunk = r.read(65536)
                            if not chunk:
                                break
                            with dl_lock:
                                dl_bytes[0] += len(chunk)
                except Exception:
                    break

        t_start_dl = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(dl_worker) for _ in range(8)]
            for f in futures:
                f.result()
        el_dl = max(time.perf_counter() - t_start_dl, 0.1)
        download_mbps = round((dl_bytes[0] * 8) / (el_dl * 1_000_000), 1)

        # 3. Multi-stream Upload test (4 threads, 3 seconds max)
        stop_ul = time.perf_counter() + 3.0
        ul_bytes = [0]
        ul_lock = threading.Lock()
        payload = b"0" * (2 * 1024 * 1024)  # 2MB block

        def ul_worker():
            url = "https://speed.cloudflare.com/__up"
            while time.perf_counter() < stop_ul:
                try:
                    req = urllib.request.Request(url, data=payload, method="POST", headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/octet-stream"})
                    with urllib.request.urlopen(req, timeout=3) as r:
                        r.read()
                    with ul_lock:
                        ul_bytes[0] += len(payload)
                except Exception:
                    break

        t_start_ul = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(ul_worker) for _ in range(4)]
            for f in futures:
                f.result()
        el_ul = max(time.perf_counter() - t_start_ul, 0.1)
        upload_mbps = round((ul_bytes[0] * 8) / (el_ul * 1_000_000), 1)

        res = {"ping_ms": ping_ms, "download_mbps": download_mbps, "upload_mbps": upload_mbps}
        self.push_log(f"[SPEEDTEST] Ping: {ping_ms} ms | Download: {download_mbps} Mbps | Upload: {upload_mbps} Mbps", "SUCCESS")
        return res

    def _create_handler(self):
        # Lưu reference của logger vào handler để nó truy cập được dữ liệu logs/password
        logger_ref = self

        class WebHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return  # Tắt log mặc định của server vào console để đỡ rác

            def check_auth(self):
                if not logger_ref.password: return True
                auth = self.headers.get("Authorization")
                if not auth: return False
                try:
                    decoded = base64.b64decode(auth.split(" ")[1]).decode()
                    return decoded.split(":", 1)[1] == logger_ref.password
                except: return False

            def do_GET(self):
                if not self.check_auth():
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="Login Required"')
                    self.end_headers()
                    self.wfile.write(b"Unauthorized")
                    return

                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(LOGGING_HTML_TEMPLATE.encode("utf-8"))

                elif parsed.path == "/server_info":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(logger_ref.get_server_info()).encode("utf-8"))

                elif parsed.path == "/speedtest":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(logger_ref.run_server_speedtest()).encode("utf-8"))

                elif parsed.path == "/links":
                    links = []
                    if os.path.exists("frp_info.config"):
                        try:
                            with open("frp_info.config", "r", encoding="utf-8") as f:
                                links = [line.strip() for line in f if line.strip()]
                        except Exception:
                            pass
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"links": links}).encode("utf-8"))

                elif parsed.path == "/logs":
                    query = parse_qs(parsed.query)
                    last_id = int(query.get("last_id", [0])[0])
                    
                    with logger_ref._lock:
                        new_logs = [l for l in logger_ref.logs if l["id"] > last_id]
                        resp = {"new_logs": new_logs, "last_id": logger_ref.log_sequence}
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(resp).encode())
        
        return WebHandler

    def start(self):
        """Khởi chạy server trong một thread riêng"""
        if self.server:
            return f"http://localhost:{self.port}"

        def run_server():
            self.server = ThreadingHTTPServer(("0.0.0.0", self.port), self._create_handler())
            self.server.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        return f"http://localhost:{self.port}"

    def stop(self):
        """Dừng server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            return True
        return False

# --- VÍ DỤ SỬ DỤNG TRONG FILE KHÁC ---
if __name__ == "__main__":
    # 1. Khởi tạo
    logger = RealtimeLogger(port=9000, password="123")
    
    # 2. Start
    logger.start()
    
    # 3. Sử dụng
    try:
        while True:
            logger.push_log("Đang xử lý dữ liệu...", "INFO")
            time.sleep(2)
    except KeyboardInterrupt:
        logger.stop()