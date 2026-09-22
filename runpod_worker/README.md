# Animate-X RunPod Worker

This worker is the cloud side of Animate-X.

V1 worker contract:

```text
RunPod input
  batch_id
  manifest_url

Worker
  download manifest from Cloudflare R2
  download each job input
  run generation pipeline
  upload outputs to Cloudflare R2
  return per-job results
```

The current implementation is a smoke-test worker. It copies/transcodes the source video and produces the same result shape the real Wan worker will return. This lets us prove RunPod + Cloudflare R2 before spending time debugging the full Wan runtime.

## Required Environment Variables

```text
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=...
R2_PUBLIC_BASE_URL=optional
WAN_MOCK=1
```

## Local Handler Test

```powershell
python -m pip install -r runpod_worker/requirements.txt
python runpod_worker/local_test.py runpod_worker/test_input.json
```

## GHCR Image

Image name format:

```text
ghcr.io/<github-owner>/animatex-wan-worker:<tag>
```

Use `scripts/build_ghcr.ps1` after setting:

```powershell
$env:GHCR_IMAGE="ghcr.io/<github-owner>/animatex-wan-worker"
$env:GHCR_TAG="0.1.0"
```

