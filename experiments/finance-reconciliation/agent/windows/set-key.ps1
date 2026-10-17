# set-key.ps1 - set GEMINI_API_KEY for the CURRENT PowerShell session only. No API calls.
#
# Usage:  .\experiments\finance-reconciliation\agent\windows\set-key.ps1
#
# You will be prompted to paste your key into a SECURE PowerShell prompt (input hidden).
# The key is set only as an environment variable for this session. It is never written to a
# file, never printed, never committed, and never sent to any chat.
#
# NEVER paste your API key into Claude, ChatGPT, GitHub, or any chat window. Only into this
# local PowerShell prompt, on your own machine.

$ErrorActionPreference = "Stop"

$secure = Read-Host -AsSecureString "Paste your GEMINI_API_KEY (input hidden)"
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($plain)) {
    Write-Host "No key entered; nothing set." -ForegroundColor Red
    exit 1
}
$env:GEMINI_API_KEY = $plain
$plain = $null

# Confirm it is set WITHOUT printing it.
if ($env:GEMINI_API_KEY) {
    $len = $env:GEMINI_API_KEY.Length
    Write-Host "GEMINI_API_KEY is set for this session (length $len). It was not printed or saved." -ForegroundColor Green
    Write-Host "It applies only to THIS PowerShell window and disappears when you close it." -ForegroundColor Yellow
} else {
    Write-Host "Failed to set the key." -ForegroundColor Red
    exit 1
}
