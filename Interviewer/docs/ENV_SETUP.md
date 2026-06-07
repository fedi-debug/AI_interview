# HireNest — Environment & Model Prep Checklist

Target hardware: **Windows 10**, **GTX 1650 (4 GB VRAM)**, **Intel i5 10th gen**.

All processing is **local** — no cloud APIs.

---

## Quick checklist

| Step | Item | Status |
|------|------|--------|
| 1 | Python 3.10+ venv | ☐ |
| 2 | Visual Studio Build Tools (C++) | ☐ |
| 3 | FFmpeg on PATH | ☐ |
| 4 | CUDA 11.8+ (optional, for GPU whisper/llama) | ☐ |
| 5 | whisper.cpp binary + GGML model | ☐ |
| 6 | llama.cpp binary + GGUF Q4 model | ☐ |
| 7 | openSMILE (native or WSL2) | ☐ |
| 8 | Python packages (`requirements.txt`) | ☐ |
| 9 | Model directory layout | ☐ |
| 10 | Smoke test (`scripts/smoke_test.ps1`) | ☐ |

---

## 1. Python virtual environment

```powershell
cd d:\interview\hirenest
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
pip install -r backend\requirements.txt
```

---

## 2. Visual Studio Build Tools

Required for some Python wheels and building native tools.

1. Download [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
2. Install workload: **Desktop development with C++**.
3. Restart terminal after install.

---

## 3. FFmpeg

```powershell
# winget (recommended)
winget install Gyan.FFmpeg

# Verify
ffmpeg -version
```

Place nothing extra in the repo; FFmpeg must be on `PATH`.

---

## 4. CUDA (optional)

GTX 1650 supports CUDA. Use only if you build **CUDA-enabled** whisper.cpp / llama.cpp.

- Install [CUDA Toolkit 11.8](https://developer.nvidia.com/cuda-11-8-0-download-archive) or 12.x matching your build.
- Install matching [cuDNN](https://developer.nvidia.com/cudnn) if required by your build scripts.

If VRAM is tight, prefer **CPU quantized** inference (Q4 GGUF + `whisper.cpp` CPU threads).

---

## 5. whisper.cpp (ASR)

### Download prebuilt Windows binary (no compile)

```powershell
mkdir -Force d:\interview\hirenest\bin\whisper
cd d:\interview\hirenest\bin\whisper
# Example release URL — check latest at https://github.com/ggerganov/whisper.cpp/releases
curl -L -o whisper.zip https://github.com/ggerganov/whisper.cpp/releases/download/v1.6.2/whisper-bin-x64.zip
Expand-Archive whisper.zip -DestinationPath .
```

Expected executable: `d:\interview\hirenest\bin\whisper\main.exe` (or `whisper-cli.exe` depending on release).

### ASR models (GGML)

| Model | VRAM/RAM | Quality | HireNest default |
|-------|----------|---------|------------------|
| `ggml-tiny.en.bin` | ~75 MB | Low | Dev / smoke |
| `ggml-base.en.bin` | ~150 MB | OK | **Recommended** |
| `ggml-small.en.bin` | ~500 MB | Better | If CPU/GPU headroom |

```powershell
mkdir -Force d:\interview\hirenest\models\whisper
cd d:\interview\hirenest\models\whisper
curl -L -o ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

Set in `.env`:

```
WHISPER_BIN=d:\interview\hirenest\bin\whisper\main.exe
WHISPER_MODEL=d:\interview\hirenest\models\whisper\ggml-base.en.bin
```

### Build from source (optional)

```powershell
git clone https://github.com/ggerganov/whisper.cpp d:\interview\hirenest\vendor\whisper.cpp
cd d:\interview\hirenest\vendor\whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j
```

---

## 6. llama.cpp (MCQ + interviewer LLM)

### Download binary

```powershell
mkdir -Force d:\interview\hirenest\bin\llama
cd d:\interview\hirenest\bin\llama
curl -L -o llama-b.zip https://github.com/ggerganov/llama.cpp/releases/download/b3960/llama-b3960-bin-win-avx2-x64.zip
Expand-Archive llama-b.zip -DestinationPath .
```

Use `llama-cli.exe` or `llama-server.exe` from the archive.

### LLM models (GGUF, GTX 1650)

| Model | Quant | Size | Notes |
|-------|-------|------|-------|
| TinyLlama-1.1B | Q4_K_M | ~700 MB | Fastest, weaker JSON |
| Phi-2 | Q4_K_M | ~1.6 GB | Good balance |
| Mistral-7B | Q4_K_M | ~4.1 GB | **Max for 4 GB VRAM** — use `-ngl 20` or CPU offload |

**Recommended for GTX 1650:** `Phi-2-GGUF Q4_K_M` or `Mistral-7B-Instruct-v0.2 Q4_K_M` with partial GPU layers.

```powershell
mkdir -Force d:\interview\hirenest\models\llama
# Example: download from Hugging Face (one-time)
# huggingface-cli download TheBloke/phi-2-GGUF phi-2.Q4_K_M.gguf --local-dir d:\interview\hirenest\models\llama
```

`.env`:

```
LLAMA_BIN=d:\interview\hirenest\bin\llama\llama-cli.exe
LLAMA_MODEL=d:\interview\hirenest\models\llama\phi-2.Q4_K_M.gguf
LLAMA_NGL=0
LLAMA_THREADS=6
```

For 7B on 4 GB VRAM: `LLAMA_NGL=15`, `LLAMA_THREADS=4`, context `2048`.

---

## 7. openSMILE (paralinguistics)

openSMILE official Windows builds are limited. **Workarounds (local only):**

### Option A — WSL2 Ubuntu (recommended)

```powershell
wsl --install -d Ubuntu
```

In WSL:

```bash
sudo apt update && sudo apt install -y build-essential cmake libportaudio2
git clone https://github.com/audeering/opensmile.git ~/opensmile
cd ~/opensmile && bash build.sh
```

Point HireNest to WSL binary via `config.py`:

```
OPENSMILE_BIN=wsl
OPENSMILE_ARGS=~/opensmile/build/progsrc/smilextract/SMILExtract -C {config} -I {input} -O {output}
```

### Option B — Python fallback (no openSMILE)

HireNest includes `backend/app/workers/prosody_fallback.py` using **librosa** + **parselmouth** (open-source) when `OPENSMILE_BIN` is unset. Metrics are approximate but local.

---

## 8. Directory layout

```
hirenest/
├── bin/
│   ├── whisper/     # main.exe
│   └── llama/       # llama-cli.exe
├── models/
│   ├── whisper/     # ggml-base.en.bin
│   └── llama/       # *.gguf
├── data/            # SQLite DB (created at runtime)
├── backend/
├── frontend/
└── scripts/
```

---

## 9. Environment file

Copy `backend/.env.example` to `backend/.env` and adjust paths.

---

## webrtcvad on Windows

`webrtcvad` needs **Microsoft C++ Build Tools** to compile. If install fails, HireNest uses an **energy-based VAD fallback** automatically. To enable webrtcvad:

```powershell
# After installing VS Build Tools:
pip install webrtcvad
```

---

## 10. Run server

```powershell
cd d:\interview\hirenest
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "d:\interview\hirenest\backend"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

---

## Performance tuning (GTX 1650)

| Setting | Value |
|---------|-------|
| Whisper model | `base` or `small` |
| Audio chunk | 1.5 s @ 16 kHz mono PCM |
| Video sample | 5–8 FPS, 640×480 |
| LLM | Q4_K_M, `temperature=0.2`, `max_tokens=256` |
| Reuse processes | Single long-lived whisper/llama subprocess pool |
| GPU layers | Start `ngl=0` (CPU); increase only if VRAM allows |

---

## Smoke test

```powershell
.\scripts\setup_windows.ps1 -SkipDownloads
.\scripts\smoke_test.ps1
```
