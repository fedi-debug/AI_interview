#!/usr/bin/env python
"""Step 6 component test: scoring fusion."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.scoring.fusion import SegmentAudioFeatures, SegmentVideoFeatures, fuse_scores

if __name__ == "__main__":
    audio = [
        SegmentAudioFeatures(words=45, duration_sec=30, asr_confidence=0.88, pitch_std=15),
    ]
    video = [
        SegmentVideoFeatures(gaze_retention=0.92, smile_score=0.35, head_nod_count=2),
    ]
    report = fuse_scores(78.0, audio, video)
    print("Final:", report["final_score"])
    print("Breakdown:", report["breakdown"])
    print("Disclaimer:", report["disclaimer"][:60], "...")
    print("OK")
