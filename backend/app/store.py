import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .config import settings
from .schemas import GenerateRequest


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dir(pid: str) -> Path:
    return settings.performances_dir / pid


def write_status(pid: str, stage: str, detail: str = "") -> dict:
    status = {"stage": stage, "detail": detail, "updated_at": _now()}
    (_dir(pid) / "status.json").write_text(json.dumps(status, indent=2))
    return status


def create(req: GenerateRequest) -> str:
    pid = uuid.uuid4().hex[:12]
    _dir(pid).mkdir(parents=True)
    (_dir(pid) / "request.json").write_text(req.model_dump_json(indent=2))
    write_status(pid, "analysing")
    return pid


def read(pid: str, name: str) -> dict | None:
    path = _dir(pid) / name
    return json.loads(path.read_text()) if path.exists() else None


def list_ids() -> list[str]:
    root = settings.performances_dir
    return sorted(p.name for p in root.iterdir()) if root.exists() else []
