import shutil

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "app_mode" in data
    assert "ffmpeg" in data
    assert isinstance(data["ffmpeg"]["available"], bool)
    assert "providers" in data
    assert "speech" in data["providers"]
    assert "llm" in data["providers"]
    assert "tts" in data["providers"]

    # Verify key values are never leaked in response
    serialized = str(data).lower()
    assert "api_key" not in serialized
    assert "bearer" not in serialized

    # Verify provider configured statuses are booleans
    assert isinstance(data["providers"]["speech"]["configured"], bool)
    assert isinstance(data["providers"]["llm"]["configured"], bool)
    assert isinstance(data["providers"]["tts"]["configured"], bool)
    assert "live_mode_ready" in data
    assert "active_sessions" in data


def test_health_ffmpeg_available(monkeypatch):
    monkeypatch.setattr("app.api.routes.health.shutil.which", lambda cmd: "/usr/bin/ffmpeg" if cmd == "ffmpeg" else None)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ffmpeg"]["available"] is True
    # Do not expose the binary path in the response
    assert "/usr/bin/ffmpeg" not in str(data)


def test_health_ffmpeg_unavailable(monkeypatch):
    monkeypatch.setattr("app.api.routes.health.shutil.which", lambda cmd: None)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ffmpeg"]["available"] is False
    assert data["live_mode_ready"] is False
