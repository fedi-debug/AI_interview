"""
WebSocket message schemas (control/metadata only — no binary in JSON).

Binary audio/video sent as separate WebSocket binary frames with preceding JSON metadata.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --- Client → Server ---

class WsControlStart(BaseModel):
    type: Literal["control.start"] = "control.start"
    session_id: str
    job_title: str
    consent: bool = False
    transport: Literal["websocket"] = "websocket"


class WsControlEnd(BaseModel):
    type: Literal["control.end"] = "control.end"
    session_id: str


class AudioChunkMeta(BaseModel):
    """
    Sent as JSON text frame immediately before binary PCM frame.
    Example: {"type":"audio.chunk","session_id":"...","seq":1,"sample_rate":16000,"channels":1,"duration_ms":1500}
    """
    type: Literal["audio.chunk"] = "audio.chunk"
    session_id: str
    seq: int
    sample_rate: int = 16000
    channels: int = 1
    duration_ms: int = 1500
    timestamp_ms: int = 0


class VideoFrameMeta(BaseModel):
    """
    Sent as JSON before JPEG binary frame.
    Example: {"type":"video.frame","session_id":"...","seq":3,"width":640,"height":480,"format":"jpeg"}
    """
    type: Literal["video.frame"] = "video.frame"
    session_id: str
    seq: int
    width: int = 640
    height: int = 480
    format: Literal["jpeg", "png"] = "jpeg"
    timestamp_ms: int = 0


# --- Server → Client ---

class TranscriptEvent(BaseModel):
    type: Literal["feature.transcript"] = "feature.transcript"
    session_id: str
    segment_index: int
    text: str
    start_ms: int
    end_ms: int
    confidence: float


class ProsodyEvent(BaseModel):
    type: Literal["feature.prosody"] = "feature.prosody"
    session_id: str
    timestamp_ms: int
    pitch_mean: float
    pitch_std: float
    energy_mean: float
    jitter: float
    shimmer: float


class GazeEvent(BaseModel):
    type: Literal["feature.gaze"] = "feature.gaze"
    session_id: str
    timestamp_ms: int
    gaze_away: bool
    gaze_away_seconds: float
    eye_aspect_ratio: float
    head_pose: dict[str, float] = Field(default_factory=dict)


class FaceEvent(BaseModel):
    type: Literal["feature.face"] = "feature.face"
    session_id: str
    timestamp_ms: int
    smile_score: float
    head_nod: bool
    facial_aus: dict[str, float] = Field(default_factory=dict)


class FollowupEvent(BaseModel):
    type: Literal["interview.followup"] = "interview.followup"
    session_id: str
    question: str


class FinalReportSchema(BaseModel):
    type: Literal["report.final"] = "report.final"
    session_id: str
    final_score: float
    breakdown: dict[str, float]
    weights: dict[str, float]
    transcripts: list[dict[str, Any]]
    human_review_required: bool = True
    disclaimer: str
