# Optional local Qwen GGUF model

The Railway entrypoint downloads the default Qwen3 0.6B Q4 model into this
directory on first boot when `AETHER_AUTO_LOCAL_AI=1`. If the download is not
available, the API still starts and chat returns an explicit fallback status.

Expected default filename: `Qwen3-0.6B-Q4_K_M.gguf`
