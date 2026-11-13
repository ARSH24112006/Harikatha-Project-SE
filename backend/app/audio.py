"""PCM16 mono WAV helpers (stdlib only)."""
import wave
from array import array
from pathlib import Path


def write_wav(path: Path, samples: array, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


def read_wav(path: Path) -> tuple[array, int]:
    with wave.open(str(path), "rb") as w:
        samples = array("h")
        samples.frombytes(w.readframes(w.getnframes()))
        return samples, w.getframerate()


def duration(samples: array, rate: int) -> float:
    return len(samples) / rate


def apply_gain(samples: array, gain_db: float) -> array:
    if gain_db == 0:
        return samples
    k = 10 ** (gain_db / 20)
    return array("h", (max(-32768, min(32767, round(s * k))) for s in samples))


def peak(samples: array) -> float:
    return max(map(abs, samples), default=0) / 32768
