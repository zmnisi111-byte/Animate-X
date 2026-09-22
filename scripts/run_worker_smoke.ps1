$ErrorActionPreference = "Stop"

if (-not (Test-Path "samples\dance_01.mp4") -or -not (Test-Path "samples\ari_reference.png")) {
    python -m animatex sample
}

python runpod_worker\smoke_local.py samples\dance_01.mp4 samples\ari_reference.png

