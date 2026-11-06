param([switch]$Install, [int]$Port = 8010)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($Install -or -not (Test-Path '.venv\Scripts\python.exe')) {
    if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path '.env')) { throw 'Copy .env.example to .env and set FOUNDRY_PROJECT_ENDPOINT first.' }
Write-Host "Brief mit QR-Code:   http://127.0.0.1:$Port/" -ForegroundColor Green
Write-Host "Patientenansicht:    http://127.0.0.1:$Port/patient" -ForegroundColor Green
Write-Host "Behandlungsteam:     http://127.0.0.1:$Port/team" -ForegroundColor Green
Write-Host 'Synthetic local demo. Stop with Ctrl+C.'
& '.\.venv\Scripts\python.exe' -m uvicorn app:app --host 127.0.0.1 --port $Port
