#!/usr/bin/env python3
"""Optional SD readiness worker. The ready marker is written only after the
actual Diffusers pipeline loads successfully from the persistent HF cache."""
from __future__ import annotations
import os, sys, time
from pathlib import Path

DATA = Path(os.getenv("AETHER_DATA_DIR", "/data"))
HF_HOME = Path(os.getenv("HF_HOME", str(DATA / "huggingface")))
MODEL = os.getenv("AETHER_STABLE_DIFFUSION_MODEL", "runwayml/stable-diffusion-v1-5")
MARKER = DATA / "stable-diffusion-ready"
STATUS = DATA / "stable-diffusion.status"
LOG = DATA / "logs" / "stable-diffusion-download.log"
CACHE = HF_HOME / "hub"


def write_status(value: str) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(value + "\n")
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {value}\n")


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True); LOG.parent.mkdir(parents=True, exist_ok=True)
    if MARKER.exists(): write_status("ready"); return 0
    write_status("downloading")
    try:
        import torch
        from diffusers import DiffusionPipeline
        dtype = torch.float32
        pipe = DiffusionPipeline.from_pretrained(MODEL, cache_dir=str(CACHE), torch_dtype=dtype, local_files_only=False)
        pipe.to("cpu")
        # Loading the pipeline is the readiness gate; do not claim ready before it succeeds.
        tmp = MARKER.with_suffix(".part")
        tmp.write_text(f"model={MODEL}\ncache={CACHE}\n")
        tmp.replace(MARKER)
        write_status("ready")
        return 0
    except Exception as exc:
        write_status(f"failed:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
