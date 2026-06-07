# Piper voice selection

HireNest uses **local** [Piper](https://github.com/rhasspy/piper) voices — no cloud TTS.

## Female voices (recommended)

| ID | Description | Download |
|----|-------------|----------|
| `amy` | US English, female (default) | `.\scripts\download_piper_voice.ps1 -Voice amy` |
| `kathleen` | US English, female | `-Voice kathleen` |
| `ljspeech` | US English, female | `-Voice ljspeech` |
| `cori` | British English, female | `-Voice cori` |

## Other

| ID | Description |
|----|-------------|
| `lessac` | US English, neutral / male-leaning |

## Configure

**Option A — UI:** Pick voice in the dropdown before **Start interview**.

**Option B — `.env`:**

```env
PIPER_VOICE=amy
TTS_ENGINE=piper
```

Restart uvicorn after changing `.env`.

## List installed voices

GET http://127.0.0.1:8000/interview/voices
