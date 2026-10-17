# pilot.ps1 - the development pilot (PAID: ~$0.72 estimated, capped at $2).
#
# 5 dev cases x {Flash-medium, Argon-medium} x 1 trial, scored by the independent grader.
# Prerequisites: smoke.ps1 passed, GEMINI_API_KEY set for this session.
# The frozen TEST set stays sealed; this runs the DEV incidents only.
#
# Usage:
#   .\experiments\finance-reconciliation\agent\windows\pilot.ps1 -DryRun   # free preflight
#   .\experiments\finance-reconciliation\agent\windows\pilot.ps1           # paid, asks to confirm

param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

if (-not $env:GEMINI_API_KEY -and -not $DryRun) {
    Write-Host "GEMINI_API_KEY not set. Run set-key.ps1 first." -ForegroundColor Red; exit 1
}

if ($DryRun) {
    & $py -m agent.run_live --mode pilot --dry-run
} else {
    Write-Host "This makes PAID calls (~`$0.72 estimated, capped at `$2)." -ForegroundColor Yellow
    & $py -m agent.run_live --mode pilot --cap 2 --go
    Write-Host ""
    Write-Host "Pilot done. Review results in experiments\finance-reconciliation\results\runs\ and the ledger." -ForegroundColor Green
    Write-Host "Share the results for approval before the frozen test run (Phase 8C)." -ForegroundColor Yellow
}
