"""LLM wrapper: validates output against a pydantic model and logs every call.

Real Sarvam calls are not wired yet; with MOCK_SARVAM=true the caller's mock_fn
supplies the response.
"""
import hashlib
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel

from .config import settings

_log_lock = threading.Lock()


def _log(entry: dict) -> None:
    d = settings.data_dir / "runtime" / "llm_log"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{datetime.now(UTC).date()}.jsonl"
    with _log_lock, path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def complete_json[T: BaseModel](
    *, pid: str, stage: str, prompt: str, model: type[T], mock_fn: Callable[[], T]
) -> T:
    start = time.monotonic()
    ok = False
    response: dict | str = ""
    try:
        if not settings.mock_sarvam:
            raise NotImplementedError("Sarvam client not wired yet (needs SARVAM_API_KEY)")
        result = model.model_validate(mock_fn())
        response, ok = result.model_dump(mode="json"), True
        return result
    except Exception as e:
        response = f"{type(e).__name__}: {e}"
        raise
    finally:
        _log({
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "performance_id": pid,
            "stage": stage,
            "model": "mock" if settings.mock_sarvam else settings.llm_model,
            "temperature": 0.3,
            "prompt_sha1": hashlib.sha1(prompt.encode()).hexdigest(),
            "prompt": prompt[:4000],
            "response": response,
            "latency_ms": round((time.monotonic() - start) * 1000),
            "validation_ok": ok,
            "retry": 0,
        })
