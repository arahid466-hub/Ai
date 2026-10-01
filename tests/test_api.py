import os


def test_api_auth_projects_media(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AETHER_OWNER_USERNAME", "owner")
    monkeypatch.setenv("AETHER_OWNER_PASSWORD", "test-password")
    monkeypatch.setenv("AETHER_SECRET_KEY", "test-secret-key")

    # Import after environment setup because the application resolves paths at import time.
    from fastapi.testclient import TestClient
    from server.main import app

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 200
        login = client.post("/api/auth/login", json={"username": "owner", "password": "test-password"})
        assert login.status_code == 200
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert client.get("/api/auth/me", headers=headers).json()["sub"] == "owner"
        project = client.post("/api/projects-v2", headers=headers, json={"name": "Smoke Project"})
        assert project.status_code == 200
        pid = project.json()["id"]
        assert client.get("/api/projects-v2", headers=headers).status_code == 200
        assert client.get(f"/api/project-files/{pid}/tree", headers=headers).status_code == 200

        image = client.post("/api/media/image", headers=headers, json={"prompt": "smoke test", "width": 256, "height": 256})
        assert image.status_code == 200
        assert client.get(image.json()["url"]).status_code == 200

        video = client.post("/api/media/video", headers=headers, json={"prompt": "smoke test", "width": 320, "height": 180, "duration": 1})
        assert video.status_code == 200
        assert client.get(video.json()["url"]).status_code == 200

        chat = client.post("/api/chat", headers=headers, json={"message": "hello"})
        assert chat.status_code == 200
        assert chat.json()["status"] in {"completed", "fallback"}

        assert client.get("/api/system-v2/info", headers=headers).status_code == 200
        assert client.get("/api/security/status", headers=headers).status_code == 200
        assert client.get("/api/tools/status", headers=headers).status_code == 200
