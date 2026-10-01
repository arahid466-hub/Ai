# AETHER AI SERVER

A premium, local-first AI control center designed for Android Termux ARM64 and portable Linux hosting.

## Included
- FastAPI + SQLite backend with PBKDF2 password hashing and HMAC-SHA256 JWT sessions.
- Premium responsive single-page chat interface at `/` (login is embedded in the root route).
- Local Qwen/llama.cpp OpenAI-compatible connector with graceful fallback to demo mode.
- **One URL server connector**: add local Termux, public host, VIP host, backup host, or any OpenAI-compatible endpoint; choose one active profile from Settings.
- Project CRUD, safe project file APIs, controlled terminal API, asynchronous jobs, system/builder health, chat history.
- Build-ready Android WebView wrapper source under `android/`.
- Termux-friendly `aether-start`, `aether-status`, `aether-stop` scripts.

## Quick start on Termux
```bash
unzip Aether-AI-Server.zip
cd Aether-AI-Server
bash scripts/setup.sh
# edit config/local-ai.env if needed
./scripts/aether-start
```
Open `http://127.0.0.1:8080/`. The first run prints a generated owner password; save it securely. Set `AETHER_OWNER_PASSWORD` before setup to choose one.

## One URL server connection
The UI's **Servers** panel stores profiles locally in the server database. Each profile has a single base URL and optional API key. Examples:
- `http://127.0.0.1:8080` for Termux local server
- `https://your-public-host.example` for a hosted server
- `https://vip.example/api` for a VIP/private server

The active profile is used by the Android wrapper and can be changed without rebuilding the APK. In the Android app, enter the URL in the first-run server screen or change it in Settings. Never paste secrets into screenshots or public URLs.

## Android APK
This sandbox did not include Android SDK/Gradle, so the deliverable includes a complete WebView Android source project, not a compiled binary. On a machine with Android SDK + Gradle:
```bash
cd android
./gradlew assembleDebug
```
Install `android/app/build/outputs/apk/debug/app-debug.apk`. Set the server URL inside `MainActivity.java` or use the in-app first-run URL screen. The wrapper uses HTTPS by default; cleartext is enabled only for local development URLs.

## Security notes
- Change the owner password immediately.
- Bind to `127.0.0.1` for private Termux use. Only use `0.0.0.0` behind TLS/auth when intentionally publishing.
- Terminal commands are allowlisted and confined to the project workspace. This is a development control plane, not a general shell.
- Cyber-lab features are intentionally limited to authorized defensive analysis; no credential theft, persistence, bypass, or intrusion tooling is included.

## Revised Security + Development Engine Extension

The package now includes:
- `ai/core/autonomous_agent.py`: intent classification and verification-first execution plan model.
- `ai/tool_registry.py`: central runtime tool registry interface.
- `/api/ai/status`, `/api/image/status`, `/api/tts/status`, `/api/builder/status`, `/api/security/status`, `/api/system/status`.
- `/api/security/apk/analyze`: bounded APK ZIP/metadata/permission/URL analysis with SHA-256 evidence.
- `security_lab/` defensive lab directories for APK, API, fuzz, bypass, anti-cheat, payment, sandbox, and report export.
- `security_lab/reports/engine.py` for JSON, Markdown, and HTML report metadata.
- `install_aether_complete.sh` for backup-aware installation and binary detection.
- `tests/test_core.py` for agent routing and APK analyzer checks.

### Honest capability reporting

A missing local engine is never reported as successful. The server returns messages such as:
- `NOT AVAILABLE / NEEDS COMPATIBLE TOOLCHAIN`
- `MODEL NOT INSTALLED`
- `BROWSER TTS ONLY`

The sandbox used to assemble this ZIP has no Android SDK/Gradle, no stable-diffusion.cpp binary, and no APK reverse-engineering binaries. Therefore the package includes detection and safe analysis interfaces, not fabricated APK/image-generation success. Install compatible ARM64 tools on Termux to enable those capabilities.

All security-lab features are restricted in scope to owned apps, owned servers, local sandboxes, or explicitly authorized targets. No credential theft, malware persistence, evasion, destructive attack, or internet-wide scanning functionality is included.

## Security boundary

This project intentionally does **not** include bypass hacking, credential theft, third-party intrusion, malware persistence, evasion, or destructive attack tools. It does include defensive checks for owned/authorized targets:

- APK integrity hash verification
- APK static surface inspection
- exported-component and risky-configuration warnings
- local/test API target guard
- toolchain availability detection
- controlled allowlisted terminal execution
- report generation with evidence

Use `/api/security/authorized-check` with `apk_integrity`, `apk_surface`, `api_target_guard`, or `toolchain` for these checks. Any non-local API target must be explicitly authorized by the owner before testing.
