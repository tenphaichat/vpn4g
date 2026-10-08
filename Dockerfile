FROM --platform=linux/amd64 python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cai ca-certificates, curl, git, procps
RUN apt-get update -y && apt-get install --no-install-recommends -y \
    ca-certificates curl git procps \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app/

# Chuan hoa LF, cai dependencies va tai san binary xray + cloudflared ngay luc build
RUN sed -i 's/\r$//' /app/*.sh /app/*.py \
 && chmod +x /app/run.sh /app/install.sh /app/entrypoint.sh \
 && ln -sf /app /root/vless \
 && pip install --no-cache-dir -q -r /app/requirements.txt \
 && python3 /app/download-xray.py \
 && python3 /app/download-cloudflared.py

EXPOSE 9999

CMD ["/app/entrypoint.sh"]
