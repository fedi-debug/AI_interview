# HireNest Windows environment setup
# Usage: .\scripts\setup_windows.ps1 [-SkipDownloads] [-PythonVersion 3.10]

param(
    [switch]$SkipDownloads,
    [string]$PythonVersion = "3.10"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== HireNest Windows Setup ===" -ForegroundColor Cyan
Write-Host "Root: $Root"

# Directories
$dirs = @(
    "bin\whisper", "bin\llama",
    "models\whisper", "models\llama",
    "data", "backend\app", "frontend", "tests", "docs"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}

# Python venv
$venv = Join-Path $Root ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating Python $PythonVersion venv..."
    py -$PythonVersion -m venv $venv
}
& "$venv\Scripts\python.exe" -m pip install --upgrade pip wheel

Write-Host "Installing Python dependencies..."
& "$venv\Scripts\pip.exe" install -r (Join-Path $Root "backend\requirements.txt")

# .env from example
$envExample = Join-Path $Root "backend\.env.example"
$envFile = Join-Path $Root "backend\.env"
if ((Test-Path $envExample) -and -not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "Created backend\.env from example."
}

# FFmpeg check
try {
    $ff = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "FFmpeg: OK — $ff" -ForegroundColor Green
} catch {
    Write-Warning "FFmpeg not on PATH. Install: winget install Gyan.FFmpeg"
}

# CUDA check (optional)
try {
    $nv = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1
    Write-Host "NVIDIA GPU: $nv" -ForegroundColor Green
} catch {
    Write-Host "nvidia-smi not found — CPU inference only." -ForegroundColor Yellow
}

if (-not $SkipDownloads) {
    Write-Host "`nOptional downloads (requires internet):" -ForegroundColor Cyan
    Write-Host "  1. whisper.cpp release -> bin\whisper\"
    Write-Host "  2. ggml-base.en.bin -> models\whisper\"
    Write-Host "  3. llama.cpp release -> bin\llama\"
    Write-Host "  4. Phi-2 or Mistral GGUF -> models\llama\"
    Write-Host "See docs\ENV_SETUP.md for exact curl URLs."
} else {
    Write-Host "Skipped download hints (-SkipDownloads)."
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host "Activate:  .\.venv\Scripts\Activate.ps1"
Write-Host "Run API:   `$env:PYTHONPATH='$Root\backend'; uvicorn app.main:app --reload --port 8000"
Write-Host "Smoke:     .\scripts\smoke_test.ps1"
