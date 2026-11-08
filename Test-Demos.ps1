<#
.SYNOPSIS
  Automated end-to-end test of all demos in presentation order, against the real Foundry agents.

.DESCRIPTION
  Order: Demo 01 Klinik Cockpit -> Demo 03 Entlass-Assistent -> Demo 04 Empfangs-Avatar -> Demo 02 Forschungsnavigator.
  For each demo: local unit tests (no Azure), then live tests (real model calls, incur usage):
    01  agent-cockpit\e2e_test.py          draft -> review -> event update -> approval -> dispatch   (~2 min)
    03  patient-voice\smoke_test.py        9 typed cases in 5 languages                              (~3 min)
        patient-voice\e2e_safety_test.py   medication card, stopped mix-up, 112 rule (app running)   (~2 min)
    04  hospital-avatar\smoke_test.py      8 typed cases in 5 languages (app running, voice-only)    (~7 min)
    02  research_demo.invoke --smoke       reference cohort questions against Foundry + Fabric      (~2 min)
  Missing local servers are started with Prepare-Demos.ps1. All demo state is reset at the end.
  Run it the day before; it doesn't replace one manual rehearsal with microphone and avatar video
  (docs\PROBELAUF-DE.md).

.EXAMPLE
  .\Test-Demos.ps1                       # everything (about 15-20 minutes)
  .\Test-Demos.ps1 -LocalOnly            # unit tests only, no Azure calls
  .\Test-Demos.ps1 -Only cockpit,avatar  # selected demos
#>
param(
    [ValidateSet('cockpit', 'voice', 'avatar', 'research')]
    [string[]]$Only = @('cockpit', 'voice', 'avatar', 'research'),
    [switch]$LocalOnly
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$LogDir = Join-Path $PSScriptRoot '.local\test-logs'
New-Item -ItemType Directory $LogDir -Force | Out-Null
$Results = New-Object System.Collections.Generic.List[object]

function Invoke-Check($demo, $name, $folder, [string[]]$arguments, [switch]$Live, [string]$pythonPath) {
    if ($Live -and $LocalOnly) { return }
    $python = if ($folder -eq '.') { '.\.venv\Scripts\python.exe' } else { Join-Path $folder '.venv\Scripts\python.exe' }
    $log = Join-Path $LogDir ("{0}-{1}.log" -f $demo, ($name -replace '[^\w]+', '-'))
    Write-Host ("  {0,-34}" -f $name) -NoNewline
    $started = Get-Date
    Push-Location (Join-Path $PSScriptRoot $folder)
    $previous = $env:PYTHONPATH
    if ($pythonPath) { $env:PYTHONPATH = $pythonPath }
    try {
        & (Join-Path $PSScriptRoot $python) @arguments *> $log
        $exit = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $previous
        Pop-Location
    }
    $seconds = [int]((Get-Date) - $started).TotalSeconds
    $summary = (Get-Content $log | Where-Object { $_ -match 'passed|failed|PASS$|FAIL$|cases passed' } | Select-Object -Last 1)
    if ($exit -eq 0) { Write-Host "PASS  ($seconds s) $summary" -ForegroundColor Green }
    else { Write-Host "FAIL  ($seconds s) see $log" -ForegroundColor Red }
    $Results.Add([pscustomobject]@{ Demo = $demo; Check = $name; Result = $(if ($exit -eq 0) { 'PASS' } else { 'FAIL' }); Seconds = $seconds; Log = $log })
}

function Test-Port($port) {
    try { return (Invoke-WebRequest "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { return $false }
}

if (-not $LocalOnly) {
    $needed = @{ voice = 8010; avatar = 8030 }
    $missing = $Only | Where-Object { $needed.ContainsKey($_) -and -not (Test-Port $needed[$_]) }
    if ($missing) {
        Write-Host "Starting local servers for: $($missing -join ', ')" -ForegroundColor Cyan
        & (Join-Path $PSScriptRoot 'Prepare-Demos.ps1') -NoBrowser -SkipAgentCheck | Out-Null
    }
}

$total = Get-Date
if ('cockpit' -in $Only) {
    Write-Host "`nDemo 01 · Klinik Cockpit" -ForegroundColor Cyan
    Invoke-Check '01-cockpit' 'Unit tests' 'agent-cockpit' @('-m', 'pytest', '-q', '-p', 'no:cacheprovider')
    Invoke-Check '01-cockpit' 'Live: agents end-to-end' 'agent-cockpit' @('e2e_test.py') -Live
}
if ('voice' -in $Only) {
    Write-Host "`nDemo 03 · Entlass-Assistent" -ForegroundColor Cyan
    Invoke-Check '03-voice' 'Unit tests' 'patient-voice' @('-m', 'pytest', '-q', '-p', 'no:cacheprovider')
    Invoke-Check '03-voice' 'Live: 9 cases, 5 languages' 'patient-voice' @('smoke_test.py') -Live
    Invoke-Check '03-voice' 'Live: safety layer via app' 'patient-voice' @('e2e_safety_test.py') -Live
}
if ('avatar' -in $Only) {
    Write-Host "`nDemo 04 · Empfangs-Avatar" -ForegroundColor Cyan
    Invoke-Check '04-avatar' 'Unit tests' 'hospital-avatar' @('-m', 'pytest', '-q', '-p', 'no:cacheprovider')
    Invoke-Check '04-avatar' 'Live: 8 cases, 5 languages' 'hospital-avatar' @('smoke_test.py') -Live
}
if ('research' -in $Only) {
    Write-Host "`nDemo 02 · Forschungsnavigator" -ForegroundColor Cyan
    $researchPath = Join-Path $PSScriptRoot 'research'
    Invoke-Check '02-research' 'Unit tests' '.' @('-m', 'pytest', '-c', 'research\pytest.ini', 'research\tests', '-q', '-p', 'no:cacheprovider') -pythonPath $researchPath
    Invoke-Check '02-research' 'Live: reference cohorts' '.' @('-m', 'research_demo.invoke', '--smoke') -Live -pythonPath $researchPath
}

if (-not $LocalOnly) {
    foreach ($port in 8020, 8010, 8030) {
        try { Invoke-RestMethod -Method Post "http://127.0.0.1:$port/api/reset" -TimeoutSec 5 | Out-Null } catch { }
    }
}

$failed = @($Results | Where-Object Result -eq 'FAIL')
Write-Host "`nSummary ($([int]((Get-Date) - $total).TotalMinutes) min)" -ForegroundColor Cyan
$Results | Format-Table Demo, Check, Result, Seconds -AutoSize | Out-Host
if ($failed) {
    Write-Host "$($failed.Count) check(s) failed. Logs: .local\test-logs" -ForegroundColor Red
    Write-Host 'Live model answers vary; read the log before changing anything, and re-run the single demo with -Only.'
    exit 1
}
Write-Host 'All checks passed. Demo state is reset. Do one manual rehearsal with microphone and avatar (docs\PROBELAUF-DE.md).' -ForegroundColor Green
