"""File-per-performance storage. See WORKFLOW_AND_STORAGE.md s3-4."""
import hashlib
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .config import settings
from .schemas import GenerateRequest


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dir(pid: str) -> Path:
    return settings.performances_dir / pid


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def read(pid: str, name: str) -> dict | None:
    path = _dir(pid) / name
    return json.loads(path.read_text()) if path.exists() else None


def _app_version() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False, capture_output=True, text=True, cwd=Path(__file__).parent, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _corpus_version() -> str:
    path = settings.data_dir / "songs.json"
    return hashlib.sha1(path.read_bytes()).hexdigest() if path.exists() else "none"


def write_status(
    pid: str, stage: str, detail: str = "", progress: float | None = None, **extra
) -> dict:
    """Overwrites status.json. script_version is carried over from meta.json."""
    meta = read(pid, "meta.json") or {}
    versions = meta.get("script_versions", [])
    status = {
        "stage": stage,
        "detail": detail,
        "progress": progress,
        "script_version": versions[-1]["v"] if versions else None,
        "updated_at": _now(),
        **extra,
    }
    _write_json(_dir(pid) / "status.json", status)
    return status


def create(req: GenerateRequest) -> str:
    pid = uuid.uuid4().hex[:12]
    d = _dir(pid)
    d.mkdir(parents=True)
    (d / "request.json").write_text(req.model_dump_json(indent=2))
    # Snapshot taken now, never re-read from .env later.
    _write_json(d / "meta.json", {
        "id": pid,
        "created_at": _now(),
        "app_version": _app_version(),
        "settings": settings.snapshot(),
        "corpus_version": _corpus_version(),
        "script_versions": [],
        "timings_sec": {},
    })
    write_status(pid, "analysing", progress=0.0)
    return pid


def save_script(pid: str, script: dict, reason: str) -> int:
    """Write an immutable script.vN.json, copy it to script.json, record it in meta."""
    d = _dir(pid)
    meta = read(pid, "meta.json")
    versions = meta["script_versions"]
    v = versions[-1]["v"] + 1 if versions else 1
    _write_json(d / f"script.v{v}.json", script)
    _write_json(d / "script.json", script)
    versions.append({"v": v, "reason": reason, "at": _now()})
    _write_json(d / "meta.json", meta)
    return v


def write_stage(pid: str, name: str, data: dict) -> None:
    path = _dir(pid) / "stages" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, data)


def update_meta(pid: str, **fields) -> None:
    meta = read(pid, "meta.json")
    meta.update(fields)
    _write_json(_dir(pid) / "meta.json", meta)


def list_ids() -> list[str]:
    root = settings.performances_dir
    return sorted(p.name for p in root.iterdir()) if root.exists() else []
