"""WebSocket interview stream with turn-based Q&A orchestrator."""

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import db
from app.session_manager import emit_feature, get_interview_session
from app.services.interview_orchestrator import (
    clear_orchestrator,
    on_audio_chunk,
    on_listen_start,
    force_finalize,
    start_interview_turns,
)
from app.workers.pool import run_in_worker
from app.workers.video_worker import VideoWorker

router = APIRouter()


def _recover_session(session_id: str):
    from app.session_manager import restore_interview_session
    from app.db import SessionRow, get_db_session

    with get_db_session() as db:
        row = db.get(SessionRow, session_id)
        if not row or row.session_type != "interview":
            return None
        import json
        meta = json.loads(row.metadata_json or "{}")
        return restore_interview_session(
            session_id,
            row.job_title or "Software Engineer",
            consent=bool(row.consent_given),
            voice_preset=meta.get("voice_preset", "Jasper"),
        )


_video_workers: dict[str, VideoWorker] = {}


@router.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    sess = get_interview_session(session_id) or _recover_session(session_id)
    if not sess:
        await websocket.send_json({
            "type": "error",
            "message": "Unknown session. Click Start interview again.",
        })
        await websocket.close()
        return

    job_title = sess.job_title
    video_w = VideoWorker()
    _video_workers[session_id] = video_w
    pending_meta: dict[str, Any] | None = None

    async def send_event(ev: dict) -> None:
        await websocket.send_json(ev)

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break

            if "text" in msg:
                data = json.loads(msg["text"])
                mtype = data.get("type")

                if mtype == "control.end":
                    break
                if mtype == "control.start":
                    await websocket.send_json({
                        "type": "control.ack",
                        "session_id": session_id,
                    })
                    await start_interview_turns(session_id, job_title, send_event)
                elif mtype == "control.listen":
                    await on_listen_start(session_id, send_event)
                elif mtype == "control.answer_done":
                    await force_finalize(session_id, job_title, send_event)
                elif mtype in ("audio.chunk", "video.frame"):
                    pending_meta = data
                continue

            if "bytes" in msg and pending_meta:
                meta = pending_meta
                pending_meta = None
                if meta.get("type") == "audio.chunk":
                    await on_audio_chunk(
                        session_id,
                        msg["bytes"],
                        job_title,
                        send_event,
                    )
                elif meta.get("type") == "video.frame":
                    events = await run_in_worker(
                        video_w.process_frame,
                        session_id,
                        msg["bytes"],
                        meta.get("timestamp_ms", 0),
                    )
                    for ev in events:
                        await _dispatch_video(websocket, session_id, ev, sess)
    except WebSocketDisconnect:
        pass
    finally:
        _video_workers.pop(session_id, None)
        clear_orchestrator(session_id)


async def _dispatch_video(websocket: WebSocket, session_id: str, ev: dict, sess):
    await websocket.send_json(ev)
    await emit_feature(session_id, ev)
    ft = ev.get("type", "")
    if ft in ("feature.audio_metrics", "feature.video_metrics"):
        db.append_feature(session_id, ev.get("timestamp_ms", 0), ft, ev)
    elif ft.startswith("feature."):
        db.append_feature(session_id, ev.get("timestamp_ms", 0), ft, ev)
