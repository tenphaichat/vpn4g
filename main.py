import os
import sys
import glob

# Ensure .venv and local user site-packages (when systemd runs as root inside /home/<user>/vless) are in sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_home = os.path.dirname(_script_dir)
for _sp in glob.glob(os.path.join(_script_dir, ".venv", "lib", "python*", "site-packages")) + glob.glob(os.path.join(_parent_home, ".local", "lib", "python*", "site-packages")):
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.insert(0, _sp)

import signal
import json
import re
import shutil
import socket
import base64
from urllib import request
from sys import prefix
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path=".env", override=False):
        if not os.path.exists(dotenv_path):
            return False
        with open(dotenv_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _s = _line.strip()
                if not _s or _s.startswith("#") or "=" not in _s:
                    continue
                _k, _v = _s.split("=", 1)
                _k, _v = _k.strip(), _v.strip().strip("'\"")
                if override or _k not in os.environ:
                    os.environ[_k] = _v
        return True
import threading
import subprocess
import platform
import uuid
import time
from logging_site import RealtimeLogger
import requests
import importlib

xray_downloader = importlib.import_module("download-xray")
cloudflared_downloader = importlib.import_module("download-cloudflared")
# WARP downloader is imported lazily only when WARP is enabled.

def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    stop_program = False
    reload_event = threading.Event()
    tunnel_refresh_event = threading.Event()

    def _handle_stop_signal(signum, frame):
        nonlocal stop_program
        stop_program = True
        reload_event.set()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handle_stop_signal)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    # =========================================
    # CONFIG SERVER (Cloudflare Tunnel)
    # =========================================
    raw_init_token = (os.getenv("TUNNEL_TOKEN") or "").strip()
    init_token_match = re.search(r"eyJ[A-Za-z0-9_\-=]+", raw_init_token)
    clean_init_token = init_token_match.group(0) if init_token_match else raw_init_token
    default_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, clean_init_token)) if clean_init_token else str(uuid.uuid4())

    default_configs = {
        "PORT": "127.0.0.1:8888",
        "XRAY_UUID": default_uuid,
        "FAKE_SNI": "api24-normal-alisg.tiktokv.com#FreeTiktok,172.67.168.158#FreeVina Ko Nen",
        "WS_PATH": "/vless",
        "WS_HOST": "trycloudflare.com",
        "TRANSPORT": "websocket",
        "XHTTP_MODE": "packet-up",
        "ENABLE_WARP": "false",
        "WEBHOOK_URL": "",
        "TUNNEL_TOKEN": "",
        "COUNTRY_CODE": "",
        "PORT_MODE": "both",
        "PROTOCOL": "vless",
        "RUN_MODE": "quick_tunnel"
    }

    def get_os_env(name):
        return os.getenv(name, default_configs.get(name))

    def get_public_url():
        try:
            ip = requests.get("https://api.ipify.org", timeout=5).text
            return ip
        except Exception as e:
            print(f"[!] Failed to get public IP: {e}")
            return "0.0.0.0"

    def init_env_file():
        env_path = ".env"
        if not os.path.exists(env_path):
            print("[*] File .env does not exist. Using default configuration...")
            with open(env_path, "w", encoding="utf-8") as f:
                for key, value in default_configs.items():
                    f.write(f"{key}={value}\n")
            print("[+] Generated .env configuration.")
        else:
            print("[*] Found .env configuration.")

    IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or os.getenv("RAILWAY_SERVICE_ID") or os.getenv("RAILWAY_PUBLIC_DOMAIN"))
    RAILWAY_WEB_PORT = os.getenv("PORT") if IS_RAILWAY else None

    init_env_file()
    load_dotenv(override=True)

    def on_dashboard_action(action, data):
        if action == "new_tunnel":
            tunnel_refresh_event.set()
        elif action in ("reload_config", "new_uuid", "create_vmess"):
            reload_event.set()

    # Start Web Dashboard once so it stays online across Xray/Tunnel reloads
    logger = None
    try:
        init_run_mode = (get_os_env("RUN_MODE") or "quick_tunnel").strip().lower()
        raw_web_port = os.getenv("WEB_PORT") or (RAILWAY_WEB_PORT if (IS_RAILWAY or init_run_mode != "direct") else None) or "9999"
        web_port = int(raw_web_port) if str(raw_web_port).isdigit() else 9999
        web_password = os.getenv("WEB_PASSWORD", "") or None
        logger = RealtimeLogger(port=web_port, password=web_password, action_callback=on_dashboard_action)
        logger_url = logger.start()
        print(f"[*] Logger Web UI & VLESS/VMess Dashboard is running at: {logger_url}")
    except Exception as e:
        print(f"[!] Failed to start Web UI: {e}")
        logger = None

    def logger_push(message, source="INFO"):
        if logger:
            logger.push_log(message, source)
            if os.getenv("DEBUG_MODE", "false").lower() == "true":
                print(f"[{source}] {message}")

    FRIENDLY_NAME_MAP = {
        "api24-normal-alisg.tiktokv.com": "FreeTiktok",
        "172.67.168.158": "FreeVina Ko Nen",
    }

    def flag_emoji(cc):
        """Convert 2-letter ISO country code to flag emoji. Returns None if invalid."""
        cc = (cc or "").strip().upper()
        if len(cc) != 2 or not all("A" <= c <= "Z" for c in cc):
            return None
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc)

    XRAY_BIN = "./xray.exe" if platform.system().lower() == "windows" else "./xray"
    CLF_BIN = "./cloudflared.exe" if platform.system().lower() == "windows" else "./cloudflared"
    WGCF_BIN = "./wgcf-cli.exe" if platform.system().lower() == "windows" else "./wgcf-cli"

    is_termux = bool(os.getenv("TERMUX_VERSION")) or "com.termux" in os.getenv("PREFIX", "")
    if is_termux:
        cloudflared_path = shutil.which("cloudflared")
        if cloudflared_path:
            CLF_BIN = cloudflared_path

    def xray_is_runnable():
        if not os.path.isfile(XRAY_BIN) or not os.access(XRAY_BIN, os.X_OK):
            return False
        try:
            subprocess.run(
                [XRAY_BIN, "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=15,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    # Main reloadable lifecycle loop
    while not stop_program:
        reload_event.clear()
        tunnel_refresh_event.clear()
        load_dotenv(override=True)
        START_TIME = int(time.time())

        PORT_ENV = get_os_env("PORT")
        UUID = (get_os_env("XRAY_UUID") or "").strip() or str(uuid.uuid4())
        FAKE_SNI = get_os_env("FAKE_SNI") or default_configs["FAKE_SNI"]
        WS_PATH = (get_os_env("WS_PATH") or "/vless").strip()
        if not WS_PATH.startswith("/"):
            WS_PATH = "/" + WS_PATH
        raw_ws_host = (get_os_env("WS_HOST") or "trycloudflare.com").strip()
        WS_HOST = re.sub(r"^https?://", "", raw_ws_host, flags=re.IGNORECASE).split("/")[0].strip() or "trycloudflare.com"
        WEBHOOK_URL = (get_os_env("WEBHOOK_URL") or "").strip()
        raw_token = (get_os_env("TUNNEL_TOKEN") or "").strip()
        token_match = re.search(r"eyJ[A-Za-z0-9_\-=]+", raw_token)
        TUNNEL_TOKEN = token_match.group(0) if token_match else raw_token
        ENABLE_WARP = (get_os_env("ENABLE_WARP") or "false").lower() == "true"
        RUN_MODE = (get_os_env("RUN_MODE") or "quick_tunnel").strip().lower()
        COUNTRY_CODE = (get_os_env("COUNTRY_CODE") or "").strip().upper()
        PORT_MODE = (get_os_env("PORT_MODE") or "both").strip().lower()
        if PORT_MODE not in ("80", "443", "both"):
            PORT_MODE = "both"

        PROTOCOL = (get_os_env("PROTOCOL") or "vless").strip().lower()
        if PROTOCOL not in ("vless", "vmess", "both"):
            PROTOCOL = "vless"

        ALLOWED_RUN_MODES = ("quick_tunnel", "named_tunnel", "direct")
        if RUN_MODE not in ALLOWED_RUN_MODES:
            print(f"[!] Unknown RUN_MODE '{RUN_MODE}', falling back to 'quick_tunnel'.")
            RUN_MODE = "quick_tunnel"

        if IS_RAILWAY and RUN_MODE == "direct":
            RUN_MODE = "named_tunnel" if TUNNEL_TOKEN else "quick_tunnel"
        if IS_RAILWAY or RUN_MODE in ("quick_tunnel", "named_tunnel"):
            PORT_ENV = os.getenv("XRAY_PORT", "127.0.0.1:8888")

        def wait_for_config_fix(err_msg):
            print(err_msg)
            logger_push(err_msg, "ERROR")
            logger_push("Hãy sửa lại cấu hình trong mục '⚙️ Cài Đặt Xray' trên Web Dashboard rồi bấm Lưu.", "INFO")
            while not reload_event.is_set() and not stop_program:
                reload_event.wait(1.0)

        if RUN_MODE == "named_tunnel":
            if not WS_HOST or WS_HOST == "trycloudflare.com":
                wait_for_config_fix("[ERROR] Mode 2 (named_tunnel) yêu cầu nhập WS_HOST là tên miền riêng (không dùng trycloudflare.com).")
                continue
            if not TUNNEL_TOKEN:
                wait_for_config_fix("[ERROR] Mode 2 (named_tunnel) yêu cầu nhập TUNNEL_TOKEN.")
                continue
        elif RUN_MODE == "direct":
            if not WS_HOST or WS_HOST == "trycloudflare.com":
                wait_for_config_fix("[ERROR] Mode 3 (direct) yêu cầu nhập WS_HOST là tên miền đã trỏ IP qua Cloudflare.")
                continue

        requested_transports = [item.strip().lower() for item in (get_os_env("TRANSPORT") or "websocket").split(",") if item.strip()]
        allowed_transports = {"websocket", "xhttp"}
        TRANSPORTS = []
        for transport in requested_transports:
            if transport in allowed_transports and transport not in TRANSPORTS:
                TRANSPORTS.append(transport)
            elif transport not in allowed_transports:
                print(f"[!] Unknown transport '{transport}' ignored.")
        if not TRANSPORTS:
            TRANSPORTS = ["websocket"]
        TRANSPORT = ",".join(TRANSPORTS)
        DUAL_TRANSPORT = len(TRANSPORTS) == 2

        XHTTP_MODE = (get_os_env("XHTTP_MODE") or "packet-up").strip().lower()
        if XHTTP_MODE not in {"packet-up", "stream-up", "stream-one"}:
            XHTTP_MODE = "packet-up"
        if "xhttp" in TRANSPORTS and RUN_MODE in ("named_tunnel", "direct") and XHTTP_MODE != "packet-up":
            logger_push(f"[INFO] Qua Cloudflare (Tunnel / CDN Flexible) yêu cầu xHTTP mode 'packet-up' (chế độ '{XHTTP_MODE}' bị Cloudflare chặn luồng upload). Đã tự động chuyển sang 'packet-up'.", "INFO")
            XHTTP_MODE = "packet-up"

        inbound_ports = []
        try:
            for p_item in PORT_ENV.split(","):
                p_item = p_item.strip()
                if not p_item:
                    continue
                if ":" in p_item:
                    parts = p_item.split(":")
                    listen_ip = ":".join(parts[:-1])
                    port_num = int(parts[-1])
                    inbound_ports.append((listen_ip, port_num))
                else:
                    inbound_ports.append(("0.0.0.0", int(p_item)))
        except ValueError:
            inbound_ports = [("127.0.0.1", 8888)]
        if not inbound_ports:
            inbound_ports = [("127.0.0.1", 8888)]

        if RUN_MODE == "direct":
            direct_ip, direct_port = inbound_ports[0]
            # Neu cong direct_port (VD: 80 hoac 8080) dang bi chiem boi Nginx/Backend, tu dong chuyen sang cong trong (VD: 2052)
            try:
                _ts = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _ts.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                _ts.bind((direct_ip if direct_ip != "0.0.0.0" else "", direct_port))
                _ts.close()
            except OSError:
                for _alt_p in (2052, 8880, 2082, 2086, 2095):
                    try:
                        _ts2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        _ts2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        _ts2.bind(("", _alt_p))
                        _ts2.close()
                        logger_push(f"[INFO] Cổng {direct_port} đang bận bởi Web Server, hệ thống tự động chuyển sang cổng nội bộ {_alt_p}.", "INFO")
                        direct_port = _alt_p
                        inbound_ports[0] = (direct_ip, direct_port)
                        break
                    except OSError:
                        pass

            # Neu VPS dang chay Nginx o cong 80, tu dong tao vhost Nginx cho WS_HOST de Cloudflare Flexible (Port 80) chuyen thang vao Xray!
            if direct_port != 80 and platform.system().lower() == "linux" and WS_HOST and WS_HOST != "trycloudflare.com" and os.path.isdir("/etc/nginx/conf.d"):
                nginx_conf_path = "/etc/nginx/conf.d/xray-vless.conf"
                nginx_vhost = (
                    "map $http_upgrade $xray_connection_upgrade {\n"
                    "    default upgrade;\n"
                    "    ''      '';\n"
                    "}\n\n"
                    "server {\n"
                    "    listen 80;\n"
                    f"    server_name {WS_HOST};\n\n"
                    "    client_max_body_size 0;\n"
                    "    proxy_buffering off;\n"
                    "    proxy_request_buffering off;\n\n"
                    "    location / {\n"
                    f"        proxy_pass http://127.0.0.1:{direct_port};\n"
                    "        proxy_http_version 1.1;\n"
                    "        proxy_set_header Upgrade $http_upgrade;\n"
                    "        proxy_set_header Connection $xray_connection_upgrade;\n"
                    "        proxy_set_header Host $host;\n"
                    "        proxy_set_header X-Real-IP $remote_addr;\n"
                    "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                    "        proxy_read_timeout 86400s;\n"
                    "        proxy_send_timeout 86400s;\n"
                    "    }\n"
                    "}\n"
                )
                try:
                    with open(nginx_conf_path, "w", encoding="utf-8") as nf:
                        nf.write(nginx_vhost)
                    if subprocess.run(["nginx", "-t"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                        subprocess.run(["nginx", "-s", "reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        logger_push(
                            f"[SUCCESS] Đã tự động gắn tên miền {WS_HOST} vào Nginx (cổng 80 -> 127.0.0.1:{direct_port}). "
                            f"Cloudflare Flexible hoạt động ngay lập tức mà KHÔNG cần tạo Origin Rule và KHÔNG ảnh hưởng website chính!",
                            "SUCCESS"
                        )
                    else:
                        os.remove(nginx_conf_path)
                except Exception as e:
                    print(f"[!] Could not auto-configure nginx: {e}")

        CLOUDFLARE_TARGET_IP, CLOUDFLARE_TARGET_PORT = inbound_ports[0]
        if CLOUDFLARE_TARGET_IP == "0.0.0.0":
            CLOUDFLARE_TARGET_IP = "127.0.0.1"

        def send_webhook(data):
            if not WEBHOOK_URL:
                return
            def task():
                try:
                    response = requests.post(WEBHOOK_URL, json=data, timeout=10)
                    if response.status_code == 200:
                        print("[+] Webhook sent successfully!")
                    else:
                        print(f"[-] Webhook failed with status: {response.status_code}")
                except Exception as e:
                    print(f"[!] Error sending webhook: {e}")
            threading.Thread(target=task, daemon=True).start()

        if is_termux and not xray_is_runnable():
            print("[*] Termux needs a runnable Android Xray binary. Downloading a fresh copy...")
            try:
                xray_downloader.install_xray()
            except Exception as error:
                wait_for_config_fix(f"[ERROR] Could not install Xray for Termux: {error}")
                continue
        elif not os.path.exists(XRAY_BIN):
            print(f"[ERROR] Unable to find xray path: {XRAY_BIN}")
            xray_downloader.install_xray()
        if RUN_MODE != "direct" and not os.path.exists(CLF_BIN):
            print(f"[ERROR] Unable to find Cloudflared path: {CLF_BIN}")
            cloudflared_downloader.install_cloudflared()

        wgcf_outbound = None
        if ENABLE_WARP:
            try:
                if not os.path.exists(WGCF_BIN):
                    importlib.import_module("download-wgcf").install_wgcf()
                if not os.path.exists("wgcf.xray.json"):
                    print("[*] Generating WARP account...")
                    subprocess.run([WGCF_BIN, "register"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run([WGCF_BIN, "generate", "--xray"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with open("wgcf.xray.json", "r") as f:
                    wgcf_outbound = json.load(f)
            except Exception as e:
                print(f"[!] WARP initialization failed ({e}), continuing without WARP.")
                wgcf_outbound = None

        def build_stream_settings(transport, path_override=None):
            use_path = path_override or WS_PATH
            if transport == "xhttp":
                return {"network": "xhttp", "security": "none", "xhttpSettings": {"path": use_path, "mode": "auto"}}
            return {"network": "ws", "security": "none", "wsSettings": {"path": use_path, "headers": {}}}

        def make_inbound(listen, port, transport, proto="vless", path_override=None):
            if proto == "vmess":
                settings = {"clients": [{"id": UUID, "alterId": 0}]}
            else:
                settings = {"clients": [{"id": UUID, "level": 0}], "decryption": "none"}
            return {
                "port": port,
                "listen": listen,
                "protocol": proto,
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
                "settings": settings,
                "streamSettings": build_stream_settings(transport, path_override=path_override)
            }

        def peek_request_info(conn, timeout=3.0):
            conn.settimeout(timeout)
            try:
                data = conn.recv(4096, socket.MSG_PEEK)
            except OSError:
                data = b""
            finally:
                conn.settimeout(None)
            first_line = data.split(b"\r\n", 1)[0]
            parts = first_line.split(b" ")
            req_path = parts[1] if len(parts) >= 2 else b""
            ws_path_bytes = (WS_PATH or "/vless").encode("utf-8")
            is_vless_path = req_path.startswith(ws_path_bytes)
            is_vmess = req_path.startswith(b"/vmess") or (PROTOCOL == "vmess" and is_vless_path)
            is_ws = b"upgrade: websocket" in data.lower()
            return is_vless_path, is_vmess, is_ws, len(data) == 0

        def handle_demux_connection(client_conn, routes):
            backend_conn = None
            try:
                client_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            try:
                is_vless_path, is_vmess, is_ws, is_empty = peek_request_info(client_conn)
                if is_empty:
                    return
                if is_vmess and "vmess_ws" in routes:
                    target_port = routes["vmess_ws"]
                elif not is_vless_path and not is_vmess and "web_ui" in routes:
                    target_port = routes["web_ui"]
                elif not is_ws and "vless_xhttp" in routes:
                    target_port = routes["vless_xhttp"]
                else:
                    target_port = routes.get("vless_ws") or routes.get("vmess_ws") or routes.get("vless_xhttp")
                idle_limit = 60.0 if target_port == routes.get("web_ui") else 300.0
                backend_conn = socket.create_connection(("127.0.0.1", target_port), timeout=5)
                try:
                    backend_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except OSError:
                    pass
                last_active = [time.monotonic()]
                client_conn.settimeout(30.0)
                backend_conn.settimeout(30.0)

                def forward(src, dst):
                    try:
                        while True:
                            try:
                                chunk = src.recv(131072)
                            except socket.timeout:
                                if time.monotonic() - last_active[0] > idle_limit:
                                    break
                                continue
                            if not chunk:
                                break
                            last_active[0] = time.monotonic()
                            dst.sendall(chunk)
                            last_active[0] = time.monotonic()
                    except OSError:
                        pass
                    finally:
                        try:
                            dst.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass

                t = threading.Thread(target=forward, args=(backend_conn, client_conn), daemon=True)
                t.start()
                forward(client_conn, backend_conn)
                t.join()
            except OSError:
                pass
            finally:
                for conn in (client_conn, backend_conn):
                    if conn is not None:
                        try:
                            conn.close()
                        except OSError:
                            pass

        def start_demux_server(listen_ip, listen_port, routes):
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass
            server.bind((listen_ip if listen_ip != "0.0.0.0" else "", listen_port))
            server.listen(128)
            stop_flag = [False]
            def accept_loop():
                while not stop_flag[0]:
                    try:
                        connection, _ = server.accept()
                    except OSError:
                        break
                    if stop_flag[0]:
                        try: connection.close()
                        except OSError: pass
                        break
                    threading.Thread(target=handle_demux_connection, args=(connection, routes), daemon=True).start()
            threading.Thread(target=accept_loop, daemon=True).start()
            print(f"[*] Demux listener: {listen_ip}:{listen_port} -> {routes}")
            return (server, listen_port, stop_flag)

        def write_configs():
            inbounds, demux_servers = [], []
            web_ui_port = logger.port if (not IS_RAILWAY and logger and getattr(logger, "port", None) and WS_PATH != "/") else None
            for ip, port in inbound_ports:
                if DUAL_TRANSPORT or (PROTOCOL == "both" and "xhttp" in TRANSPORTS) or (web_ui_port and ("xhttp" in TRANSPORTS or PROTOCOL == "vmess")):
                    routes = {}
                    if web_ui_port and port != web_ui_port:
                        routes["web_ui"] = web_ui_port
                    if PROTOCOL in ("vless", "both"):
                        if "websocket" in TRANSPORTS:
                            vless_ws_port = port + 10000
                            inbounds.append(make_inbound("127.0.0.1", vless_ws_port, "websocket", proto="vless", path_override=WS_PATH))
                            routes["vless_ws"] = vless_ws_port
                        if "xhttp" in TRANSPORTS:
                            vless_xhttp_port = port + 20000
                            inbounds.append(make_inbound("127.0.0.1", vless_xhttp_port, "xhttp", proto="vless", path_override=WS_PATH))
                            routes["vless_xhttp"] = vless_xhttp_port
                    if PROTOCOL in ("vmess", "both"):
                        vmess_ws_port = port + 11000
                        vmess_path = "/vmess" if PROTOCOL == "both" else WS_PATH
                        inbounds.append(make_inbound("127.0.0.1", vmess_ws_port, "websocket", proto="vmess", path_override=vmess_path))
                        routes["vmess_ws"] = vmess_ws_port
                    demux_servers.append((ip, port, routes))
                elif PROTOCOL in ("vless", "both") and (PROTOCOL == "both" or (web_ui_port and port != web_ui_port)):
                    # Chay song song VLESS (+ VMess) + Web UI bang native fallbacks cua Xray-core (Go 100%, khong qua Python proxy)
                    vless_ws_port = port + 10000
                    fallbacks = [{"path": WS_PATH, "dest": vless_ws_port}]
                    if PROTOCOL == "both":
                        vmess_ws_port = port + 11000
                        fallbacks.append({"path": "/vmess", "dest": vmess_ws_port})
                    if web_ui_port and port != web_ui_port:
                        fallbacks.append({"dest": web_ui_port})
                    inbounds.append({
                        "port": port,
                        "listen": ip,
                        "protocol": "vless",
                        "settings": {
                            "clients": [{"id": UUID, "level": 0}],
                            "decryption": "none",
                            "fallbacks": fallbacks
                        },
                        "streamSettings": {"network": "tcp", "security": "none"}
                    })
                    inbounds.append(make_inbound("127.0.0.1", vless_ws_port, "websocket", proto="vless", path_override=WS_PATH))
                    if PROTOCOL == "both":
                        inbounds.append(make_inbound("127.0.0.1", vmess_ws_port, "websocket", proto="vmess", path_override="/vmess"))
                else:
                    inbounds.append(make_inbound(ip, port, TRANSPORTS[0], proto=PROTOCOL, path_override=WS_PATH))
            xray_config = {
                "log": {"loglevel": "error", "access": "none"},
                "inbounds": inbounds,
                "outbounds": [{"protocol": "freedom", "settings": {"domainStrategy": "UseIPv4"}}]
            }
            if ENABLE_WARP and wgcf_outbound:
                xray_config["outbounds"].insert(0, wgcf_outbound)
            with open("config.json", "w", encoding="utf-8") as config_file:
                json.dump(xray_config, config_file, indent=2)
            return inbounds, demux_servers

        if os.path.exists("frp_info.config"):
            try: os.remove("frp_info.config")
            except OSError: pass

        # Dam bao tat sach tien trinh xray / cloudflared cu con sot lai giu cong 8888
        if platform.system().lower() != "windows":
            subprocess.run(["pkill", "-9", "-x", "xray"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "-x", "cloudflared"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.3)

        inbounds_list, demux_intents = write_configs()
        print(f"[*] Launching XRAY (Mode={RUN_MODE}, Protocol={PROTOCOL}, PortMode={PORT_MODE})...")
        xp = subprocess.Popen([XRAY_BIN, "run", "-c", "config.json"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        clp = None
        demux_listeners = []

        try:
            xray_check_port = inbounds_list[0]["port"]
            xray_check_ip = inbounds_list[0]["listen"]
            if xray_check_ip == "0.0.0.0":
                xray_check_ip = "127.0.0.1"

            def wait_for_xray_listener(timeout=10):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    exit_code = xp.poll()
                    if exit_code is not None:
                        details = xp.stdout.read().strip() if xp.stdout else ""
                        print(f"[ERROR] Xray stopped during startup (exit code {exit_code}).")
                        if details:
                            print(f"[XRAY ERROR] {details}")
                            logger_push(details, "ERROR")
                        return False
                    try:
                        with socket.create_connection((xray_check_ip, xray_check_port), timeout=0.5):
                            print(f"[OK] Xray is listening at {xray_check_ip}:{xray_check_port}.")
                            return True
                    except OSError:
                        time.sleep(0.2)
                print(f"[ERROR] Xray did not open {xray_check_ip}:{xray_check_port} within {timeout}s.")
                return False

            if not wait_for_xray_listener():
                wait_for_config_fix("[ERROR] Xray không thể khởi động với cấu hình hiện tại.")
                continue

            if demux_intents:
                for ip, port, routes in demux_intents:
                    try:
                        demux_listeners.append(start_demux_server(ip, port, routes))
                    except OSError as error:
                        holder = ""
                        if platform.system().lower() != "windows":
                            try:
                                out = subprocess.check_output(["ss", "-tulpn", f"sport = :{port}"], text=True, stderr=subprocess.DEVNULL)
                                m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', out)
                                if m:
                                    holder = f" (đang bị chiếm bởi: {m.group(1)} PID {m.group(2)})"
                            except Exception:
                                pass
                        free_cf_ports = []
                        for cf_p in (8880, 2052, 2082, 2086, 2095, 8080, 80):
                            try:
                                ts = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                ts.bind(("0.0.0.0", cf_p))
                                ts.close()
                                free_cf_ports.append(str(cf_p))
                            except OSError:
                                pass
                        free_hint = f" Các cổng Cloudflare đang TRỐNG trên VPS: {', '.join(free_cf_ports)}." if free_cf_ports else ""
                        wait_for_config_fix(
                            f"[ERROR] Không thể mở cổng demux {ip}:{port}{holder}: {error}.{free_hint} "
                            f"Hãy đổi sang cổng trống (VD: 0.0.0.0:{free_cf_ports[0] if free_cf_ports else '2052'}) hoặc dùng Mode 2 (Named Tunnel)!"
                        )
                        break
                if len(demux_listeners) != len(demux_intents):
                    continue

            def launch_cloudflared():
                if RUN_MODE == "direct":
                    return None
                if RUN_MODE == "named_tunnel":
                    print("[*] Launching Cloudflare Named Tunnel (token mode, HTTP/2)...")
                    named_tunnel_args = [CLF_BIN, "tunnel", "--protocol", "http2", "run", "--token", TUNNEL_TOKEN]
                    return subprocess.Popen(
                        named_tunnel_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace"
                    )

                tunnel_protocol = "http2" if RUN_MODE == "quick_tunnel" else "auto"
                print(f"[*] Launching Cloudflare Tunnel ({tunnel_protocol}) pointing to http://{CLOUDFLARE_TARGET_IP}:{CLOUDFLARE_TARGET_PORT}...")
                return subprocess.Popen(
                    [CLF_BIN, "tunnel", "--protocol", tunnel_protocol, "--url", f"http://{CLOUDFLARE_TARGET_IP}:{CLOUDFLARE_TARGET_PORT}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )

            clp = launch_cloudflared()
            cloudflare_url = None
            published_link_host = None

            def build_vmess_link(sni, port_num, host_hdr, path_str, remark_str, use_tls):
                vmess_obj = {
                    "v": "2",
                    "ps": remark_str,
                    "add": sni,
                    "port": str(port_num),
                    "id": UUID,
                    "aid": "0",
                    "scy": "auto",
                    "net": "ws",
                    "type": "none",
                    "host": host_hdr,
                    "path": path_str,
                    "tls": "tls" if use_tls else "",
                    "sni": host_hdr if use_tls else "",
                    "alpn": "",
                    "fp": "chrome" if use_tls else ""
                }
                raw = json.dumps(vmess_obj, ensure_ascii=False, separators=(",", ":"))
                return "vmess://" + base64.b64encode(raw.encode("utf-8")).decode("utf-8")

            def print_vless_links(tunnel_host, uuid_str, fake_sni, ws_path):
                import urllib.parse
                encoded_path = urllib.parse.quote(ws_path, safe="")
                tunnel_host_info = WS_HOST if WS_HOST and WS_HOST != "trycloudflare.com" else tunnel_host
                payloads = []
                country_flag = flag_emoji(COUNTRY_CODE)
                country_prefix = f"[{country_flag}] {COUNTRY_CODE} | " if country_flag else ""
                http_link_port = 80

                def add_vless_link(sni, transport, label):
                    params = f"type={'ws' if transport == 'websocket' else 'xhttp'}&encryption=none&security="
                    xhttp_params = f"&mode={XHTTP_MODE}" if transport == "xhttp" else ""
                    tr_label = f"{label} {'WS' if transport == 'websocket' else 'XHTTP'}"
                    if PORT_MODE in ("443", "both"):
                        tls_params = f"tls&path={encoded_path}&host={tunnel_host_info}&sni={tunnel_host_info}{xhttp_params}"
                        if transport == "xhttp":
                            tls_params += "&alpn=h3%2Ch2"
                        link_name_443 = urllib.parse.quote(f"{tr_label} 443", safe="")
                        payloads.append(f"vless://{uuid_str}@{sni}:443?{params}{tls_params}#{link_name_443}")
                    if PORT_MODE in ("80", "both"):
                        link_name_80 = urllib.parse.quote(f"{tr_label} {http_link_port}", safe="")
                        payloads.append(f"vless://{uuid_str}@{sni}:{http_link_port}?{params}&path={encoded_path}&host={tunnel_host_info}{xhttp_params}#{link_name_80}")

                def add_vmess_links(sni, label):
                    vmess_path = "/vmess" if PROTOCOL == "both" else ws_path
                    if PORT_MODE in ("443", "both"):
                        payloads.append(build_vmess_link(sni, 443, tunnel_host_info, vmess_path, f"{label} VMess 443", True))
                    if PORT_MODE in ("80", "both"):
                        payloads.append(build_vmess_link(sni, http_link_port, tunnel_host_info, vmess_path, f"{label} VMess {http_link_port}", False))

                for sni_entry in fake_sni.split(","):
                    sni_entry = sni_entry.strip()
                    if not sni_entry:
                        continue
                    sni, _, remark = sni_entry.partition("#")
                    sni, remark = sni.strip(), remark.strip()
                    remark = {"Free Tiktok": "FreeTiktok", "Free Vina Ko Nen": "FreeVina Ko Nen"}.get(remark, remark)
                    base_label = remark or FRIENDLY_NAME_MAP.get(sni) or sni
                    label = f"{country_prefix}{base_label}"
                    if PROTOCOL in ("vless", "both"):
                        for transport in TRANSPORTS:
                            add_vless_link(sni, transport, label)
                    if PROTOCOL in ("vmess", "both"):
                        add_vmess_links(sni, label)

                print("\n" + "=" * 70)
                print(" DIRECT MODE (Cloudflare proxied DNS -> origin :80)" if RUN_MODE == "direct" else " CONNECTED TO CLOUDFLARE TUNNEL")
                print("=" * 70 + "\n")
                with open("frp_info.config", "w", encoding="utf-8") as links_file:
                    links_file.write("\n".join(payloads) + ("\n" if payloads else ""))
                print(" ACTIVE LINKS (VLESS / VMess)")
                print("-" * 70)
                for payload in payloads:
                    print(payload)
                print("-" * 70)
                print("[OK] Links saved to: frp_info.config & /sub endpoint")
                logger_push(f"Đã tạo thành công {len(payloads)} cấu hình ({PROTOCOL.upper()}) tại domain: {tunnel_host_info}", "SUCCESS")

                frp_info = {
                    "payloads": payloads,
                    "ip": get_public_url(),
                    "wshost": tunnel_host,
                    "wspath": ws_path,
                    "transport": TRANSPORT,
                    "protocol": PROTOCOL,
                    "xhttp_mode": XHTTP_MODE if "xhttp" in TRANSPORTS else None,
                    "start_time": START_TIME
                }
                send_webhook(frp_info)
                with open("frp_info.json", "w", encoding="utf-8") as info_file:
                    json.dump(frp_info, info_file, indent=4)

            def monitor_xray(pipe):
                try:
                    with pipe:
                        for line in iter(pipe.readline, ""):
                            logger_push(line.strip(), "XRAY")
                            if re.search(r"permission denied|eacces|address already in use|\berror\b|\bfailed\b", line, re.IGNORECASE):
                                print(f"[XRAY ERROR] {line.strip()}")
                except Exception:
                    pass

            def monitor_cloudflare(pipe):
                nonlocal cloudflare_url, published_link_host
                ansi_escape = re.compile(r"\x1b\[[0-9;]*[mK]")
                try:
                    with pipe:
                        for line in iter(pipe.readline, ""):
                            clean_line = ansi_escape.sub("", line)
                            print(f"[CLOUDFLARE LOG] {clean_line.strip()}")
                            logger_push(clean_line.strip(), "CLOUDFLARE")

                            if RUN_MODE == "named_tunnel":
                                if re.search(r"[Rr]egistered tunnel connection", clean_line):
                                    logger_push(f"Đã kết nối thành công replica vào Cloudflare Named Tunnel ({WS_HOST})!", "SUCCESS")
                                    if published_link_host != WS_HOST:
                                        cloudflare_url = WS_HOST
                                        print_vless_links(cloudflare_url, UUID, FAKE_SNI, WS_PATH)
                                        published_link_host = cloudflare_url
                                continue

                            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", clean_line)
                            if match:
                                new_url = match.group(0).replace("https://", "")
                                if new_url != cloudflare_url:
                                    if cloudflare_url:
                                        print(f"[*] Detected new tunnel domain: {new_url} (was: {cloudflare_url})")
                                    cloudflare_url = new_url
                            if cloudflare_url and published_link_host != cloudflare_url and re.search(r"[Rr]egistered tunnel connection", clean_line):
                                print_vless_links(cloudflare_url, UUID, FAKE_SNI, WS_PATH)
                                published_link_host = cloudflare_url
                except Exception:
                    pass

            threading.Thread(target=monitor_xray, args=(xp.stdout,), daemon=True).start()
            if clp is not None:
                threading.Thread(target=monitor_cloudflare, args=(clp.stdout,), daemon=True).start()

            if RUN_MODE in ("direct", "named_tunnel"):
                cloudflare_url = WS_HOST
                if RUN_MODE == "direct":
                    print("[!] Recommended: restrict origin port 80 to Cloudflare IP ranges only.")
                print_vless_links(cloudflare_url, UUID, FAKE_SNI, WS_PATH)
                published_link_host = cloudflare_url

            while not reload_event.is_set() and not stop_program:
                if tunnel_refresh_event.is_set():
                    tunnel_refresh_event.clear()
                    if RUN_MODE == "quick_tunnel" and clp is not None:
                        print("[*] Refreshing Cloudflare Quick Tunnel on user request...")
                        try:
                            clp.terminate()
                        except OSError:
                            pass
                    else:
                        break

                if RUN_MODE == "direct":
                    if xp.poll() is not None:
                        print("\n[!] WARNING: Xray process has stopped.")
                        break
                else:
                    if xp.poll() is not None:
                        print("\n[!] WARNING: Xray process has stopped; stopping Cloudflare Tunnel.")
                        try:
                            clp.terminate()
                        except OSError:
                            pass
                        break

                    if clp.poll() is not None and xp.poll() is None:
                        print("[!] Launching new Cloudflare Tunnel process...")
                        cloudflare_url = None
                        published_link_host = None
                        clp = launch_cloudflared()
                        threading.Thread(target=monitor_cloudflare, args=(clp.stdout,), daemon=True).start()

                reload_event.wait(0.5)

        except KeyboardInterrupt:
            stop_program = True
            print("\n[*] Stopping services...")
        finally:
            for srv, d_port, stop_flag in demux_listeners:
                stop_flag[0] = True
                try:
                    srv.close()
                except Exception:
                    pass
                try:
                    with socket.create_connection(("127.0.0.1", d_port), timeout=0.1):
                        pass
                except Exception:
                    pass
            for proc in (clp, xp):
                if proc is not None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass

    if logger is not None:
        try:
            logger.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
