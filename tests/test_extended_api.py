import io
import json
import time


def test_extended_files_jobs_models_stream(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AETHER_OWNER_USERNAME", "owner")
    monkeypatch.setenv("AETHER_OWNER_PASSWORD", "test-password")
    monkeypatch.setenv("AETHER_SECRET_KEY", "test-secret-key")
    from fastapi.testclient import TestClient
    from server.main import app

    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "owner", "password": "test-password"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        upload = client.post("/api/files/upload", headers=headers, files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")})
        assert upload.status_code == 200
        record = upload.json()["file"]
        assert client.get("/api/files", headers=headers).json()[0]["name"] == "note.txt"
        assert client.get(record["url"], headers=headers).content == b"hello"

        job = client.post("/api/jobs", headers=headers, json={"type": "image", "payload": {"prompt": "test"}})
        assert job.status_code == 200
        job_id = job.json()["job_id"]
        for _ in range(20):
            current = client.get(f"/api/jobs/{job_id}", headers=headers).json()
            if current["status"] == "completed": break
            time.sleep(0.01)
        assert current["status"] == "completed"
        assert client.get("/api/models/status", headers=headers).status_code == 200
        stream = client.get("/api/chat/stream", headers=headers, params={"message": "hello"})
        assert stream.status_code == 200
        assert "[DONE]" in stream.text
