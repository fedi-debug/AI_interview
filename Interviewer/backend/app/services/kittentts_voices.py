"""KittenTTS voice presets."""

from __future__ import annotations

from typing import TypedDict


DEFAULT_VOICE = "Jasper"


class VoicePreset(TypedDict):
    id: str
    label: str
    gender: str
    locale: str
    downloaded: bool


VOICE_PRESETS: dict[str, VoicePreset] = {
    "Bella": {
        "id": "Bella",
        "label": "Bella (female)",
        "gender": "female",
        "locale": "en_US",
        "downloaded": True,
    },
    "Jasper": {
        "id": "Jasper",
        "label": "Jasper (male)",
        "gender": "male",
        "locale": "en_US",
        "downloaded": True,
    },
    "Luna": {
        "id": "Luna",
        "label": "Luna (female)",
        "gender": "female",
        "locale": "en_US",
        "downloaded": True,
    },
    "Bruno": {
        "id": "Bruno",
        "label": "Bruno (male)",
        "gender": "male",
        "locale": "en_US",
        "downloaded": True,
    },
    "Rosie": {
        "id": "Rosie",
        "label": "Rosie (female)",
        "gender": "female",
        "locale": "en_US",
        "downloaded": True,
    },
    "Hugo": {
        "id": "Hugo",
        "label": "Hugo (male)",
        "gender": "male",
        "locale": "en_US",
        "downloaded": True,
    },
    "Kiki": {
        "id": "Kiki",
        "label": "Kiki (female)",
        "gender": "female",
        "locale": "en_US",
        "downloaded": True,
    },
    "Leo": {
        "id": "Leo",
        "label": "Leo (male)",
        "gender": "male",
        "locale": "en_US",
        "downloaded": True,
    },
}

_ALIASES = {
    "amy": "Bella",
    "kathleen": "Luna",
    "ljspeech": "Rosie",
    "cori": "Kiki",
    "lessac": "Jasper",
}


def normalize_voice_id(voice_id: str | None = None) -> str:
    raw = (voice_id or DEFAULT_VOICE).strip()
    if raw in VOICE_PRESETS:
        return raw

    lowered = raw.lower()
    if lowered in _ALIASES:
        return _ALIASES[lowered]

    for voice in VOICE_PRESETS:
        if voice.lower() == lowered:
            return voice

    return DEFAULT_VOICE


def list_voices() -> list[dict]:
    return [dict(voice) for voice in VOICE_PRESETS.values()]
