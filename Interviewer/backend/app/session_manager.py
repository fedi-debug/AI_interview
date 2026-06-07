"""In-memory session queues for real-time feature events."""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class InterviewSession:
    session_id: str
    job_title: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    transcript_context: str = ""
    segment_counter: int = 0
    active: bool = True
    consent_given: bool = False
    voice_preset: str = "Jasper"
    language: str = "en"
    question_count: int = 10


_sessions: dict[str, InterviewSession] = {}


def create_interview_session(
    job_title: str,
    consent: bool = False,
    voice_preset: str = "Jasper",
    language: str = "en",
    question_count: int = 10,
) -> InterviewSession:
    sid = str(uuid.uuid4())
    sess = InterviewSession(
        session_id=sid,
        job_title=job_title,
        consent_given=consent,
        voice_preset=voice_preset or "Jasper",
        language=language if language in {"en", "fr"} else "en",
        question_count=max(3, min(question_count, 20)),
    )
    _sessions[sid] = sess
    return sess


def get_interview_session(session_id: str) -> Optional[InterviewSession]:
    return _sessions.get(session_id)


def restore_interview_session(
    session_id: str,
    job_title: str,
    consent: bool = False,
    voice_preset: str = "Jasper",
    language: str = "en",
    question_count: int = 10,
) -> InterviewSession:
    """Re-register a session after server reload (in-memory map cleared)."""
    sess = InterviewSession(
        session_id=session_id,
        job_title=job_title,
        consent_given=consent,
        voice_preset=voice_preset,
        language=language if language in {"en", "fr"} else "en",
        question_count=max(3, min(question_count, 20)),
    )
    _sessions[session_id] = sess
    return sess


def end_interview_session(session_id: str) -> None:
    if session_id in _sessions:
        _sessions[session_id].active = False


async def emit_feature(session_id: str, event: dict[str, Any]) -> None:
    sess = _sessions.get(session_id)
    if sess and sess.active:
        await sess.queue.put(event)


async def stream_features(session_id: str) -> AsyncIterator[dict[str, Any]]:
    sess = _sessions.get(session_id)
    if not sess:
        return
    while sess.active or not sess.queue.empty():
        try:
            event = await asyncio.wait_for(sess.queue.get(), timeout=1.0)
            yield event
        except asyncio.TimeoutError:
            if not sess.active:
                break
