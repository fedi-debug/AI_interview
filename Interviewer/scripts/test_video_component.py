#!/usr/bin/env python
"""Step 5 component test: video worker (mock if MediaPipe unavailable)."""
import os
import sys

import numpy as np
import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.workers.video_worker import VideoWorker

if __name__ == "__main__":
    # Synthetic JPEG (gradient frame)
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:, :, 2] = np.linspace(0, 255, 640, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    jpeg = buf.tobytes() if ok else b""

    worker = VideoWorker()
    events = worker.process_frame("demo-video", jpeg, timestamp_ms=1000)
    print(f"Events: {len(events)}")
    for e in events:
        print(" ", e.get("type"), e.get("gaze_away"), e.get("smile_score", ""))
    print("OK")
