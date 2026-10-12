#!/usr/bin/env bash
# Build the widget APK and hand it to the web app so it can be downloaded from /settings/widget.
set -euo pipefail
cd "$(dirname "$0")"
./build.sh >/dev/null
sudo install -d -o tadpole -g tadpole -m 0750 /var/lib/tadpole/apk
sudo install -o tadpole -g tadpole -m 0640 build/tadpole-widget.apk /var/lib/tadpole/apk/tadpole-widget.apk
# keep a signed copy in the repo: the website build (and GitHub Actions) ships this file, since the signing key never leaves this machine
mkdir -p ../release && cp build/tadpole-widget.apk ../release/tadpole.apk
echo "published $(stat -c %s build/tadpole-widget.apk) bytes"
