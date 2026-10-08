import os
import re
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
    "CUSTOM_DOMAIN": "",
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
        .card { background: #1e293b; padding: 1.25rem 1.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); max-width: 1020px; margin: 0 auto 18px auto; display: flex; flex-direction: column; border: 1px solid #334155; }
        h2 { margin-top: 0; border-bottom: 1px solid #334155; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; color: #f8fafc; font-size: 1.15rem; flex-wrap: wrap; gap: 8px; }
        .badge { font-size: 12px; color: #4ade80; background: rgba(74, 222, 128, 0.12); padding: 4px 10px; border-radius: 999px; font-weight: 600; }
        .badge-warn { font-size: 13px; color: #fbbf24; background: rgba(251, 191, 36, 0.15); padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(251, 191, 36, 0.4); }
        .badge-proto { font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 6px; min-width: 58px; text-align: center; }
        .proto-vless { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }
        .proto-vmess { background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }
        .sub-box { background: #0f172a; border: 1px solid #0284c7; border-radius: 8px; padding: 12px; margin-bottom: 14px; }
        .sub-title { font-size: 13px; font-weight: 600; color: #38bdf8; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; }
        .sub-hint { font-size: 11.5px; color: #94a3b8; margin-top: 6px; line-height: 1.45; }
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

        /* Mode Tabs */
        .mode-tabs { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-bottom: 16px; }
        .mode-tab { background: #0f172a; border: 2px solid #334155; border-radius: 10px; padding: 12px 14px; cursor: pointer; text-align: left; transition: 0.15s; color: #cbd5e1; }
        .mode-tab:hover { border-color: #64748b; }
        .mode-tab.active-m1 { border-color: #10b981; background: rgba(16, 185, 129, 0.1); }
        .mode-tab.active-m2 { border-color: #38bdf8; background: rgba(56, 189, 248, 0.1); }
        .mode-tab.active-m3 { border-color: #a855f7; background: rgba(168, 85, 247, 0.1); }
        .mode-tab-title { font-size: 14px; font-weight: 700; color: #f8fafc; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }
        .mode-tab-sub { font-size: 11.5px; color: #94a3b8; line-height: 1.35; }

        .guide-box { background: #0f172a; border-left: 4px solid #38bdf8; border-radius: 6px; padding: 12px 14px; margin-bottom: 16px; font-size: 12.5px; line-height: 1.55; color: #cbd5e1; }
        .guide-box.m1 { border-left-color: #10b981; }
        .guide-box.m2 { border-left-color: #38bdf8; }
        .guide-box.m3 { border-left-color: #a855f7; }
        .guide-box code { background: #1e293b; color: #fde047; padding: 2px 6px; border-radius: 4px; font-family: monospace; }

        .step-box { background: rgba(15, 23, 42, 0.55); border: 1px solid #334155; border-radius: 8px; padding: 12px 14px; margin-bottom: 12px; }
        .step-header { font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
        .step-num { background: #0284c7; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 999px; }

        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
        .form-group { display: flex; flex-direction: column; gap: 5px; }
        .form-group.full { grid-column: 1 / -1; }
        .form-group label { font-size: 12px; color: #cbd5e1; font-weight: 600; }
        .form-control { background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; font-size: 13px; font-family: inherit; width: 100%; }
        .form-control:focus { outline: none; border-color: #38bdf8; }
        .field-hint { font-size: 11px; color: #94a3b8; }

        #log-container { background: #090d16; color: #cbd5e1; padding: 14px; border-radius: 8px; overflow-y: auto; font-family: monospace; font-size: 12px; height: 340px; border: 1px solid #334155; }
        .log-entry { margin-bottom: 4px; border-bottom: 1px solid #1e293b; padding-bottom: 2px; word-break: break-all; }
        .timestamp { color: #64748b; margin-right: 8px; }
        .type-info { color: #38bdf8; font-weight: bold; }
        .type-error { color: #f87171; font-weight: bold; }
        .type-success { color: #4ade80; font-weight: bold; }
        .status-toast { font-size: 12.5px; color: #4ade80; font-weight: 600; }
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
                💡 Dán <b>Link Sub</b> này vào app VPN 1 lần duy nhất. Khi đổi Tunnel mới hoặc tạo VMess/VLESS mới, bạn chỉ cần bấm <b>"Cập nhật Sub (Update Subscription)"</b> trên app là tự động lấy toàn bộ link mới!
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

    <!-- CARD 3: STEP-BY-STEP WIZARD CHO MODE 1 - MODE 2 - MODE 3 -->
    <div class="card">
        <h2>
            <span>⚙️ Cài Đặt Xray Theo Từng Chế Độ (Mode 1 - Mode 2 - Mode 3)</span>
            <span id="current-mode-badge" class="badge">Đang tải...</span>
        </h2>

        <!-- 3 TAB CHỌN MODE -->
        <div class="mode-tabs">
            <div class="mode-tab" id="tab-quick_tunnel" onclick="selectMode('quick_tunnel')">
                <div class="mode-tab-title">
                    <span>1️⃣ Mode 1: Quick Tunnel</span>
                    <span style="font-size:11px; color:#10b981;">Khuyên dùng</span>
                </div>
                <div class="mode-tab-sub">Không cần domain. Tự cấp <code>*.trycloudflare.com</code>. Chạy tốt trên cả Railway & Ubuntu VPS.</div>
            </div>

            <div class="mode-tab" id="tab-named_tunnel" onclick="selectMode('named_tunnel')">
                <div class="mode-tab-title">
                    <span>2️⃣ Mode 2: Named Tunnel</span>
                    <span style="font-size:11px; color:#38bdf8;">Domain cố định</span>
                </div>
                <div class="mode-tab-sub">Dùng Domain riêng + Cloudflare Zero Trust Token. Link cố định vĩnh viễn, hỗ trợ cả xHTTP.</div>
            </div>

            <div class="mode-tab" id="tab-direct" onclick="selectMode('direct')">
                <div class="mode-tab-title">
                    <span>3️⃣ Mode 3: Direct Cloudflare</span>
                    <span style="font-size:11px; color:#c084fc;">Chỉ VPS có IP riêng</span>
                </div>
                <div class="mode-tab-sub">Không dùng <code>cloudflared</code>. Cloudflare DNS Proxy trỏ thẳng về Port 80 của VPS.</div>
            </div>
        </div>

        <!-- HƯỚNG DẪN SETUP TƯƠNG ỨNG TỪNG MODE -->
        <div id="guide-quick_tunnel" class="guide-box m1" style="display:none;">
            <b>🟢 Quy trình Mode 1 (Quick Tunnel - 4 bước chuẩn <code>run.sh</code>):</b><br>
            • Không cần mua tên miền hay cấu hình Cloudflare. Hệ thống tự tạo kết nối HTTP/2 tốc độ cao tới Cloudflare.<br>
            • Transport tự động tối ưu ở <code>WebSocket</code> (do <code>trycloudflare.com</code> chỉ hỗ trợ WebSocket) và lắng nghe nội bộ tại <code>127.0.0.1:8888</code>.
        </div>

        <div id="guide-named_tunnel" class="guide-box m2" style="display:none;">
            <b>🔵 Chuẩn bị trên Cloudflare Zero Trust trước khi bật Mode 2 (6 bước chuẩn <code>run.sh</code>):</b><br>
            1. Mở <a href="https://one.dash.cloudflare.com/" target="_blank" style="color:#38bdf8;">Cloudflare Zero Trust</a> &rarr; <b>Networks</b> &rarr; <b>Tunnels</b> &rarr; <b>Create a tunnel</b> &rarr; chọn <b>Cloudflared</b>.<br>
            2. Sao chép <b>Tunnel Token</b> (dạng <code>eyJhIjoi...</code> — bạn có thể dán cả câu lệnh <code>cloudflared service install eyJ...</code>, hệ thống sẽ tự lọc lấy token).<br>
            3. Sang tab <b>Public Hostname</b> &rarr; <b>Add a public hostname</b>:<br>
            &nbsp;&nbsp;&bull; <b>Domain / Subdomain</b>: Ví dụ <code>vless.tenmien.com</code> (nhập đúng tên miền này vào ô <b>Domain</b> ở Bước 1 bên dưới).<br>
            &nbsp;&nbsp;&bull; <b>Service Type</b>: Chọn <code>HTTP</code> &nbsp;|&nbsp; <b>URL</b>: Nhập chính xác <code>127.0.0.1:8888</code>.
        </div>

        <div id="guide-direct" class="guide-box m3" style="display:none;">
            <b>🟣 Chuẩn bị trên Cloudflare DNS trước khi bật Mode 3 (6 bước chuẩn <code>run.sh</code>):</b><br>
            1. Vào Cloudflare DNS &rarr; tạo bản ghi <b>A</b> cho tên miền (VD: <code>vless.tenmien.com</code>) trỏ về IP Server: <code id="direct-ip-hint">Đang lấy IP...</code>, bật <b>Proxy ON (Đám mây cam 🟠)</b>.<br>
            2. Vào mục <b>SSL/TLS &rarr; Overview</b> trên Cloudflare &rarr; đổi sang chế độ <code>Flexible</code>.<br>
            3. Mở cổng TCP <code>80</code> trên tường lửa VPS.<br>
            <span style="color:#fbbf24;">⚠️ Lưu ý: Mode 3 chỉ dùng cho <b>Ubuntu VPS</b> có IP riêng mở được port 80. Trên <b>Railway</b> không mở trực tiếp port 80 theo IP riêng được, hãy dùng <b>Mode 1</b> hoặc <b>Mode 2</b>!</span>
        </div>

        <input type="hidden" id="cfg-RUN_MODE" value="quick_tunnel" />

        <!-- BƯỚC 1 (CHỈ HIỆN Ở MODE 2 & MODE 3): DOMAIN & TOKEN / ORIGIN PORT -->
        <div class="step-box" id="step-domain-box" style="display:none;">
            <div class="step-header">
                <span class="step-num" id="lbl-step-domain">Bước 1/6</span>
                <span id="title-step-domain">Cấu hình Tên miền (Domain) & Kết nối Cloudflare</span>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Tên miền của bạn (WS_HOST - Bắt buộc cho Mode 2 & 3)</label>
                    <input class="form-control" id="cfg-CUSTOM_DOMAIN" placeholder="Ví dụ: vless.example.com" />
                    <span class="field-hint">Chỉ nhập tên miền (VD: <code>vless.tenmien.com</code>), không kèm <code>https://</code></span>
                </div>

                <!-- Chỉ hiện ở Mode 2 -->
                <div class="form-group" id="grp-TUNNEL_TOKEN">
                    <label>Cloudflare Tunnel Token (TUNNEL_TOKEN - Bắt buộc cho Mode 2)</label>
                    <input class="form-control" id="cfg-TUNNEL_TOKEN" placeholder="Dán mã eyJhIjoi... hoặc lệnh cloudflared service install eyJ..." />
                    <span class="field-hint">Tự động nhận diện mã <code>eyJ...</code> nếu bạn dán nguyên câu lệnh từ Cloudflare</span>
                </div>

                <!-- Chỉ hiện ở Mode 3 -->
                <div class="form-group" id="grp-DIRECT_PORT" style="display:none;">
                    <label>Cổng lắng nghe trực tiếp trên VPS (Origin Listen Address:Port)</label>
                    <input class="form-control" id="cfg-DIRECT_PORT" value="0.0.0.0:80" placeholder="0.0.0.0:80" />
                    <span class="field-hint">Cloudflare Flexible SSL sẽ chuyển tiếp lưu lượng về cổng 80 này</span>
                </div>
            </div>
        </div>

        <!-- BƯỚC TIẾP THEO: FAKE SNI -->
        <div class="step-box">
            <div class="step-header">
                <span class="step-num" id="lbl-step-sni">Bước 1/4</span>
                <span>Chọn Bug Host / Fake SNI nền</span>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Chọn nhanh gói SNI (Giống menu <code>run.sh</code>)</label>
                    <select class="form-control" id="sni-preset" onchange="applySniPreset()">
                        <option value="both">3. Cả FreeTiktok + FreeVina Ko Nen (Mặc định)</option>
                        <option value="tiktok">1. Chỉ FreeTiktok (api24-normal-alisg.tiktokv.com)</option>
                        <option value="vina">2. Chỉ FreeVina Ko Nen (172.67.168.158)</option>
                        <option value="custom">4. Tùy chỉnh (Nhập danh sách SNI bên cạnh)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Giá trị FAKE_SNI (Cách nhau bởi dấu phẩy, kèm #Tên_Hiển_Thị)</label>
                    <input class="form-control" id="cfg-FAKE_SNI" oninput="document.getElementById('sni-preset').value='custom'" />
                </div>
            </div>
        </div>

        <!-- BƯỚC TRANSPORT (CHỈ HIỆN Ở MODE 2 & MODE 3, MODE 1 TỰ ĐỘNG DÙNG WEBSOCKET) -->
        <div class="step-box" id="step-transport-box" style="display:none;">
            <div class="step-header">
                <span class="step-num">Bước 3/6</span>
                <span>Chọn Điểm Cuối Transport (WebSocket / xHTTP)</span>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Loại Transport (TRANSPORT)</label>
                    <select class="form-control" id="cfg-TRANSPORT" onchange="updateXhttpVisibility()">
                        <option value="websocket">1. WebSocket (Ổn định / Hỗ trợ mọi app client)</option>
                        <option value="xhttp">2. xHTTP (Transport HTTP hiện đại)</option>
                        <option value="websocket,xhttp">3. Cả WebSocket + xHTTP (Song song)</option>
                    </select>
                </div>
                <div class="form-group" id="grp-XHTTP_MODE" style="display:none;">
                    <label>Chế độ xHTTP (XHTTP_MODE)</label>
                    <select class="form-control" id="cfg-XHTTP_MODE">
                        <option value="packet-up">1. packet-up (Mặc định)</option>
                        <option value="stream-up">2. stream-up</option>
                        <option value="stream-one">3. stream-one</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Đường dẫn Endpoint (WS_PATH)</label>
                    <input class="form-control" id="cfg-WS_PATH" value="/vless" placeholder="/vless" />
                </div>
            </div>
        </div>

        <!-- BƯỚC CHỌN PORT & GIAO THỨC VLESS / VMESS -->
        <div class="step-box">
            <div class="step-header">
                <span class="step-num" id="lbl-step-port">Bước 2/4</span>
                <span>Chọn Cổng Xuất Link (80 / 443) & Giao Thức (VLESS / VMess)</span>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Chế độ Cổng cho Link (PORT_MODE)</label>
                    <select class="form-control" id="cfg-PORT_MODE">
                        <option value="both">3. Cả Port 80 (Không TLS) + Port 443 (TLS) (Mặc định)</option>
                        <option value="443">2. Chỉ Port 443 (TLS)</option>
                        <option value="80">1. Chỉ Port 80 (Không TLS)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Giao thức tạo Link (PROTOCOL)</label>
                    <select class="form-control" id="cfg-PROTOCOL">
                        <option value="both">Cả VLESS (vless://) + VMess (vmess://)</option>
                        <option value="vless">Chỉ VLESS (vless:// - Nhẹ & tốc độ cao nhất)</option>
                        <option value="vmess">Chỉ VMess (vmess:// - Tương thích V2Ray cũ)</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- BƯỚC VỊ TRÍ NODE & UUID -->
        <div class="step-box">
            <div class="step-header">
                <span class="step-num" id="lbl-step-node">Bước 3/4</span>
                <span>Vị Trí Node (Cờ Quốc Gia), UUID & Tuỳ Chọn Phụ</span>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Mã Quốc Gia 2 ký tự (COUNTRY_CODE - VD: SG, VN, US)</label>
                    <div style="display:flex; gap:6px;">
                        <input class="form-control" id="cfg-COUNTRY_CODE" placeholder="Để trống hoặc nhập SG, VN..." />
                        <button class="btn" type="button" onclick="autoFillCountry()">📍 Tự lấy theo IP</button>
                    </div>
                </div>
                <div class="form-group">
                    <label>UUID Kết Nối (XRAY_UUID)</label>
                    <div style="display:flex; gap:6px;">
                        <input class="form-control" id="cfg-XRAY_UUID" />
                        <button class="btn" type="button" onclick="randomizeUuidInput()">🎲 Random</button>
                    </div>
                </div>
                <div class="form-group">
                    <label>Cloudflare WARP Outbound (ENABLE_WARP)</label>
                    <select class="form-control" id="cfg-ENABLE_WARP">
                        <option value="false">Tắt (Mặc định - Tốc độ tối đa)</option>
                        <option value="true">Bật (Bọc lưu lượng ra qua Cloudflare WARP)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Webhook URL (Tùy chọn gửi thông báo khi có link mới)</label>
                    <input class="form-control" id="cfg-WEBHOOK_URL" placeholder="https://discord.com/api/webhooks/..." />
                </div>
            </div>
        </div>

        <!-- BƯỚC CUỐI: LƯU & KHỞI ĐỘNG -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-top:4px;">
            <span id="save-hint" style="font-size:12px; color:#94a3b8;">Hệ sẽ lưu vào <code>.env</code> và khởi động lại Xray + Tunnel ngay lập tức.</span>
            <button class="btn btn-green" style="padding:10px 20px; font-size:13.5px;" onclick="saveConfig()" id="save-cfg-btn">
                🚀 Lưu & Khởi Động Chế Độ Này
            </button>
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

        const SNI_BOTH = "api24-normal-alisg.tiktokv.com#FreeTiktok,172.67.168.158#FreeVina Ko Nen";
        const SNI_TIKTOK = "api24-normal-alisg.tiktokv.com#FreeTiktok";
        const SNI_VINA = "172.67.168.158#FreeVina Ko Nen";

        let lastLogId = 0;
        let currentLinksText = "";
        let detectedCountry = "";
        let detectedIp = "";

        function showToast(msg, isErr = false) {
            const el = document.getElementById("action-status");
            el.style.color = isErr ? "#f87171" : "#4ade80";
            el.innerText = msg;
            setTimeout(() => { if (el.innerText === msg) el.innerText = ""; }, 6000);
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

        function autoFillCountry() {
            if (detectedCountry && detectedCountry !== "?") {
                document.getElementById("cfg-COUNTRY_CODE").value = detectedCountry;
            }
        }

        function applySniPreset() {
            const v = document.getElementById("sni-preset").value;
            const input = document.getElementById("cfg-FAKE_SNI");
            if (v === "both") input.value = SNI_BOTH;
            else if (v === "tiktok") input.value = SNI_TIKTOK;
            else if (v === "vina") input.value = SNI_VINA;
        }

        function syncSniPresetDropdown(val) {
            const preset = document.getElementById("sni-preset");
            if (val === SNI_BOTH) preset.value = "both";
            else if (val === SNI_TIKTOK) preset.value = "tiktok";
            else if (val === SNI_VINA) preset.value = "vina";
            else preset.value = "custom";
        }

        function updateXhttpVisibility() {
            const tr = document.getElementById("cfg-TRANSPORT").value;
            document.getElementById("grp-XHTTP_MODE").style.display = tr.includes("xhttp") ? "flex" : "none";
        }

        function selectMode(mode) {
            document.getElementById("cfg-RUN_MODE").value = mode;

            const t1 = document.getElementById("tab-quick_tunnel");
            const t2 = document.getElementById("tab-named_tunnel");
            const t3 = document.getElementById("tab-direct");
            t1.className = "mode-tab" + (mode === "quick_tunnel" ? " active-m1" : "");
            t2.className = "mode-tab" + (mode === "named_tunnel" ? " active-m2" : "");
            t3.className = "mode-tab" + (mode === "direct" ? " active-m3" : "");

            document.getElementById("guide-quick_tunnel").style.display = mode === "quick_tunnel" ? "block" : "none";
            document.getElementById("guide-named_tunnel").style.display = mode === "named_tunnel" ? "block" : "none";
            document.getElementById("guide-direct").style.display = mode === "direct" ? "block" : "none";

            const stepDomain = document.getElementById("step-domain-box");
            const stepTransport = document.getElementById("step-transport-box");
            const grpToken = document.getElementById("grp-TUNNEL_TOKEN");
            const grpDirectPort = document.getElementById("grp-DIRECT_PORT");
            const saveBtn = document.getElementById("save-cfg-btn");

            if (mode === "quick_tunnel") {
                stepDomain.style.display = "none";
                stepTransport.style.display = "none";
                document.getElementById("lbl-step-sni").innerText = "Bước 1/4";
                document.getElementById("lbl-step-port").innerText = "Bước 2/4";
                document.getElementById("lbl-step-node").innerText = "Bước 3/4";
                saveBtn.innerText = "🚀 Lưu & Chạy Mode 1 (Quick Tunnel - Bước 4/4)";
            } else if (mode === "named_tunnel") {
                stepDomain.style.display = "block";
                stepTransport.style.display = "block";
                grpToken.style.display = "flex";
                grpDirectPort.style.display = "none";
                document.getElementById("title-step-domain").innerText = "Domain & Cloudflare Tunnel Token (Bắt buộc)";
                document.getElementById("lbl-step-sni").innerText = "Bước 2/6";
                document.getElementById("lbl-step-port").innerText = "Bước 4/6";
                document.getElementById("lbl-step-node").innerText = "Bước 5/6";
                saveBtn.innerText = "🚀 Lưu & Chạy Mode 2 (Named Tunnel - Bước 6/6)";
                updateXhttpVisibility();
            } else {
                stepDomain.style.display = "block";
                stepTransport.style.display = "block";
                grpToken.style.display = "none";
                grpDirectPort.style.display = "flex";
                document.getElementById("title-step-domain").innerText = "Domain Cloudflare & Cổng Origin Listener (Bắt buộc)";
                document.getElementById("lbl-step-sni").innerText = "Bước 2/6";
                document.getElementById("lbl-step-port").innerText = "Bước 4/6";
                document.getElementById("lbl-step-node").innerText = "Bước 5/6";
                saveBtn.innerText = "🚀 Lưu & Chạy Mode 3 (Direct Mode - Bước 6/6)";
                updateXhttpVisibility();
            }
        }

        function cleanDomain(raw) {
            let s = (raw || "").trim();
            s = s.replace(/^https?:\\/\\//i, "").split("/")[0].trim();
            return s;
        }

        function extractTunnelToken(raw) {
            let s = (raw || "").trim();
            const m = s.match(/eyJ[A-Za-z0-9_\\-=]+/);
            return m ? m[0] : s;
        }

        async function loadConfig() {
            try {
                const res = await fetch("/config");
                const cfg = await res.json();
                const mode = cfg.RUN_MODE || "quick_tunnel";
                const modeNames = {
                    "quick_tunnel": "Đang chạy: Mode 1 (Quick Tunnel)",
                    "named_tunnel": "Đang chạy: Mode 2 (Named Tunnel)",
                    "direct": "Đang chạy: Mode 3 (Direct Mode)"
                };
                document.getElementById("current-mode-badge").innerText = modeNames[mode] || mode;

                document.getElementById("cfg-PROTOCOL").value = cfg.PROTOCOL || "vless";
                document.getElementById("cfg-PORT_MODE").value = cfg.PORT_MODE || "both";
                document.getElementById("cfg-TRANSPORT").value = cfg.TRANSPORT || "websocket";
                document.getElementById("cfg-XHTTP_MODE").value = cfg.XHTTP_MODE || "packet-up";
                document.getElementById("cfg-FAKE_SNI").value = cfg.FAKE_SNI || SNI_BOTH;
                syncSniPresetDropdown(document.getElementById("cfg-FAKE_SNI").value);
                document.getElementById("cfg-XRAY_UUID").value = cfg.XRAY_UUID || "";
                document.getElementById("cfg-WS_PATH").value = cfg.WS_PATH || "/vless";
                document.getElementById("cfg-TUNNEL_TOKEN").value = cfg.TUNNEL_TOKEN || "";
                document.getElementById("cfg-COUNTRY_CODE").value = cfg.COUNTRY_CODE || "";
                document.getElementById("cfg-ENABLE_WARP").value = cfg.ENABLE_WARP || "false";
                document.getElementById("cfg-WEBHOOK_URL").value = cfg.WEBHOOK_URL || "";

                const savedDomain = (cfg.WS_HOST && cfg.WS_HOST !== "trycloudflare.com") ? cfg.WS_HOST : (cfg.CUSTOM_DOMAIN || "");
                document.getElementById("cfg-CUSTOM_DOMAIN").value = savedDomain;
                if (mode === "direct" && cfg.PORT) {
                    document.getElementById("cfg-DIRECT_PORT").value = cfg.PORT;
                }

                selectMode(mode);
            } catch (e) {}
        }

        async function saveConfig() {
            const mode = document.getElementById("cfg-RUN_MODE").value;
            const customDomain = cleanDomain(document.getElementById("cfg-CUSTOM_DOMAIN").value);
            const tunnelToken = extractTunnelToken(document.getElementById("cfg-TUNNEL_TOKEN").value);
            document.getElementById("cfg-CUSTOM_DOMAIN").value = customDomain;
            document.getElementById("cfg-TUNNEL_TOKEN").value = tunnelToken;

            if (mode === "named_tunnel") {
                if (!customDomain || customDomain === "trycloudflare.com") {
                    alert("⚠️ Mode 2 (Named Tunnel) bắt buộc phải nhập Tên miền riêng (WS_HOST) ở Bước 1/6!");
                    document.getElementById("cfg-CUSTOM_DOMAIN").focus();
                    return;
                }
                if (!tunnelToken) {
                    alert("⚠️ Mode 2 (Named Tunnel) bắt buộc phải nhập Cloudflare Tunnel Token (TUNNEL_TOKEN) ở Bước 1/6!");
                    document.getElementById("cfg-TUNNEL_TOKEN").focus();
                    return;
                }
            } else if (mode === "direct") {
                if (!customDomain || customDomain === "trycloudflare.com") {
                    alert("⚠️ Mode 3 (Direct Mode) bắt buộc phải nhập Tên miền đã trỏ Cloudflare DNS ở Bước 1/6!");
                    document.getElementById("cfg-CUSTOM_DOMAIN").focus();
                    return;
                }
            }

            const payload = {
                RUN_MODE: mode,
                PROTOCOL: document.getElementById("cfg-PROTOCOL").value,
                PORT_MODE: document.getElementById("cfg-PORT_MODE").value,
                FAKE_SNI: document.getElementById("cfg-FAKE_SNI").value.trim() || SNI_BOTH,
                XRAY_UUID: document.getElementById("cfg-XRAY_UUID").value.trim(),
                WS_PATH: document.getElementById("cfg-WS_PATH").value.trim() || "/vless",
                COUNTRY_CODE: document.getElementById("cfg-COUNTRY_CODE").value.trim().toUpperCase(),
                ENABLE_WARP: document.getElementById("cfg-ENABLE_WARP").value,
                WEBHOOK_URL: document.getElementById("cfg-WEBHOOK_URL").value.trim(),
                CUSTOM_DOMAIN: customDomain,
                TUNNEL_TOKEN: tunnelToken
            };

            // Áp dụng quy tắc chuẩn của từng Mode giống hệt run.sh
            if (mode === "quick_tunnel") {
                payload.WS_HOST = "trycloudflare.com";
                payload.PORT = "127.0.0.1:8888";
                payload.TRANSPORT = "websocket";
                payload.WS_PATH = "/vless";
            } else if (mode === "named_tunnel") {
                payload.WS_HOST = customDomain;
                payload.PORT = "127.0.0.1:8888";
                payload.TRANSPORT = document.getElementById("cfg-TRANSPORT").value;
                payload.XHTTP_MODE = document.getElementById("cfg-XHTTP_MODE").value;
            } else {
                payload.WS_HOST = customDomain;
                payload.PORT = document.getElementById("cfg-DIRECT_PORT").value.trim() || "0.0.0.0:80";
                payload.TRANSPORT = document.getElementById("cfg-TRANSPORT").value;
                payload.XHTTP_MODE = document.getElementById("cfg-XHTTP_MODE").value;
            }

            const btn = document.getElementById("save-cfg-btn");
            btn.disabled = true;
            btn.innerText = "⏳ Đang lưu & khởi động lại Xray...";
            try {
                const res = await fetch("/config", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payload)
                });
                const d = await res.json();
                showToast(d.message || "✅ Đã lưu cấu hình & khởi động lại Xray!");
                currentLinksText = "";
                linksContainer.innerHTML = "⏳ Đang khởi tạo kết nối theo chế độ mới và tạo lại link (~4 giây)...";
                await loadConfig();
            } catch (e) {
                showToast("❌ Lỗi khi lưu cấu hình", true);
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    selectMode(document.getElementById("cfg-RUN_MODE").value);
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
                showToast("❌ Có lỗi xảy ra", true);
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
                detectedCountry = d.country || "";
                detectedIp = d.ip || "";
                document.getElementById("srv-loc").innerText = `${d.city || "?"} (${d.country || "?"}) - ${d.ip || ""}`;
                const ipHint = document.getElementById("direct-ip-hint");
                if (ipHint && d.ip) ipHint.innerText = d.ip;
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
                if k == "TUNNEL_TOKEN" and clean_v:
                    m = re.search(r"eyJ[A-Za-z0-9_\-=]+", clean_v)
                    if m:
                        clean_v = m.group(0)
                elif k in ("WS_HOST", "CUSTOM_DOMAIN") and clean_v:
                    clean_v = re.sub(r"^https?://", "", clean_v, flags=re.IGNORECASE).split("/")[0].strip()
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
            url = "https://speed.cloudflare.com/__down?bytes=100000000"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            while time.perf_counter() < stop_dl:
                try:
                    with urllib.request.urlopen(req, timeout=4) as r:
                        while time.perf_counter() < stop_dl:
                            chunk = r.read(1048576)
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
                        f"[CONFIG] Đã lưu cấu hình (Mode={cfg.get('RUN_MODE')}, Host={cfg.get('WS_HOST')}, Protocol={cfg.get('PROTOCOL')}, Transport={cfg.get('TRANSPORT')}). Đang khởi động lại...",
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