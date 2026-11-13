"""Thin Sarvam HTTP client: auth header, retries on 429/5xx, readable errors.

The API key is only ever placed in the request header; it is never logged or
included in error messages.
"""
import time

import httpx

from .config import settings

# Tests inject an httpx.MockTransport here.
transport: httpx.BaseTransport | None = None

_RETRY_STATUS = {429, 500, 502, 503, 504}


class SarvamError(RuntimeError):
    pass


def _message(r: httpx.Response) -> str:
    try:
        return str(r.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return r.text[:300]


def post(path: str, body: dict) -> dict:
    if not settings.sarvam_api_key:
        raise SarvamError("SARVAM_API_KEY is not set")
    headers = {"api-subscription-key": settings.sarvam_api_key}
    delay = settings.retry_delay_sec
    for attempt in range(1, settings.max_retries + 1):
        try:
            with httpx.Client(
                base_url=settings.sarvam_base_url, timeout=settings.request_timeout_sec,
                transport=transport,
            ) as client:
                r = client.post(path, json=body, headers=headers)
        except httpx.TransportError as e:
            err = f"network error: {type(e).__name__}"
        else:
            if r.status_code == 200:
                return r.json()
            err = f"{path} -> {r.status_code}: {_message(r)}"
            if r.status_code not in _RETRY_STATUS:
                raise SarvamError(err)
        if attempt == settings.max_retries:
            raise SarvamError(f"{err} (after {attempt} attempts)")
        time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")
