import itertools
import json
import shutil
from array import array

import numpy as np
import pytest

from app import audio, mixer, sounds
from app.config import settings

RATE = 24000
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def voice_clip(seconds=2.0, f0=150.0, pad=0.5):
    """A voiced tone with silence padding on both sides, like a TTS clip."""
    t = np.arange(int(seconds * RATE)) / RATE
    tone = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 6)) * 0.15
    z = np.zeros(int(pad * RATE))
    return np.concatenate([z, tone, z]).astype(np.float32)


def make_script():
    layout = [("invocation", "shloka"), ("prastavana", "narration"), ("nirupana_1", "narration"),
              ("nirupana_1", "song"), ("nirupana_1", "narration"), ("mangalam", "shloka")]
    segs = [{"id": f"{sec}.{i}", "section": sec, "type": typ, "delivery": {"pace": 1.0}}
            for i, (sec, typ) in enumerate(layout, 1)]
    return {"segments": segs}, {s["id"]: voice_clip() for s in segs}


def test_trim_silence_removes_tts_padding():
    out = mixer.trim_silence(voice_clip(2.0, pad=0.5), RATE)
    assert 2.0 <= len(out) / RATE < 2.1  # 2 s of tone plus the small margin
    assert abs(out[0]) < 1e-3 and abs(out[-1]) < 1e-3  # faded edges, no clicks


def test_pauses_replace_silence_and_timeline_is_tight():
    script, clips = make_script()
    mix = mixer.build(script, clips, RATE)
    tl = mix.timeline
    assert tl[0]["start"] == mixer.PRE_ROLL
    gaps = [b["start"] - a["end"] for a, b in itertools.pairwise(tl)]
    expected = [mixer.PAUSE["section"], mixer.PAUSE["section"], mixer.PAUSE["into_song"],
                mixer.PAUSE["out_of_song"], mixer.PAUSE["section"]]
    assert gaps == pytest.approx(expected, abs=0.005)
    assert max(gaps) <= 0.8 + 0.005  # the raw clips carried 1 s of silence per join
    assert len(mix.samples) / RATE == pytest.approx(tl[-1]["end"] + mixer.POST_ROLL, abs=0.01)


def test_no_dead_air_in_the_mix():
    script, clips = make_script()
    x = mixer.build(script, clips, RATE).samples
    win = RATE // 10
    lo, hi = int(mixer.PRE_ROLL * RATE), len(x) - int(mixer.POST_ROLL * RATE)
    levels = [mixer.rms(x[i: i + win]) for i in range(lo, hi - win, win)]
    assert 20 * np.log10(min(levels) + 1e-9) > -60  # the drone fills every pause


def test_estimate_f0_and_semitone_shift():
    assert mixer.estimate_f0(voice_clip(3, f0=150, pad=0), RATE) == pytest.approx(150, abs=3)
    assert mixer.estimate_f0(np.zeros(RATE * 3, dtype=np.float32), RATE) is None
    assert mixer.semitone_shift(100, 200) == pytest.approx(0, abs=1e-6)  # octaves are equivalent
    assert mixer.semitone_shift(117.9, 138.4) == pytest.approx(2.8, abs=0.1)
    assert -6 <= mixer.semitone_shift(100, 141.4) <= 6


def test_drone_is_shifted_to_the_voice_and_loop_is_seamless():
    script, clips = make_script()
    mix = mixer.build(script, clips, RATE)
    shift = mix.recipe["drone"]["shift_semitones"]
    assert abs(shift) <= 6 and mix.recipe["voice_f0_hz"] == pytest.approx(150, abs=3)

    bed = sounds.synth_tanpura(RATE).samples
    loop = mixer.make_loop(mixer.pitch_shift(bed, 2.0), RATE)
    tiled = mixer.tile_to(loop, len(loop) * 2)
    seam = abs(float(tiled[len(loop)]) - float(tiled[len(loop) - 1]))
    assert seam < 5 * float(np.abs(np.diff(loop)).mean()) + 0.02


def test_smooth_ducks_fast_and_recovers_slowly():
    target = np.concatenate([np.ones(100), np.full(100, 0.1), np.ones(100)])
    out = mixer.smooth(target)
    fall = int(np.argmax(out[100:] < 0.2))
    rise = int(np.argmax(out[200:] > 0.9))
    assert fall < rise  # attack is faster than release
    assert fall / mixer.ENV_RATE < 0.5 and out[199] < 0.2


@needs_ffmpeg
def test_master_hits_loudness_target(tmp_path):
    script, clips = make_script()
    mix = mixer.build(script, clips, RATE)
    result = mixer.master(mix.samples, RATE, tmp_path)
    assert result["output_lufs"] == pytest.approx(mixer.TARGET_LUFS, abs=1.0)
    assert result["output_true_peak"] <= -1.0
    samples, rate = audio.read_wav(tmp_path / "performance.wav")
    assert rate == RATE and len(samples) / RATE == pytest.approx(len(mix.samples) / RATE, abs=0.05)
    assert (tmp_path / "performance.mp3").exists()


def test_synthesised_beds_need_no_files_and_no_credits():
    script, clips = make_script()
    mix = mixer.build(script, clips, RATE)
    assert mix.recipe["drone"]["file"] == "synthesised" and mix.recipe["scene"] is None
    assert mix.credits == []


@needs_ffmpeg
def test_credits_list_only_beds_actually_used(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "sounds_dir", tmp_path)
    t = np.arange(RATE * 4) / RATE
    manifest = {}
    for name, hz, kind, by in [("tan_low.wav", 100.0, "tanpura", True), ("tan_high.wav", 141.4, "tanpura", False),
                               ("ghat.wav", 90.0, "scene", False)]:
        wave = (np.sin(2 * np.pi * hz * t) * 0.3).astype(np.float32)
        audio.write_wav(tmp_path / name, array("h", (wave * 32767).astype(np.int16).tolist()), RATE)
        manifest[name] = {"kind": kind, "sa_hz": hz, "title": name, "author": "someone", "licence": "CC BY 4.0",
                          "source": "http://example", "requires_attribution": by}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    script, clips = make_script()
    mix = mixer.build(script, clips, RATE)
    files = [c["file"] for c in mix.credits]
    # voice is ~150 Hz: tan_low (100) needs a +7 -> -5 semitone shift, tan_high (141.4) only +1
    assert files == ["tan_high.wav", "ghat.wav"] and mix.recipe["scene"] == "ghat.wav"
    assert mix.credits[0]["requires_attribution"] is False


def test_render_exposes_credits_and_loudness(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    pid = client.post("/api/v1/performances", json={"title": "G", "story": "A. B.", "duration_minutes": 2}).json()["id"]
    client.post(f"/api/v1/performances/{pid}/render")
    got = client.get(f"/api/v1/performances/{pid}").json()
    assert got["status"]["stage"] == "done", got["status"]
    assert got["credits"] == []
    mix_stage = json.loads((settings.performances_dir / pid / "stages" / "09_mix.json").read_text())
    assert "loudness" in mix_stage and mix_stage["drone"]["shift_semitones"] is not None


def test_render_without_ffmpeg_still_produces_a_wav(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import render
    from app.main import app

    client = TestClient(app)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(render.shutil, "which", lambda _: None)
    pid = client.post("/api/v1/performances", json={"title": "G", "story": "A. B.", "duration_minutes": 2}).json()["id"]
    client.post(f"/api/v1/performances/{pid}/render")
    status = client.get(f"/api/v1/performances/{pid}/status").json()
    assert status["stage"] == "done" and status["files"] == ["performance.wav"], status
    assert client.get(f"/api/v1/performances/{pid}/audio?fmt=wav").status_code == 200
    assert client.get(f"/api/v1/performances/{pid}/audio?fmt=mp3").status_code == 404
