# Animate-X

Local-first test harness for a daily Wan Animate batch system.

This V1 includes:

- SQLite job queue
- manifest-based daily batching
- local temporary storage
- mock Wan worker with real job state transitions
- local "Drive" output folder
- dependency-free web control panel
- CLI for repeatable testing

The mock worker copies/transcodes local video inputs so the full orchestration can be tested before wiring RunPod and Google Drive credentials.

Jobs automatically receive a generation plan based on detected duration:

- `single_window` for clips that fit in one Wan window
- `longform_windowed` for longer reference videos
- `generated_anchor` first-frame preparation for longform jobs and character swaps

## Quick Start

```powershell
python -m animatex init
python -m animatex sample
python -m animatex add --video samples\dance_01.mp4 --reference samples\ari_reference.png --character Ari --mode pose_retarget --profile "TikTok Standard"
python -m animatex run
python -m animatex queue
python -m animatex serve --port 8765
```

Open `http://127.0.0.1:8765` for the control panel.

## Data Layout

```text
data/
  animatex.sqlite
  temp/
  manifests/
  drive/
```

## Cloud Adapter Boundary

The production RunPod/Drive implementation should replace:

- `animatex.workers.mock.MockWanWorker`
- `animatex.storage.LocalTempStore`
- `animatex.storage.LocalDriveStore`

Everything above those adapters should remain stable.

## RunPod Worker

The RunPod worker scaffold lives in `runpod_worker/`.

```powershell
.\scripts\run_worker_smoke.ps1
```

GHCR build notes are in `docs/runpod-ghcr.md`. The recommended path is GitHub Actions, so local Docker is not required.

Cloud commands:

```powershell
python -m animatex cloud-stage
python -m animatex cloud-submit
python -m animatex cloud-status <runpod-job-id>
```

Create `.env` from `.env.example` before using cloud commands.
