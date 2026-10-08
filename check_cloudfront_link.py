"""Diagnose a VLESS-over-WebSocket link that points at a CloudFront distribution.

The script answers one question fast: is this link broken because of DNS, the
CloudFront configuration, the origin, or the VLESS credential?

Usage
-----
    python check_cloudfront_link.py "vless://uuid@entry:80?host=...&path=/vpn&security=none&type=ws#name"
    python check_cloudfront_link.py --cf-host d2fhr3e9msynb2.cloudfront.net --path /vpn
    python check_cloudfront_link.py "vless://..." --vless        # also run a full VLESS probe

Only the Python standard library is used, so it also runs on a bare VPS/Termux.
Exit code 0 means "link reached the origin", 1 means "something upstream failed".
"""

import argparse
import base64
import json
import os
import socket
import ssl
import struct
import sys
import urllib.parse
import urllib.request
import uuid

DEFAULT_TIMEOUT = 10.0
RANDOM_PATH = "/khong-ton-tai-" + os.urandom(4).hex()
DOH_URL = "https://cloudflare-dns.com/dns-query?name={}&type=A"


# --- link parsing -----------------------------------------------------------

def parse_vless(link):
    """Return dict(uuid, entry, port, host, path, security)."""
    body = link.split("://", 1)[1]
    body = body.split("#", 1)[0]
    if "?" in body:
        body, query = body.split("?", 1)
        params = urllib.parse.parse_qs(query)
    else:
        params = {}
    userinfo, _, endpoint = body.rpartition("@")
    host, _, port = endpoint.rpartition(":")
    return {
        "uuid": userinfo,
        "entry": host,
        "port": int(port or 443),
        "host": (params.get("host") or [""])[0],
        "path": urllib.parse.unquote((params.get("path") or ["/"])[0]),
        "security": (params.get("security") or ["none"])[0],
    }


# --- DNS --------------------------------------------------------------------

def system_resolve(name, timeout=DEFAULT_TIMEOUT):
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    finally:
        socket.setdefaulttimeout(old)
    return sorted({info[4][0] for info in infos})


def doh_resolve(name, timeout=DEFAULT_TIMEOUT):
    """Independent check via DNS-over-HTTPS. Returns [] , or None if DoH failed."""
    try:
        req = urllib.request.Request(DOH_URL.format(name), headers={"accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]


# --- raw HTTP / WebSocket probes --------------------------------------------

def read_http_head(sock):
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    return head.decode("iso-8859-1"), rest


def open_socket(ip, port, tls, sni, timeout):
    """TCP connect, optionally wrapped in TLS with the distribution domain as SNI."""
    raw = socket.create_connection((ip, port), timeout=timeout)
    if not tls:
        return raw
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_alpn_protocols(["http/1.1"])
    return ctx.wrap_socket(raw, server_hostname=sni)


def http_probe(ip, port, cf_host, path, use_tls, timeout=DEFAULT_TIMEOUT):
    """Plain GET, no upgrade. The CloudFront status code is what we care about."""
    scheme = "https" if use_tls else "http"
    try:
        sock = open_socket(ip, port, use_tls, cf_host, timeout)
    except Exception as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {exc}", "headers": {}}
    try:
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {cf_host}\r\n"
            "User-Agent: Mozilla/5.0\r\nAccept: */*\r\nConnection: close\r\n\r\n"
        )
        sock.sendall(request.encode())
        head, body = read_http_head(sock)
    except Exception as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {exc}", "headers": {}}
    finally:
        sock.close()
    lines = head.split("\r\n")
    status = lines[0].strip()
    headers = {}
    for line in lines[1:]:
        key, _, value = line.partition(":")
        if key:
            headers[key.strip().lower()] = value.strip()
    return {
        "status": status,
        "code": status.split()[1] if len(status.split()) > 1 else "000",
        "headers": headers,
        "scheme": scheme,
        "error": None,
    }


def ws_upgrade_probe(ip, port, cf_host, path, use_tls, timeout=DEFAULT_TIMEOUT):
    """Real WebSocket handshake. 101 means CloudFront routed us to the origin."""
    try:
        sock = open_socket(ip, port, use_tls, cf_host, timeout)
    except Exception as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {exc}"}
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {cf_host}\r\n"
            "User-Agent: Mozilla/5.0\r\nOrigin: https://www.tiktok.com\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode())
        head, _ = read_http_head(sock)
    except Exception as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        sock.close()
    status = head.split("\r\n")[0].strip()
    return {"status": status, "upgraded": "101" in status, "error": None}


# --- optional VLESS end-to-end probe ----------------------------------------

def _recv_exact(sock, size):
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def _ws_send_binary(sock, payload):
    key = os.urandom(4)
    masked = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    size = len(payload)
    if size < 126:
        header = struct.pack("!BB", 0x82, 0x80 | size)
    elif size < 65536:
        header = struct.pack("!BBH", 0x82, 0x80 | 126, size)
    else:
        header = struct.pack("!BBQ", 0x82, 0x80 | 127, size)
    sock.sendall(header + key + masked)


def _ws_recv_frame(sock):
    b1, b2 = _recv_exact(sock, 2)
    size = b2 & 0x7F
    if size == 126:
        size = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif size == 127:
        size = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if b2 & 0x80 else None
    data = _recv_exact(sock, size) if size else b""
    if mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return b1 & 0x0F, data


def vless_probe(ip, port, cf_host, path, uid, use_tls, timeout=DEFAULT_TIMEOUT,
                dest_ip="1.1.1.1", dest_port=80, dest_host="one.one.one.one"):
    """Send a real VLESS TCP request over the WebSocket and count the bytes back."""
    sock = None
    try:
        sock = open_socket(ip, port, use_tls, cf_host, timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {cf_host}\r\n"
            "User-Agent: Mozilla/5.0\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode())
        head, _ = read_http_head(sock)
        if "101" not in head.split("\r\n")[0]:
            return {"ok": False, "bytes": 0, "note": head.split("\r\n")[0].strip()}

        payload = (
            f"GET / HTTP/1.1\r\nHost: {dest_host}\r\n"
            "User-Agent: cf-link-check\r\nAccept: */*\r\nConnection: close\r\n\r\n"
        ).encode()
        frame = (
            b"\x00" + uuid.UUID(uid).bytes + b"\x00" + b"\x01"
            + struct.pack("!H", dest_port) + b"\x01"
            + socket.inet_aton(dest_ip) + payload
        )
        _ws_send_binary(sock, frame)
        total = 0
        while total < 4096:
            try:
                opcode, data = _ws_recv_frame(sock)
            except (socket.timeout, ConnectionError):
                break
            if opcode == 0x8:
                break
            if opcode in (0x9, 0xA):
                continue
            total += len(data)
            if total:
                break
        return {"ok": total > 0, "bytes": total,
                "note": "data received" if total else "no data returned (UUID rejected or no egress)"}
    except Exception as exc:
        return {"ok": False, "bytes": 0, "note": f"{type(exc).__name__}: {exc}"}
    finally:
        if sock is not None:
            sock.close()


# --- verdict ----------------------------------------------------------------

def verdict(cf_host, dist_sys, dist_doh, path_probe, random_probe, ws_probe):
    """Map the collected evidence to a single root cause."""
    domain_missing = not dist_sys or (dist_doh is not None and not dist_doh)
    if domain_missing:
        return (False, "CF_DOMAIN_NOT_FOUND",
                f"{cf_host} has no A record in public DNS, so no CloudFront edge can map the "
                "Host header. The request is rejected with 403 'Bad request / Error from cloudfront'.",
                "Open the CloudFront console and copy the 'Distribution domain name' of the "
                "distribution; check its Status is 'Deployed'. Fix host= in the link, or enable "
                "the distribution if it is Disabled. Disabled distributions stop resolving in DNS.")

    code = path_probe.get("code")
    if code == "301":
        return (False, "REDIRECT_HTTP_TO_HTTPS",
                "CloudFront answers 301 because that cache behavior uses 'Redirect HTTP to HTTPS'. "
                "A VLESS client does not follow redirects, so the tunnel dies silently.",
                "Set Viewer protocol policy = 'HTTP and HTTPS' on every behavior that matches the path.")
    if code == "403":
        same_random = random_probe.get("code") == "403"
        detail = ("every path is rejected identically (random path also 403), which means the block "
                  "happens before routing" if same_random else "the path is rejected")
        return (False, "VIEWER_HTTPS_ONLY_OR_BLOCKED",
                f"CloudFront returns 403 and {detail}.",
                "Set Viewer protocol policy = 'HTTP and HTTPS' on the behavior matching the WS path, "
                "and make sure a cache behavior actually matches that path instead of the default '*'.")
    if code == "502":
        return (False, "ORIGIN_TLS_MISMATCH",
                "CloudFront got no valid response from the origin (502). It is still speaking TLS to "
                "an origin that no longer terminates TLS.",
                "Set the origin Protocol to 'HTTP Only' and point the origin HTTP port at the port "
                "Xray listens on.")
    if code in ("504", "000", None):
        return (False, "ORIGIN_UNREACHABLE",
                f"CloudFront could not reach the origin within the timeout (code={code}).",
                "Check that Xray is running and listening, that the origin port matches, and that "
                "the VPS firewall allows the CloudFront IP ranges.")
    if ws_probe.get("upgraded"):
        return (True, "WS_ROUTED_TO_ORIGIN",
                f"HTTP {code} plus a successful WebSocket upgrade (101) means CloudFront routed the "
                "request to Xray and the path matched.",
                "The tunnel path is fine. If the client still fails, the problem is the client's "
                "UUID/transport settings, not CloudFront.")
    return (True, "REACHED_ORIGIN",
            f"HTTP {code} came from the origin/Xray itself, so DNS, CloudFront and the origin hop all work.",
            "Compare the client's path/transport with the server config; run with --vless to test the UUID.")


def main():
    parser = argparse.ArgumentParser(description="Diagnose a VLESS-over-WS link that goes through CloudFront.")
    parser.add_argument("link", nargs="?", help="vless:// link to inspect")
    parser.add_argument("--cf-host", help="CloudFront distribution domain (host= in the link)")
    parser.add_argument("--entry", help="entry hostname used for DNS lookup (link.e.tiktok.com)")
    parser.add_argument("--path", help="WebSocket path")
    parser.add_argument("--port", type=int, help="viewer port (80 or 443)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--vless", action="store_true", help="also run a real VLESS end-to-end probe")
    args = parser.parse_args()

    parsed = parse_vless(args.link) if args.link else {}
    cf_host = args.cf_host or parsed.get("host")
    entry = args.entry or parsed.get("entry")
    path = args.path or parsed.get("path") or "/"
    port = args.port or parsed.get("port") or 80
    uid = parsed.get("uuid")
    use_tls = port == 443

    if not cf_host:
        parser.error("need a distribution domain: pass a vless:// link or --cf-host")

    print("=== VLESS / CloudFront link check ===")
    print(f"distribution domain : {cf_host}")
    print(f"entry host          : {entry or '(none)'}")
    print(f"path                : {path}")
    print(f"viewer port         : {port} ({'https' if use_tls else 'http'})")
    print()

    print("[1/6] DNS for the distribution domain (system resolver)")
    dist_sys = system_resolve(cf_host, args.timeout)
    print(f"      system : {', '.join(dist_sys) if dist_sys else 'NO A RECORD'}")
    dist_doh = doh_resolve(cf_host, args.timeout)
    if dist_doh is None:
        print("      DoH    : (cloudflare-dns.com unreachable, skipped)")
    else:
        print(f"      DoH    : {', '.join(dist_doh) if dist_doh else 'NO A RECORD'}")

    print("[2/6] DNS for the entry host (the address the client dials)")
    entry_ips = system_resolve(entry, args.timeout) if entry else []
    if entry:
        print(f"      system : {', '.join(entry_ips) if entry_ips else 'NO A RECORD'}")
    else:
        print("      skipped (no entry host)")
    target_ip = entry_ips[0] if entry_ips else (dist_sys[0] if dist_sys else None)
    if not target_ip:
        print("\n[RESULT] nothing to connect to: neither the entry host nor the distribution resolves.")
        return 1
    print(f"      using  : {target_ip}:{port}")
    print()

    print(f"[3/6] HTTP GET {path}")
    path_probe = http_probe(target_ip, port, cf_host, path, use_tls, args.timeout)
    print(f"      status : {path_probe['status'] or path_probe['error']}")
    if path_probe.get("headers", {}).get("x-cache"):
        print(f"      x-cache: {path_probe['headers']['x-cache']}")

    print(f"[4/6] HTTP GET {RANDOM_PATH} (random path, to tell policy-level from path-level blocks)")
    random_probe = http_probe(target_ip, port, cf_host, RANDOM_PATH, use_tls, args.timeout)
    print(f"      status : {random_probe['status'] or random_probe['error']}")
    print()

    print(f"[5/6] WebSocket upgrade on {path}")
    ws_probe = ws_upgrade_probe(target_ip, port, cf_host, path, use_tls, args.timeout)
    print(f"      status : {ws_probe['status'] or ws_probe['error']}")
    print()

    vless_result = None
    if args.vless:
        print("[6/6] VLESS end-to-end probe (uuid from the link)")
        if not uid:
            print("      skipped: no uuid in the link")
        else:
            vless_result = vless_probe(target_ip, port, cf_host, path, uid, use_tls, args.timeout)
            print(f"      result : {vless_result['note']} (bytes={vless_result['bytes']})")
        print()

    ok, label, finding, step = verdict(cf_host, dist_sys, dist_doh, path_probe, random_probe, ws_probe)
    print("=== RESULT ===")
    print(f"verdict  : {'PASS' if ok else 'FAIL'} / {label}")
    print(f"finding  : {finding}")
    print(f"next step: {step}")
    if vless_result and not vless_result["ok"] and ok:
        print(f"vless    : UUID rejected or no egress - verify XRAY_UUID and the outbound of the VPS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
