"""Render job, stages 6-9 of WORKFLOW_AND_STORAGE.md s2.2.

Modulation and mixing are placeholders (gain only; clips concatenated with short gaps).
Pitch snapping, drone, scenes and ducking come later.
"""
import shutil
import subprocess
import time
from array import array

from . import audio, store, tts
from .config import settings

MAX_FIT_ROUNDS = 2
GAP_SEC = 0.35


def _synth_all(pid: str, script: dict) -> tuple[dict[str, array], int]:
    clips, hits = {}, 0
    for seg in script["segments"]:
        clips[seg["id"]], hit = tts.synthesize(
            seg["text"], script["language"], seg["delivery"]["pace"]
        )
        hits += hit
    return clips, hits


def _overruns(script: dict, clips: dict[str, array]) -> list[dict]:
    rate = settings.tts_sample_rate
    return [
        {"id": s["id"], "budget_sec": s["target_sec"], "actual_sec": audio.duration(clips[s["id"]], rate),
         "overrun": audio.duration(clips[s["id"]], rate) / s["target_sec"] - 1}
        for s in script["segments"]
    ]


def _shorten(seg: dict, row: dict) -> None:
    """Placeholder for the LLM rewrite: trim text in proportion to the overrun."""
    keep = max(10, int(len(seg["text"]) * row["budget_sec"] / row["actual_sec"]))
    seg["text"] = seg["text"][:keep].rstrip()


def run_render_job(pid: str) -> None:
    timings: dict[str, float] = {}
    t0 = time.monotonic()

    def lap(name: str) -> None:
        nonlocal t0
        timings[name] = round(timings.get(name, 0) + time.monotonic() - t0, 2)
        t0 = time.monotonic()

    try:
        d = settings.performances_dir / pid
        script = store.read(pid, "script.json")
        rate = settings.tts_sample_rate
        cache_hits = 0

        store.write_status(pid, "synthesizing", progress=0.1)
        clips, hits = _synth_all(pid, script)
        cache_hits += hits
        lap("tts")

        for rnd in range(1, MAX_FIT_ROUNDS + 1):
            rows = _overruns(script, clips)
            late = [r for r in rows if r["overrun"] > settings.overrun_threshold]
            if not late:
                break
            store.write_status(pid, "rewriting", f"round {rnd}: {len(late)} segments", progress=0.35)
            by_id = {s["id"]: s for s in script["segments"]}
            for r in late:
                _shorten(by_id[r["id"]], r)
            v = store.save_script(
                pid, script, f"fit round {rnd}: shortened {', '.join(r['id'] for r in late)}"
            )
            store.write_stage(pid, f"07_fit_round{rnd}.json", {
                "script_version": v, "segments": rows, "shortened": [r["id"] for r in late],
            })
            clips, hits = _synth_all(pid, script)
            cache_hits += hits
            lap("fit")

        store.write_status(pid, "modulating", progress=0.6)
        report, voiced = [], {}
        for seg in script["segments"]:
            gain = seg["delivery"]["gain_db"]
            voiced[seg["id"]] = audio.apply_gain(clips[seg["id"]], gain)
            audio.write_wav(d / "clips" / f"{seg['id']}.wav", voiced[seg["id"]], rate)
            report.append({"id": seg["id"], "gain_db": gain, "peak": round(audio.peak(voiced[seg["id"]]), 3),
                           "raga": None, "unsnapped_fraction": None})
        store.write_stage(pid, "08_modulation.json", {"note": "placeholder: gain only", "segments": report})
        lap("modulate")

        store.write_status(pid, "mixing", progress=0.8)
        mix, timeline, cursor = array("h"), [], 0.0
        gap = array("h", [0] * round(GAP_SEC * rate))
        rows = {r["id"]: r for r in _overruns(script, clips)}
        for seg in script["segments"]:
            samples = voiced[seg["id"]]
            end = cursor + audio.duration(samples, rate)
            timeline.append({
                "id": seg["id"], "section": seg["section"], "type": seg["type"],
                "start": round(cursor, 3), "end": round(end, 3), "audio": f"clips/{seg['id']}.wav",
                "budget_sec": seg["target_sec"], "overrun": round(rows[seg["id"]]["overrun"], 3),
            })
            mix.extend(samples)
            mix.extend(gap)
            cursor = end + GAP_SEC
        audio.write_wav(d / "performance.wav", mix, rate)
        files = ["performance.wav"]
        if shutil.which("ffmpeg"):
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(d / "performance.wav"),
                 "-b:a", "192k", str(d / "performance.mp3")],
                check=True,
            )
            files.append("performance.mp3")
        store.write_stage(pid, "09_mix.json", {
            "note": "placeholder: concatenation only", "gap_sec": GAP_SEC,
            "peak": round(audio.peak(mix), 3), "mp3": "performance.mp3" in files,
        })
        lap("mix")

        version = store.read(pid, "meta.json")["script_versions"][-1]["v"]
        store.write_json(pid, "timeline.json", {
            "performance_id": pid, "sample_rate": rate, "voice_sa_hz": None,
            "target_sec": script["target_sec"], "total_sec": round(audio.duration(mix, rate), 3),
            "script_version": version, "segments": timeline,
        })
        meta = store.read(pid, "meta.json")
        store.update_meta(
            pid, timings_sec={**meta["timings_sec"], **timings},
            tts_chars=sum(len(s["text"]) for s in script["segments"]), tts_cache_hits=cache_hits,
        )
        store.write_status(pid, "done", progress=1.0, files=files, total_sec=round(audio.duration(mix, rate), 3))
    except Exception as e:  # noqa: BLE001 - surfaced to the UI via status.json
        store.write_status(pid, "error", f"{type(e).__name__}: {e}")
