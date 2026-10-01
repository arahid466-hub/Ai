"""Lazy, process-local Stable Diffusion image generation.
The API only enters this path after the persistent readiness marker exists.
"""
from __future__ import annotations
import os
from pathlib import Path

_PIPELINE = None


def generate(prompt: str, width: int, height: int, output: Path) -> str:
    global _PIPELINE
    if not (Path(os.getenv("AETHER_DATA_DIR", "/data")) / "stable-diffusion-ready").exists():
        raise RuntimeError("Stable Diffusion model is not ready")
    import torch
    from diffusers import DiffusionPipeline
    if _PIPELINE is None:
        _PIPELINE = DiffusionPipeline.from_pretrained(
            os.getenv("AETHER_STABLE_DIFFUSION_MODEL", "runwayml/stable-diffusion-v1-5"),
            cache_dir=os.getenv("HF_HOME", "/data/huggingface"),
            torch_dtype=torch.float32,
            local_files_only=True,
        )
        _PIPELINE.to("cpu")
    result = _PIPELINE(prompt=prompt, width=width, height=height, num_inference_steps=int(os.getenv("AETHER_SD_STEPS", "20")))
    result.images[0].save(output, format="PNG")
    return "Stable Diffusion CPU pipeline"
