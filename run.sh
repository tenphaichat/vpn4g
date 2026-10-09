#!/usr/bin/env bash
set -o pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$SCRIPT_DIR" || exit 1

# Detect Termux
IS_TERMUX=false
if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux"* ]]; then
    IS_TERMUX=true
fi

SERVICE_NAME="xray-vless"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# File quan ly tien trinh khi chay trong Container (Railway/Docker) khong co systemd PID 1
PID_FILE="$SCRIPT_DIR/.${SERVICE_NAME}.pid"
CHILD_PID_FILE="$SCRIPT_DIR/.${SERVICE_NAME}.child.pid"
RUNNER_FILE="$SCRIPT_DIR/.${SERVICE_NAME}-runner.sh"
LOG_FILE="$SCRIPT_DIR/${SERVICE_NAME}.log"

has_systemd(){
    command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]
}

DEF_PORT_QUICK="127.0.0.1:8888"
DEF_PORT_NAMED="127.0.0.1:8888"
DEF_PORT_DIRECT="0.0.0.0:80"
DEF_FAKE_SNI="api24-normal-alisg.tiktokv.com#FreeTiktok,172.67.168.158#FreeVina Ko Nen"
DEF_WS_PATH="/vless"
DEF_WS_HOST="trycloudflare.com"
DEF_TRANSPORT="websocket,xhttp"
DEF_XHTTP_MODE="packet-up"

RUN_MODE=""; PORT=""; UUID=""; FAKE_SNI=""; WS_PATH=""; WS_HOST=""; TUNNEL_TOKEN=""; ENABLE_WARP="false"; WEBHOOK_URL=""; TRANSPORT="websocket,xhttp"; XHTTP_MODE="packet-up"; COUNTRY_CODE=""; CUSTOM_DOMAIN=""; PORT_MODE="both"

header(){ echo; echo -e "${CYAN}===================================================${NC}"; echo -e "${GREEN} $1${NC}"; echo -e "${CYAN}===================================================${NC}"; }
ok(){ echo -e " ${GREEN}[OK]${NC} $1"; }
warn(){ echo -e " ${YELLOW}[!]${NC}  $1"; }
err(){ echo -e " ${RED}[ERR]${NC} $1"; }
info(){ echo -e " ${BLUE}[i]${NC}  $1"; }
setup_step(){
    echo
    echo -e "${CYAN}===================================================${NC}"
    echo -e " ${GREEN}BUOC $1${NC}  $2"
    echo -e "${CYAN}===================================================${NC}"
}
pause_next(){ echo; read -r -p " Press Enter to continue..." _; }
ask_yes_no(){ local ans hint default="${2:-y}"; [ "$default" = "y" ] && hint="Y/n" || hint="y/N"; read -r -p " $1 [$hint]: " ans; ans="${ans:-$default}"; [[ "$ans" =~ ^[Yy]$ ]]; }
ask_val(){ local prompt="$1" default="$2" ans; read -r -p " $prompt [$default]: " ans; [ -n "$ans" ] && echo "$ans" || echo "$default"; }
ask_country(){
    local ans cc
    echo -e " ${BLUE}[i]${NC}  Server country flag (optional)"
    echo -e "      Hint: VN  JP  US  SG  DE  FR  KR  HK  TW  NL  GB  AU  CA"
    read -r -p " Country code (Enter to skip) [${COUNTRY_CODE:-}]: " ans
    if [ -n "$ans" ]; then
        cc="$(printf '%s' "$ans" | tr 'a-z' 'A-Z' | tr -dc 'A-Z')"
        COUNTRY_CODE="${cc:0:2}"
    fi
    [ -n "$COUNTRY_CODE" ] && ok "Country: $COUNTRY_CODE" || info "No country flag."
}
ask_fake_sni(){
    local choice default_choice="3"
    case "$FAKE_SNI" in
        "api24-normal-alisg.tiktokv.com#FreeTiktok"|"api24-normal-alisg.tiktokv.com#Free Tiktok") default_choice="1" ;;
        "172.67.168.158#FreeVina Ko Nen"|"172.67.168.158#Free Vina Ko Nen") default_choice="2" ;;
        "$DEF_FAKE_SNI"|"api24-normal-alisg.tiktokv.com#Free Tiktok,172.67.168.158#Free Vina Ko Nen"|"") ;;
        *) default_choice="tuy chinh" ;;
    esac
    echo -e " ${BLUE}[i]${NC}  FAKE_SNI selection:"
    echo "   1. FreeTiktok  (api24-normal-alisg.tiktokv.com)"
    echo "   2. FreeVina Ko Nen  (172.67.168.158)"
    echo "   3. Ca hai (mac dinh)"
    echo "   Hoac nhap gia tri FAKE_SNI tuy chinh"
    read -r -p " Chon [1/2/3/tuy chinh] [$default_choice]: " choice
    choice="${choice:-$default_choice}"
    case "$choice" in
        1) FAKE_SNI="api24-normal-alisg.tiktokv.com#FreeTiktok" ;;
        2) FAKE_SNI="172.67.168.158#FreeVina Ko Nen" ;;
        3) FAKE_SNI="$DEF_FAKE_SNI" ;;
        "tuy chinh") ;;
        *) FAKE_SNI="$choice" ;;
    esac
    ok "FAKE_SNI: $FAKE_SNI"
}
ask_transport(){
    local choice mode_choice default_choice="3"
    case "$TRANSPORT" in
        xhttp) default_choice="2" ;;
        websocket) default_choice="1" ;;
    esac
    echo -e " ${BLUE}[i]${NC}  Chon transport:"
    echo "   1. WebSocket (on dinh / ho tro client rong nhat)"
    echo "   2. xHTTP (transport HTTP hien dai)"
    echo "   3. Ca WebSocket + xHTTP"
    read -r -p " Chon [1/2/3] [$default_choice]: " choice
    choice="${choice:-$default_choice}"
    case "$choice" in
        1) TRANSPORT="websocket" ;;
        2) TRANSPORT="xhttp" ;;
        3) TRANSPORT="websocket,xhttp" ;;
        *) warn "Lua chon khong hop le; giu lai $TRANSPORT." ;;
    esac
    if [[ "$TRANSPORT" == *xhttp* ]]; then
        echo "   xHTTP mode:"
        echo "   1. packet-up"
        echo "   2. stream-up"
        echo "   3. stream-one"
        case "$XHTTP_MODE" in stream-up) mode_choice=2 ;; stream-one) mode_choice=3 ;; *) mode_choice=1 ;; esac
        read -r -p " Chon xHTTP mode [1/2/3] [$mode_choice]: " choice
        choice="${choice:-$mode_choice}"
        case "$choice" in 1) XHTTP_MODE="packet-up" ;; 2) XHTTP_MODE="stream-up" ;; 3) XHTTP_MODE="stream-one" ;; *) warn "Mode khong hop le; giu lai $XHTTP_MODE." ;; esac
    fi
    if [[ "$TRANSPORT" == *xhttp* ]]; then
        ok "Transport: $TRANSPORT (xHTTP mode: $XHTTP_MODE)"
    else
        ok "Transport: $TRANSPORT"
    fi
}
quick_tunnel_transport(){
    TRANSPORT="websocket"
    warn "Luu y: Quick Tunnel (trycloudflare.com) khong ho tro xHTTP."
    ok "Transport: WebSocket"
}

ask_port_mode(){
    local choice default_choice="3"
    echo -e " ${BLUE}[i]${NC}  Chon port cho link VLESS:"
    echo "   1. Chi port 80 (KHONG TLS)"
    echo "   2. Chi port 443 (TLS)"
    echo "   3. Ca 80 + 443 (mac dinh)"
    read -r -p " Chon [1/2/3] [$default_choice]: " choice
    choice="${choice:-$default_choice}"
    case "$choice" in
        1) PORT_MODE="80" ;;
        2) PORT_MODE="443" ;;
        3) PORT_MODE="both" ;;
        *) warn "Lua chon khong hop le; giu lai ${PORT_MODE:-both}."; PORT_MODE="${PORT_MODE:-both}" ;;
    esac
    ok "Che do port: $PORT_MODE"
}
env_get(){ grep -E "^$1=" .env 2>/dev/null | head -n1 | cut -d= -f2-; }

run_as_root(){
    if [ "$(id -u)" = "0" ]; then "$@"; else sudo "$@"; fi
}

uuid_gen(){
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import uuid; print(uuid.uuid4())'
    elif command -v uuidgen >/dev/null 2>&1; then
        uuidgen
    else
        cat /proc/sys/kernel/random/uuid 2>/dev/null
    fi
}

# ==================== Termux ====================
termux_bootstrap(){
    $IS_TERMUX || return 0
    echo
    echo -e " ${GREEN}========================================${NC}"
    echo -e " ${GREEN}  Ban dang chay server tren Termux!${NC}"
    echo -e " ${GREEN}========================================${NC}"
    echo
    if ! command -v python3 >/dev/null 2>&1; then
        info "Dang cai Python..."
        if ! pkg install -y python; then
            err "Cai Python that bai. Hay chay 'termux-change-repo', chon mirror hoat dong, sau do thu lai."
            return 1
        fi
    fi
    if ! python3 -m pip --version >/dev/null 2>&1; then
        err "Python pip chua san sang. Hay chay: pkg install python"
        return 1
    fi
    ok "Python Termux san sang."
}

# ==================== Python bootstrap ====================
detect_python(){
    if $IS_TERMUX; then
        if command -v python3 >/dev/null 2>&1; then echo python3; return; fi
        err "Khong tim thay Python 3. Hay chay: pkg install python"
        return
    fi
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        if "$SCRIPT_DIR/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
            echo "$SCRIPT_DIR/.venv/bin/python"; return
        fi
        warn ".venv bi loi (khong co pip). Dang xoa..."
        rm -rf "$SCRIPT_DIR/.venv"
    fi
    if command -v python3 >/dev/null 2>&1; then echo python3; return; fi
    if command -v python >/dev/null 2>&1; then
        if python -c 'import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)' 2>/dev/null; then
            echo python; return
        fi
    fi
    err "Khong tim thay Python 3. Hay cai: sudo apt install python3 python3-venv python3-pip"
}

install_venv_package(){
    local py="$1"
    command -v apt-get >/dev/null 2>&1 || return 1
    local pyver
    pyver="$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "3")"
    info "Dang tu cai python${pyver}-venv python3-pip qua apt..."
    run_as_root apt-get update -qq 2>/dev/null
    run_as_root apt-get install -y -qq "python${pyver}-venv" python3-pip 2>&1 | tail -3
}

ensure_python_deps(){
    local py="$1"
    if $IS_TERMUX; then
        if "$py" -c "import dotenv, requests" 2>/dev/null; then return 0; fi
        warn "Thieu Python dependencies. Dang cai..."
        if "$py" -m pip install --user -q python-dotenv requests; then
            "$py" -c "import dotenv, requests" 2>/dev/null && { ok "Da cai dependencies can thiet."; return 0; }
        fi
        err "Cai dependencies can thiet that bai. Kiem tra ket noi mang roi thu lai."
        return 1
    fi

    # Tren Linux/Ubuntu, systemd chay duoi quyen root nen phai kiem tra bang run_as_root hoac dung .venv
    if [[ "$py" = "$SCRIPT_DIR/.venv/"* ]]; then
        if "$py" -c "import dotenv, requests" 2>/dev/null; then return 0; fi
    else
        if run_as_root "$py" -c "import dotenv, requests" 2>/dev/null; then return 0; fi
    fi
    warn "Thieu Python dependencies. Dang cai..."

    if command -v apt-get >/dev/null 2>&1; then
        run_as_root apt-get update -qq 2>/dev/null || true
        run_as_root apt-get install -y -qq python3-dotenv python3-requests python3-pip python3-venv >/dev/null 2>&1 || true
        if run_as_root "$py" -c "import dotenv, requests" 2>/dev/null; then
            ok "Da cai dependencies qua apt."
            return 0
        fi
    fi

    if run_as_root "$py" -m pip install -q python-dotenv requests 2>/dev/null || run_as_root "$py" -m pip install --break-system-packages -q python-dotenv requests 2>/dev/null; then
        if run_as_root "$py" -c "import dotenv, requests" 2>/dev/null; then
            ok "Deps installed."
            return 0
        fi
    fi

    info "Dang tao .venv..."
    rm -rf "$SCRIPT_DIR/.venv"
    if ! "$py" -m venv "$SCRIPT_DIR/.venv" 2>/dev/null || [ ! -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        install_venv_package "$py"
        rm -rf "$SCRIPT_DIR/.venv"
        "$py" -m venv "$SCRIPT_DIR/.venv" 2>/dev/null
    fi
    [ -x "$SCRIPT_DIR/.venv/bin/python" ] || { err "Tao .venv that bai."; return 1; }
    local venv_py="$SCRIPT_DIR/.venv/bin/python"
    "$venv_py" -m pip install -q python-dotenv requests 2>&1 | tail -3
    if "$venv_py" -c "import dotenv, requests" 2>/dev/null; then
        ok "Da cai dependencies vao .venv/."
        PYBIN="$venv_py"; return 0
    fi
    err "Cai dependencies that bai."; return 1
}

prepare_python(){
    PYBIN="$(detect_python)"
    [ -z "$PYBIN" ] && return 1
    ensure_python_deps "$PYBIN" || return 1
    if [[ "$PYBIN" = /* ]]; then PYBIN_ABS="$PYBIN"
    else PYBIN_ABS="$(command -v "$PYBIN" 2>/dev/null)"; fi
    ok "Python san sang: $PYBIN_ABS"
}

# ==================== .env ====================
write_env(){
    UUID="${UUID:-$(uuid_gen)}"
    [ -n "$UUID" ] || { err "Khong tao duoc VLESS UUID."; return 1; }
    {
        echo "RUN_MODE=$RUN_MODE"; echo "PORT=$PORT"; echo "XRAY_UUID=$UUID"
        echo "FAKE_SNI=$FAKE_SNI"; echo "WS_PATH=$WS_PATH"; echo "WS_HOST=$WS_HOST"
        echo "TRANSPORT=$TRANSPORT"; echo "XHTTP_MODE=$XHTTP_MODE"; echo "ENABLE_WARP=$ENABLE_WARP"
        echo "WEBHOOK_URL=$WEBHOOK_URL"; echo "TUNNEL_TOKEN=$TUNNEL_TOKEN"
        echo "COUNTRY_CODE=$COUNTRY_CODE"
        echo "CUSTOM_DOMAIN=$CUSTOM_DOMAIN"
        echo "PORT_MODE=$PORT_MODE"
    } > .env
    ok "Da ghi .env (RUN_MODE=$RUN_MODE)"
}

load_existing(){
    [ -f .env ] || return 0
    UUID="$(env_get XRAY_UUID)"; FAKE_SNI="$(env_get FAKE_SNI)"
    WS_PATH="$DEF_WS_PATH"; WS_HOST="$(env_get WS_HOST)"
    TUNNEL_TOKEN="$(env_get TUNNEL_TOKEN)"; ENABLE_WARP="$(env_get ENABLE_WARP)"
    WEBHOOK_URL="$(env_get WEBHOOK_URL)"; TRANSPORT="$(env_get TRANSPORT)"; XHTTP_MODE="$(env_get XHTTP_MODE)"
    XHTTP_MODE="${XHTTP_MODE:-$DEF_XHTTP_MODE}"
    COUNTRY_CODE="$(env_get COUNTRY_CODE)"
    CUSTOM_DOMAIN="$(env_get CUSTOM_DOMAIN)"
    PORT_MODE="$(env_get PORT_MODE)"
    PORT_MODE="${PORT_MODE:-both}"
}

# ==================== Systemd & Container Supervisor ====================
has_entrypoint(){
    tr '\0' ' ' < /proc/1/cmdline 2>/dev/null | grep -q "entrypoint.sh"
}

svc_is_active(){
    if has_systemd; then
        systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null
    elif has_entrypoint; then
        pgrep -f "$SCRIPT_DIR/main.py" >/dev/null 2>&1
    else
        [ -f "$PID_FILE" ] || return 1
        local pid
        pid="$(cat "$PID_FILE" 2>/dev/null)"
        [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
    fi
}

svc_exists(){
    if has_systemd; then
        [ -f "$SERVICE_FILE" ]
    elif has_entrypoint; then
        return 0
    else
        [ -f "$RUNNER_FILE" ]
    fi
}

svc_stop(){
    if has_systemd; then
        run_as_root systemctl stop "$SERVICE_NAME" 2>/dev/null
        return $?
    fi
    if [ -f "$PID_FILE" ]; then
        local sup_pid
        sup_pid="$(cat "$PID_FILE" 2>/dev/null)"
        [ -n "$sup_pid" ] && kill -0 "$sup_pid" 2>/dev/null && kill -TERM "$sup_pid" 2>/dev/null
    fi
    if [ -f "$CHILD_PID_FILE" ]; then
        local cpid
        cpid="$(cat "$CHILD_PID_FILE" 2>/dev/null)"
        if [ -n "$cpid" ] && kill -0 "$cpid" 2>/dev/null; then
            kill -INT "$cpid" 2>/dev/null || true
            pkill -TERM -P "$cpid" 2>/dev/null || true
            sleep 1
            kill -TERM "$cpid" 2>/dev/null || true
            pkill -KILL -P "$cpid" 2>/dev/null || true
        fi
    fi
    pkill -9 -f "$SCRIPT_DIR/main.py" 2>/dev/null || true
    pkill -9 -f "$SCRIPT_DIR/xray" 2>/dev/null || true
    pkill -9 -f "$SCRIPT_DIR/cloudflared" 2>/dev/null || true
    pkill -9 -x "tee" 2>/dev/null || true
    rm -f "$PID_FILE" "$CHILD_PID_FILE"
    return 0
}

tune_network_sysctl(){
    $IS_TERMUX && return 0
    command -v sysctl >/dev/null 2>&1 || return 0
    run_as_root sysctl -w net.core.rmem_max=26214400 >/dev/null 2>&1 || true
    run_as_root sysctl -w net.core.wmem_max=26214400 >/dev/null 2>&1 || true
    run_as_root sysctl -w net.core.rmem_default=26214400 >/dev/null 2>&1 || true
    run_as_root sysctl -w net.core.wmem_default=26214400 >/dev/null 2>&1 || true
    run_as_root sysctl -w net.ipv4.tcp_rmem="4096 87380 26214400" >/dev/null 2>&1 || true
    run_as_root sysctl -w net.ipv4.tcp_wmem="4096 65536 26214400" >/dev/null 2>&1 || true
    run_as_root sysctl -w net.core.default_qdisc=fq >/dev/null 2>&1 || true
    run_as_root sysctl -w net.ipv4.tcp_congestion_control=bbr >/dev/null 2>&1 || true
}

svc_start(){
    tune_network_sysctl
    if has_systemd; then
        run_as_root systemctl start "$SERVICE_NAME" 2>/dev/null
        return $?
    elif has_entrypoint; then
        svc_stop
        sleep 4
        svc_is_active
        return $?
    fi
    if [ ! -x "$RUNNER_FILE" ]; then
        install_service
        return $?
    fi
    svc_is_active && svc_stop
    if command -v setsid >/dev/null 2>&1; then
        setsid nohup "$RUNNER_FILE" >/dev/null 2>&1 < /dev/null &
    else
        nohup "$RUNNER_FILE" >/dev/null 2>&1 < /dev/null &
    fi
    echo $! > "$PID_FILE"
    sleep 1
    svc_is_active
}

svc_restart(){
    tune_network_sysctl
    if has_systemd; then
        run_as_root systemctl restart "$SERVICE_NAME" 2>/dev/null
        sleep 2
        svc_is_active
    elif has_entrypoint; then
        svc_stop
        sleep 4
        svc_is_active
    else
        if [ ! -x "$RUNNER_FILE" ]; then
            install_service
            return $?
        fi
        svc_stop
        sleep 1
        svc_start
    fi
}

svc_status(){
    if has_systemd; then
        systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null || info "Chua cai."
    else
        if ! svc_exists; then
            info "Chua cai."
            return 1
        fi
        if svc_is_active; then
            echo -e " ${GREEN}●${NC} ${SERVICE_NAME} - Railway/Container Background Supervisor"
            echo "   Active  : active (running)"
            echo "   Sup PID : $(cat "$PID_FILE" 2>/dev/null)"
            echo "   Main PID: $(cat "$CHILD_PID_FILE" 2>/dev/null)"
            echo "   Log file: $LOG_FILE"
            echo
            ps -ef | grep -E "vless/(main\.py|xray|cloudflared)" | grep -v grep || true
            echo
            echo "--- 20 dong log gan nhat ---"
            tail -n 20 "$LOG_FILE" 2>/dev/null || true
        else
            echo -e " ${YELLOW}○${NC} ${SERVICE_NAME} - Railway/Container Background Supervisor"
            echo "   Active  : inactive (dead)"
        fi
    fi
}

svc_logs(){
    if has_systemd; then
        journalctl -u "$SERVICE_NAME" -f --no-pager -n 50
    else
        touch "$LOG_FILE"
        tail -n 50 -f "$LOG_FILE"
    fi
}

svc_remove(){
    if has_systemd; then
        if [ -f "$SERVICE_FILE" ]; then
            svc_is_active && run_as_root systemctl stop "$SERVICE_NAME"
            run_as_root systemctl disable "$SERVICE_NAME" 2>/dev/null
            run_as_root rm -f "$SERVICE_FILE"
            run_as_root systemctl daemon-reload
            ok "Da xoa service."
        else
            info "Chua cai."
        fi
    else
        if svc_exists || svc_is_active; then
            svc_stop
            rm -f "$RUNNER_FILE" "$LOG_FILE"
            ok "Da xoa background service."
        else
            info "Chua cai."
        fi
    fi
}

install_cli_shims(){
    # Cai wrapper systemctl & journalctl vao /usr/local/bin de lenh systemctl status xray-vless hoat dong trong container
    [ "$(id -u)" = "0" ] || return 0
    [ -d /usr/local/bin ] || return 0
    cat <<SHIM > /usr/local/bin/systemctl
#!/usr/bin/env bash
if [ -d /run/systemd/system ] && [ -x /bin/systemctl ]; then exec /bin/systemctl "\$@"; fi
QUIET=false; ARGS=()
for a in "\$@"; do
    case "\$a" in
        --quiet|-q|--no-pager|-l) [ "\$a" = "--quiet" ] || [ "\$a" = "-q" ] && QUIET=true ;;
        *) ARGS+=("\$a") ;;
    esac
done
ACTION="\${ARGS[0]:-}"
case "\$ACTION" in
    start) bash "$SCRIPT_DIR/run.sh" --start ;;
    stop) bash "$SCRIPT_DIR/run.sh" --stop ;;
    restart) bash "$SCRIPT_DIR/run.sh" --restart ;;
    status) bash "$SCRIPT_DIR/run.sh" --status ;;
    is-active)
        if [ -f "$PID_FILE" ] && kill -0 "\$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
            \$QUIET || echo "active"; exit 0
        else
            \$QUIET || echo "inactive"; exit 3
        fi ;;
    *) exit 0 ;;
esac
SHIM
    cat <<JSHIM > /usr/local/bin/journalctl
#!/usr/bin/env bash
if [ -d /run/systemd/system ] && [ -x /bin/journalctl ]; then exec /bin/journalctl "\$@"; fi
FOLLOW=false; LINES=50
while [ \$# -gt 0 ]; do
    case "\$1" in
        -f|--follow) FOLLOW=true; shift ;;
        -n|--lines) LINES="\$2"; shift 2 ;;
        *) shift ;;
    esac
done
touch "$LOG_FILE"
\$FOLLOW && exec tail -n "\$LINES" -f "$LOG_FILE" || exec tail -n "\$LINES" "$LOG_FILE"
JSHIM
    chmod +x /usr/local/bin/systemctl /usr/local/bin/journalctl 2>/dev/null || true
}

install_service(){
    [ -f .env ] || { err "Khong tim thay .env."; return 1; }
    prepare_python || return 1
    tune_network_sysctl

    if has_systemd; then
        if [ "$(id -u)" != "0" ] && ! command -v sudo >/dev/null 2>&1; then
            err "Can quyen root hoac sudo."; return 1
        fi
        svc_is_active && svc_stop

        info "Dang cai systemd service: $SERVICE_NAME"
        run_as_root tee "$SERVICE_FILE" >/dev/null <<UNIT
[Unit]
Description=May chu Xray VLESS-WS
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYBIN_ABS $SCRIPT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
UNIT

        run_as_root systemctl daemon-reload || return 1
        run_as_root systemctl enable "$SERVICE_NAME" 2>/dev/null || true
        run_as_root systemctl start "$SERVICE_NAME" || { err "Khong the khoi dong systemd service."; return 1; }
        ok "Service da chay (systemd). Dang doi link VLESS..."
    else
        svc_stop
        info "Moi truong Railway/Container (khong can systemd PID 1)."
        info "Dang khoi tao Background Supervisor cho: $SERVICE_NAME"
        cat <<RUNNER > "$RUNNER_FILE"
#!/usr/bin/env bash
cd "$SCRIPT_DIR" || exit 1
export PYTHONUNBUFFERED=1
cleanup() {
    if [ -n "\${CHILD_PID:-}" ] && kill -0 "\$CHILD_PID" 2>/dev/null; then
        kill -INT "\$CHILD_PID" 2>/dev/null || true
        pkill -TERM -P "\$CHILD_PID" 2>/dev/null || true
        sleep 1
        kill -TERM "\$CHILD_PID" 2>/dev/null || true
    fi
    rm -f "$CHILD_PID_FILE"
    exit 0
}
trap '' HUP
trap cleanup TERM INT EXIT
while true; do
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] [SUPERVISOR] Starting $PYBIN_ABS $SCRIPT_DIR/main.py" >> "$LOG_FILE"
    "$PYBIN_ABS" -u "$SCRIPT_DIR/main.py" >> "$LOG_FILE" 2>&1 &
    CHILD_PID=\$!
    echo "\$CHILD_PID" > "$CHILD_PID_FILE"
    wait "\$CHILD_PID"
    EXIT_CODE=\$?
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] [SUPERVISOR] main.py exited (\$EXIT_CODE). Restarting in 10s..." >> "$LOG_FILE"
    sleep 10
done
RUNNER
        chmod +x "$RUNNER_FILE"
        : > "$LOG_FILE"
        install_cli_shims
        svc_start || { err "Khong the khoi dong background supervisor."; return 1; }
        ok "Service da chay ngam (PID $(cat "$PID_FILE")). Dang doi link VLESS..."
    fi
}

wait_and_show_links(){
    local tries=0
    while [ $tries -lt 90 ]; do
        if [ -f "$SCRIPT_DIR/frp_info.config" ] && [ -s "$SCRIPT_DIR/frp_info.config" ]; then
            sleep 2
            echo
            header "Link VLESS"
            echo
            cat "$SCRIPT_DIR/frp_info.config"
            echo
            ok "Sao chep mot link ben tren vao v2rayNG / Shadowrocket."
            if [ "$RUN_MODE" = "quick_tunnel" ]; then
                warn "Hostname Quick Tunnel thay doi sau moi lan khoi dong lai."
                info "Xem link moi sau khi khoi dong lai: cat $SCRIPT_DIR/frp_info.config"
            fi
            return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    err "Het thoi gian doi link VLESS sau 90 giay."
    if has_systemd; then
        info "Kiem tra service: journalctl -u $SERVICE_NAME -e --no-pager -n 30"
    else
        info "Kiem tra log: tail -n 30 $LOG_FILE"
    fi
    return 1
}

# ==================== Khoi dong server ====================
start_server(){
    rm -f "$SCRIPT_DIR/frp_info.config"
    if $IS_TERMUX; then
        prepare_python || return 1
        if [ "$RUN_MODE" != "direct" ] && ! command -v cloudflared >/dev/null 2>&1; then
            info "Quick/Named Tunnel can cloudflared. Dang cai package can thiet..."
            if ! pkg install -y cloudflared; then
                err "Cai cloudflared that bai. Hay kiem tra mirror/mang roi thu lai."
                return 1
            fi
        fi
        echo
        info "Dang chay server truc tiep (che do Termux)..."
        info "Nhan Ctrl+C de dung server."
        echo
        "$PYBIN_ABS" "$SCRIPT_DIR/main.py"
    else
        install_service || return 1
        wait_and_show_links
    fi
}

# ==================== Cac che do cai dat ====================
quick_mode(){
    header "Quick Tunnel"
    info "Khong can domain. Cloudflare cap hostname ngau nhien sau moi lan chay."
    load_existing

    setup_step "1/4" "Fake SNI"
    ask_fake_sni

    setup_step "2/4" "Port link VLESS"
    WS_PATH="$DEF_WS_PATH"
    quick_tunnel_transport
    RUN_MODE="quick_tunnel"; PORT="$DEF_PORT_QUICK"
    [ -n "$WS_HOST" ] && [ "$WS_HOST" != "$DEF_WS_HOST" ] && CUSTOM_DOMAIN="$WS_HOST"
    WS_HOST="$DEF_WS_HOST"
    ask_port_mode

    setup_step "3/4" "Vi tri node"
    ask_country

    setup_step "4/4" "Luu va khoi dong"
    write_env || return 1
    start_server
}

auto_quick_mode(){
    header "Quick Tunnel (Auto Mode 1 - Railway)"
    load_existing
    RUN_MODE="quick_tunnel"
    PORT="$DEF_PORT_QUICK"
    FAKE_SNI="${FAKE_SNI:-$DEF_FAKE_SNI}"
    WS_PATH="$DEF_WS_PATH"
    WS_HOST="$DEF_WS_HOST"
    TRANSPORT="websocket"
    PORT_MODE="${PORT_MODE:-both}"
    write_env || exit 1
    start_server
}

named_mode(){
    header "Named Cloudflare Tunnel"
    info "Can Cloudflare Zero Trust."
    echo -e " ${CYAN}Truoc khi tiep tuc trong Zero Trust:${NC}"
    echo "   - Networks -> Tunnels -> Create -> Cloudflared -> sao chep token."
    echo -e "   - Public Hostname -> Service = ${GREEN}http://127.0.0.1:8888${NC}"
    echo
    read -r -p " Nhan Enter khi san sang..." _
    load_existing
    [ "$(env_get RUN_MODE)" = "quick_tunnel" ] && TRANSPORT="$DEF_TRANSPORT"

    setup_step "1/6" "Domain va tunnel credentials"
    local def_host="${WS_HOST:-}"
    [ "$def_host" = "trycloudflare.com" ] || [ -z "$def_host" ] && def_host="${CUSTOM_DOMAIN:-}"
    WS_HOST="$(ask_val "Domain (vi du: vless.example.com)" "$def_host")"
    TUNNEL_TOKEN="$(ask_val "Tunnel connector token" "${TUNNEL_TOKEN:-}")"
    [ -z "$WS_HOST" ] || [ "$WS_HOST" = "trycloudflare.com" ] && { err "Can domain."; return 1; }
    [ -z "$TUNNEL_TOKEN" ] && { err "Can token."; return 1; }
    RUN_MODE="named_tunnel"; PORT="$DEF_PORT_NAMED"

    setup_step "2/6" "Fake SNI"
    ask_fake_sni

    setup_step "3/6" "Diem cuoi transport"
    WS_PATH="$DEF_WS_PATH"; TRANSPORT="${TRANSPORT:-$DEF_TRANSPORT}"
    ask_transport

    setup_step "4/6" "Port link VLESS"
    ask_port_mode

    setup_step "5/6" "Vi tri node"
    ask_country

    setup_step "6/6" "Luu va khoi dong"
    CUSTOM_DOMAIN="$WS_HOST"
    write_env || return 1
    start_server
}

direct_mode(){
    header "Direct Cloudflare"
    info "Khong dung cloudflared. Cloudflare chuyen tiep vao port 80."
    echo -e " ${CYAN}Truoc khi tiep tuc trong Cloudflare:${NC}"
    echo -e "   - ${GREEN}vless.example.com -> A -> <VPS IP>${NC}, proxy ${GREEN}ON${NC} (orange cloud)"
    echo -e "   - SSL/TLS -> ${GREEN}Flexible${NC}"
    echo -e "   - Cho phep TCP inbound ${GREEN}80${NC} tu IP Cloudflare"
    echo
    read -r -p " Nhan Enter khi san sang..." _
    load_existing
    [ "$(env_get RUN_MODE)" = "quick_tunnel" ] && TRANSPORT="$DEF_TRANSPORT"

    setup_step "1/6" "Domain va origin listener"
    local def_host="${WS_HOST:-}"
    [ "$def_host" = "trycloudflare.com" ] || [ -z "$def_host" ] && def_host="${CUSTOM_DOMAIN:-}"
    WS_HOST="$(ask_val "Domain" "$def_host")"
    PORT="$(ask_val "Origin listen address:port" "$DEF_PORT_DIRECT")"
    [ -z "$WS_HOST" ] || [ "$WS_HOST" = "trycloudflare.com" ] && { err "Can domain."; return 1; }
    RUN_MODE="direct"

    setup_step "2/6" "Fake SNI"
    ask_fake_sni

    setup_step "3/6" "Diem cuoi transport"
    WS_PATH="$DEF_WS_PATH"; TRANSPORT="${TRANSPORT:-$DEF_TRANSPORT}"
    ask_transport

    setup_step "4/6" "Port link VLESS"
    ask_port_mode

    setup_step "5/6" "Vi tri node"
    ask_country

    setup_step "6/6" "Luu va khoi dong"
    CUSTOM_DOMAIN="$WS_HOST"
    write_env || return 1
    start_server
}

# ==================== Quan ly Service ====================
service_manager(){
    if $IS_TERMUX; then
        warn "Quan ly Service khong ho tro tren Termux."
        info "Tren Termux, chay mot setup mode (1/2/3) de khoi dong server truc tiep."
        return 1
    fi
    while true; do
        header "Quan ly Service"
        local st
        if svc_is_active; then
            st="${GREEN}● Dang chay${NC}"
        elif svc_exists; then
            st="${YELLOW}● Da dung${NC}"
        else
            st="${RED}● Chua cai${NC}"
        fi
        echo -e "  Service : ${CYAN}${SERVICE_NAME}${NC}    $st"
        [ -f .env ] && echo -e "  Mode    : ${CYAN}$(env_get RUN_MODE)${NC}  →  $(env_get WS_HOST)"
        echo
        echo " 1. Khoi dong"
        echo " 2. Dung"
        echo " 3. Khoi dong lai"
        echo " 4. Xem log (truc tiep)"
        echo " 5. Trang thai"
        echo " 6. Xem link VLESS"
        echo " 7. Cai lai service"
        echo " 8. Xoa service"
        echo " 0. Quay lai"
        read -r -p " Chon [0-8]: " c
        case "$c" in
            1) svc_start && ok "Da khoi dong." || err "That bai." ;;
            2) svc_stop && ok "Da dung." || err "Khong dang chay." ;;
            3) svc_restart && ok "Da khoi dong lai." || err "That bai." ;;
            4) info "Nhan Ctrl+C de dung xem log."; echo; svc_logs ;;
            5) svc_status ;;
            6) if [ -f "$SCRIPT_DIR/frp_info.config" ] && [ -s "$SCRIPT_DIR/frp_info.config" ]; then
                   header "Link VLESS"; echo; cat "$SCRIPT_DIR/frp_info.config"; echo
               else info "Chua co link. Hay khoi dong service truoc."; fi ;;
            7) install_service ;;
            8) svc_remove ;;
            0) return ;;
            *) err "Lua chon khong hop le" ;;
        esac
        pause_next
    done
}

# ==================== Go cai dat ====================
uninstall_all(){
    header "Go cai dat"
    info "CHI xoa file do project nay tai ve/tao ra."
    echo -e " ${YELLOW}Se xoa:${NC}"
    echo "   Binaries: xray, cloudflared, wgcf-cli"
    echo "   Tao ra: .env, config.json, wgcf.json, frp_info.*, config.yml"
    echo "   Thu muc: xray_bin, wgcf_bin, __pycache__, .venv"
    svc_exists && echo -e "   Service: ${CYAN}$SERVICE_NAME${NC}"
    echo
    info "KHONG BAO GIO xoa file source."
    echo
    ask_yes_no "Tiep tuc?" "n" || { info "Da huy."; return; }
    if ! $IS_TERMUX && (svc_exists || svc_is_active); then
        svc_remove
    fi
    local removed=0
    for f in xray xray.exe cloudflared cloudflared.exe wgcf-cli wgcf-cli.exe \
             .env config.json wgcf.json wgcf.xray.json frp_info.json frp_info.config \
             frpc.toml config.yml xray.zip cloudflared_temp.archive wgcf-cli.tar.zstd \
             "$PID_FILE" "$CHILD_PID_FILE" "$RUNNER_FILE" "$LOG_FILE"; do
        [ -e "$f" ] && rm -rf -- "$f" && { ok "Removed $f"; removed=1; }
    done
    for d in xray_bin wgcf_bin __pycache__ .venv; do
        [ -d "$d" ] && rm -rf -- "$d" && { ok "Removed $d/"; removed=1; }
    done
    [ "$removed" = "0" ] && info "Da sach." || ok "Hoan tat."
}

# ==================== Tham so CLI (Non-Interactive) ====================
case "${1:-}" in
    --auto|--quick|--mode1)
        auto_quick_mode
        exit $?
        ;;
    --start)
        if [ ! -x "$RUNNER_FILE" ]; then install_service; else svc_start; fi
        exit $?
        ;;
    --stop)
        svc_stop
        exit $?
        ;;
    --restart)
        rm -f "$SCRIPT_DIR/frp_info.config"
        svc_restart && wait_and_show_links
        exit $?
        ;;
    --status)
        svc_status
        exit $?
        ;;
    --logs)
        svc_logs
        exit $?
        ;;
esac

# ==================== Menu chinh ====================
termux_bootstrap || { err "Khong the chuan bi Termux. Hay sua package/mirror roi chay lai."; exit 1; }
while true; do
    header "May chu Xray VLESS-WS (Railway Optimized)"
    $IS_TERMUX && echo -e "  ${GREEN}[Termux]${NC} Che do truc tiep (khong systemd)"
    ! $IS_TERMUX && ! has_systemd && echo -e "  ${CYAN}[Railway/Container]${NC} Background Supervisor (khong can systemd PID 1)"
    if ! $IS_TERMUX && (svc_exists || svc_is_active); then
        if svc_is_active; then
            echo -e "  ${GREEN}● Service dang chay${NC}  $(env_get RUN_MODE) → $(env_get WS_HOST)"
        else
            echo -e "  ${YELLOW}● Service da dung${NC}"
        fi
        echo
    fi
    echo " 1. [1] Quick Tunnel - [tao ngay khong can domain]"
    echo " 2. [2] Named Cloudflare Tunnel - [can domain]"
    echo " 3. [3] Direct Cloudflare - [can domain + public port]"
    echo " 4. Quan ly Service"
    echo " 5. Go cai dat"
    echo " 6. Thoat"
    read -r -p " Chon [1-6] [1]: " MENU_CHOICE
    MENU_CHOICE="${MENU_CHOICE:-1}"
    case "$MENU_CHOICE" in
        1) quick_mode ;;
        2) named_mode ;;
        3) direct_mode ;;
        4) service_manager ;;
        5) uninstall_all ;;
        6) exit 0 ;;
        *) err "Lua chon khong hop le" ;;
    esac
    pause_next
done
