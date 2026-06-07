"""MCQ REST endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.services import mcq_service

router = APIRouter(prefix="/mcq", tags=["mcq"])


class McqGenerateRequest(BaseModel):
    job_title: str = Field(..., examples=["Software Engineer"])
    session_id: str | None = None
    candidate_id: str | None = None


class McqAnswerItem(BaseModel):
    question_id: int
    selected: str = Field(..., min_length=1, max_length=1)


class McqSubmitRequest(BaseModel):
    answers: list[McqAnswerItem]


@router.post("/generate")
async def generate_mcq(body: McqGenerateRequest) -> dict[str, Any]:
    """
    Generate 20 role-specific MCQs via llama.cpp.

    Example:
        POST {"job_title": "Software Engineer"}
        -> {"session_id": "...", "questions": [20 items]}
    """
    result = mcq_service.generate_and_store(body.job_title, body.session_id)
    return result


@router.get("/{session_id}")
async def get_mcq(session_id: str) -> dict[str, Any]:
    data = db.get_mcq(session_id)
    if not data:
        raise HTTPException(404, "Session not found")
    return {"session_id": session_id, **data}


@router.post("/{session_id}/submit")
async def submit_mcq(session_id: str, body: McqSubmitRequest) -> dict[str, Any]:
    """
    Grade answers and map skills.

    Example:
        POST answers: [{"question_id": 1, "selected": "B"}, ...]
    """
    try:
        return mcq_service.grade_submission(
            session_id, [a.model_dump() for a in body.answers]
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
