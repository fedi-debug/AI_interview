#!/usr/bin/env python
"""Step 4 component test: audio worker."""
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ["MOCK_ASR"] = "true"

from app.workers.audio_worker import AudioWorker

if __name__ == "__main__":
    sr = 16000
    t = np.linspace(0, 2.0, int(sr * 2))
    pcm = (np.sin(2 * np.pi * 180 * t) * 0.4 * 32767).astype(np.int16).tobytes()
    worker = AudioWorker()
    events = worker.process_chunk("demo-audio", pcm, timestamp_ms=0)
    print(f"Events: {len(events)}")
    for e in events:
        print(" ", e["type"], e.get("text", "")[:40] if "text" in e else e.get("pitch_mean"))
    print("OK")
