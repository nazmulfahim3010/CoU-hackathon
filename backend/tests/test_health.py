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
