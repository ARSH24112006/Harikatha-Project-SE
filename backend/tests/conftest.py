import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    """Tests must never depend on .env or hit the real Sarvam API."""
    monkeypatch.setattr(settings, "mock_sarvam", True)
    monkeypatch.setattr(settings, "sarvam_api_key", "")
