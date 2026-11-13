"""TTS with a global content-addressed cache.

Real Bulbul calls are not wired yet. In mock mode a quiet 200 Hz tone is
generated whose length is len(text) / MOCK_CHARS_PER_SEC.
"""
import hashlib
from array import array

from . import audio
from .config import settings

MOCK_CHARS_PER_SEC = 12.0
_MOCK_HZ = 200  # divides every supported rate into whole periods


def cache_key(text: str, language: str, pace: float) -> str:
    parts = [text, language, f"{pace:.3f}", settings.tts_model, settings.tts_speaker,
             str(settings.tts_sample_rate), "mock" if settings.mock_sarvam else "live"]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def _mock_tone(text: str, pace: float) -> array:
    rate = settings.tts_sample_rate
    n = max(rate // 3, round(len(text) / (MOCK_CHARS_PER_SEC * pace) * rate))
    period = rate // _MOCK_HZ
    cycle = array("h", (round(6000 * ((i / period) % 1 * 2 - 1)) for i in range(period)))
    samples = (cycle * (n // period + 1))[:n]
    fade = min(n // 2, rate // 50)
    for i in range(fade):  # 20 ms fades avoid clicks at segment joins
        samples[i] = samples[i] * i // fade
        samples[n - 1 - i] = samples[n - 1 - i] * i // fade
    return samples


def synthesize(text: str, language: str, pace: float = 1.0) -> tuple[array, bool]:
    """Returns (samples, cache_hit)."""
    path = settings.data_dir / "runtime" / "tts_cache" / f"{cache_key(text, language, pace)}.wav"
    if path.exists():
        return audio.read_wav(path)[0], True
    if not settings.mock_sarvam:
        raise NotImplementedError("Bulbul client not wired yet (needs SARVAM_API_KEY)")
    samples = _mock_tone(text, pace)
    audio.write_wav(path, samples, settings.tts_sample_rate)
    return samples, False
