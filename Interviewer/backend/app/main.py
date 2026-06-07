"""
HireNest FastAPI application.

Run locally:
  cd hirenest
  .\.venv\Scripts\Activate.ps1
  $env:PYTHONPATH="d:\interview\hirenest\backend"
  $env:MOCK_LLM="true"
  $env:MOCK_ASR="true"
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import interview, mcq, websocket_handler
from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="HireNest",
    description="Local offline AI interview system — MCQ + live AV interview",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mcq.router)
app.include_router(interview.router)
app.include_router(websocket_handler.router)


@app.get("/health")
async def health():
    from app.services.tts import resolve_tts_engine
    from app.workers.whisper_client import resolve_asr_engine

    return {
        "status": "ok",
        "mock_llm": settings.mock_llm,
        "mock_asr": settings.mock_asr,
        "asr_engine": resolve_asr_engine(),
        "tts_engine": resolve_tts_engine(),
        "kittentts_model": settings.kittentts_model,
        "kittentts_voice": settings.kittentts_voice,
        "kittentts_cache_dir": settings.kittentts_cache_dir,
    }


@app.get("/")
async def root():
    return {
        "name": "HireNest",
        "docs": "/docs",
        "ethics": "Automated scores are advisory only. Human review required.",
    }
