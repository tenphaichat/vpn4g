import os
import json
import uuid
import base64
import time
import socket
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DEFAULT_ENV_CONFIG = {
    "RUN_MODE": "quick_tunnel",
    "PROTOCOL": "vless",
    "PORT_MODE": "both",
    "TRANSPORT": "websocket",
    "XHTTP_MODE": "packet-up",
    "PORT": "127.0.0.1:8888",
    "XRAY_UUID": "",
    "FAKE_SNI": "api24-normal-alisg.tiktokv.com#FreeTiktok,172.67.168.158#FreeVina Ko Nen",
    "WS_PATH": "/vless",
    "WS_HOST": "trycloudflare.com",
    "TUNNEL_TOKEN": "",
    "COUNTRY_CODE": "",
    "ENABLE_WARP": "false",
    "WEBHOOK_URL": "",
}

# --- GIAO DIỆN WEB DASHBOARD & LOGGING REALTIME ---
LOGGING_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xray VLESS / VMess Dashboard</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #0f172a; color: #e2e8f0; margin: 0; padding: 16px; }
        .card { background: #1e293b; padding: 1.25rem 1.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); max-width: 1000px; margin: 0 auto 18px auto; display: flex; flex-direction: column; border: 1px solid #334155; }
        h2 { margin-top: 0; border-bottom: 1px solid #334155; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; color: #f8fafc; font-size: 1.15rem; flex-wrap: wrap; gap: 8px; }
        .badge { font-size: 12px; color: #4ade80; background: rgba(74, 222, 128, 0.12); padding: 4px 10px; border-radius: 999px; font-weight: 600; }
        .badge-warn { font-size: 13px; color: #fbbf24; background: rgba(251, 191, 36, 0.15); padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(251, 191, 36, 0.4); }
        .badge-proto { font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 6px; min-width: 58px; text-align: center; }
        .proto-vless { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }
        .proto-vmess { background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }
        .sub-box { background: #0f172a; border: 1px solid #0284c7; border-radius: 8px; padding: 12px; margin-bottom: 14px; }
        .sub-title { font-size: 13px; font-weight: 600; color: #38bdf8; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; }
        .sub-hint { font-size: 11.5px; color: #94a3b8; margin-top: 6px; }
        .toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
        .link-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
        .link-input { flex: 1; background: #0f172a; color: #38bdf8; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; font-family: monospace; font-size: 12px; min-width: 0; }
        .btn { background: #0284c7; color: white; border: none; border-radius: 6px; padding: 8px 13px; cursor: pointer; font-weight: 600; font-size: 12px; white-space: nowrap; transition: 0.15s; }
        .btn:hover { background: #0369a1; }
        .btn:disabled { background: #475569; cursor: not-allowed; }
        .btn-green { background: #059669; }
        .btn-green:hover { background: #047857; }
        .btn-purple { background: #7c3aed; }
        .btn-purple:hover { background: #6d28d9; }
        .btn-amber { background: #d97706; }
        .btn-amber:hover { background: #b45309; }
        .speed-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 4px; }
        .speed-box { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center; }
        .speed-label { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
        .speed-val { font-size: 20px; font-weight: 700; color: #38bdf8; font-family: monospace; }
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
        .form-group { display: flex; flex-direction: column; gap: 5px; }
        .form-group.full { grid-column: 1 / -1; }
        .form-group label { font-size: 12px; color: #cbd5e1; font-weight: 600; }
        .form-control { background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; font-size: 13px; font-family: inherit; }
        .form-control:focus { outline: none; border-color: #38bdf8; }
        .mode-help { font-size: 12px; color: #94a3b8; background: #0f172a; border-left: 3px solid #38bdf8; padding: 8px 12px; border-radius: 4px; margin-bottom: 12px; }
        #log-container { background: #090d16; color: #cbd5e1; padding: 14px; border-radius: 8px; overflow-y: auto; font-family: monospace; font-size: 12px; height: 340px; border: 1px solid #334155; }
        .log-entry { margin-bottom: 4px; border-bottom: 1px solid #1e293b; padding-bottom: 2px; word-break: break-all; }
        .timestamp { color: #64748b; margin-right: 8px; }
        .type-info { color: #38bdf8; font-weight: bold; }
        .type-error { color: #f87171; font-weight: bold; }
        .type-success { color: #4ade80; font-weight: bold; }
        .status-toast { font-size: 12.5px; color: #4ade80; font-weight: 600; margin-left: 8px; }
    </style>
</head>
<body>
    <!-- CARD 1: SPEEDTEST & SERVER REGION -->
    <div class="card">
        <h2>
            <span>⚡ Speedtest & Vị trí Máy chủ (Railway / VPS)</span>
            <button class="btn" onclick="runSpeedtest()" id="speedtest-btn">Chạy Speedtest Server</button>
        </h2>
        <div id="region-warn" style="display:none;" class="badge-warn"></div>
        <div class="speed-grid">
            <div class="speed-box">
                <div class="speed-label">Vị trí Server (Region)</div>
                <div class="speed-val" id="srv-loc" style="font-size:14px;">Đang kiểm tra...</div>
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

    <!-- CARD 2: SUBSCRIPTION LINK & VLESS/VMESS LINKS -->
    <div class="card">
        <h2>
            <span>🔗 Link Subscription (Sub) & Cấu Hình VLESS / VMess</span>
            <span id="action-status" class="status-toast"></span>
        </h2>

        <div class="sub-box">
            <div class="sub-title">
                <span>📲 Link Sub Tự Động Cập Nhật (Shadowrocket / v2rayNG / v2rayN / NekoBox / Sing-box)</span>
            </div>
            <div class="link-row" style="margin-bottom:0;">
                <input class="link-input" readonly id="sub-url-input" value="" />
                <button class="btn btn-green" onclick="copyText(document.getElementById('sub-url-input').value, this)">Copy Link Sub</button>
                <button class="btn" onclick="window.open(document.getElementById('sub-url-input').value + '?raw=1', '_blank')">Xem Raw</button>
            </div>
            <div class="sub-hint">
                💡 Chỉ cần thêm <b>Link Sub</b> này vào app VPN 1 lần duy nhất. Khi đổi Tunnel mới hoặc tạo VMess/VLESS mới, bạn chỉ cần bấm <b>"Cập nhật Sub (Update Subscription)"</b> trên app là tự lấy toàn bộ link mới!
            </div>
        </div>

        <div class="toolbar">
            <button class="btn btn-amber" onclick="triggerAction('new_tunnel', this)">🔄 Đổi Tunnel Mới (Làm mới Link)</button>
            <button class="btn btn-purple" onclick="triggerAction('create_vmess', this)">➕ Tạo VMess + VLESS Mới</button>
            <button class="btn" onclick="triggerAction('new_uuid', this)">🎲 Đổi UUID Mới & Tạo Lại Link</button>
            <button class="btn btn-green" onclick="copyAllLinks()" id="copy-all-btn">📋 Copy Tất Cả Link</button>
        </div>

        <div id="links-container">Đang khởi tạo và lấy danh sách link...</div>
    </div>

    <!-- CARD 3: XRAY SETTINGS & MODE 1-2-3 -->
    <div class="card">
        <h2>
            <span>⚙️ Cài Đặt Xray & Chế Độ Chạy (Mode 1 - 2 - 3)</span>
            <button class="btn btn-green" onclick="saveConfig()" id="save-cfg-btn">💾 Lưu Cấu Hình & Khởi Động Lại Xray</button>
        </h2>

        <div id="mode-desc" class="mode-help"></div>

        <div class="form-grid">
            <div class="form-group">
                <label>Chế độ chạy (RUN_MODE)</label>
                <select class="form-control" id="cfg-RUN_MODE" onchange="updateModeUI()">
                    <option value="quick_tunnel">Mode 1: Quick Tunnel (trycloudflare.com - Không cần domain)</option>
                    <option value="named_tunnel">Mode 2: Named Tunnel (Domain cố định + Cloudflare Token)</option>
                    <option value="direct">Mode 3: Direct Mode (Trỏ IP trực tiếp qua Cloudflare Port 80)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Giao thức xuất link (PROTOCOL)</label>
                <select class="form-control" id="cfg-PROTOCOL">
                    <option value="both">Cả VLESS + VMess (Song song cả 2 loại link)</option>
                    <option value="vless">Chỉ VLESS (Nhẹ & tốc độ tối đa)</option>
                    <option value="vmess">Chỉ VMess (Chuẩn vmess:// V2Ray)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Chế độ Cổng xuất link (PORT_MODE)</label>
                <select class="form-control" id="cfg-PORT_MODE">
                    <option value="both">Cả Port 443 (TLS) & Port 80 (Non-TLS)</option>
                    <option value="443">Chỉ Port 443 (TLS)</option>
                    <option value="80">Chỉ Port 80 (Non-TLS)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Truyền tải (TRANSPORT)</label>
                <select class="form-control" id="cfg-TRANSPORT">
                    <option value="websocket">WebSocket (WS - Ổn định nhất)</option>
                    <option value="xhttp">xHTTP (SplitHTTP)</option>
                    <option value="websocket,xhttp">Cả WebSocket + xHTTP</option>
                </select>
            </div>

            <div class="form-group full">
                <label>Danh sách Bug Host / SNI nền (FAKE_SNI - cách nhau bởi dấu phẩy, kèm #Tên)</label>
                <input class="form-control" id="cfg-FAKE_SNI" placeholder="api24-normal-alisg.tiktokv.com#FreeTiktok,172.67.168.158#FreeVina Ko Nen" />
            </div>

            <div class="form-group">
                <label>XRAY UUID (ID kết nối)</label>
                <div style="display:flex; gap:6px;">
                    <input class="form-control" style="flex:1;" id="cfg-XRAY_UUID" />
                    <button class="btn" type="button" onclick="randomizeUuidInput()">🎲 Random</button>
                </div>
            </div>

            <div class="form-group">
                <label>Đường dẫn WebSocket (WS_PATH)</label>
                <input class="form-control" id="cfg-WS_PATH" placeholder="/vless" />
            </div>

            <div class="form-group" id="grp-WS_HOST">
                <label>Tên miền / WS_HOST (Dùng cho Mode 2 & Mode 3)</label>
                <input class="form-control" id="cfg-WS_HOST" placeholder="trycloudflare.com hoặc sub.domain.com" />
            </div>

            <div class="form-group" id="grp-TUNNEL_TOKEN">
                <label>Cloudflare Tunnel Token (TUNNEL_TOKEN - Bắt buộc cho Mode 2)</label>
                <input class="form-control" id="cfg-TUNNEL_TOKEN" placeholder="eyJhIjoi..." />
            </div>

            <div class="form-group">
                <label>Cổng lắng nghe nội bộ Xray (PORT)</label>
                <input class="form-control" id="cfg-PORT" placeholder="127.0.0.1:8888 (Mode 1/2) hoặc 0.0.0.0:80 (Mode 3)" />
            </div>

            <div class="form-group">
                <label>Mã Quốc Gia hiển thị cờ (COUNTRY_CODE, VD: SG, VN)</label>
                <input class="form-control" id="cfg-COUNTRY_CODE" placeholder="SG" />
            </div>

            <div class="form-group">
                <label>Cloudflare WARP Outbound (ENABLE_WARP)</label>
                <select class="form-control" id="cfg-ENABLE_WARP">
                    <option value="false">Tắt (Mặc định - Nhanh nhất)</option>
                    <option value="true">Bật (Ẩn IP Server qua Cloudflare WARP)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Webhook URL (Tùy chọn gửi link tự động)</label>
                <input class="form-control" id="cfg-WEBHOOK_URL" placeholder="https://discord.com/api/webhooks/..." />
            </div>
        </div>
    </div>

    <!-- CARD 4: REALTIME LOGS -->
    <div class="card">
        <h2>
            <span>📋 Log Hệ Thống Realtime</span>
            <span class="badge">● Đang hoạt động</span>
        </h2>
        <div id="log-container">Đang chờ log...</div>
    </div>

    <script>
        const logContainer = document.getElementById("log-container");
        const linksContainer = document.getElementById("links-container");
        const subUrlInput = document.getElementById("sub-url-input");
        subUrlInput.value = window.location.origin + "/sub";

        let lastLogId = 0;
        let currentLinksText = "";

        function showToast(msg) {
            const el = document.getElementById("action-status");
            el.innerText = msg;
            setTimeout(() => { if (el.innerText === msg) el.innerText = ""; }, 5000);
        }

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

        function randomizeUuidInput() {
            if (crypto && crypto.randomUUID) {
                document.getElementById("cfg-XRAY_UUID").value = crypto.randomUUID();
            } else {
                const s4 = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1);
                document.getElementById("cfg-XRAY_UUID").value = `${s4()}${s4()}-${s4()}-4${s4().substr(0,3)}-${s4()}-${s4()}${s4()}${s4()}`;
            }
        }

        function updateModeUI() {
            const mode = document.getElementById("cfg-RUN_MODE").value;
            const desc = document.getElementById("mode-desc");
            const grpHost = document.getElementById("grp-WS_HOST");
            const grpToken = document.getElementById("grp-TUNNEL_TOKEN");

            if (mode === "quick_tunnel") {
                desc.innerHTML = "<b>Mode 1 (Quick Tunnel):</b> Tự động tạo domain <code>*.trycloudflare.com</code> miễn phí, không cần tên miền riêng. Phù hợp nhất cho Railway & VPS. Kết hợp với <b>Link Sub</b> ở trên để tự động cập nhật khi tên miền đổi.";
                grpToken.style.display = "none";
                grpHost.style.display = "none";
            } else if (mode === "named_tunnel") {
                desc.innerHTML = "<b>Mode 2 (Named Tunnel):</b> Sử dụng tên miền riêng cố định qua Cloudflare Zero Trust. Link không bao giờ thay đổi khi khởi động lại. Cần điền <b>WS_HOST</b> (ví dụ <code>vpn.tenmien.com</code>) và <b>TUNNEL_TOKEN</b>.";
                grpToken.style.display = "flex";
                grpHost.style.display = "flex";
            } else {
                desc.innerHTML = "<b>Mode 3 (Direct Mode):</b> Kết nối trực tiếp qua DNS Cloudflare (Bật đám mây cam Proxied, SSL/TLS đặt <b>Flexible</b>) tới cổng 80 của VPS. Cần điền <b>WS_HOST</b> là tên miền đã trỏ IP và đặt <b>PORT</b> là <code>0.0.0.0:80</code>.";
                grpToken.style.display = "none";
                grpHost.style.display = "flex";
            }
        }

        async function loadConfig() {
            try {
                const res = await fetch("/config");
                const cfg = await res.json();
                const keys = ["RUN_MODE", "PROTOCOL", "PORT_MODE", "TRANSPORT", "FAKE_SNI", "XRAY_UUID", "WS_PATH", "WS_HOST", "TUNNEL_TOKEN", "PORT", "COUNTRY_CODE", "ENABLE_WARP", "WEBHOOK_URL"];
                keys.forEach(k => {
                    const el = document.getElementById("cfg-" + k);
                    if (el && cfg[k] !== undefined) el.value = cfg[k];
                });
                updateModeUI();
            } catch (e) {}
        }

        async function saveConfig() {
            const btn = document.getElementById("save-cfg-btn");
            btn.disabled = true;
            btn.innerText = "⏳ Đang lưu & khởi động lại Xray...";
            const keys = ["RUN_MODE", "PROTOCOL", "PORT_MODE", "TRANSPORT", "FAKE_SNI", "XRAY_UUID", "WS_PATH", "WS_HOST", "TUNNEL_TOKEN", "PORT", "COUNTRY_CODE", "ENABLE_WARP", "WEBHOOK_URL"];
            const payload = {};
            keys.forEach(k => {
                const el = document.getElementById("cfg-" + k);
                if (el) payload[k] = el.value.trim();
            });
            if (payload.RUN_MODE === "quick_tunnel" && !payload.WS_HOST) {
                payload.WS_HOST = "trycloudflare.com";
            }
            try {
                const res = await fetch("/config", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payload)
                });
                const d = await res.json();
                showToast(d.message || "✅ Đã lưu cấu hình & khởi động lại Xray!");
                currentLinksText = "";
                linksContainer.innerHTML = "⏳ Đang áp dụng cấu hình mới và tạo lại link (~4 giây)...";
            } catch (e) {
                showToast("❌ Lỗi khi lưu cấu hình");
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerText = "💾 Lưu Cấu Hình & Khởi Động Lại Xray";
                    fetchLinks();
                }, 3000);
            }
        }

        async function triggerAction(actionName, btn) {
            const oldText = btn.innerText;
            btn.disabled = true;
            btn.innerText = "⏳ Đang xử lý...";
            currentLinksText = "";
            linksContainer.innerHTML = "⏳ Đang tạo lại Tunnel / Link mới (~4 giây)...";
            try {
                const res = await fetch("/action", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({action: actionName})
                });
                const d = await res.json();
                showToast(d.message || "✅ Đã thực hiện!");
                await loadConfig();
            } catch (e) {
                showToast("❌ Có lỗi xảy ra");
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerText = oldText;
                    fetchLinks();
                }, 3500);
            }
        }

        async function fetchServerInfo() {
            try {
                const res = await fetch("/server_info");
                const d = await res.json();
                document.getElementById("srv-loc").innerText = `${d.city || "?"} (${d.country || "?"}) - ${d.ip || ""}`;
                if (d.country && !["SG", "VN", "HK", "JP", "TW"].includes(d.country)) {
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
                        linksContainer.innerHTML = data.links.map((l, idx) => {
                            const isVmess = l.startsWith("vmess://");
                            const badgeClass = isVmess ? "proto-vmess" : "proto-vless";
                            const badgeLabel = isVmess ? "VMess" : "VLESS";
                            return `
                                <div class="link-row">
                                    <span class="badge-proto ${badgeClass}">${badgeLabel}</span>
                                    <input class="link-input" readonly value="${l.replace(/"/g, '&quot;')}" id="link-${idx}" />
                                    <button class="btn" onclick="copyText(document.getElementById('link-${idx}').value, this)">Copy</button>
                                </div>
                            `;
                        }).join("");
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

        loadConfig();
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
    def __init__(self, port=8080, password="admin", max_logs=500, action_callback=None):
        self.port = port
        self.password = password
        self.max_logs = max_logs
        self.action_callback = action_callback
        self.logs = []
        self.log_sequence = 0
        self.server = None
        self.server_thread = None
        self.extra_servers = []
        self._lock = threading.Lock()
        self._cached_info = None

    def set_password(self, password):
        self.password = password

    def set_port(self, port):
        if self.server:
            return False
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

    def get_links_list(self):
        links = []
        if os.path.exists("frp_info.config"):
            try:
                with open("frp_info.config", "r", encoding="utf-8") as f:
                    links = [line.strip() for line in f if line.strip()]
            except Exception:
                pass
        return links

    def get_env_config(self):
        cfg = dict(DEFAULT_ENV_CONFIG)
        if os.path.exists(".env"):
            try:
                with open(".env", "r", encoding="utf-8") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip()
            except Exception:
                pass
        for k in DEFAULT_ENV_CONFIG:
            env_val = os.getenv(k)
            if env_val is not None and k != "PORT":
                cfg[k] = env_val
        return cfg

    def save_env_config(self, updates):
        cfg = self.get_env_config()
        for k, v in updates.items():
            if k in DEFAULT_ENV_CONFIG and v is not None:
                clean_v = str(v).replace("\r", "").replace("\n", "").strip()
                cfg[k] = clean_v
                os.environ[k] = clean_v

        lines = []
        seen = set()
        if os.path.exists(".env"):
            try:
                with open(".env", "r", encoding="utf-8") as f:
                    for raw_line in f:
                        stripped = raw_line.strip()
                        if stripped and not stripped.startswith("#") and "=" in stripped:
                            k = stripped.split("=", 1)[0].strip()
                            if k in cfg:
                                lines.append(f"{k}={cfg[k]}")
                                seen.add(k)
                                continue
                        lines.append(raw_line.rstrip("\r\n"))
            except Exception:
                pass

        for k, v in cfg.items():
            if k not in seen:
                lines.append(f"{k}={v}")

        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return cfg

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
        pings = []
        for _ in range(3):
            t0 = time.perf_counter()
            try:
                with socket.create_connection(("1.1.1.1", 443), timeout=2):
                    pings.append((time.perf_counter() - t0) * 1000.0)
            except Exception:
                pass
        ping_ms = round(min(pings), 1) if pings else 0.0

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

        stop_ul = time.perf_counter() + 3.0
        ul_bytes = [0]
        ul_lock = threading.Lock()
        payload = b"0" * (2 * 1024 * 1024)

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
        logger_ref = self

        class WebHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def check_auth(self):
                if not logger_ref.password:
                    return True
                auth = self.headers.get("Authorization")
                if not auth:
                    return False
                try:
                    decoded = base64.b64decode(auth.split(" ")[1]).decode()
                    return decoded.split(":", 1)[1] == logger_ref.password
                except Exception:
                    return False

            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)

                # Cho phép truy cập /sub không cần mật khẩu để các app VPN (Shadowrocket, v2rayNG...) tự động cập nhật
                if parsed.path == "/sub":
                    query = parse_qs(parsed.query)
                    links = logger_ref.get_links_list()
                    proto_filter = (query.get("type", [""])[0] or "").lower()
                    if proto_filter in ("vless", "vmess"):
                        links = [l for l in links if l.startswith(f"{proto_filter}://")]
                    raw_text = "\n".join(links)
                    if query.get("raw", ["0"])[0] == "1":
                        body = (raw_text + "\n").encode("utf-8")
                    else:
                        body = base64.b64encode(raw_text.encode("utf-8"))
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Profile-Update-Interval", "1")
                    self.send_header("Subscription-Userinfo", "upload=0; download=0; total=10737418240000; expire=0")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if not self.check_auth():
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="Login Required"')
                    self.end_headers()
                    self.wfile.write(b"Unauthorized")
                    return

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
                    links = logger_ref.get_links_list()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"links": links}).encode("utf-8"))

                elif parsed.path == "/config":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(logger_ref.get_env_config()).encode("utf-8"))

                elif parsed.path == "/logs":
                    query = parse_qs(parsed.query)
                    last_id = int(query.get("last_id", [0])[0])
                    with logger_ref._lock:
                        new_logs = [l for l in logger_ref.logs if l["id"] > last_id]
                        resp = {"new_logs": new_logs, "last_id": logger_ref.log_sequence}
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(resp).encode("utf-8"))

                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if not self.check_auth():
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="Login Required"')
                    self.end_headers()
                    self.wfile.write(b"Unauthorized")
                    return

                parsed = urlparse(self.path)
                content_len = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
                try:
                    data = json.loads(raw_body)
                except Exception:
                    data = {}

                if parsed.path == "/config":
                    cfg = logger_ref.save_env_config(data)
                    logger_ref.push_log(
                        f"[CONFIG] Đã lưu cấu hình mới (Mode={cfg.get('RUN_MODE')}, Protocol={cfg.get('PROTOCOL')}, PortMode={cfg.get('PORT_MODE')}). Đang khởi động lại Xray...",
                        "SUCCESS"
                    )
                    if logger_ref.action_callback:
                        threading.Thread(target=logger_ref.action_callback, args=("reload_config", cfg), daemon=True).start()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "message": "✅ Đã lưu cấu hình & đang khởi động lại Xray!"}).encode("utf-8"))

                elif parsed.path == "/action":
                    act = data.get("action", "")
                    msg = "✅ Đã thực hiện!"
                    if act == "new_tunnel":
                        logger_ref.push_log("[ACTION] Yêu cầu làm mới Cloudflare Tunnel để lấy tên miền & bộ link mới...", "INFO")
                        msg = "🔄 Đang tạo Cloudflare Tunnel mới (~4 giây)..."
                    elif act == "new_uuid":
                        new_id = str(uuid.uuid4())
                        logger_ref.save_env_config({"XRAY_UUID": new_id})
                        logger_ref.push_log(f"[ACTION] Đã tạo UUID mới ({new_id}) và đang làm mới toàn bộ link...", "SUCCESS")
                        msg = f"🎲 Đã đổi UUID mới ({new_id[:8]}...) & đang tạo lại link!"
                    elif act == "create_vmess":
                        logger_ref.save_env_config({"PROTOCOL": "both"})
                        logger_ref.push_log("[ACTION] Đã bật chế độ song song VLESS + VMess và đang tạo link vmess:// + vless:// mới...", "SUCCESS")
                        msg = "➕ Đang tạo bộ link VMess + VLESS mới (~4 giây)..."

                    if logger_ref.action_callback:
                        threading.Thread(target=logger_ref.action_callback, args=(act, data), daemon=True).start()

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "message": msg}).encode("utf-8"))

                else:
                    self.send_response(404)
                    self.end_headers()

        return WebHandler

    def start(self):
        """Khởi chạy server trong một thread riêng (tự động mở thêm port 9999 và 8080 làm dự phòng cho Railway)"""
        if self.server:
            return f"http://localhost:{self.port}"

        ThreadingHTTPServer.allow_reuse_address = True
        handler_cls = self._create_handler()

        def run_server():
            try:
                self.server = ThreadingHTTPServer(("0.0.0.0", self.port), handler_cls)
                self.server.serve_forever()
            except Exception as e:
                print(f"[!] Web UI port {self.port} bind error: {e}")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        self.extra_servers = []
        for extra_port in (9999, 8080):
            if extra_port != self.port:
                try:
                    extra_srv = ThreadingHTTPServer(("0.0.0.0", extra_port), handler_cls)
                    threading.Thread(target=extra_srv.serve_forever, daemon=True).start()
                    self.extra_servers.append(extra_srv)
                except Exception:
                    pass

        return f"http://localhost:{self.port} (fallback: 9999, 8080)"

    def stop(self):
        """Dừng server"""
        for extra_srv in getattr(self, "extra_servers", []):
            try:
                extra_srv.shutdown()
                extra_srv.server_close()
            except Exception:
                pass
        self.extra_servers = []
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            return True
        return False

if __name__ == "__main__":
    logger = RealtimeLogger(port=9000, password=None)
    info = logger.get_server_info()
    print("=" * 60)
    print(f" 🌐 Vị trí Server : {info.get('city', '?')}, {info.get('region', '?')}, {info.get('country', '?')}")
    print(f" 🖧  IP / Nhà mạng : {info.get('ip', '?')} ({info.get('org', '?')})")
    print("=" * 60)
    print(" ⚡ Đang chạy Speedtest đa luồng tới Cloudflare (~8 giây)...")
    res = logger.run_server_speedtest()
    print("-" * 60)
    print(f" 🟢 Ping     : {res['ping_ms']} ms")
    print(f" ⬇️  Download : {res['download_mbps']} Mbps")
    print(f" ⬆️  Upload   : {res['upload_mbps']} Mbps")
    print("=" * 60)