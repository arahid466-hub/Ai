#!/data/data/com.termux/files/usr/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p database logs run workspace uploads backups config
python3 -m venv .venv 2>/dev/null || true
if [ -x .venv/bin/pip ]; then .venv/bin/pip install -r requirements.txt; else pip3 install --user -r requirements.txt; fi
if [ ! -f .env ]; then cp .env.example .env; fi
python3 -m server.main --init-db
chmod +x scripts/aether-start scripts/aether-stop scripts/aether-status
printf '\nAETHER setup complete. Run: ./scripts/aether-start\n'
