#!/usr/bin/env bash
set -euo pipefail

REPO="${XRAY_VLESS_REPO:-https://github.com/tenphaichat/vpn4g.git}"
INSTALL_DIR="${HOME}/vless"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}  Xray VLESS-WS Server - Railway Optimized Install${NC}"
echo -e "${CYAN}====================================================${NC}"
echo

run_root() {
    if [ "$(id -u)" = "0" ]; then "$@"; else sudo "$@"; fi
}

# 1. Install git & essential process utilities if needed
if ! command -v git >/dev/null 2>&1 || ! command -v pgrep >/dev/null 2>&1; then
    echo -e " ${YELLOW}[!]${NC} Installing required packages (git, procps, python3-venv)..."
    if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux"* ]]; then
        pkg install -y git python
    elif command -v apt-get >/dev/null 2>&1; then
        run_root apt-get update -qq && run_root apt-get install -y -qq git curl procps python3 python3-venv python3-pip
    elif command -v yum >/dev/null 2>&1; then
        run_root yum install -y git curl procps-ng python3 python3-pip
    fi
fi

# 2. Neu chay trong Container (Railway/Docker) khong co systemd PID 1,
#    tu dong cai dat systemctl & journalctl container shim vao /usr/local/bin
if [ ! -d /run/systemd/system ] && [ "$(id -u)" = "0" ]; then
    echo -e " ${CYAN}[i]${NC} Phat hien Container khong co systemd PID 1 -> Cai dat Container Service Shim..."
    mkdir -p /usr/local/bin /run/container-services /var/log/container-services /etc/systemd/system

    cat << 'EOF' > /usr/local/bin/systemctl
#!/usr/bin/env bash
if [ -d /run/systemd/system ] && [ -x /bin/systemctl ]; then exec /bin/systemctl "$@"; fi

STATE_DIR="/run/container-services"
LOG_DIR="/var/log/container-services"
mkdir -p "$STATE_DIR" "$LOG_DIR"

QUIET=false; ARGS=()
for arg in "$@"; do
    case "$arg" in
        --quiet|-q|--no-pager|-l) [ "$arg" = "--quiet" ] || [ "$arg" = "-q" ] && QUIET=true ;;
        *) ARGS+=("$arg") ;;
    esac
done

ACTION="${ARGS[0]:-}"; SVC="${ARGS[1]:-xray-vless}"; SVC="${SVC%.service}"
UNIT_FILE="/etc/systemd/system/${SVC}.service"
PID_FILE="${STATE_DIR}/${SVC}.pid"
CHILD_PID_FILE="${STATE_DIR}/${SVC}.child.pid"
RUNNER_FILE="${STATE_DIR}/${SVC}.runner.sh"
LOG_FILE="${LOG_DIR}/${SVC}.log"

parse_unit() {
    if [ -f "$UNIT_FILE" ]; then
        WORKDIR="$(grep -E '^WorkingDirectory=' "$UNIT_FILE" | head -n1 | cut -d= -f2-)"
        EXECSTART="$(grep -E '^ExecStart=' "$UNIT_FILE" | head -n1 | cut -d= -f2-)"
        RESTARTSEC="$(grep -E '^RestartSec=' "$UNIT_FILE" | head -n1 | cut -d= -f2-)"
    fi
    WORKDIR="${WORKDIR:-/root/vless}"
    if [ -z "${EXECSTART:-}" ]; then
        if [ -x "${WORKDIR}/.venv/bin/python" ]; then
            EXECSTART="${WORKDIR}/.venv/bin/python ${WORKDIR}/main.py"
        else
            EXECSTART="python3 ${WORKDIR}/main.py"
        fi
    fi
    RESTARTSEC="${RESTARTSEC:-10}"
}

is_running() {
    if [ -f "/root/vless/.${SVC}.pid" ] && kill -0 "$(cat "/root/vless/.${SVC}.pid" 2>/dev/null)" 2>/dev/null; then
        return 0
    fi
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null
}

stop_svc() {
    [ -f "$PID_FILE" ] && kill -TERM "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null || true
    [ -f "/root/vless/.${SVC}.pid" ] && kill -TERM "$(cat "/root/vless/.${SVC}.pid" 2>/dev/null)" 2>/dev/null || true
    for cfile in "$CHILD_PID_FILE" "/root/vless/.${SVC}.child.pid"; do
        if [ -f "$cfile" ]; then
            cpid="$(cat "$cfile" 2>/dev/null)"
            if [ -n "$cpid" ]; then
                kill -INT "$cpid" 2>/dev/null || true
                pkill -TERM -P "$cpid" 2>/dev/null || true
                sleep 1
                kill -TERM "$cpid" 2>/dev/null || true
            fi
        fi
    done
    pkill -f "/root/vless/main.py" 2>/dev/null || true
    pkill -f "/root/vless/xray" 2>/dev/null || true
    pkill -f "/root/vless/cloudflared" 2>/dev/null || true
    rm -f "$PID_FILE" "$CHILD_PID_FILE" "/root/vless/.${SVC}.pid" "/root/vless/.${SVC}.child.pid"
}

start_svc() {
    parse_unit || return 1
    stop_svc
    cat <<RUNNER > "$RUNNER_FILE"
#!/usr/bin/env bash
cd "$WORKDIR" || exit 1
export PYTHONUNBUFFERED=1
trap 'if [ -n "\${CHILD_PID:-}" ]; then kill -INT "\$CHILD_PID" 2>/dev/null; pkill -TERM -P "\$CHILD_PID" 2>/dev/null; fi; exit 0' TERM INT EXIT
while true; do
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] [SUPERVISOR] Starting: $EXECSTART" >> "$LOG_FILE"
    $EXECSTART >> "$LOG_FILE" 2>&1 &
    CHILD_PID=\$!
    echo "\$CHILD_PID" > "$CHILD_PID_FILE"
    wait "\$CHILD_PID"
    sleep "$RESTARTSEC"
done
RUNNER
    chmod +x "$RUNNER_FILE"
    : > "$LOG_FILE"
    ln -sf "$LOG_FILE" "${WORKDIR}/${SVC}.log" 2>/dev/null || true
    nohup "$RUNNER_FILE" >/dev/null 2>&1 &
    echo $! > "$PID_FILE"
    sleep 1
    is_running
}

case "$ACTION" in
    start) start_svc ;;
    stop) stop_svc ;;
    restart) stop_svc; sleep 1; start_svc ;;
    is-active) is_running && { $QUIET || echo "active"; exit 0; } || { $QUIET || echo "inactive"; exit 3; } ;;
    status)
        if is_running; then
            echo "● ${SVC}.service - Active (Running in Railway Container)"
            ps -ef | grep -E "vless/(main\.py|xray|cloudflared)" | grep -v grep || true
            echo "--- Recent Logs ---"
            if [ -s "/root/vless/${SVC}.log" ]; then
                tail -n 20 "/root/vless/${SVC}.log" 2>/dev/null || true
            else
                tail -n 20 "$LOG_FILE" 2>/dev/null || true
            fi
        else
            echo "○ ${SVC}.service - Inactive (Dead)"; exit 3
        fi ;;
    *) exit 0 ;;
esac
EOF

    cat << 'EOF' > /usr/local/bin/journalctl
#!/usr/bin/env bash
if [ -d /run/systemd/system ] && [ -x /bin/journalctl ]; then exec /bin/journalctl "$@"; fi
FOLLOW=false; LINES=50; SVC="xray-vless"
while [ $# -gt 0 ]; do
    case "$1" in
        -u|--unit) SVC="${2%.service}"; shift 2 ;;
        -f|--follow) FOLLOW=true; shift ;;
        -n|--lines) LINES="$2"; shift 2 ;;
        *) shift ;;
    esac
done
if [ -f "/root/vless/${SVC}.log" ]; then
    LOG_FILE="/root/vless/${SVC}.log"
else
    LOG_FILE="/var/log/container-services/${SVC}.log"
fi
touch "$LOG_FILE"
$FOLLOW && exec tail -n "$LINES" -f "$LOG_FILE" || exec tail -n "$LINES" "$LOG_FILE"
EOF

    chmod +x /usr/local/bin/systemctl /usr/local/bin/journalctl
fi

# 3. Clone hoac cap nhat source vao ~/vless
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
if [ -f "$SRC_DIR/main.py" ] && [ -f "$SRC_DIR/run.sh" ] && [ "$SRC_DIR" != "$INSTALL_DIR" ]; then
    echo -e " ${GREEN}[*]${NC} Copying local optimized project to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    cp -rf "$SRC_DIR"/. "$INSTALL_DIR"/
    cd "$INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
    echo -e " ${GREEN}[OK]${NC} Found existing install at $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git fetch --all -q 2>/dev/null || true
    git reset --hard origin/main -q 2>/dev/null || git pull --ff-only 2>/dev/null || true
elif [ -f "$INSTALL_DIR/main.py" ] && [ -f "$INSTALL_DIR/run.sh" ]; then
    echo -e " ${GREEN}[OK]${NC} Found existing install at $INSTALL_DIR"
    cd "$INSTALL_DIR"
else
    echo -e " ${GREEN}[*]${NC} Cloning to $INSTALL_DIR..."
    git clone "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

chmod +x "$INSTALL_DIR/run.sh" 2>/dev/null || true
echo
exec bash "$INSTALL_DIR/run.sh" "$@"