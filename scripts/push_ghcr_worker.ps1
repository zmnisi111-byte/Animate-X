$ErrorActionPreference = "Stop"

function Load-DotEnv {
    param([string]$Path = ".env")
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($key -and -not [Environment]::GetEnvironmentVariable($key, "Process")) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

Load-DotEnv

if (-not $env:GITHUB_CLASSIC_TOKEN) {
    throw "Missing GITHUB_CLASSIC_TOKEN in .env"
}

if (-not $env:GHCR_IMAGE -or $env:GHCR_IMAGE -like "*<github-owner>*") {
    $env:GHCR_IMAGE = "ghcr.io/zmnisi111-byte/animatex-wan-worker"
}

if (-not $env:GHCR_TAG) {
    $env:GHCR_TAG = "0.1.0"
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not ready. Open Docker Desktop and wait until it says it is running."
}

$env:GITHUB_CLASSIC_TOKEN | docker login ghcr.io -u zmnisi111-byte --password-stdin
if ($LASTEXITCODE -ne 0) {
    throw "GHCR login failed."
}

.\scripts\build_ghcr.ps1 -Image $env:GHCR_IMAGE -Tag $env:GHCR_TAG

