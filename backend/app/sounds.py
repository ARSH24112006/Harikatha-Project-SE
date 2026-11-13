"""Sound beds: recorded files listed in sounds/manifest.json, or synthesised stand-ins.

Recordings are git-ignored (see sounds/fetch_sounds.sh), so every bed has a synthetic
fallback and the mixer works on a fresh checkout and in CI.
"""
import json
import subprocess
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .config import settings


@dataclass
class Bed:
    samples: np.ndarray  # float32 mono at the requested rate
    sa_hz: float | None = None
    file: str | None = None  # None means synthesised
    meta: dict | None = None  # manifest entry (licence, author, ...)


def _manifest() -> dict[str, dict]:
    path = settings.sounds_dir / "manifest.json"
    if not path.exists():
        return {}
    return {k: v for k, v in json.loads(path.read_text()).items() if isinstance(v, dict)}


@lru_cache(maxsize=32)
def _decode(path: str, rate: int, mtime: float) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def recorded(kind: str, rate: int) -> list[Bed]:
    """Recorded beds of this kind that exist on disk and decode, sorted by file name."""
    beds = []
    for name, meta in sorted(_manifest().items()):
        path = settings.sounds_dir / name
        if meta.get("kind") != kind or not path.exists():
            continue
        try:
            samples = _decode(str(path), rate, path.stat().st_mtime)
        except (OSError, subprocess.SubprocessError):  # no ffmpeg, or a corrupt file
            continue
        beds.append(Bed(samples, meta.get("sa_hz"), name, meta))
    return beds


# --- synthesised fallbacks ---------------------------------------------------

def synth_tanpura(rate: int, sa_hz: float = 138.6) -> Bed:
    """Four plucked strings (Pa, Sa, Sa, low Sa) in a 6 s cycle that wraps seamlessly."""
    n = 6 * rate
    t = np.arange(n) / rate
    out = np.zeros(n)
    for f, t0 in [(1.5 * sa_hz, 0.0), (sa_hz, 1.5), (sa_hz, 3.0), (sa_hz / 2, 4.5)]:
        tone = sum(np.sin(2 * np.pi * f * h * t) / h**1.2 for h in range(1, 12)) * np.exp(-t / 1.8)
        out += np.roll(tone, int(t0 * rate))
    return Bed((out / np.abs(out).max() * 0.5).astype(np.float32), sa_hz)


def synth_bell(rate: int) -> Bed:
    t = np.arange(6 * rate) / rate
    partials = [(1.0, 1.0), (2.0, 0.6), (2.76, 0.5), (5.4, 0.3), (8.93, 0.2)]
    x = sum(a * np.sin(2 * np.pi * 440 * r * t) * np.exp(-t * (0.8 + 0.5 * r)) for r, a in partials)
    return Bed((x / np.abs(x).max() * 0.8).astype(np.float32))


def synth_cymbal(rate: int) -> Bed:
    t = np.arange(rate) / rate
    noise = np.diff(np.random.default_rng(0).standard_normal(rate + 1))  # crude high-pass
    return Bed((noise * np.exp(-t / 0.12) / 4).astype(np.float32))


def tanpuras(rate: int) -> list[Bed]:
    return recorded("tanpura", rate) or [synth_tanpura(rate)]


def one_shot(kind: str, rate: int) -> Bed:
    beds = recorded(kind, rate)
    if beds:
        return beds[0]
    return synth_bell(rate) if kind == "bell" else synth_cymbal(rate)


def scene(rate: int) -> Bed | None:
    beds = recorded("scene", rate)
    return beds[0] if beds else None  # no synthetic scene: skipping it is better than fake crowd noise
