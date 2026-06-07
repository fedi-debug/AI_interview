"""Application configuration loaded from environment."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{ROOT / 'data' / 'hirenest.db'}"
    whisper_bin: str = str(ROOT / "bin" / "whisper" / "main.exe")
    whisper_model: str = str(ROOT / "models" / "whisper" / "ggml-base.en.bin")
    whisper_threads: int = 4
    # faster-whisper (pip) — real speech-to-text without whisper.cpp binary
    faster_whisper_model: str = "base.en"
    faster_whisper_device: str = "cpu"
    faster_whisper_compute: str = "int8"
    asr_engine: str = "auto"  # auto | faster_whisper | whisper_cpp | mock
    llama_bin: str = str(ROOT / "bin" / "llama" / "llama-cli.exe")
    llama_model: str = str(ROOT / "models" / "llama" / "phi-2.Q4_K_M.gguf")
    llama_ngl: int = 0
    llama_threads: int = 6
    llama_max_tokens: int = 512
    # KittenTTS voices: Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo
    kittentts_model: str = "KittenML/kitten-tts-nano-0.8"
    kittentts_voice: str = "Jasper"
    kittentts_cache_dir: str = str(ROOT / "models" / "kittentts")
    tts_engine: str = "auto"  # auto | kittentts | pyttsx3 | browser
    opensmile_bin: str = ""
    use_prosody_fallback: bool = True
    audio_chunk_sec: float = 1.5
    video_fps: int = 6
    mock_llm: bool = False
    mock_asr: bool = False
    score_weights_content: float = 0.50
    score_weights_fluency: float = 0.20
    score_weights_prosody: float = 0.15
    score_weights_nonverbal: float = 0.15


@lru_cache
def get_settings() -> Settings:
    return Settings()
