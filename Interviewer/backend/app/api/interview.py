"""Interview session REST endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.scoring.fusion import SegmentAudioFeatures, SegmentVideoFeatures, fuse_scores
from app.services.llama_client import generate_followup, score_content
from app.session_manager import create_interview_session, end_interview_session, get_interview_session

router = APIRouter(prefix="/interview", tags=["interview"])


class ConsentRequest(BaseModel):
    job_title: str
    candidate_id: str | None = None
    consent: bool = False
    voice_preset: str = "Jasper"  # Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo
    language: str = Field("en", pattern="^(en|fr)$")
    question_count: int = Field(10, ge=3, le=20)


@router.get("/voices")
async def list_interview_voices() -> dict:
    """Available KittenTTS voices."""
    from app.config import get_settings
    from app.services.kittentts_voices import list_voices, normalize_voice_id

    s = get_settings()
    return {"default": normalize_voice_id(s.kittentts_voice), "voices": list_voices()}


class FollowupRequest(BaseModel):
    answer: str
    context: str = ""


class EndSessionRequest(BaseModel):
    content_score: float | None = None
    expected_points: str = ""


@router.post("/start")
async def start_interview(body: ConsentRequest) -> dict[str, Any]:
    if not body.consent:
        raise HTTPException(400, "Consent required before starting interview.")
    from app.services.kittentts_voices import normalize_voice_id

    voice = normalize_voice_id(body.voice_preset)
    sess = create_interview_session(
        body.job_title,
        consent=True,
        voice_preset=voice,
        language=body.language,
        question_count=body.question_count,
    )
    db.save_session(
        sess.session_id, "interview", body.job_title,
        candidate_id=body.candidate_id, consent=True,
        metadata={
            "human_review_required": True,
            "voice_preset": voice,
            "language": body.language,
            "question_count": body.question_count,
        },
    )
    return {
        "session_id": sess.session_id,
        "job_title": body.job_title,
        "voice_preset": voice,
        "language": body.language,
        "question_count": body.question_count,
        "ws_url": f"/ws/interview/{sess.session_id}",
        "message": "Connect WebSocket to stream audio/video.",
    }


@router.post("/{session_id}/followup")
async def followup(session_id: str, body: FollowupRequest) -> dict[str, str]:
    sess = get_interview_session(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    q = generate_followup(
        sess.job_title,
        body.answer,
        body.context or sess.transcript_context,
        language=sess.language,
    )
    return {"session_id": session_id, "followup_question": q}


@router.post("/{session_id}/end")
async def end_interview(
    session_id: str,
    body: EndSessionRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """End session, run scoring fusion, persist report."""
    sess = get_interview_session(session_id)
    job_title = sess.job_title if sess else "default"
    end_interview_session(session_id)

    content = body.content_score
    if content is None and body.expected_points:
        scored = score_content("", body.expected_points)
        content = float(scored.get("content_score", 50))
    content = content or 50.0

    audio_feats, video_feats = _load_session_features(session_id)
    report = fuse_scores(content, audio_feats, video_feats)
    report["session_id"] = session_id
    report["job_title"] = job_title
    if sess:
        report["language"] = sess.language
        report["question_count"] = sess.question_count
    report["human_review_required"] = True
    db.save_report(session_id, report)
    return report


def _load_session_features(session_id: str):
    """Build segment lists from stored feature rows (simplified)."""
    from sqlalchemy import select
    from app.db import FeatureRow, get_db_session

    audio: list[SegmentAudioFeatures] = []
    video: list[SegmentVideoFeatures] = []
    with get_db_session() as db:
        rows = db.execute(
            select(FeatureRow).where(FeatureRow.session_id == session_id)
        ).scalars().all()
    import json
    for row in rows:
        p = json.loads(row.payload_json)
        if row.feature_type == "audio_metrics":
            audio.append(SegmentAudioFeatures(
                words=p.get("words", 0),
                duration_sec=p.get("duration_sec", 1),
                pause_sec=p.get("pause_sec", 0),
                asr_confidence=p.get("asr_confidence", 0.8),
                pitch_mean=p.get("pitch_mean", 150),
                pitch_std=p.get("pitch_std", 20),
                energy_mean=p.get("energy_mean", 0.05),
                jitter=p.get("jitter", 0.01),
                shimmer=p.get("shimmer", 0.02),
            ))
        elif row.feature_type == "video_metrics":
            video.append(SegmentVideoFeatures(
                gaze_retention=p.get("gaze_retention", 0.8),
                gaze_away_seconds=p.get("gaze_away_seconds", 0),
                head_nod_count=p.get("head_nod_count", 0),
                smile_score=p.get("smile_score", 0.3),
                eye_aspect_ratio=p.get("eye_aspect_ratio", 0.25),
            ))
    if not audio:
        audio = [SegmentAudioFeatures()]
    if not video:
        video = [SegmentVideoFeatures()]
    return audio, video
