param(
    [string]$Image = $env:GHCR_IMAGE,
    [string]$Tag = $env:GHCR_TAG
)

if (-not $Image) {
    throw "Set GHCR_IMAGE, for example: ghcr.io/<github-owner>/animatex-wan-worker"
}

if (-not $Tag) {
    $Tag = "0.1.0"
}

$fullTag = "${Image}:${Tag}"
$latestTag = "${Image}:latest"

docker build -f runpod_worker/Dockerfile -t $fullTag -t $latestTag .
docker push $fullTag
docker push $latestTag

Write-Output "Pushed $fullTag"
Write-Output "Use this RunPod container image: $fullTag"

