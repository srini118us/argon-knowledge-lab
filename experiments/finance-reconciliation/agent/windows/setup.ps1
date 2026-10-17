# setup.ps1 - one-time environment setup on Windows (PowerShell). No API calls.
# Run from the repository root:  .\experiments\finance-reconciliation\agent\windows\setup.ps1
#
# Creates a virtual environment, installs dependencies, and runs the offline test suite.
# This script NEVER asks for or prints an API key.

$ErrorActionPreference = "Stop"
Write-Host "== Experiment 3 setup (offline) ==" -ForegroundColor Cyan

# 1. venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment .venv ..."
    python -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"

# 2. dependencies
Write-Host "Installing dependencies ..."
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet duckdb pytest "google-genai>=2.30.1"

# 3. offline test suite (no key, no network)
Write-Host "Running the offline test suite ..." -ForegroundColor Cyan
& $py -m pytest experiments\finance-reconciliation\tests -q
if ($LASTEXITCODE -ne 0) { Write-Host "Offline tests FAILED. Stop and investigate." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Setup complete. Offline tests passed." -ForegroundColor Green
Write-Host "Next: set your key for THIS session (see set-key.ps1) then run smoke.ps1." -ForegroundColor Yellow
