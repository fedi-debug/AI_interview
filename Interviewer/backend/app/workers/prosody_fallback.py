"""Local prosody extraction fallback when openSMILE is unavailable (librosa)."""

import io
import struct
from typing import Optional

import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


def pcm_to_float(pcm_int16: bytes) -> np.ndarray:
    arr = np.frombuffer(pcm_int16, dtype=np.int16).astype(np.float32)
    return arr / 32768.0


def extract_prosody(pcm_int16: bytes, sample_rate: int = 16000) -> dict:
    """
    Extract pitch_mean, pitch_std, energy_mean, jitter, shimmer.

    Example output:
        {"pitch_mean": 142.3, "pitch_std": 18.2, "energy_mean": 0.04,
         "jitter": 0.012, "shimmer": 0.021}
    """
    y = pcm_to_float(pcm_int16)
    if len(y) < sample_rate * 0.2:
        return _default_prosody()

    if not HAS_LIBROSA:
        return _default_prosody()

    energy = float(np.sqrt(np.mean(y ** 2)))
    f0, _, _ = librosa.pyin(
        y, fmin=75, fmax=400, sr=sample_rate, frame_length=2048, fill_na=np.nan
    )
    voiced = f0[~np.isnan(f0)]
    if len(voiced) < 3:
        return {**_default_prosody(), "energy_mean": energy}

    pitch_mean = float(np.nanmean(voiced))
    pitch_std = float(np.nanstd(voiced))
    # Simple jitter/shimmer proxies from frame-to-frame F0 and amplitude
    amp = librosa.feature.rms(y=y)[0]
    jitter = float(np.std(np.diff(voiced)) / (pitch_mean + 1e-6)) if len(voiced) > 2 else 0.01
    shimmer = float(np.std(np.diff(amp)) / (np.mean(amp) + 1e-6)) if len(amp) > 2 else 0.02
    return {
        "pitch_mean": pitch_mean,
        "pitch_std": pitch_std,
        "energy_mean": energy,
        "jitter": min(jitter, 0.1),
        "shimmer": min(shimmer, 0.1),
    }


def extract_opensmile(pcm_int16: bytes, sample_rate: int, bin_path: str) -> Optional[dict]:
    """Run openSMILE via subprocess if configured."""
    import subprocess
    import tempfile
    from pathlib import Path
    if not bin_path:
        return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wf:
        wav = wf.name
    from app.workers.whisper_client import _write_wav
    _write_wav(wav, pcm_int16, sample_rate)
    out_csv = wav + ".csv"
    try:
        # Minimal LLD config path — user must provide IS13_ComParE.conf in production
        subprocess.run([bin_path, "-I", wav, "-O", out_csv], timeout=30, check=False)
        if Path(out_csv).exists():
            return _parse_opensmile_csv(out_csv)
    except Exception:
        return None
    finally:
        Path(wav).unlink(missing_ok=True)
        Path(out_csv).unlink(missing_ok=True)
    return None


def _parse_opensmile_csv(path: str) -> dict:
    # Stub: return defaults; extend when openSMILE CSV columns are wired
    return _default_prosody()


def _default_prosody() -> dict:
    return {
        "pitch_mean": 150.0,
        "pitch_std": 20.0,
        "energy_mean": 0.05,
        "jitter": 0.01,
        "shimmer": 0.02,
    }
