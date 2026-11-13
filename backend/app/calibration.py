"""Measured TTS speed (chars/sec), smoothed over runs. Used to turn seconds into characters."""
import json

from .config import settings

FALLBACK_CPS = 13.2
_SMOOTHING = 0.3  # weight of the newest measurement


def _path():
    return settings.data_dir / "runtime" / "calibration.json"


def _key(language: str) -> str:
    return f"{language}|{settings.tts_speaker}|{settings.tts_model}|{'mock' if settings.mock_sarvam else 'live'}"


def _load() -> dict:
    return json.loads(_path().read_text()) if _path().exists() else {}


def get(language: str) -> float:
    return _load().get(_key(language), FALLBACK_CPS)


def update(language: str, chars: int, seconds: float) -> None:
    if chars < 50 or seconds <= 0:
        return
    data = _load()
    measured = chars / seconds
    old = data.get(_key(language))
    data[_key(language)] = round(measured if old is None else old * (1 - _SMOOTHING) + measured * _SMOOTHING, 3)
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(data, indent=2))
