"""Scoring fusion unit tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.scoring.fusion import (
    SegmentAudioFeatures,
    SegmentVideoFeatures,
    FusionWeights,
    fuse_scores,
    fuse_from_dicts,
)


def test_fuse_scores_balanced():
    audio = [SegmentAudioFeatures(words=30, duration_sec=15, asr_confidence=0.9)]
    video = [SegmentVideoFeatures(gaze_retention=0.9, smile_score=0.4)]
    result = fuse_scores(80.0, audio, video)
    assert 0 <= result["final_score"] <= 100
    assert "breakdown" in result
    assert result["breakdown"]["content"] == 80.0


def test_fuse_from_dicts():
    result = fuse_from_dicts(
        75,
        [{"words": 20, "duration_sec": 10, "asr_confidence": 0.85}],
        [{"gaze_retention": 0.8, "smile_score": 0.3}],
    )
    assert "final_score" in result
    assert "disclaimer" in result


def test_custom_weights():
    w = FusionWeights(content=0.6, fluency=0.1, prosody=0.15, nonverbal=0.15)
    r = fuse_scores(100, [], [], w)
    assert r["final_score"] >= 50
