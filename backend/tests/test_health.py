from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "app_mode" in data
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


def test_health_reports_ffmpeg_and_gates_live_mode(client, monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    body = client.get("/api/health").json()
    assert body["ffmpeg"] == {"available": False}
    assert body["live_mode_ready"] is False  # never ready without ffmpeg, whatever the keys

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert client.get("/api/health").json()["ffmpeg"] == {"available": True}
