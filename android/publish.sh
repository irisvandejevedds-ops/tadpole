#!/usr/bin/env bash
# Build the widget APK and hand it to the web app so it can be downloaded from /settings/widget.
set -euo pipefail
cd "$(dirname "$0")"
./build.sh >/dev/null
sudo install -d -o tadpole -g tadpole -m 0750 /var/lib/tadpole/apk
sudo install -o tadpole -g tadpole -m 0640 build/tadpole-widget.apk /var/lib/tadpole/apk/tadpole-widget.apk
echo "published $(stat -c %s build/tadpole-widget.apk) bytes"
