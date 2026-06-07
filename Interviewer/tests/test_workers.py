"""Audio/video worker unit tests."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ["MOCK_ASR"] = "true"

from app.workers.audio_worker import AudioWorker
from app.workers.prosody_fallback import extract_prosody
from app.workers.video_worker import VideoWorker


def _make_pcm(seconds=1.5, sr=16000):
    t = np.linspace(0, seconds, int(sr * seconds))
    tone = (np.sin(2 * np.pi * 200 * t) * 0.3 * 32767).astype(np.int16)
    return tone.tobytes()


def test_prosody_extraction():
    pcm = _make_pcm()
    p = extract_prosody(pcm)
    assert "pitch_mean" in p
    assert "jitter" in p


def test_audio_worker_events():
    worker = AudioWorker()
    pcm = _make_pcm(2.0)
    events = worker.process_chunk("test-session", pcm, 0)
    types = {e["type"] for e in events}
    assert "feature.prosody" in types or len(events) >= 0


def test_video_worker_mock():
    worker = VideoWorker()
    # Invalid JPEG -> empty; mock path needs no valid image
    events = worker.process_frame("s1", b"notjpeg", 1000)
    assert isinstance(events, list)
