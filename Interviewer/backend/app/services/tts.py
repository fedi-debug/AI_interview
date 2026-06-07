"""Local TTS powered by KittenTTS."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from threading import Lock
from typing import Optional

import soundfile as sf
from phonemizer.backend import EspeakBackend

from app.config import get_settings
from app.services.kittentts_voices import DEFAULT_VOICE, normalize_voice_id

SAMPLE_RATE = 24_000

_kitten_model = None
_kitten_model_key: str | None = None
_kitten_lock = Lock()
_phonemizer_language: str | None = None

PHONEMIZER_LANGUAGES = {
    "en": "en-us",
    "fr": "fr-fr",
}


def resolve_tts_engine(voice_preset: str | None = None) -> str:
    s = get_settings()
    requested = (s.tts_engine or "auto").lower().strip()
    if requested == "browser":
        return "browser"
    if requested in ("auto", "kitten", "kittentts", "piper", "pyttsx3"):
        # Old env values are intentionally routed to KittenTTS.
        return "kittentts"
    return "kittentts"


def _load_kittentts_model():
    global _kitten_model, _kitten_model_key
    s = get_settings()
    model_name = s.kittentts_model
    cache_dir = Path(s.kittentts_cache_dir)
    key = f"{model_name}|{cache_dir}"

    if _kitten_model is not None and _kitten_model_key == key:
        return _kitten_model

    cache_dir.mkdir(parents=True, exist_ok=True)
    from kittentts import KittenTTS

    _kitten_model = KittenTTS(model_name, cache_dir=str(cache_dir))
    _kitten_model_key = key
    return _kitten_model


def _set_model_language(model, language: str) -> None:
    global _phonemizer_language
    phonemizer_language = PHONEMIZER_LANGUAGES.get(language, "en-us")
    if _phonemizer_language == phonemizer_language:
        return
    model.model.phonemizer = EspeakBackend(
        language=phonemizer_language,
        preserve_punctuation=True,
        with_stress=True,
    )
    _phonemizer_language = phonemizer_language


def _synthesize_kittentts(
    text: str,
    voice_preset: str | None = None,
    language: str = "en",
) -> Optional[bytes]:
    voice = normalize_voice_id(voice_preset)
    with _kitten_lock:
        model = _load_kittentts_model()
        _set_model_language(model, language)
        audio = model.generate(text, voice=voice, speed=1.0, clean_text=(language == "en"))

    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    data = buf.getvalue()
    return data if len(data) > 100 else None


def synthesize_wav_base64(
    text: str,
    voice_preset: str | None = None,
    language: str = "en",
) -> tuple[Optional[str], str]:
    """
    Returns (base64_wav_or_none, engine_label).
    engine_label e.g. kittentts:Jasper
    """
    text = (text or "").strip()
    if not text:
        return None, "browser"

    preset = normalize_voice_id(voice_preset or get_settings().kittentts_voice or DEFAULT_VOICE)
    engine = resolve_tts_engine(preset)
    label = f"kittentts:{preset}" if engine == "kittentts" else engine

    if engine == "kittentts":
        try:
            wav = _synthesize_kittentts(text, preset, language)
        except Exception as exc:
            print(f"KittenTTS synthesis failed: {exc}")
            return None, "kittentts:error"
        if wav:
            return base64.b64encode(wav).decode("ascii"), label

    return None, "browser"
