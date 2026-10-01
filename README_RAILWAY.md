# Aether AI Server — Production Railway

This repository is designed for GitHub → Railway Docker deployment. After deploy,
no SSH `pip install`, `apt install`, model download, `chmod`, directory creation or
manual process start is required.

## Railway variables

```env
AETHER_OWNER_USERNAME=owner
AETHER_OWNER_PASSWORD=<strong-password>
AETHER_SECRET_KEY=<long-random-secret>
AETHER_DATA_DIR=/data
AETHER_AUTO_LOCAL_AI=1
AETHER_ENABLE_STABLE_DIFFUSION=1
AETHER_PUBLIC_URL=https://ai-production-df18.up.railway.app
AETHER_APK_SERVER_URL=https://ai-production-df18.up.railway.app
```

Attach a persistent Railway volume at `/data`. Startup creates all required
subdirectories without deleting existing content. Qwen download uses a `.part`
file and atomic rename. The Qwen supervisor avoids duplicates and restarts the
optional process after a crash. If Qwen or Stable Diffusion is unavailable, the
FastAPI process remains online and reports the real fallback/status.

## Public endpoints

- `GET /` bundled web dashboard
- `GET /health`, `GET /api/health`
- `GET /api/config/public`
- `POST /api/auth/login`, `GET /api/auth/me`

Authenticated endpoints include chat/history, projects/files, system and builder
status, authorized terminal, media, security analysis, file upload/download,
persistent jobs (`/api/jobs` and `/api/jobs/{id}`), model status and SSE chat
streaming (`/api/chat/stream`).

## APK

The Android app is a bundled WebView client: its HTML/CSS/JS and `config.js` are
inside the APK, while API/data requests go to the single URL in
`android/server-url.txt`. The build script generates `config.js` from that file,
so URL changes do not require editing Java code.

```bash
cd android
./build-apk.sh
```

The client includes the D2D chat UI, login, history, project/media navigation,
file upload picker and job status. Server-side features remain protected by JWT.

## Stable Diffusion

The Docker image installs the CPU-compatible Diffusers/Torch stack and starts a
background readiness worker automatically. The worker downloads/resumes
`runwayml/stable-diffusion-v1-5` into `/data/huggingface/hub`, loads the actual
pipeline, and writes `/data/stable-diffusion-ready` only after that load succeeds.
Startup never blocks the FastAPI process. Until then, `GET /api/models/status`
reports `downloading`; on a real failure it reports `failed:<reason>`. Logs are
stored at `/data/logs/stable-diffusion-download.log`.

## Validation

```bash
python3 -m pip install -r requirements.txt pytest
python3 -m compileall -q .
python3 -m pytest -q
```
