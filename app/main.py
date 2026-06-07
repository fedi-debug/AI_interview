from __future__ import annotations

import io
import os
from pathlib import Path
from threading import Lock

import soundfile as sf
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from kittentts import KittenTTS
from phonemizer.backend import EspeakBackend


SAMPLE_RATE = 24_000
DEFAULT_MODEL = os.getenv("KITTENTTS_MODEL", "KittenML/kitten-tts-nano-0.8")
MODEL_CACHE_DIR = Path(os.getenv("KITTENTTS_CACHE_DIR", "model_cache"))
VOICE_NAMES = ["Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo"]
LANGUAGES = {
    "en-US": {"label": "English", "phonemizer": "en-us", "clean_text": True},
    "fr-FR": {"label": "Francais", "phonemizer": "fr-fr", "clean_text": False},
}

app = FastAPI(title="KittenTTS Speaker")

_model: KittenTTS | None = None
_model_lock = Lock()
_generation_lock = Lock()
_current_phonemizer_language: str | None = None


def get_tts_model() -> KittenTTS:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _model = KittenTTS(DEFAULT_MODEL, cache_dir=str(MODEL_CACHE_DIR), backend="cpu")
    return _model


def set_phonemizer_language(model: KittenTTS, language_code: str) -> None:
    global _current_phonemizer_language
    if _current_phonemizer_language == language_code:
        return

    model.model.phonemizer = EspeakBackend(
        language=language_code,
        preserve_punctuation=True,
        with_stress=True,
    )
    _current_phonemizer_language = language_code


def synthesize_wav(text: str, voice: str, speed: float, language: str) -> io.BytesIO:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=400, detail="Text is required.")
    if len(cleaned_text) > 1_000:
        raise HTTPException(status_code=400, detail="Text must be 1000 characters or less.")
    if voice not in VOICE_NAMES:
        raise HTTPException(status_code=400, detail=f"Voice must be one of: {', '.join(VOICE_NAMES)}.")
    if not 0.5 <= speed <= 2.0:
        raise HTTPException(status_code=400, detail="Speed must be between 0.5 and 2.0.")
    if language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be English or Francais.")

    model = get_tts_model()
    language_settings = LANGUAGES[language]
    with _generation_lock:
        set_phonemizer_language(model, language_settings["phonemizer"])
        audio = model.generate(
            cleaned_text,
            voice=voice,
            speed=speed,
            clean_text=language_settings["clean_text"],
        )

    wav_file = io.BytesIO()
    sf.write(wav_file, audio, SAMPLE_RATE, format="WAV")
    wav_file.seek(0)
    return wav_file


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    voice_options = "\n".join(
        f'<option value="{voice}"{" selected" if voice == "Jasper" else ""}>{voice}</option>'
        for voice in VOICE_NAMES
    )
    language_options = "\n".join(
        f'<option value="{code}">{settings["label"]}</option>'
        for code, settings in LANGUAGES.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KittenTTS Speaker</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f4ee;
      color: #20222a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 28px;
      background:
        linear-gradient(135deg, rgba(37, 88, 124, 0.12), transparent 38%),
        linear-gradient(315deg, rgba(194, 78, 64, 0.12), transparent 42%),
        #f7f4ee;
    }}
    main {{
      width: min(760px, 100%);
      display: grid;
      gap: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    p {{
      margin: 0;
      color: #5a5f6b;
      line-height: 1.5;
    }}
    form {{
      display: grid;
      gap: 14px;
      padding: 22px;
      border: 1px solid #ddd6cc;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.82);
      box-shadow: 0 18px 50px rgba(32, 34, 42, 0.10);
    }}
    label {{
      display: grid;
      gap: 7px;
      font-weight: 700;
      color: #292c35;
    }}
    textarea, select, input {{
      width: 100%;
      border: 1px solid #c9c1b5;
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      color: #20222a;
      background: #fffdf9;
    }}
    textarea {{
      min-height: 150px;
      resize: vertical;
      line-height: 1.5;
    }}
    .controls {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    button {{
      min-height: 46px;
      border: 0;
      border-radius: 6px;
      background: #25587c;
      color: white;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }}
    button:disabled {{
      cursor: wait;
      opacity: 0.72;
    }}
    audio {{
      width: 100%;
      min-height: 42px;
    }}
    #status {{
      min-height: 24px;
      color: #5a5f6b;
      font-weight: 650;
    }}
    @media (max-width: 640px) {{
      body {{ padding: 18px; }}
      h1 {{ font-size: 28px; }}
      form {{ padding: 16px; }}
      .controls {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>KittenTTS Speaker</h1>
      <p>Type text, choose a voice, and hear the generated speech in your browser.</p>
    </header>
    <form id="tts-form">
      <label>
        Text
        <textarea name="text" maxlength="1000" required>Hello, this is Kitten TTS. Bonjour, ceci est une voix de synthese.</textarea>
      </label>
      <div class="controls">
        <label>
          Language
          <select name="language">{language_options}</select>
        </label>
        <label>
          Voice
          <select name="voice">{voice_options}</select>
        </label>
        <label>
          Speed
          <input name="speed" type="number" min="0.5" max="2" step="0.1" value="1">
        </label>
      </div>
      <button type="submit">Speak</button>
      <div id="status" role="status"></div>
      <audio id="player" controls></audio>
    </form>
  </main>
  <script>
    const form = document.querySelector("#tts-form");
    const status = document.querySelector("#status");
    const player = document.querySelector("#player");
    const button = form.querySelector("button");
    let currentAudioUrl = null;

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      button.disabled = true;
      status.textContent = "Generating audio...";
      player.removeAttribute("src");

      if (currentAudioUrl) {{
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
      }}

      try {{
        const response = await fetch("/speak", {{
          method: "POST",
          body: new FormData(form)
        }});

        if (!response.ok) {{
          const error = await response.json().catch(() => ({{ detail: "Could not generate audio." }}));
          throw new Error(error.detail || "Could not generate audio.");
        }}

        const audioBlob = await response.blob();
        currentAudioUrl = URL.createObjectURL(audioBlob);
        player.src = currentAudioUrl;
        await player.play();
        status.textContent = "Ready.";
      }} catch (error) {{
        status.textContent = error.message;
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


@app.post("/speak")
def speak(
    text: str = Form(...),
    language: str = Form("en-US"),
    voice: str = Form("Jasper"),
    speed: float = Form(1.0),
) -> StreamingResponse:
    wav_file = synthesize_wav(text=text, voice=voice, speed=speed, language=language)
    return StreamingResponse(
        wav_file,
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="speech.wav"'},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": DEFAULT_MODEL}
