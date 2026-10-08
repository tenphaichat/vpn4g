# CloudFront cổng 80 (không TLS): cấu hình, chi phí và giới hạn

[English version](CLOUDFRONT_NO_TLS.md)

Ghi chú vận hành cho kiểu triển khai **client → CloudFront (cổng 80, HTTP thuần) → VPS VLESS-WebSocket (không TLS)**.
Dùng khi bạn muốn ăn ưu đãi data của nhà mạng bằng IP của distribution mà không cần chứng chỉ TLS.

```text
[Client VLESS] --HTTP:80--> [CloudFront edge] --HTTP thuần--> [VPS: Xray VLESS-WS không TLS]
   host=d111111abcdef8.cloudfront.net     Origin Protocol = HTTP Only
   path=/vlesscf                          Origin port = 80 hoặc 8443
```

---

## 1. Checklist CloudFront (bắt buộc đúng các mục này)

| Mục | Giá trị phải đặt | Nếu sai thì |
| --- | --- | --- |
| Behavior `/vlesscf` → **Viewer protocol policy** | `HTTP and HTTPS` | `HTTPS only` ⇒ cổng 80 trả `403`; `Redirect HTTP to HTTPS` ⇒ trả `301`, client VLESS không follow redirect nên chết lặng |
| Origin → **Protocol** | `HTTP Only` | CF cố TLS tới origin không TLS ⇒ `502` |
| Origin → **HTTP port** | cổng Xray đang listen (80 hoặc 8443) | `504` |
| Origin → **Origin request policy** | `AllViewerExceptHostHeader` (không forward `Host`) | origin thấy Host lạ ⇒ Xray không match inbound |
| Behavior → **Cache policy** | `CachingDisabled` | CF cache phản hồi WebSocket ⇒ lỗi handshake ngẫu nhiên |
| Behavior → **Allowed HTTP methods** | tối thiểu `GET, HEAD, OPTIONS` + `POST` nếu dùng xhttp | `400/403` khi upgrade |
| Origin → **Response timeout** | ≥ 30s (WebSocket sống lâu, mặc định thấp dễ bị ngắt) | kết nối bị cắt giữa phiên |
| DNS | bản ghi A (`origin.example.com → IP VPS`), **grey cloud** (không proxy Cloudflare) | proxy chồng proxy, CF lấy IP Cloudflare làm origin |

CloudFront **không** cần bật gì cho WebSocket: nó bật sẵn, kết nối được thiết lập khi client gửi `Upgrade: websocket`
và origin trả `101`. WSS cũng được hỗ trợ, nhưng ở mô hình này ta không dùng.

## 2. Link client (mẫu đúng)

```text
vless://00000000-0000-0000-0000-000000000000@entry.example.com:80?encryption=none&host=d111111abcdef8.cloudfront.net&path=%2Fvlesscf&security=none&type=ws#Example
```

- `entry.example.com` chỉ dùng để **DNS lookup** ra IP edge; `host=` quyết định CF route về distribution của bạn.
- Bỏ `fp=`, `sni=`, `alpn=`, `fp=chrome`: không có TLS thì các tham số đó vô nghĩa.
- `security=none` + `:80` + `type=ws` là đủ.

## 3. Kiểm tra nhanh bằng curl

```powershell
# 1. Cổng 80 phải KHÔNG còn 403 tức thời (phải đi tới origin: 400/404/504 tuỳ trạng thái Xray)
curl.exe -s -o NUL -D - -H "Host: d111111abcdef8.cloudfront.net" http://203.0.113.10/vlesscf

# 2. So với HTTPS: hai bên phải cùng "họ" status code, không còn chênh 403 vs 504
curl.exe -sk -o NUL -w "%{http_code}`n" -H "Host: d111111abcdef8.cloudfront.net" https://203.0.113.10/vlesscf

# 3. Origin HTTP thuần còn sống (Xray WS không TLS: GET thường trả 404/426, không phải timeout)
curl.exe -s -o NUL -w "%{http_code}`n" --max-time 8 http://origin.example.com:8443/vlesscf
```

| Status | Nghĩa |
| --- | --- |
| `403` | Viewer protocol policy vẫn là `HTTPS only` |
| `301` | Vẫn `Redirect HTTP to HTTPS` |
| `502` | Origin Protocol không phải `HTTP Only`, hoặc sai cổng origin |
| `504` | Xray không listen / firewall chặn cổng origin |
| `400` / `404` / `426` | Bình thường (đã tới origin) |

---

## 4. CloudFront có mất phí không?

CloudFront **không có gói miễn phí vĩnh viễn cho lưu lượng** kiểu "free mãi mãi" trong chế độ pay-as-you-go.
Chỉ có **AWS Free Tier 12 tháng đầu** (tính từ ngày tạo tài khoản AWS), sau đó tính theo bảng giá.

### 4.1 Free Tier (12 tháng đầu)

| Hạng mục | Miễn phí mỗi tháng |
| --- | --- |
| Data transfer out | 1 TB (1.000 GB) |
| HTTP/HTTPS requests | 10.000.000 request |
| CloudFront Functions | 2.000.000 invocation |

Điều kiện: chỉ áp dụng cho tài khoản mới trong 12 tháng, và tổng hoá đơn phải vượt ngưỡng tối thiểu của AWS mới bị tính phần vượt.
Hết 12 tháng, toàn bộ lưu lượng bị tính phí từ byte/request đầu tiên.

### 4.2 Giá pay-as-you-go (sau Free Tier) — đơn giá tham chiếu

| Hạng mục | Đơn giá | Ghi chú |
| --- | --- | --- |
| Data transfer out (US/Canada/Europe) | ~$0,085/GB | mức thấp nhất |
| Data transfer out (Asia, gồm VN/HK/SG/JP) | ~$0,109–0,120/GB | **đây là mức bạn sẽ bị tính** |
| HTTPS requests | ~$0,01 / 10.000 request (sau 20 triệu) | ~$1 / 1 triệu request |
| HTTP requests | tương tự HTTPS (chênh rất ít) | dùng cổng 80 không làm bill rẻ hơn |

> [!IMPORTANT]
> Vì sao **cổng 80 không giúp giảm tiền CloudFront**: CloudFront tính phí trên *lưu lượng đi ra* (data transfer out) và *số request*,
> không tính theo việc bạn dùng HTTP hay HTTPS. Bỏ TLS chỉ giúp **không phải mua/quản lý chứng chỉ** và tránh lỗi cert chain;
> hoá đơn tính đúng như cũ. Giá trị kinh tế thật của mô hình này nằm ở phía **nhà mạng** (zero-rating), không phải phía AWS.

### 4.3 Ước tính chi phí thực tế theo dung lượng dùng

Giả định đơn giá Asia ~$0,11/GB và bỏ qua số request (không đáng kể):

| Dung lượng / tháng | Chi phí sau Free Tier | Sau Free Tier + 500 GB đầu được bù bởi Billing credit |
| --- | --- | --- |
| 200 GB | ~$22 | $0 |
| 500 GB | ~$55 | $0 |
| 1 TB | ~$110 | ~$55 |
| 3 TB | ~$330 | ~$275 |
| 10 TB | ~$1.100 | ~$1.045 |

Cách giảm chi phí: dùng **AWS Billing → Credits** (credit khuyến mãi/act chào mừng, thường dùng để bù phần data transfer out
500 GB đầu), hoặc gắn **AWS Budget** để tự tắt distribution khi vượt ngưỡng.

### 4.4 Cách chặn trần chi phí (không để "cháy" tài khoản)

> [!WARNING]
> Không có công tắc "giới hạn cứng" cho pay-as-you-go. Ba lớp bảo vệ nên làm ngay:

1. **CloudFront flat-rate plans** (`Free` / `Pro` / `Business` / `Premium`): trả giá cố định theo tháng, **không phụ phí vượt**,
   nhưng vượt hạn mức thì bị ngắt/không phục vụ — đúng kiểu "có trần". Gói thấp nhất có thể là `$0/tháng`.
   Kế hoạch này **không áp dụng** quota `150 Gbps` và `250.000 request/giây` (2 quota đó bị miễn cho distribution theo plan).
2. **AWS Budgets**: cảnh báo và/hoặc auto-action (lambda tắt distribution) khi hết ngưỡng.
3. **CloudWatch → Billing alarm**: cảnh báo ở $5 / $20 / $50.

## 5. Giới hạn kỹ thuật cần biết (trích từ quota CloudFront)

| Quota | Giá trị mặc định | Ảnh hưởng tới VPN của bạn |
| --- | --- | --- |
| Data transfer rate per distribution | 150 Gbps | Trần băng thông một distribution; vượt ⇒ bị throttle. Xin tăng được. |
| Requests per second per distribution | 250.000 | Trần request/giây; mỗi kết nối WS chỉ tính ~1 request khi handshake |
| Số connection attempt mỗi origin | 3 | CF retry 3 lần rồi bỏ |
| Connection timeout tới origin | 10 giây | Origin "im" quá 10s ⇒ `504` |
| Response timeout tới origin | 120 giây (mặc định 30s) | **Set ≥ 30s** cho WebSocket; nên xin tăng nếu tải nặng |
| Keep-alive timeout tới origin | 300 giây | Chỉ áp dụng origin custom/VPC |
| Độ dài URL | 8.192 ký tự | Không lo |
| Độ dài request/origin response (header + query, không tính body) | 32.768 byte | Header VLESS rất nhỏ |
| Số distribution / tài khoản | 500 | Không lo |
| Alternate domain name / distribution | 100 | Không lo |
| Chain of distributions | **2** (không khuyến khích) | Đặt CF trước CF ⇒ `403`. **Đừng** cho Cloudflare proxy chồng lên CF. |
| Invalidation | 1.000 path/tháng (miễn phí), sau đó ~$0,005/path | Không liên quan WebSocket |

Lưu ý quan trọng với mô hình no-TLS:

- **Không có timeout "tuổi thọ kết nối" cứng** cho WebSocket; kết nối sống tới khi một trong hai bên đóng,
  nhưng thực tế bị ảnh hưởng bởi `Response timeout` và bởi NAT/idle timeout của nhà mạng. Nên bật `mux` /
  keep-alive (ping) trong client Xray để giữ tunnel.
- **Không có quota "số kết nối WebSocket đồng thời"** riêng cho CF; giới hạn thật là `Requests per second` và `Data transfer rate`.

## 6. Những mất mát thật khi bỏ TLS (đừng bỏ qua)

1. **Mất mã hoá cả 2 chặng**: client→CF (cổng 80) và CF→VPS đều là HTTP plaintext. UUID, Host, metadata lộ cho
   ISP / Wi-Fi / nhà cung cấp VPS. Kẻ MITM đọc được UUID ⇒ **dùng lại được VPN của bạn**. VLESS bản thân không mã hoá payload.
2. **Có thể mất zero-rating**: whitelist của nhà mạng thường dựa trên **SNI**, mà cổng 80 **không có SNI**.
   Nếu whitelist của họ dựa theo IP/ASN (hostname entry phân giải ra IP CloudFront) thì cổng 80 vẫn ăn;
   nếu dựa theo SNI thì sẽ bị tính data thường. **Phải tự test bằng cách rút data và xem app còn "free" hay không.**
3. **Dễ bị dò quét**: một hostname CloudFront nhận HTTP upgrade WebSocket từ IP ngẫu nhiên là mẫu lưu lượng khá lộ.
   Cân nhắc đổi path định kỳ và không chia sẻ link công khai.
4. **Điểm cộng**: hết lỗi `502` do thiếu intermediate cert, hết phải quan tâm ALPN (`ALPN http/1.1` chỉ cần khi TLS).

## 7. Cách kiểm tra mức dùng thật và hoá đơn

Máy này không có AWS CLI, nên hãy chạy các lệnh sau trong **AWS CloudShell** (terminal trên trình duyệt)
hoặc sau khi cài AWS CLI:

```bash
# Dung lượng đi ra (GB) trong 30 ngày gần nhất, theo từng distribution
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront --metric-name BytesDownloaded \
  --dimensions Name=DistributionId,Value=YOUR_DIST_ID \
  --start-time "$(date -u -d '-30 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 2592000 --statistics Sum --region us-east-1

# Số request trong cùng khoảng
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront --metric-name Requests \
  --dimensions Name=DistributionId,Value=YOUR_DIST_ID \
  --start-time "$(date -u -d '-30 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 2592000 --statistics Sum --region us-east-1

# Chi phí từ đầu tháng theo từng service (tìm dòng CloudFront)
aws ce get-cost-and-usage --time-period Start="$(date -u +%Y-%m-01)",End="$(date -u +%Y-%m-%d)" \
  --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE
```

Quy đổi: `GB × ~$0,11` (Asia) và `số request ÷ 10000 × ~$0,01`.

Bật ngay các mục sau (Console → CloudFront → Monitoring, và Console → Billing):

- **Báo cáo trong CloudFront console**: Monitoring → biểu đồ *Data transfer* và *Requests*, cùng *Popular objects*
  để biết đường dẫn VLESS thực sự chở bao nhiêu lưu lượng.
- **Billing → Budgets**: cảnh báo ở mức bạn thấy an toàn.
- **Billing → Cost Explorer**, nhóm theo *Usage type* để tách riêng `DataTransfer-Out-Bytes` của CloudFront khu vực Asia.

---

## 8. Tạo server mới nhưng không ping được? Chạy tool trước khi sửa gì

Đừng đoán. Chạy:

```powershell
python check_cloudfront_link.py "vless://...&host=<dist>.cloudfront.net&path=/vpn&security=none&type=ws#test"
python check_cloudfront_link.py "vless://..." --vless     # kiểm tra luôn cả UUID
```

Tool kiểm tra 6 bước: DNS distribution, DNS entry host, GET đúng path, GET path rác, WebSocket upgrade, và (tuỳ chọn) VLESS end-to-end.
Nó in ra `verdict` + `next step` cụ thể. Ví dụ thật:

| Trường hợp | Kết quả tool | Nguyên nhân |
| --- | --- | --- |
| `host=` là domain không tồn tại | `FAIL / CF_DOMAIN_NOT_FOUND` | Domain gõ sai / chưa có thật, distribution **chưa deploy xong**, hoặc đang **Disabled** (CloudFront ngừng publish DNS) |
| Viewer protocol policy = `HTTPS only` | `FAIL / VIEWER_HTTPS_ONLY_OR_BLOCKED` | Mọi path đều `403`, kể cả path rác |
| Viewer protocol policy = `Redirect HTTP to HTTPS` | `FAIL / REDIRECT_HTTP_TO_HTTPS` | CF trả `301` |
| Origin Protocol vẫn là HTTPS | `FAIL / ORIGIN_TLS_MISMATCH` | `502` |
| Xray không listen / sai cổng origin | `FAIL / ORIGIN_UNREACHABLE` | `504` |
| Cấu hình chuẩn | `PASS / WS_ROUTED_TO_ORIGIN` | `101 Switching Protocols`, VLESS probe trả về byte thật |

### Phân biệt 403 "không tồn tại" và 403 "policy HTTPS only"

Cả hai đều trả về body giống hệt nhau (`403 ERROR` … `Bad request.` … `X-Cache: Error from cloudfront`), nên **phải nhìn DNS** mới phân biệt được:

```powershell
# Domain thật -> có A record ; domain sai/distribution Disabled -> KHÔNG có A record
Resolve-DnsName d111111abcdef8.cloudfront.net -Type A
Resolve-DnsName d2fhr3e9msynb2.cloudfront.net -Type A
```

Kiểm tra chéo bằng resolver khác để loại trừ cache DNS:

```powershell
nslookup d2fhr3e9msynb2.cloudfront.net 8.8.8.8
Invoke-RestMethod 'https://cloudflare-dns.com/dns-query?name=d2fhr3e9msynb2.cloudfront.net&type=A' -Headers @{accept='application/dns-json'}
```

Nếu **không có A record**: vào CloudFront console, **copy lại** *Distribution domain name* (đừng gõ tay), kiểm tra *Status = Deployed*, và nếu là `Disabled` thì **Enable** rồi chờ deploy xong. Sau đó dán đúng domain vào `host=` của link.

Distribution vừa tạo có thể bị `403` ở mọi path trong vài phút đầu, nên hãy kiểm DNS lại vài lần
(ví dụ 20 giây một lần trong ~2 phút). Nếu sau ~15 phút vẫn không có A record thì **gần như chắc chắn**
domain bị gõ sai, hoặc distribution đang `Disabled`/đã bị xoá — chờ thêm cũng vô ích.

> [!NOTE]
> CloudFront console đôi khi hiện status `Deployed` nhưng distribution vẫn `Disabled` — trạng thái triển khai và trạng thái bật/tắt là 2 cột khác nhau. Cột cần xem là **Status/State** (Enabled/Disabled), không phải *Last modified*.
