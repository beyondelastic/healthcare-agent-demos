param(
    [switch]$Install,
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($Install) {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r 'backend\requirements.lock.txt'
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    Push-Location frontend
    try {
        npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    finally { Pop-Location }
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    throw 'Run .\Start-Cockpit.ps1 -Install once to prepare the environment.'
}
Push-Location frontend
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
finally { Pop-Location }
Write-Host "Klinik Studio: http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host 'Synthetic local demo only. Stop with Ctrl+C. Live AI requires Foundry authentication and FOUNDRY_MODEL.'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
