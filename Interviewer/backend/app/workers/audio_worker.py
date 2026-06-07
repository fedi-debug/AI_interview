"""
Audio processing worker: webrtcvad → whisper.cpp → openSMILE/fallback → feature events.
"""

import struct
from typing import Any, Callable, Optional

try:
    import webrtcvad
    HAS_WEBRTCVAD = True
except ImportError:
    HAS_WEBRTCVAD = False

from app.config import get_settings
from app.workers.prosody_fallback import extract_opensmile, extract_prosody
from app.workers.whisper_client import transcribe_pcm

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_BYTES = int(SAMPLE_RATE * FRAME_MS / 1000) * 2


class AudioWorker:
    """Processes PCM chunks; invokes callback with feature event dicts."""

    def __init__(self, on_event: Optional[Callable[[dict], None]] = None):
        self.vad = webrtcvad.Vad(2) if HAS_WEBRTCVAD else None
        self.on_event = on_event
        self._speech_buffer = bytearray()
        self._segment_index = 0
        self._last_end_ms = 0

    def process_chunk(
        self,
        session_id: str,
        pcm_int16: bytes,
        timestamp_ms: int = 0,
    ) -> list[dict]:
        """
        Process one audio chunk (e.g. 1.5s @ 16kHz).

        Example:
            worker = AudioWorker()
            events = worker.process_chunk("sess-1", pcm_bytes, 0)
            # events may include feature.transcript, feature.prosody
        """
        events: list[dict] = []
        frames = self._split_frames(pcm_int16)
        speech_ratio = sum(1 for f in frames if self._is_speech(f)) / max(len(frames), 1)
        settings = get_settings()

        # In mock/dev mode or quiet mics, still process so the UI shows transcripts
        if speech_ratio < 0.15 and not settings.mock_asr:
            return events

        self._speech_buffer.extend(pcm_int16)
        if len(self._speech_buffer) < SAMPLE_RATE * 2:  # min ~0.5s for ASR
            return events

        segment_pcm = bytes(self._speech_buffer)
        self._speech_buffer.clear()

        asr = transcribe_pcm(segment_pcm, SAMPLE_RATE)
        text = asr.get("text", "").strip()
        conf = float(asr.get("confidence", 0.0))
        start_ms = self._last_end_ms
        duration_ms = len(segment_pcm) // 2 * 1000 // SAMPLE_RATE
        end_ms = start_ms + duration_ms
        self._last_end_ms = end_ms

        if text:
            self._segment_index += 1
            ev = {
                "type": "feature.transcript",
                "session_id": session_id,
                "segment_index": self._segment_index,
                "text": text,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "confidence": conf,
            }
            events.append(ev)
            if self.on_event:
                self.on_event(ev)

        settings = get_settings()
        prosody = None
        if settings.opensmile_bin:
            prosody = extract_opensmile(segment_pcm, SAMPLE_RATE, settings.opensmile_bin)
        if prosody is None:
            prosody = extract_prosody(segment_pcm, SAMPLE_RATE)

        pev = {
            "type": "feature.prosody",
            "session_id": session_id,
            "timestamp_ms": timestamp_ms or end_ms,
            **prosody,
        }
        events.append(pev)
        if self.on_event:
            self.on_event(pev)

        # Fluency helper fields for fusion
        words = len(text.split()) if text else 0
        events.append({
            "type": "feature.audio_metrics",
            "session_id": session_id,
            "timestamp_ms": end_ms,
            "words": words,
            "duration_sec": duration_ms / 1000.0,
            "pause_sec": 0.2 if speech_ratio < 0.5 else 0.05,
            "asr_confidence": conf,
            **prosody,
        })
        return events

    def _split_frames(self, pcm: bytes) -> list[bytes]:
        frames = []
        for i in range(0, len(pcm) - FRAME_BYTES + 1, FRAME_BYTES):
            frames.append(pcm[i : i + FRAME_BYTES])
        return frames

    def _is_speech(self, frame: bytes) -> bool:
        if len(frame) != FRAME_BYTES:
            return False
        if self.vad is not None:
            try:
                return self.vad.is_speech(frame, SAMPLE_RATE)
            except Exception:
                pass
        # Energy-based fallback when webrtcvad unavailable (common on Windows without MSVC)
        import numpy as np
        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(samples ** 2)))
        return rms > 0.01
