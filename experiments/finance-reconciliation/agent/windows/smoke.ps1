# smoke.ps1 - the two-model live smoke test (PAID: ~$0.14 estimated, <$2 worst-case).
#
# Prerequisites: setup.ps1 has run, and set-key.ps1 has set GEMINI_API_KEY for this session.
# Makes ONE short function-call round trip per model (Flash, then Argon) to confirm live
# compatibility. Stops if either model fails.
#
# Usage:
#   .\experiments\finance-reconciliation\agent\windows\smoke.ps1 -DryRun   # free preflight
#   .\experiments\finance-reconciliation\agent\windows\smoke.ps1           # paid, asks to confirm

param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

if (-not $env:GEMINI_API_KEY -and -not $DryRun) {
    Write-Host "GEMINI_API_KEY not set. Run set-key.ps1 first." -ForegroundColor Red; exit 1
}

if ($DryRun) {
    & $py -m agent.run_live --mode smoke --dry-run
} else {
    Write-Host "This makes PAID calls (~`$0.14 estimated, capped at `$1)." -ForegroundColor Yellow
    & $py -m agent.run_live --mode smoke --cap 1 --go
}
