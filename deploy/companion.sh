#!/usr/bin/env bash
# One-time setup of the phone companion: a self-signed certificate (the phone pins it, so it needs no certificate authority) and a second service that
# answers ONLY the sync route over TLS on the home network. Safe to run again; it keeps an existing certificate.
set -euo pipefail
PORT="${TADPOLE_SYNC_PORT:-8120}"
sudo install -d -m 700 -o tadpole -g tadpole /var/lib/tadpole/tls
if [ ! -f /var/lib/tadpole/tls/cert.pem ]; then
  sudo -u tadpole openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=tadpole-companion" \
    -keyout /var/lib/tadpole/tls/key.pem -out /var/lib/tadpole/tls/cert.pem 2>/dev/null
  sudo chmod 600 /var/lib/tadpole/tls/key.pem
fi
sudo tee /etc/systemd/system/tadpole-sync.service >/dev/null <<UNIT
[Unit]
Description=Tadpole phone companion (sync route only, TLS)
After=network.target

[Service]
User=tadpole
Group=tadpole
EnvironmentFile=/etc/tadpole/tadpole.env
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=TADPOLE_SYNC_ONLY=1
Environment=TADPOLE_SYNC_PORT=$PORT
WorkingDirectory=/opt/tadpole/app
ExecStart=/opt/tadpole/venv/bin/uvicorn tadpole.main:get_app --factory --host 0.0.0.0 --port $PORT --no-server-header --ssl-keyfile /var/lib/tadpole/tls/key.pem --ssl-certfile /var/lib/tadpole/tls/cert.pem
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/tadpole
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=
MemoryMax=200M

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now tadpole-sync
sudo systemctl restart tadpole-sync
echo "companion listening on port $PORT"
