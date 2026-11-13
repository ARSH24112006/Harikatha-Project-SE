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


def test_script_versions_are_immutable(tmp_path, monkeypatch):
    from app import store
    from app.schemas import GenerateRequest

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    pid = store.create(GenerateRequest(title="t", story="s"))
    d = settings.performances_dir / pid

    meta = store.read(pid, "meta.json")
    assert meta["settings"]["tts_model"] == "bulbul:v3"
    assert "sarvam_api_key" not in meta["settings"]

    assert store.save_script(pid, {"segments": ["a"]}, "initial") == 1
    assert store.save_script(pid, {"segments": ["b"]}, "fit round 1") == 2

    assert store.read(pid, "script.v1.json") == {"segments": ["a"]}
    assert store.read(pid, "script.json") == {"segments": ["b"]}
    assert [v["v"] for v in store.read(pid, "meta.json")["script_versions"]] == [1, 2]
    assert store.write_status(pid, "scripted")["script_version"] == 2
    assert (d / "script.v2.json").exists()
