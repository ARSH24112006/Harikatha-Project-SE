from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    title: str
    story: str
    language: str = "en-IN"
    duration_minutes: int = Field(default=8, ge=1, le=60)
    audience: str = "general"


class Status(BaseModel):
    stage: Literal[
        "analysing", "planning", "writing", "scripted", "queued",
        "synthesizing", "rewriting", "modulating", "mixing", "done", "error",
    ]
    detail: str = ""
    updated_at: str
