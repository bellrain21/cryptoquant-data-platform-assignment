param(
    [switch]$SkipDbt
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

New-Item -ItemType Directory -Force "data/delta/ethereum_logs", "data/analytics" | Out-Null
$ValidationRoot = "data/tmp/dbt_validation/local"
New-Item -ItemType Directory -Force $ValidationRoot | Out-Null
$env:DELTA_LOGS_PATH = (Join-Path (Resolve-Path $ValidationRoot) "ethereum_logs").Replace("\", "/")
$env:DUCKDB_PATH = (Join-Path (Resolve-Path $ValidationRoot) "ethereum_analytics.duckdb").Replace("\", "/")
New-Item -ItemType Directory -Force "data/duckdb_extensions" | Out-Null
$env:DUCKDB_EXTENSION_DIR = (Resolve-Path "data/duckdb_extensions").Path.Replace("\", "/")

$DevCompose = @(
    "compose",
    "-f",
    "docker-compose.yaml",
    "-f",
    ".devcontainer/docker-compose.devcontainer.yaml"
)

$results = New-Object System.Collections.Generic.List[string]

function Invoke-Check {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host "== $Name =="
    & $Command
    if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
        $results.Add("PASS $Name")
    } else {
        $results.Add("FAIL $Name exit=$LASTEXITCODE")
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker command was not found. Install Docker Desktop and enable WSL2 backend."
    exit 1
}

Invoke-Check "docker compose config" { docker @DevCompose config --quiet }
Invoke-Check "workspace-dev build" { docker @DevCompose build workspace-dev }
Invoke-Check "python version" { docker @DevCompose run --rm --no-deps workspace-dev python --version }
Invoke-Check "pip check" { docker @DevCompose run --rm --no-deps workspace-dev python -m pip check }
Invoke-Check "airflow version" { docker @DevCompose run --rm --no-deps workspace-dev airflow version }
Invoke-Check "ruff check" { docker @DevCompose run --rm --no-deps workspace-dev ruff check . }
Invoke-Check "pytest" { docker @DevCompose run --rm --no-deps workspace-dev python -m pytest -q }

if (-not $SkipDbt) {
    Invoke-Check "dbt debug" {
        docker @DevCompose run --rm --no-deps workspace-dev dbt debug --project-dir dbt --profiles-dir dbt
    }
    Invoke-Check "dbt build" {
        docker @DevCompose run --rm --no-deps workspace-dev python scripts/create_dbt_validation_fixture.py --root /workspace/data/tmp/dbt_validation/local
        docker @DevCompose run --rm --no-deps -e DELTA_LOGS_PATH=/workspace/data/tmp/dbt_validation/local/ethereum_logs -e DUCKDB_PATH=/workspace/data/tmp/dbt_validation/local/ethereum_analytics.duckdb -e DUCKDB_EXTENSION_DIR=/workspace/data/duckdb_extensions workspace-dev dbt build --project-dir dbt --profiles-dir dbt --select tag:ethereum_hourly --vars '{ "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T01:00:00Z" }'
    }
}

Write-Host "== Summary =="
$results | ForEach-Object { Write-Host $_ }
