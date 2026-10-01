#!/usr/bin/env bash
set -Eeuo pipefail
PORT="${PORT:-8080}"
DATA_ROOT="${AETHER_DATA_DIR:-/data}"
export AETHER_PORT="$PORT" AETHER_HOST="0.0.0.0" AETHER_DATA_DIR="$DATA_ROOT"
MODEL_DIR="${AETHER_MODEL_DIR:-$DATA_ROOT/models}"
MODEL="${AETHER_LOCAL_AI_MODEL:-Qwen3-0.6B-Q4_K_M.gguf}"
MODEL_PATH="$MODEL_DIR/$MODEL"
MODEL_URL="${AETHER_LOCAL_AI_MODEL_URL:-https://huggingface.co/QuantFactory/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B.Q4_K_M.gguf}"
LLAMA_BIN="${AETHER_LLAMA_SERVER_BIN:-/opt/llama.cpp/build/bin/llama-server}"
LLAMA_PID="$DATA_ROOT/llama.pid"
LOG_DIR="$DATA_ROOT/logs"
SD_MARKER="$DATA_ROOT/stable-diffusion-ready"
SD_STATUS="$DATA_ROOT/stable-diffusion.status"
mkdir -p "$MODEL_DIR" "$DATA_ROOT/huggingface/hub" "$DATA_ROOT/workspace" "$DATA_ROOT/uploads" "$DATA_ROOT/media" "$DATA_ROOT/jobs" "$DATA_ROOT/cache" "$LOG_DIR"

echo "AETHER: data root=$DATA_ROOT"
echo "AETHER: model path=$MODEL_PATH"

if [ "${AETHER_AUTO_LOCAL_AI:-1}" = "1" ] && [ ! -s "$MODEL_PATH" ]; then
  echo "AETHER: downloading/resuming Qwen model (optional)"
  part="${MODEL_PATH}.part"
  # Keep the .part file after a failed attempt; curl resumes it on the next restart.
  if curl -L --fail --continue-at - --connect-timeout 20 --max-time "${AETHER_MODEL_DOWNLOAD_TIMEOUT:-3600}" \
      --retry "${AETHER_MODEL_RETRIES:-5}" --retry-delay 5 -o "$part" "$MODEL_URL" && [ -s "$part" ]; then
    mv -f "$part" "$MODEL_PATH"
  else
    echo "AETHER: Qwen unavailable; partial download preserved at $part; API uses fallback" >&2
  fi
fi

start_qwen() {
  [ "${AETHER_AUTO_LOCAL_AI:-1}" = "1" ] || return 0
  [ -x "$LLAMA_BIN" ] && [ -s "$MODEL_PATH" ] || return 0
  if [ -f "$LLAMA_PID" ] && kill -0 "$(cat "$LLAMA_PID")" 2>/dev/null; then return 0; fi
  "$LLAMA_BIN" -m "$MODEL_PATH" --host "${AETHER_AI_HOST:-127.0.0.1}" --port "${AETHER_AI_PORT:-8090}" \
    -c "${AETHER_AI_CONTEXT:-2048}" -t "${AETHER_AI_THREADS:-2}" -ngl "${AETHER_AI_NGL:-0}" >>"$LOG_DIR/llama.log" 2>&1 &
  echo $! > "$LLAMA_PID"
  echo "AETHER: Qwen started pid=$(cat "$LLAMA_PID")"
}
qwen_supervisor() {
  while true; do start_qwen || true; sleep "${AETHER_QWEN_CHECK_INTERVAL:-10}"; done
}
qwen_supervisor &
QWEN_SUPERVISOR_PID=$!

stable_diffusion_supervisor() {
  if [ -f "$SD_MARKER" ]; then echo ready > "$SD_STATUS"; return 0; fi
  if [ "${AETHER_ENABLE_STABLE_DIFFUSION:-1}" != "1" ]; then echo disabled > "$SD_STATUS"; return 0; fi
  echo downloading > "$SD_STATUS"
  local attempt=0 max="${AETHER_SD_MAX_RETRIES:-0}" delay="${AETHER_SD_RETRY_DELAY:-30}"
  while [ ! -f "$SD_MARKER" ]; do
    attempt=$((attempt + 1))
    if python scripts/stable_diffusion_worker.py >>"$LOG_DIR/stable-diffusion-download.log" 2>&1; then
      echo ready > "$SD_STATUS"; return 0
    fi
    echo "failed attempt=$attempt" > "$SD_STATUS"
    [ "$max" -gt 0 ] && [ "$attempt" -ge "$max" ] && return 0
    sleep "$delay"
    [ "$delay" -lt 900 ] && delay=$((delay * 2))
  done
}
stable_diffusion_supervisor &
SD_SUPERVISOR_PID=$!

# Persist the generated fallback secret on the Railway volume so restarts do not invalidate JWTs.
if [ -z "${AETHER_SECRET_KEY:-}" ]; then
  SECRET_FILE="$DATA_ROOT/.aether_secret"
  if [ -s "$SECRET_FILE" ]; then AETHER_SECRET_KEY="$(cat "$SECRET_FILE")"; else
    AETHER_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    umask 077; printf '%s' "$AETHER_SECRET_KEY" > "$SECRET_FILE"
  fi
  export AETHER_SECRET_KEY
fi
cleanup() { kill "$QWEN_SUPERVISOR_PID" "$SD_SUPERVISOR_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
exec python -m uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
