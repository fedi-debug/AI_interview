"""
Scoring fusion: normalize raw signals to 0–100 and combine with configurable weights.

Weights default: content 50%, fluency 20%, prosody 15%, nonverbal 15%.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SegmentAudioFeatures:
    words: int = 0
    duration_sec: float = 1.0
    pause_sec: float = 0.0
    asr_confidence: float = 0.8
    pitch_mean: float = 150.0
    pitch_std: float = 20.0
    energy_mean: float = 0.05
    jitter: float = 0.01
    shimmer: float = 0.02


@dataclass
class SegmentVideoFeatures:
    gaze_retention: float = 0.85
    gaze_away_seconds: float = 0.0
    head_nod_count: int = 0
    smile_score: float = 0.3
    eye_aspect_ratio: float = 0.25


@dataclass
class FusionWeights:
    content: float = 0.50
    fluency: float = 0.20
    prosody: float = 0.15
    nonverbal: float = 0.15


def clamp01(x: float) -> float:
    return max(0.0, min(100.0, x))


def normalize_fluency(segments: list[SegmentAudioFeatures]) -> dict[str, float]:
    if not segments:
        return {"speech_rate": 50, "pause": 50, "asr_confidence": 50}
    total_words = sum(s.words for s in segments)
    total_dur = sum(s.duration_sec for s in segments) or 1.0
    wpm = total_words / total_dur * 60
    # Ideal ~120–160 wpm for interviews
    speech_rate = clamp01(100 - abs(wpm - 140) * 0.8)
    avg_pause = sum(s.pause_sec for s in segments) / len(segments)
    pause_score = clamp01(100 - avg_pause * 40)
    avg_conf = sum(s.asr_confidence for s in segments) / len(segments)
    conf_score = clamp01(avg_conf * 100)
    return {
        "speech_rate": speech_rate,
        "pause": pause_score,
        "asr_confidence": conf_score,
    }


def normalize_prosody(segments: list[SegmentAudioFeatures]) -> dict[str, float]:
    if not segments:
        return {"pitch_stability": 50, "energy": 50, "voice_quality": 50}
    pitch_std = sum(s.pitch_std for s in segments) / len(segments)
    # Lower std = more stable (good), cap normalization
    pitch_stability = clamp01(100 - pitch_std * 1.5)
    energy = sum(s.energy_mean for s in segments) / len(segments)
    energy_score = clamp01(min(energy * 2000, 100))
    jitter = sum(s.jitter for s in segments) / len(segments)
    shimmer = sum(s.shimmer for s in segments) / len(segments)
    voice_quality = clamp01(100 - (jitter * 500 + shimmer * 300))
    return {
        "pitch_stability": pitch_stability,
        "energy": energy_score,
        "voice_quality": voice_quality,
    }


def normalize_nonverbal(segments: list[SegmentVideoFeatures]) -> dict[str, float]:
    if not segments:
        return {"gaze": 50, "engagement": 50, "expression": 50}
    gaze = sum(s.gaze_retention for s in segments) / len(segments)
    gaze_score = clamp01(gaze * 100)
    away = sum(s.gaze_away_seconds for s in segments)
    away_penalty = clamp01(100 - away * 10)
    nods = sum(s.head_nod_count for s in segments)
    engagement = clamp01(50 + nods * 5)
    smile = sum(s.smile_score for s in segments) / len(segments)
    ear = sum(s.eye_aspect_ratio for s in segments) / len(segments)
    expression = clamp01((smile * 50 + min(ear * 200, 50)))
    return {
        "gaze": (gaze_score + away_penalty) / 2,
        "engagement": engagement,
        "expression": expression,
    }


def fuse_scores(
    content_score: float,
    audio_segments: list[SegmentAudioFeatures],
    video_segments: list[SegmentVideoFeatures],
    weights: Optional[FusionWeights] = None,
) -> dict[str, Any]:
    """
    Accept per-segment feature arrays and return final weighted score, breakdown, audit.

    Example input:
        content_score=78
        audio_segments=[SegmentAudioFeatures(words=12, duration_sec=5, ...)]
        video_segments=[SegmentVideoFeatures(gaze_retention=0.9, ...)]
    """
    w = weights or FusionWeights()
    fluency_parts = normalize_fluency(audio_segments)
    fluency = (
        fluency_parts["speech_rate"] * 0.4
        + fluency_parts["pause"] * 0.3
        + fluency_parts["asr_confidence"] * 0.3
    )
    prosody_parts = normalize_prosody(audio_segments)
    prosody = (
        prosody_parts["pitch_stability"] * 0.4
        + prosody_parts["energy"] * 0.3
        + prosody_parts["voice_quality"] * 0.3
    )
    nonverbal_parts = normalize_nonverbal(video_segments)
    nonverbal = (
        nonverbal_parts["gaze"] * 0.5
        + nonverbal_parts["engagement"] * 0.25
        + nonverbal_parts["expression"] * 0.25
    )
    content = clamp01(content_score)
    final = (
        content * w.content
        + fluency * w.fluency
        + prosody * w.prosody
        + nonverbal * w.nonverbal
    )
    return {
        "final_score": round(final, 2),
        "breakdown": {
            "content": round(content, 2),
            "fluency": round(fluency, 2),
            "prosody": round(prosody, 2),
            "nonverbal": round(nonverbal, 2),
        },
        "weights": {
            "content": w.content,
            "fluency": w.fluency,
            "prosody": w.prosody,
            "nonverbal": w.nonverbal,
        },
        "raw_normalized": {
            "fluency": fluency_parts,
            "prosody": prosody_parts,
            "nonverbal": nonverbal_parts,
        },
        "audit": {
            "audio_segment_count": len(audio_segments),
            "video_segment_count": len(video_segments),
            "audio_raw": [s.__dict__ for s in audio_segments],
            "video_raw": [s.__dict__ for s in video_segments],
        },
        "disclaimer": (
            "Automated score is advisory only. Human review required before hiring decisions."
        ),
    }


def fuse_from_dicts(
    content_score: float,
    audio_features: list[dict],
    video_features: list[dict],
    weights: Optional[dict] = None,
) -> dict[str, Any]:
    """Convenience wrapper accepting plain dicts from DB/WebSocket."""
    audio = [SegmentAudioFeatures(**{k: v for k, v in d.items() if hasattr(SegmentAudioFeatures, k)})
             for d in audio_features]
    video = [SegmentVideoFeatures(**{k: v for k, v in d.items() if hasattr(SegmentVideoFeatures, k)})
             for d in video_features]
    w = None
    if weights:
        w = FusionWeights(**weights)
    return fuse_scores(content_score, audio, video, w)
