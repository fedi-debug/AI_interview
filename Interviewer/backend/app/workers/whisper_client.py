"""ASR: faster-whisper (pip) → whisper.cpp → mock (dev only)."""

import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import get_settings

_faster_whisper_model = None


def _pcm_to_float32(pcm_int16: bytes) -> np.ndarray:
    return np.frombuffer(pcm_int16, dtype=np.int16).astype(np.float32) / 32768.0


def _get_faster_whisper():
    global _faster_whisper_model
    if _faster_whisper_model is None:
        from faster_whisper import WhisperModel
        s = get_settings()
        _faster_whisper_model = WhisperModel(
            s.faster_whisper_model,
            device=s.faster_whisper_device,
            compute_type=s.faster_whisper_compute,
        )
    return _faster_whisper_model


def _transcribe_faster_whisper(
    pcm_int16: bytes,
    sample_rate: int = 16000,
    language: str = "en",
) -> dict:
    audio = _pcm_to_float32(pcm_int16)
    if len(audio) < sample_rate * 0.25:
        return {"text": "", "confidence": 0.0, "engine": "faster_whisper"}
    model = _get_faster_whisper()
    segments, info = model.transcribe(
        audio,
        language="fr" if language == "fr" else "en",
        vad_filter=True,
        beam_size=1,
    )
    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    text = " ".join(parts).strip()
    conf = float(1.0 - getattr(info, "language_probability", 0.3)) if text else 0.0
    conf = min(max(conf, 0.5), 0.98) if text else 0.0
    return {"text": text, "confidence": conf, "engine": "faster_whisper"}


def _transcribe_whisper_cpp(pcm_int16: bytes, sample_rate: int) -> dict:
    settings = get_settings()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    try:
        _write_wav(wav_path, pcm_int16, sample_rate)
        cmd = [
            settings.whisper_bin,
            "-m", settings.whisper_model,
            "-f", wav_path,
            "-t", str(settings.whisper_threads),
            "--no-timestamps",
            "-otxt",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace"
        )
        text = result.stdout.strip()
        return {"text": text, "confidence": 0.85 if text else 0.0, "engine": "whisper_cpp"}
    finally:
        Path(wav_path).unlink(missing_ok=True)


def _faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def resolve_asr_engine() -> str:
    s = get_settings()
    if s.mock_asr:
        return "mock"
    if s.asr_engine == "mock":
        return "mock"
    if s.asr_engine == "faster_whisper":
        return "faster_whisper" if _faster_whisper_available() else "none"
    if s.asr_engine == "whisper_cpp":
        return "whisper_cpp" if Path(s.whisper_bin).is_file() else "none"
    # auto
    if _faster_whisper_available():
        return "faster_whisper"
    if Path(s.whisper_bin).is_file() and Path(s.whisper_model).is_file():
        return "whisper_cpp"
    return "none"


def transcribe_pcm(pcm_int16: bytes, sample_rate: int = 16000, language: str = "en") -> dict:
    """
    Transcribe 16-bit mono PCM → {"text", "confidence", "engine"}.
    """
    engine = resolve_asr_engine()
    if engine == "mock":
        return _mock_asr(pcm_int16)
    if engine == "faster_whisper":
        try:
            return _transcribe_faster_whisper(pcm_int16, sample_rate, language)
        except Exception as e:
            return {"text": "", "confidence": 0.0, "engine": "error", "error": str(e)}
    if engine == "whisper_cpp":
        try:
            return _transcribe_whisper_cpp(pcm_int16, sample_rate)
        except Exception:
            pass
    duration = len(pcm_int16) / 2 / sample_rate
    if duration < 0.3:
        return {"text": "", "confidence": 0.0, "engine": "none"}
    return {
        "text": "",
        "confidence": 0.0,
        "engine": "none",
        "error": "No ASR engine. pip install faster-whisper and set MOCK_ASR=false",
    }


def _mock_asr(pcm: bytes) -> dict:
    duration = len(pcm) / 2 / 16000
    if duration < 0.3:
        return {"text": "", "confidence": 0.0, "engine": "mock"}
    return {
        "text": "[mock — set MOCK_ASR=false and install faster-whisper]",
        "confidence": 0.75,
        "engine": "mock",
    }


def _write_wav(path: str, pcm: bytes, sample_rate: int):
    n = len(pcm)
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + n))
        f.write(b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", n))
        f.write(pcm)
