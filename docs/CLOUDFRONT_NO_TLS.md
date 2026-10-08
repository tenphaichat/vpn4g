# CloudFront port 80 (no TLS): configuration, cost, and limits

[Xem bản tiếng Việt](CLOUDFRONT_NO_TLS_vi.md)

Operating notes for the **client → CloudFront (port 80, plain HTTP) → VPS VLESS-WebSocket (no TLS)** deployment.
Use it when you want carrier data perks based on the distribution's IP without needing a TLS certificate.

```text
[VLESS client] --HTTP:80--> [CloudFront edge] --plain HTTP--> [VPS: Xray VLESS-WS, no TLS]
   host=d111111abcdef8.cloudfront.net     Origin Protocol = HTTP Only
   path=/vlesscf                          Origin port = 80 or 8443
```

---

## 1. CloudFront checklist (all of these are mandatory)

| Setting | Required value | If wrong |
| --- | --- | --- |
| Behavior `/vlesscf` → **Viewer protocol policy** | `HTTP and HTTPS` | `HTTPS only` ⇒ port 80 returns `403`; `Redirect HTTP to HTTPS` ⇒ `301`, and the VLESS client does not follow redirects, so it dies silently |
| Origin → **Protocol** | `HTTP Only` | CF tries TLS to a non-TLS origin ⇒ `502` |
| Origin → **HTTP port** | the port Xray listens on (80 or 8443) | `504` |
| Origin → **Origin request policy** | `AllViewerExceptHostHeader` (do not forward `Host`) | origin sees an unknown Host ⇒ Xray does not match the inbound |
| Behavior → **Cache policy** | `CachingDisabled` | CF caches the WebSocket response ⇒ random handshake failures |
| Behavior → **Allowed HTTP methods** | at least `GET, HEAD, OPTIONS`, plus `POST` for xhttp | `400/403` on upgrade |
| Origin → **Response timeout** | ≥ 30s (long-lived WebSocket; low defaults cut sessions) | connection dropped mid-session |
| DNS | A record (`origin.example.com → VPS IP`), **grey cloud** (not Cloudflare-proxied) | proxy-on-proxy; CF resolves a Cloudflare IP as origin |

CloudFront needs **no** WebSocket toggle: support is always on, and the connection is upgraded when the client sends
`Upgrade: websocket` and the origin replies `101`. WSS is supported too, but this model does not use it.

## 2. Client link (correct example)

```text
vless://00000000-0000-0000-0000-000000000000@entry.example.com:80?encryption=none&host=d111111abcdef8.cloudfront.net&path=%2Fvlesscf&security=none&type=ws#Example
```

- `entry.example.com` is only used for the **DNS lookup** to obtain an edge IP; `host=` is what routes the request to your distribution.
- Drop `fp=`, `sni=`, `alpn=`: they are meaningless without TLS.
- `security=none` + `:80` + `type=ws` is all you need.

## 3. Quick curl verification

```powershell
# 1. Port 80 must no longer 403 instantly (it should reach the origin: 400/404/504 depending on Xray state)
curl.exe -s -o NUL -D - -H "Host: d111111abcdef8.cloudfront.net" http://203.0.113.10/vlesscf

# 2. Compare with HTTPS: both should return the same status family, no more 403 vs 504 gap
curl.exe -sk -o NUL -w "%{http_code}`n" -H "Host: d111111abcdef8.cloudfront.net" https://203.0.113.10/vlesscf

# 3. Is the plain-HTTP origin alive (non-TLS Xray WS: a plain GET usually returns 404/426, not a timeout)
curl.exe -s -o NUL -w "%{http_code}`n" --max-time 8 http://origin.example.com:8443/vlesscf
```

| Status | Meaning |
| --- | --- |
| `403` | Viewer protocol policy is still `HTTPS only` |
| `301` | Still `Redirect HTTP to HTTPS` |
| `502` | Origin Protocol is not `HTTP Only`, or the origin port is wrong |
| `504` | Xray is not listening / firewall blocks the origin port |
| `400` / `404` / `426` | Normal (request reached the origin) |

---

## 4. Does CloudFront cost money?

CloudFront has **no permanent free allowance for traffic** in pay-as-you-go mode.
There is only the **AWS Free Tier for the first 12 months** (from the day the AWS account was created); after that you pay list price.

### 4.1 Free Tier (first 12 months)

| Item | Free per month |
| --- | --- |
| Data transfer out | 1 TB (1,000 GB) |
| HTTP/HTTPS requests | 10,000,000 requests |
| CloudFront Functions | 2,000,000 invocations |

Conditions: new accounts only, first 12 months, and charges apply to the portion above the allowance.
After 12 months, every byte and request is billed from the first unit.

### 4.2 Pay-as-you-go reference rates (after Free Tier)

| Item | Price | Note |
| --- | --- | --- |
| Data transfer out (US/Canada/Europe) | ~$0.085/GB | cheapest tier |
| Data transfer out (Asia, incl. VN/HK/SG/JP) | ~$0.109–0.120/GB | **this is your tier** |
| HTTPS requests | ~$0.01 per 10,000 (after 20M) | ~$1 per 1M requests |
| HTTP requests | basically the same as HTTPS | port 80 does not lower the bill |

> [!IMPORTANT]
> Why **port 80 does not reduce CloudFront cost**: CloudFront bills *data transfer out* and *number of requests*,
> not whether the viewer used HTTP or HTTPS. Dropping TLS only removes certificate purchase/renewal and cert-chain
> failures; the bill is unchanged. The real economic value of this model is on the **carrier** side (zero-rating), not AWS.

### 4.3 Realistic monthly cost estimates

Assuming ~$0.11/GB for Asia and ignoring request charges (negligible):

| Volume per month | Cost after Free Tier | After Free Tier + first 500 GB offset by billing credits |
| --- | --- | --- |
| 200 GB | ~$22 | $0 |
| 500 GB | ~$55 | $0 |
| 1 TB | ~$110 | ~$55 |
| 3 TB | ~$330 | ~$275 |
| 10 TB | ~$1,100 | ~$1,045 |

Ways to cut cost: use **AWS Billing → Credits** (promotional/welcome credits often offset the first 500 GB of data
transfer out), or attach **AWS Budgets** to automatically disable the distribution past a threshold.

### 4.4 Putting a hard ceiling on spend

> [!WARNING]
> There is no hard "stop spending" switch in pay-as-you-go. Set up these three layers immediately:

1. **CloudFront flat-rate plans** (`Free` / `Pro` / `Business` / `Premium`): a fixed monthly price with **no overage
   charges**, but exceeding the allowance stops service instead of billing more — a real ceiling. The lowest tier can be `$0/month`.
   These plans **exempt** the `150 Gbps` and `250,000 requests/second` quotas on the subscribed distribution.
2. **AWS Budgets**: alerts and/or an auto-action (Lambda disabling the distribution) at a threshold.
3. **CloudWatch billing alarm**: warn at $5 / $20 / $50.


## 5. Technical limits worth knowing (CloudFront quotas)

| Quota | Default | Impact on your VPN |
| --- | --- | --- |
| Data transfer rate per distribution | 150 Gbps | Per-distribution bandwidth cap; exceeding it throttles. Increase is requestable. |
| Requests per second per distribution | 250,000 | Request-rate cap; a WS connection counts as ~1 request at handshake |
| Connection attempts per origin | 3 | CF retries 3 times, then gives up |
| Connection timeout to origin | 10 seconds | Origin silent > 10s ⇒ `504` |
| Response timeout to origin | 120 seconds (default 30s) | **Set ≥ 30s** for WebSocket; request an increase under heavy load |
| Keep-alive timeout to origin | 300 seconds | Custom/VPC origins only |
| Maximum URL length | 8,192 characters | Not a concern |
| Maximum request/origin response length (headers + query, body excluded) | 32,768 bytes | VLESS headers are tiny |
| Distributions per account | 500 | Not a concern |
| Alternate domain names per distribution | 100 | Not a concern |
| Chain of distributions | **2** (not recommended) | Distribution-behind-distribution returns `403`. Do **not** put a Cloudflare proxy in front of CF. |
| Invalidation | 1,000 paths/month free, then ~$0.005/path | Irrelevant to WebSocket |

Notes specific to no-TLS:

- There is **no hard maximum WebSocket connection lifetime**; a connection lives until either side closes. In practice it
  is bounded by `Response timeout` and by carrier NAT/idle timeouts. Enable `mux` / keep-alive (ping) in the Xray client
  to hold the tunnel open.
- There is **no separate concurrent-WebSocket-connection quota**; the real limits are `Requests per second` and
  `Data transfer rate`.

## 6. What you actually give up without TLS

1. **Encryption lost on both hops**: client→CF (port 80) and CF→VPS are both plain HTTP. UUID, Host, and metadata are
   exposed to the ISP / Wi-Fi operator / VPS provider. An MITM that reads the UUID can **reuse your VPN**. VLESS itself
   does not encrypt payloads; it borrows TLS for cover.
2. **Zero-rating may break**: carrier whitelists are often SNI-based, and port 80 has **no SNI**. If their whitelist is
   IP/ASN-based (the entry hostname resolves to a CloudFront IP) you are still fine; if it is SNI-based, traffic gets
   billed normally. **Test it yourself by draining data and watching whether the app stays "free".**
3. **Easier to discover**: a CloudFront hostname accepting WebSocket upgrades from random IPs is a fairly obvious
   traffic pattern. Rotate the path periodically and do not share the link publicly.
4. **Upside**: no more `502` from a missing intermediate cert, and ALPN no longer matters (`ALPN http/1.1` is only
   needed with TLS).


## 7. Checking your real usage and bill

There is no AWS CLI installed in this workspace, so run these in **AWS CloudShell** (browser terminal) or after
installing the AWS CLI:

```bash
# Data transfer out in GB over the last 30 days, per distribution
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront --metric-name BytesDownloaded \
  --dimensions Name=DistributionId,Value=YOUR_DIST_ID \
  --start-time "$(date -u -d '-30 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 2592000 --statistics Sum --region us-east-1

# Requests over the same window
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront --metric-name Requests \
  --dimensions Name=DistributionId,Value=YOUR_DIST_ID \
  --start-time "$(date -u -d '-30 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 2592000 --statistics Sum --region us-east-1

# Month-to-date cost by service (find the CloudFront line)
aws ce get-cost-and-usage --time-period Start="$(date -u +%Y-%m-01)",End="$(date -u +%Y-%m-%d)" \
  --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE
```

Convert with: `GB × ~$0.11` (Asia) and `requests ÷ 10000 × ~$0.01`.

Turn these on right away (Console → CloudFront → Monitoring, and Console → Billing):

- **CloudFront console reports**: Monitoring → *Data transfer* and *Requests* charts, plus *Popular objects* to see how
  much traffic the VLESS path actually carries.
- **Billing → Budgets** with an alert at your comfort threshold.
- **Billing → Cost Explorer** grouped by *Usage type* to isolate `DataTransfer-Out-Bytes` for CloudFront Asia.

---

## 8. New server, but the HTTP ping fails? Run the tool before changing anything

Do not guess. Run:

```powershell
python check_cloudfront_link.py "vless://...&host=<dist>.cloudfront.net&path=/vpn&security=none&type=ws#test"
python check_cloudfront_link.py "vless://..." --vless     # also probes the UUID end to end
```

The tool runs 6 steps: distribution DNS, entry-host DNS, GET on the real path, GET on a random path,
WebSocket upgrade, and (optional) a real VLESS end-to-end probe. It prints a `verdict` plus a concrete
`next step`. Real cases seen on this project:

| Case | Tool output | Root cause |
| --- | --- | --- |
| `host=` is a domain that does not exist | `FAIL / CF_DOMAIN_NOT_FOUND` | Wrong/nonexistent domain, distribution **not deployed yet**, or **Disabled** (CloudFront stops publishing DNS) |
| Viewer protocol policy = `HTTPS only` | `FAIL / VIEWER_HTTPS_ONLY_OR_BLOCKED` | every path returns `403`, including the random one |
| Viewer protocol policy = `Redirect HTTP to HTTPS` | `FAIL / REDIRECT_HTTP_TO_HTTPS` | CloudFront returns `301` |
| Origin Protocol is still HTTPS | `FAIL / ORIGIN_TLS_MISMATCH` | `502` |
| Xray not listening / wrong origin port | `FAIL / ORIGIN_UNREACHABLE` | `504` |
| Correct configuration | `PASS / WS_ROUTED_TO_ORIGIN` | `101 Switching Protocols`, VLESS probe returns real bytes |

### Telling 403 "does not exist" apart from 403 "HTTPS only policy"

Both return a byte-identical body (`403 ERROR` … `Bad request.` … `X-Cache: Error from cloudfront`),
so **only DNS separates them**:

```powershell
# Real domain -> has an A record ; wrong domain or Disabled distribution -> NO A record
Resolve-DnsName d111111abcdef8.cloudfront.net -Type A
Resolve-DnsName d2fhr3e9msynb2.cloudfront.net -Type A
```

Cross-check with another resolver to rule out DNS caching:

```powershell
nslookup d2fhr3e9msynb2.cloudfront.net 8.8.8.8
Invoke-RestMethod 'https://cloudflare-dns.com/dns-query?name=d2fhr3e9msynb2.cloudfront.net&type=A' -Headers @{accept='application/dns-json'}
```

If there is **no A record**: open the CloudFront console, **copy** the *Distribution domain name*
(never retype it), confirm *Status = Deployed*, and if it is `Disabled`, **Enable** it and wait for the
deploy to finish. Then paste the exact domain into `host=` of the link.

A freshly created distribution can return `403` on every path for the first few minutes, so re-check DNS
a few times (for example every 20 s for ~2 minutes). If there is still no A record after ~15 minutes, the
domain string is wrong or the distribution is `Disabled`/deleted — waiting longer will not help.

> [!NOTE]
> The console can show `Deployed` while the distribution is still `Disabled`; those are two different
> columns. Look at **Status/State** (Enabled/Disabled), not *Last modified*.
