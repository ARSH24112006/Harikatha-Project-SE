import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    """Tests must never depend on .env or hit the real Sarvam API."""
    monkeypatch.setattr(settings, "mock_sarvam", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "")


@pytest.fixture(autouse=True)
def _no_recorded_sounds(tmp_path_factory, monkeypatch):
    """Default to an empty sounds dir so tests use the synthesised beds, like CI does."""
    monkeypatch.setattr(settings, "sounds_dir", tmp_path_factory.mktemp("sounds"))
