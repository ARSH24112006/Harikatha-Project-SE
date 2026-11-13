"""LLM wrapper: validates output against a pydantic model, retries once with the
validation error as feedback, and logs every attempt.

MOCK_SARVAM=true uses the caller's mock_fn instead of the network.
"""
import hashlib
import json
import threading
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from . import sarvam
from .config import settings

MAX_ATTEMPTS = 2
_log_lock = threading.Lock()
_calls: Counter[str] = Counter()


class LLMError(RuntimeError):
    """The model answered, but never with output that passed validation."""


def calls_for(pid: str) -> int:
    return _calls[pid]


def _log(entry: dict) -> None:
    d = settings.data_dir / "runtime" / "llm_log"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{datetime.now(UTC).date()}.jsonl"
    with _log_lock, path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def _chat(messages: list[dict], reasoning_effort: str) -> tuple[str, dict]:
    data = sarvam.post("/v1/chat/completions", {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        # The API accepts only low/medium/high (despite its docs); null disables reasoning.
        "reasoning_effort": None if reasoning_effort == "none" else reasoning_effort,
        "response_format": {"type": "json_object"},
    })
    choice = data["choices"][0]
    content = choice["message"].get("content") or ""
    if not content and choice.get("finish_reason") == "length":
        raise LLMError("response truncated by max_tokens (reasoning used the whole budget)")
    return content, data.get("usage") or {}


def complete_json[T: BaseModel](
    *, pid: str, stage: str, prompt: str, model: type[T], mock_fn: Callable[[], T],
    system: str = "", check: Callable[[T], None] | None = None, reasoning_effort: str | None = None,
) -> T:
    """check() may raise ValueError to reject semantically bad output (triggers the retry)."""
    mock = settings.mock_sarvam
    schema = json.dumps(model.model_json_schema())
    messages = [
        {"role": "system", "content": f"{system}\n\nRespond with ONE JSON object and nothing else, "
                                      f"matching this JSON Schema:\n{schema}".strip()},
        {"role": "user", "content": prompt},
    ]
    _calls[pid] += 1
    last_error = ""
    for attempt in range(MAX_ATTEMPTS):
        start = time.monotonic()
        ok, response, usage = False, "", {}
        try:
            if mock:
                result = model.model_validate(mock_fn())
                response = result.model_dump(mode="json")
            else:
                response, usage = _chat(messages, reasoning_effort or settings.reasoning_effort)
                result = model.model_validate(_extract_json(response))
            if check:
                check(result)
            ok = True
            return result
        except (ValueError, ValidationError) as e:  # JSONDecodeError and pydantic errors are ValueErrors
            last_error = str(e)[:500]
            if mock:
                raise
            messages += [
                {"role": "assistant", "content": response},
                {"role": "user", "content": f"That was invalid: {last_error}\nReturn corrected JSON only."},
            ]
        finally:
            _log({
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "performance_id": pid,
                "stage": stage,
                "model": "mock" if mock else settings.llm_model,
                "temperature": settings.llm_temperature,
                "prompt_sha1": hashlib.sha1(prompt.encode()).hexdigest(),
                "prompt": prompt[:4000],
                "response": response,
                "tokens": usage,
                "latency_ms": round((time.monotonic() - start) * 1000),
                "validation_ok": ok,
                "retry": attempt,
            })
    raise LLMError(f"{stage}: invalid output after {MAX_ATTEMPTS} attempts: {last_error}")
