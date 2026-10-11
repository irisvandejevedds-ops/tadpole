#!/usr/bin/env bash
# Copy the app to /opt/tadpole/app (root-owned, world-readable) and restart the service.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)/app"
sudo rm -rf /opt/tadpole/app.new && sudo mkdir -p /opt/tadpole/app.new
sudo cp -r "$SRC/tadpole" /opt/tadpole/app.new/tadpole
sudo find /opt/tadpole/app.new -name __pycache__ -type d -prune -exec rm -rf {} +
sudo chmod -R a+rX /opt/tadpole/app.new
sudo rm -rf /opt/tadpole/app.old
[ -d /opt/tadpole/app ] && sudo mv /opt/tadpole/app /opt/tadpole/app.old
sudo mv /opt/tadpole/app.new /opt/tadpole/app
sudo systemctl restart tadpole-web
echo "deployed; service restarted"
