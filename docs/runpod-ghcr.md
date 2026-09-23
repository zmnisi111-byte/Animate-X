# RunPod + GHCR Setup

## 1. Pick the Image Name

Use this format:

```text
ghcr.io/<github-owner>/animatex-wan-worker:0.1.0
```

`<github-owner>` is your GitHub username or organization.

## 2. Recommended: Build with GitHub Actions

This avoids local Docker entirely.

Create a GitHub repo under:

```text
zmnisi111-byte
```

Push this project to that repo. The workflow at `.github/workflows/publish-worker.yml` will publish:

```text
ghcr.io/zmnisi111-byte/animatex-wan-worker:0.1.0
ghcr.io/zmnisi111-byte/animatex-wan-worker:latest
```

You can trigger it by pushing to `main`, or manually from:

```text
GitHub repo -> Actions -> Publish RunPod Worker -> Run workflow
```

No GitHub PAT is needed for the workflow. It uses GitHub's built-in `GITHUB_TOKEN` with package write permission.

## 3. Alternative: Login to GHCR Locally

Create a GitHub Personal Access Token with package write permissions.

Then:

```powershell
$env:GHCR_PAT="github_pat_..."
echo $env:GHCR_PAT | docker login ghcr.io -u <github-owner> --password-stdin
```

For this repo, you can also put a temporary `GITHUB_CLASSIC_TOKEN` in `.env` and run:

```powershell
.\scripts\push_ghcr_worker.ps1
```

Remove `GITHUB_CLASSIC_TOKEN` from `.env` after the image has been pushed.

## 4. Build and Push Locally

```powershell
$env:GHCR_IMAGE="ghcr.io/<github-owner>/animatex-wan-worker"
$env:GHCR_TAG="0.1.0"
.\scripts\build_ghcr.ps1
```

## 5. Configure RunPod Serverless

Create a Serverless endpoint with:

```text
Container image: ghcr.io/<github-owner>/animatex-wan-worker:0.1.0
GPU: RTX PRO 6000 96GB
Min workers: 0
Max workers: 1
Execution timeout: high enough for long videos
```

If the GHCR package is private, add private registry credentials in RunPod:

```text
Registry server: ghcr.io
Username: zmnisi111-byte
Password / Token: GitHub classic token with read:packages
```

Keep this token private. It is only for RunPod pulling the container image.

Add environment variables:

```text
R2_ENDPOINT_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
R2_PUBLIC_BASE_URL optional
WAN_MOCK=1
```

Keep `WAN_MOCK=1` for the first cloud smoke test. Set it to `0` only after the official Wan2.2 Animate runtime is wired into `runpod_worker/wan_runner.py`.

## 5.1 Local Animate-X Environment

Copy `.env.example` to `.env` and fill in:

```text
RUNPOD_API_KEY
RUNPOD_ENDPOINT_ID
R2_ENDPOINT_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
GHCR_USERNAME optional local note
GHCR_TOKEN optional local note
```

The `.env` file is ignored by git. It should contain local secrets only.

## 6. RunPod Job Shape

```json
{
  "input": {
    "batch_id": "batch-id",
    "manifest_url": "r2://bucket/manifests/batch-id.json"
  }
}
```

The manifest itself contains per-job R2 input URIs.

## 7. Local Cloud Commands

Stage queued jobs to R2 without submitting:

```powershell
python -m animatex cloud-stage
```

Stage and submit queued jobs to RunPod:

```powershell
python -m animatex cloud-submit
```

Poll a RunPod job:

```powershell
python -m animatex cloud-status <runpod-job-id>
```

## Current Smoke Endpoint

The initial RunPod smoke endpoint was created with:

```text
Endpoint ID: yv6r8py4oiq293
Image: ghcr.io/zmnisi111-byte/animatex-wan-worker:0.1.0
GPU pool: BLACKWELL_96
Workers: min 0, max 1
WAN_MOCK: 1
```

The first cloud smoke job completed and wrote output to R2 under:

```text
outputs/5c7ce99b-5e3c-4d5b-8aa6-a9154796e8ab/
```

## Real Wan Runtime

The worker image contains the official `Wan-Video/Wan2.2` inference code. The image does not bake in the
Wan2.2-Animate model weights; when `WAN_MOCK=0`, the worker downloads them with `huggingface-cli` unless
`WAN_AUTO_DOWNLOAD=0`.

Production-relevant endpoint environment variables:

```text
WAN_MOCK=0
WAN_MODEL_ID=Wan-AI/Wan2.2-Animate-14B
WAN_REPO_DIR=/opt/Wan2.2
WAN_MODEL_DIR=/workspace/models/Wan2.2-Animate-14B
WAN_AUTO_DOWNLOAD=1
WAN_RESOLUTION_AREA=1280 720
WAN_REFERT_NUM=1
WAN_OFFLOAD_MODEL=True
WAN_PREPROCESS_TIMEOUT_SECONDS=1800
WAN_GENERATE_TIMEOUT_SECONDS=7200
WAN_MODEL_DOWNLOAD_TIMEOUT_SECONDS=7200
```

The first real generation test should use a very short Draft job. Model download can dominate the first run unless
a RunPod network volume or other persistent cache is added.
