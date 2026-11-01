param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Checking Docker..."
docker version | Out-Null

if ($NoBuild) {
    docker compose -f docker/docker-compose.yml --project-directory . up -d
} else {
    docker compose -f docker/docker-compose.yml --project-directory . up -d --build
}

Write-Host "Waiting for API health..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { break }
    } catch { }
    Start-Sleep -Seconds 2
}

Write-Host "Importing Langflow flows..."
python scripts/langflow/import_flows.py

Write-Host "Demo ready:"
Write-Host "  Frontend: http://localhost:5173 (or http://localhost)"
Write-Host "  API docs: http://localhost:8000/docs"
Write-Host "  Langflow: http://localhost:7860"
