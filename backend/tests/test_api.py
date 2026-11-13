from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_create_and_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    r = client.post("/api/v1/performances", json={"title": "Gajendra", "story": "x"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.get(f"/api/v1/performances/{pid}/status").json()["stage"] == "analysing"
    assert client.get("/api/v1/performances/nope").status_code == 404
