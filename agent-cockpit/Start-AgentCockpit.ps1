param([int]$Port = 8020)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Create .venv and install requirements first (see README).' }
if (-not (Test-Path '.env')) { throw 'Copy .env.example to .env first.' }
if (-not (Test-Path '.agents.json')) { throw 'Run python create_agents.py first.' }
Write-Host "Klinik Cockpit · KI-Agenten: http://127.0.0.1:$Port/" -ForegroundColor Green
Write-Host 'Synthetic local demo. Stop with Ctrl+C.'
& '.\.venv\Scripts\python.exe' -m uvicorn app:app --host 127.0.0.1 --port $Port
