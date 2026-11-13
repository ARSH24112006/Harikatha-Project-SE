from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import router

app = FastAPI(title="Harikatha")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

@router.get("/")
def healthCheck():
    return "healthy"
