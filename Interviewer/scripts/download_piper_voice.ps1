# Download Piper voice model — local natural TTS
# Usage: .\scripts\download_piper_voice.ps1 -Voice amy
param(
    [ValidateSet("lessac", "amy", "kathleen", "ljspeech", "cori")]
    [string]$Voice = "amy"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Out = Join-Path $Root "models\piper"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$voices = @{
    lessac   = @{ path = "en/en_US/lessac/medium";   stem = "en_US-lessac-medium" }
    amy      = @{ path = "en/en_US/amy/medium";      stem = "en_US-amy-medium" }
    kathleen = @{ path = "en/en_US/kathleen/medium"; stem = "en_US-kathleen-medium" }
    ljspeech = @{ path = "en/en_US/ljspeech/medium"; stem = "en_US-ljspeech-medium" }
    cori     = @{ path = "en/en_GB/cori/medium";     stem = "en_GB-cori-medium" }
}

$v = $voices[$Voice]
$base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/$($v.path)"
$files = @("$($v.stem).onnx", "$($v.stem).onnx.json")

Write-Host "Downloading Piper voice '$Voice' to $Out ..."
foreach ($f in $files) {
    $dest = Join-Path $Out $f
    if (Test-Path $dest) { Write-Host "  exists: $f"; continue }
    curl.exe -L -o $dest "$base/$f"
    Write-Host "  saved: $f"
}

Write-Host ""
Write-Host "Set in backend\.env:"
Write-Host "  PIPER_VOICE=$Voice"
Write-Host "  TTS_ENGINE=piper"
Write-Host "  PIPER_MODEL=$Out\$($v.stem).onnx"
Write-Host "  PIPER_CONFIG=$Out\$($v.stem).onnx.json"
