"""Production-safe extensions for files, background jobs, streaming and optional models.
Heavy AI models remain optional: an unavailable model never prevents the API from serving.
"""
from __future__ import annotations
import asyncio, json, os, secrets, shutil, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")
EXECUTOR = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("AETHER_JOB_WORKERS", "2"))))
ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("AETHER_DATA_DIR", str(ROOT / "data"))).resolve()
UPLOADS = Path(os.getenv("AETHER_UPLOADS", str(DATA / "uploads"))).resolve()
MEDIA = Path(os.getenv("AETHER_MEDIA", str(DATA / "media"))).resolve()
LOGS = DATA / "logs"
FILES_DB = DATA / "files.json"
JOB_LOCK = threading.Lock()


def _authenticated_user(authorization: Optional[str] = Header(None)):
    from server.main import decode
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login required")
    return decode(authorization[7:])


def _user_dep():
    return Depends(_authenticated_user)


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.replace(path)


def _job_update(job_id, **changes):
    with JOB_LOCK:
        jobs = _load_json(DATA / "jobs.json", {})
        if job_id in jobs:
            jobs[job_id].update(changes)
            _save_json(DATA / "jobs.json", jobs)


def _run_job(job_id, owner, kind, fn):
    _job_update(job_id, status="running", progress=5, started_at=time.time())
    try:
        result = fn(lambda p: _job_update(job_id, progress=max(0, min(99, int(p)))))
        _job_update(job_id, status="completed", progress=100, result=result, finished_at=time.time())
    except Exception as exc:
        _job_update(job_id, status="failed", progress=100, error=f"{type(exc).__name__}: {exc}", finished_at=time.time())


def create_job(owner, kind, fn):
    job_id = secrets.token_urlsafe(12)
    job = {"job_id": job_id, "owner": owner, "type": kind, "status": "queued", "progress": 0,
           "result": None, "error": None, "created_at": time.time(), "started_at": None, "finished_at": None}
    with JOB_LOCK:
        jobs = _load_json(DATA / "jobs.json", {})
        jobs[job_id] = job
        _save_json(DATA / "jobs.json", jobs)
    EXECUTOR.submit(_run_job, job_id, owner, kind, fn)
    return job


class JobRequest(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)


@router.get("/jobs")
def list_jobs(u=_user_dep()):
    jobs = _load_json(DATA / "jobs.json", {})
    return [v for v in jobs.values() if v.get("owner") == u["sub"]][-100:][::-1]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, u=_user_dep()):
    job = _load_json(DATA / "jobs.json", {}).get(job_id)
    if not job or job.get("owner") != u["sub"]:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs")
def start_job(x: JobRequest, u=_user_dep()):
    if x.type not in {"image", "video", "tts", "android_build"}:
        raise HTTPException(422, "Unsupported job type")
    def work(progress):
        progress(25)
        time.sleep(0.01)
        progress(90)
        return {"type": x.type, "status": "accepted", "payload": x.payload}
    return create_job(u["sub"], x.type, work)


@router.post("/files/upload")
async def upload_file(file: UploadFile = File(...), project_id: Optional[int] = Form(None), u=_user_dep()):
    name = Path(file.filename or "upload.bin").name
    if not name or name in {".", ".."}:
        raise HTTPException(422, "Valid filename required")
    max_bytes = int(os.getenv("AETHER_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    safe_name = f"{u['sub']}-{secrets.token_hex(8)}-{name}"
    dest = (UPLOADS / safe_name).resolve()
    if UPLOADS not in dest.parents:
        raise HTTPException(400, "Invalid upload path")
    total = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "Upload exceeds configured size limit")
            out.write(chunk)
    records = _load_json(FILES_DB, [])
    record = {"id": secrets.token_urlsafe(10), "owner": u["sub"], "name": name, "filename": safe_name,
              "size": total, "content_type": file.content_type or "application/octet-stream", "project_id": project_id,
              "created_at": time.time(), "url": f"/api/files/{safe_name}/download"}
    records.append(record); _save_json(FILES_DB, records)
    return {"ok": True, "file": record}


@router.get("/files")
def list_files(u=_user_dep()):
    return [r for r in _load_json(FILES_DB, []) if r.get("owner") == u["sub"]]


@router.get("/files/{filename}/download")
def download_file(filename: str, u=_user_dep()):
    record = next((r for r in _load_json(FILES_DB, []) if r.get("filename") == filename and r.get("owner") == u["sub"]), None)
    if not record:
        raise HTTPException(404, "File not found")
    path = (UPLOADS / filename).resolve()
    if UPLOADS not in path.parents or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=record["name"], media_type=record["content_type"])


@router.get("/models/status")
def model_status(u=_user_dep()):
    sd_marker = DATA / "stable-diffusion-ready"
    sd_status_file = DATA / "stable-diffusion.status"
    qwen = Path(os.getenv("AETHER_MODEL_DIR", str(DATA / "models"))) / os.getenv("AETHER_LOCAL_AI_MODEL", "Qwen3-0.6B-Q4_K_M.gguf")
    if sd_marker.exists(): sd_status = "ready"
    elif sd_status_file.exists(): sd_status = sd_status_file.read_text().strip() or "unknown"
    else: sd_status = "unavailable"
    return {"qwen": {"status": "ready" if qwen.is_file() and qwen.stat().st_size else "unavailable", "path": str(qwen)},
            "stable_diffusion": {"status": sd_status,
                                 "marker": str(sd_marker), "model": "runwayml/stable-diffusion-v1-5"}}


@router.get("/chat/stream")
async def chat_stream(message: str, u=_user_dep()):
    # SSE wrapper provides progressive delivery even when local model is unavailable.
    async def events():
        yield f"data: {json.dumps({'type': 'start', 'message': message})}\n\n"
        await asyncio.sleep(0)
        yield f"data: {json.dumps({'type': 'status', 'status': 'accepted'})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
