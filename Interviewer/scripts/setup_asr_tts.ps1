# Install real speech recognition + KittenTTS voice
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $Root ".venv\Scripts\pip.exe"

Write-Host "Installing faster-whisper and KittenTTS..."
& $py install faster-whisper "https://github.com/KittenML/KittenTTS/releases/download/0.8.1/kittentts-0.8.1-py3-none-any.whl"

$envFile = Join-Path $Root "backend\.env"
$lines = @(
    "MOCK_ASR=false",
    "MOCK_LLM=true",
    "ASR_ENGINE=auto",
    "TTS_ENGINE=kittentts",
    "KITTENTTS_MODEL=KittenML/kitten-tts-nano-0.8",
    "KITTENTTS_VOICE=Jasper",
    "FASTER_WHISPER_MODEL=base.en",
    "FASTER_WHISPER_DEVICE=cpu",
    "FASTER_WHISPER_COMPUTE=int8"
)
Write-Host "`nAdd to backend\.env:"
$lines | ForEach-Object { Write-Host "  $_" }
Write-Host "`nRestart uvicorn after updating .env"
