#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
mkdir -p backups database logs run workspace uploads models
if [ -f .env ]; then cp .env "backups/.env.$(date +%Y%m%d%H%M%S).bak"; fi
PY=python3; command -v "$PY" >/dev/null || { echo 'PYTHON NOT AVAILABLE'; exit 1; }
"$PY" -m venv .venv 2>/dev/null || true
if [ -x .venv/bin/pip ]; then .venv/bin/pip install -r requirements.txt; else "$PY" -m pip install --user -r requirements.txt; fi
[ -f .env ] || cp .env.example .env
"${PY}" -m py_compile server/main.py ai/core/autonomous_agent.py
for x in python3 node java gradle ffmpeg adb aapt apktool jadx; do command -v "$x" >/dev/null 2>&1 && echo "$x: AVAILABLE" || echo "$x: NOT AVAILABLE / NEEDS COMPATIBLE TOOLCHAIN"; done
"${PY}" -m server.main
printf 'AETHER COMPLETE INSTALL OK\n'
