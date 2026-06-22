param(
    [switch]$Start
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Set ETH_RPC_URL before running the DAG."
}

New-Item -ItemType Directory -Force `
    "airflow/logs", `
    "data/delta/ethereum_logs", `
    "data/analytics", `
    "data/tmp" | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker command was not found. Install Docker Desktop before starting Airflow."
    exit 0
}

if ($Start) {
    docker compose up --build airflow-init
    docker compose up --build airflow-webserver airflow-scheduler
} else {
    Write-Host "Bootstrap complete. Run 'docker compose up --build' when Docker Desktop is ready."
}
