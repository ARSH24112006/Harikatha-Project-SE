"""TTS with a global content-addressed cache (one entry per sentence chunk).

Mock mode generates a quiet 200 Hz tone whose length is len(text) / MOCK_CHARS_PER_SEC.
Live mode calls Bulbul (POST /text-to-speech) and caches the returned WAV.
"""
import base64
import hashlib
import re
import wave
from array import array

from . import audio, sarvam
from .config import settings

MOCK_CHARS_PER_SEC = 12.0
MAX_CHUNK_CHARS = 400  # API limit is 2500; short chunks keep prosody natural and cache well
_MOCK_HZ = 200  # divides every supported rate into whole periods
_SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")


def split_text(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Greedy-pack whole sentences into chunks of at most `limit` chars."""
    chunks: list[str] = []
    for sentence in _SENTENCE_END.split(text.strip()):
        while len(sentence) > limit:  # a single run-on sentence: cut at the last space
            cut = sentence.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if chunks and sentence and len(chunks[-1]) + 1 + len(sentence) <= limit:
            chunks[-1] += " " + sentence
        elif sentence:
            chunks.append(sentence)
    return chunks or [text]


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


def _bulbul(text: str, language: str, pace: float) -> bytes:
    data = sarvam.post("/text-to-speech", {
        "text": text,
        "language_code": language,
        "speaker": settings.tts_speaker,
        "model": settings.tts_model,
        "pace": min(2.0, max(0.5, pace)),
        "speech_sample_rate": settings.tts_sample_rate,
        "output_audio_codec": "wav",
        "temperature": 0.6,
    })
    # Per the docs, audios may be split across elements: join, then decode.
    return base64.b64decode("".join(data["audios"]))


def _synth_chunk(text: str, language: str, pace: float) -> tuple[array, bool]:
    path = settings.data_dir / "runtime" / "tts_cache" / f"{cache_key(text, language, pace)}.wav"
    if path.exists():
        return audio.read_wav(path)[0], True
    if settings.mock_sarvam:
        samples = _mock_tone(text, pace)
        audio.write_wav(path, samples, settings.tts_sample_rate)
        return samples, False
    wav_bytes = _bulbul(text, language, pace)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{id(wav_bytes)}.tmp")  # atomic: concurrent renders share the cache
    tmp.write_bytes(wav_bytes)
    try:
        samples, rate = audio.read_wav(tmp)
    except wave.Error as e:
        tmp.unlink(missing_ok=True)
        raise sarvam.SarvamError(f"unexpected WAV from Bulbul: {e}") from e
    if rate != settings.tts_sample_rate:
        tmp.unlink(missing_ok=True)
        raise sarvam.SarvamError(f"Bulbul returned {rate} Hz, expected {settings.tts_sample_rate}")
    tmp.replace(path)
    return samples, False


def synthesize(text: str, language: str, pace: float = 1.0) -> tuple[array, bool]:
    """Returns (samples, all_chunks_cached)."""
    chunks = [text] if settings.mock_sarvam else split_text(text)
    out, all_hit = array("h"), True
    for chunk in chunks:
        samples, hit = _synth_chunk(chunk, language, pace)
        out.extend(samples)
        all_hit &= hit
    return out, all_hit
