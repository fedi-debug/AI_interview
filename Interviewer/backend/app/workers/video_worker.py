"""
Video worker: MediaPipe Face Mesh @ 5–10 FPS — gaze, head pose, EAR, smile proxy.
"""

import time
from typing import Any, Callable, Optional

import cv2
import numpy as np

try:
    import mediapipe as mp
    HAS_MP = hasattr(mp, "solutions")
except ImportError:
    HAS_MP = False
    mp = None  # type: ignore

# Gaze-away threshold: seconds eyes off-center
GAZE_AWAY_THRESHOLD_SEC = 0.5


class VideoWorker:
    def __init__(self, on_event: Optional[Callable[[dict], None]] = None):
        self.on_event = on_event
        self._gaze_away_start: Optional[float] = None
        self._gaze_away_total = 0.0
        self._gaze_away_events: list[dict] = []
        self._prev_pitch: Optional[float] = None
        self._nod_count = 0
        self._face_mesh = None
        if HAS_MP and mp is not None:
            try:
                self._mp_face = mp.solutions.face_mesh
                self._face_mesh = self._mp_face.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except (AttributeError, Exception):
                self._face_mesh = None

    def process_frame(
        self,
        session_id: str,
        jpeg_bytes: bytes,
        timestamp_ms: int = 0,
    ) -> list[dict]:
        """
        Process one JPEG frame.

        Example:
            with open("frame.jpg","rb") as f:
                events = VideoWorker().process_frame("s1", f.read(), 1000)
        """
        events: list[dict] = []
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return events

        if not self._face_mesh:
            return self._mock_face_events(session_id, timestamp_ms)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            self._track_gaze_away(session_id, timestamp_ms, True)
            return events

        lm = results.multi_face_landmarks[0].landmark
        ear = _eye_aspect_ratio(lm, w, h)
        smile = _smile_score(lm)
        head_pose = _estimate_head_pose(lm, w, h)
        gaze_off = _is_gaze_off_center(lm)

        self._track_gaze_away(session_id, timestamp_ms, gaze_off)
        nod = False
        pitch = head_pose.get("pitch", 0)
        if self._prev_pitch is not None and pitch - self._prev_pitch > 8:
            nod = True
            self._nod_count += 1
        self._prev_pitch = pitch

        gaze_retention = 1.0 - min(self._gaze_away_total / max(timestamp_ms / 1000, 1), 1.0)

        gev = {
            "type": "feature.gaze",
            "session_id": session_id,
            "timestamp_ms": timestamp_ms,
            "gaze_away": gaze_off,
            "gaze_away_seconds": self._gaze_away_total,
            "eye_aspect_ratio": ear,
            "head_pose": head_pose,
        }
        events.append(gev)
        fev = {
            "type": "feature.face",
            "session_id": session_id,
            "timestamp_ms": timestamp_ms,
            "smile_score": smile,
            "head_nod": nod,
            "facial_aus": {"AU12": smile},  # smile proxy
        }
        events.append(fev)
        mev = {
            "type": "feature.video_metrics",
            "session_id": session_id,
            "timestamp_ms": timestamp_ms,
            "gaze_retention": gaze_retention,
            "gaze_away_seconds": self._gaze_away_total,
            "head_nod_count": self._nod_count,
            "smile_score": smile,
            "eye_aspect_ratio": ear,
        }
        events.extend([gev, fev, mev])
        for e in [gev, fev, mev]:
            if self.on_event:
                self.on_event(e)
        return events

    def _track_gaze_away(self, session_id: str, ts_ms: int, away: bool):
        now = ts_ms / 1000.0
        if away:
            if self._gaze_away_start is None:
                self._gaze_away_start = now
        else:
            if self._gaze_away_start is not None:
                dur = now - self._gaze_away_start
                if dur >= GAZE_AWAY_THRESHOLD_SEC:
                    self._gaze_away_total += dur
                    self._gaze_away_events.append({
                        "start_ms": int(self._gaze_away_start * 1000),
                        "duration_ms": int(dur * 1000),
                    })
                self._gaze_away_start = None

    def _mock_face_events(self, session_id: str, timestamp_ms: int) -> list[dict]:
        return [{
            "type": "feature.gaze",
            "session_id": session_id,
            "timestamp_ms": timestamp_ms,
            "gaze_away": False,
            "gaze_away_seconds": 0.0,
            "eye_aspect_ratio": 0.28,
            "head_pose": {"yaw": 0, "pitch": 0, "roll": 0},
        }]


def _eye_aspect_ratio(lm, w: int, h: int) -> float:
    # Standard EAR using MediaPipe indices (left eye)
    idx = [33, 160, 158, 133, 153, 144]
    pts = [(lm[i].x * w, lm[i].y * h) for i in idx]
    def dist(a, b):
        return np.hypot(a[0] - b[0], a[1] - b[1])
    vertical = (dist(pts[1], pts[5]) + dist(pts[2], pts[4])) / 2
    horizontal = dist(pts[0], pts[3]) + 1e-6
    return float(vertical / horizontal)


def _smile_score(lm) -> float:
    # Mouth corner lift proxy
    left, right = lm[61], lm[291]
    upper = lm[13]
    return float(max(0, min(1, (left.y + right.y) / 2 - upper.y)))


def _estimate_head_pose(lm, w: int, h: int) -> dict:
    nose = lm[1]
    chin = lm[152]
    return {
        "yaw": float((lm[234].x - lm[454].x) * 90),
        "pitch": float((chin.y - nose.y) * 100),
        "roll": float((lm[33].y - lm[263].y) * 100),
    }


def _is_gaze_off_center(lm) -> bool:
    # Iris vs eye center — simplified with iris landmarks when refine_landmarks=True
    left_iris = lm[468]
    right_iris = lm[473]
    off = abs(left_iris.x - 0.38) > 0.08 or abs(right_iris.x - 0.62) > 0.08
    return off
