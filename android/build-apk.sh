#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
FILE_URL="$(awk '!/^[[:space:]]*#/ && NF {print; exit}' "$ROOT/server-url.txt" 2>/dev/null || true)"
URL="${AETHER_SERVER_URL:-$FILE_URL}"
if [[ -z "$URL" || "$URL" == *YOUR-* || ! "$URL" =~ ^https?:// ]]; then
  echo "ERROR: Put the real deployed server URL in android/server-url.txt or set AETHER_SERVER_URL." >&2
  exit 2
fi
mkdir -p "$ROOT/app/src/main/assets"
printf "window.AETHER_CONFIG = { serverUrl: '%s' };\n" "$URL" > "$ROOT/app/src/main/assets/config.js"
if ! command -v gradle >/dev/null 2>&1; then
  echo "ERROR: Gradle is required. Install Android SDK + Gradle, then rerun this script." >&2
  exit 2
fi
gradle -p "$ROOT" --no-daemon assembleDebug
APK="$ROOT/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
echo "APK_READY=$APK"
