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
