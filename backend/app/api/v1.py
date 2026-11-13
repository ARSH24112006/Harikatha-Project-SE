from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import planner, store
from ..config import settings
from ..schemas import GenerateRequest

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health():
    return {"ok": True, "mock": settings.mock_sarvam}


@router.post("/performances", status_code=201)
def create_performance(req: GenerateRequest, background: BackgroundTasks):
    pid = store.create(req)
    background.add_task(planner.run_script_job, pid)
    return {"id": pid, "status": store.read(pid, "status.json")}


@router.get("/performances")
def list_performances():
    return [{"id": pid, "request": store.read(pid, "request.json")} for pid in store.list_ids()]


def _get_or_404(pid: str) -> dict:
    request = store.read(pid, "request.json")
    if request is None:
        raise HTTPException(404, "performance not found")
    return request


@router.get("/performances/{pid}")
def get_performance(pid: str):
    return {
        "id": pid,
        "request": _get_or_404(pid),
        "script": store.read(pid, "script.json"),
        "timeline": store.read(pid, "timeline.json"),
        "status": store.read(pid, "status.json"),
    }


@router.get("/performances/{pid}/status")
def get_status(pid: str):
    _get_or_404(pid)
    return store.read(pid, "status.json")


@router.post("/performances/{pid}/render", status_code=202)
def render(pid: str):
    _get_or_404(pid)
    # TODO: run stages 6-9 as a background job
    return store.write_status(pid, "queued")
