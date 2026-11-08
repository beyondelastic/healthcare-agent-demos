<#
.SYNOPSIS
  Prepares all demos before a presentation: checks, starts the local servers, resets state, opens the browser.

.DESCRIPTION
  Presentation order: Demo 01 Klinik Cockpit -> Demo 03 Entlass-Assistent -> Demo 04 Empfangs-Avatar
  -> Demo 02 Forschungsnavigator (Teams). Demos 01, 03 and 04 run locally; Demo 02 runs in Teams.

  1. Checks each app folder (.venv, .env, agents created).
  2. Checks the Azure CLI sign-in for the demo tenant.
  3. Checks that the Foundry agents exist (no model calls, no cost).
  4. Stops old demo servers on the demo ports and starts them in the background (logs in .local\logs).
  5. Waits until every server answers, then resets all demo state.
  6. Checks the Fabric capacity for Demo 02 (FABRIC_CAPACITY_RESOURCE_ID in the root .env); -ResumeFabric starts it.
     Optional (-CheckResearch): runs the research smoke test against the published Foundry agent (live, costs).
  7. Opens the presentation tabs in order and prints a checklist.

.EXAMPLE
  .\Prepare-Demos.ps1                                # full preparation
  .\Prepare-Demos.ps1 -ResumeFabric -CheckResearch   # also start Fabric and check the research agent live
  .\Prepare-Demos.ps1 -Stop -PauseFabric             # after the event: stop servers, pause Fabric (billing)
#>
param(
    [switch]$Stop,
    [switch]$CheckResearch,
    [switch]$ResumeFabric,
    [switch]$PauseFabric,
    [switch]$NoBrowser,
    [switch]$SkipAgentCheck
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

$Demos = @(
    @{ Key = 'cockpit'; Name = 'Demo 01 · Klinik Cockpit';     Folder = 'agent-cockpit';   Port = 8020
       Pages = @('/'); Reset = '/api/reset'; Needs = @('.agents.json')
       Agents = 'list(settings.agent_versions()[k]["name"] for k in ("writer", "reviewer"))' },
    @{ Key = 'voice';   Name = 'Demo 03 · Entlass-Assistent';  Folder = 'patient-voice';   Port = 8010
       Pages = @('/', '/team'); Reset = '/api/reset'; Needs = @()
       Agents = '[settings.AGENT_NAME]' },
    @{ Key = 'avatar';  Name = 'Demo 04 · Empfangs-Avatar';    Folder = 'hospital-avatar'; Port = 8030
       Pages = @('/', '/team'); Reset = '/api/reset'; Needs = @()
       Agents = '[settings.AGENT_NAME]' }
)
$LogDir = Join-Path $PSScriptRoot '.local\logs'
New-Item -ItemType Directory $LogDir -Force | Out-Null

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "  [OK]   $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  [WARN] $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host "  [FAIL] $text" -ForegroundColor Red; $script:Failures++ }
$script:Failures = 0

function Stop-DemoServer($demo) {
    $connections = Get-NetTCPConnection -LocalPort $demo.Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
        if ($process.CommandLine -match 'uvicorn' -and $process.CommandLine -match "--port $($demo.Port)") {
            Stop-Process -Id $connection.OwningProcess -Force
            Ok "$($demo.Name): stopped old server (PID $($connection.OwningProcess))"
        } else {
            Fail "$($demo.Name): port $($demo.Port) is used by another program: $($process.CommandLine)"
        }
    }
}

function Read-EnvValue($file, $name) {
    if (-not (Test-Path $file)) { return $null }
    $line = Get-Content $file | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
    if ($line) { return ($line -split '=', 2)[1].Trim() }
    return $null
}

function Get-FabricState($capacity) {
    $state = az rest --method get --url "https://management.azure.com$($capacity)?api-version=2023-11-01" --query properties.state -o tsv 2>$null
    if ($LASTEXITCODE -ne 0) { return 'unknown (no access?)' }
    return $state
}

if ($Stop) {
    Step 'Stopping local demo servers'
    foreach ($demo in $Demos) { Stop-DemoServer $demo }
    $capacity = Read-EnvValue (Join-Path $PSScriptRoot '.env') 'FABRIC_CAPACITY_RESOURCE_ID'
    if ($PauseFabric -and $capacity) {
        az rest --method post --url "https://management.azure.com$capacity/suspend?api-version=2023-11-01" -o none 2>$null
        if ($LASTEXITCODE -eq 0) { Ok 'Fabric capacity pause requested (stops billing; affects every workload on it)' }
        else { Fail 'Could not pause the Fabric capacity' }
    }
    return
}

# ---------------------------------------------------------------- 1. Folders
Step '1/7 Checking the demo folders'
foreach ($demo in $Demos) {
    $folder = Join-Path $PSScriptRoot $demo.Folder
    $missing = @('.venv\Scripts\python.exe', '.env') + $demo.Needs | Where-Object { -not (Test-Path (Join-Path $folder $_)) }
    if ($missing) { Fail "$($demo.Name): missing $($missing -join ', ') (see $($demo.Folder)\README.md)" }
    else { Ok "$($demo.Name): ready" }
}
if ($script:Failures) { throw 'Fix the setup first (see the README of the demo).' }

# ---------------------------------------------------------------- 2. Azure sign-in
Step '2/7 Checking the Azure sign-in'
$tenant = Read-EnvValue (Join-Path $PSScriptRoot 'patient-voice\.env') 'AZURE_TENANT_ID'
$tokenArgs = @('account', 'get-access-token', '--resource', 'https://ai.azure.com', '--query', 'expiresOn', '-o', 'tsv')
if ($tenant) { $tokenArgs += @('--tenant', $tenant) }
$expires = & az @tokenArgs 2>$null
if ($LASTEXITCODE -ne 0 -or -not $expires) {
    Warn "No valid token for the demo tenant. Starting 'az login'..."
    if ($tenant) { az login --tenant $tenant | Out-Null } else { az login | Out-Null }
    $expires = & az @tokenArgs 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Azure sign-in failed.' }
}
Ok "Signed in (token valid until $expires)"

# ---------------------------------------------------------------- 3. Foundry agents
Step '3/7 Checking the Foundry agents (no model calls)'
if ($SkipAgentCheck) { Warn 'Skipped (-SkipAgentCheck)' }
else {
    foreach ($demo in $Demos) {
        $code = @"
import settings
from azure.ai.projects import AIProjectClient
names = $($demo.Agents)
with settings.credential() as c, AIProjectClient(endpoint=settings.ENDPOINT, credential=c, allow_preview=True) as p:
    for k in names:
        info = p.agents.get(agent_name=k).as_dict()
        print(k + ' v' + str(info.get('versions', {}).get('latest', {}).get('version', '?')))
"@
        Push-Location (Join-Path $PSScriptRoot $demo.Folder)
        $output = $code | & '.\.venv\Scripts\python.exe' - 2>&1
        $exit = $LASTEXITCODE
        Pop-Location
        if ($exit -eq 0) { Ok "$($demo.Name): $(($output | Out-String).Trim() -replace '\r?\n', ', ')" }
        else { Fail "$($demo.Name): $(($output | Select-Object -Last 1))" }
    }
}

# ---------------------------------------------------------------- 4. Servers
Step '4/7 Starting the local demo servers'
foreach ($demo in $Demos) {
    Stop-DemoServer $demo
    $folder = Join-Path $PSScriptRoot $demo.Folder
    $log = Join-Path $LogDir "$($demo.Key).log"
    $process = Start-Process -FilePath (Join-Path $folder '.venv\Scripts\python.exe') `
        -ArgumentList @('-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', $demo.Port) `
        -WorkingDirectory $folder -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    Ok "$($demo.Name): started on port $($demo.Port) (PID $($process.Id), log .local\logs\$($demo.Key).log)"
}

# ---------------------------------------------------------------- 5. Health + reset
Step '5/7 Waiting for the servers and resetting the demo state'
foreach ($demo in $Demos) {
    $base = "http://127.0.0.1:$($demo.Port)"
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        try { $ready = (Invoke-WebRequest "$base/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { Start-Sleep 1 }
    }
    if (-not $ready) { Fail "$($demo.Name): no answer on $base (see .local\logs\$($demo.Key).log.err)"; continue }
    try {
        Invoke-RestMethod -Method Post "$base$($demo.Reset)" | Out-Null
        Ok "$($demo.Name): running and reset ($base)"
    } catch { Fail "$($demo.Name): reset failed: $($_.Exception.Message)" }
}

# ---------------------------------------------------------------- 6. Research (Teams)
Step '6/7 Demo 02 · Forschungsnavigator (Teams)'
$capacity = Read-EnvValue (Join-Path $PSScriptRoot '.env') 'FABRIC_CAPACITY_RESOURCE_ID'
if ($capacity) {
    $state = Get-FabricState $capacity
    if ($state -eq 'Paused' -and $ResumeFabric) {
        Write-Host '  Resuming the Fabric capacity (billed while active) ...'
        az rest --method post --url "https://management.azure.com$capacity/resume?api-version=2023-11-01" -o none 2>$null
        for ($i = 0; $i -lt 40 -and $state -ne 'Active'; $i++) { Start-Sleep 6; $state = Get-FabricState $capacity }
    }
    if ($state -eq 'Active') { Ok 'Fabric capacity is active' }
    elseif ($state -eq 'Paused') { Fail 'Fabric capacity is paused: the research agent cannot query data. Run with -ResumeFabric.' }
    else { Warn "Fabric capacity state: $state" }
} else {
    Warn 'Fabric capacity not checked (set FABRIC_CAPACITY_RESOURCE_ID in the root .env).'
}
if ($CheckResearch) {
    if (-not (Test-Path '.venv\Scripts\python.exe')) { Fail 'Root .venv for research missing (see research\README.md)' }
    else {
        $env:PYTHONPATH = Join-Path $PSScriptRoot 'research'
        Write-Host '  Running the live research smoke test (Foundry agent + Fabric, takes 1-3 minutes) ...'
        & '.\.venv\Scripts\python.exe' -m research_demo.invoke --smoke *> (Join-Path $LogDir 'research-smoke.log')
        if ($LASTEXITCODE -eq 0) { Ok 'Research agent answered the reference questions (log .local\logs\research-smoke.log)' }
        else { Fail 'Research smoke test failed (see .local\logs\research-smoke.log); check Fabric capacity and sign-in' }
    }
} else {
    Warn 'Not checked live. Run with -CheckResearch, or test the baseline question in Teams (docs\RESEARCH-SCRIPT-DE.md).'
}

# ---------------------------------------------------------------- 7. Browser + checklist
Step '7/7 Opening the presentation tabs'
$tabs = foreach ($demo in $Demos) { foreach ($page in $demo.Pages) { "http://127.0.0.1:$($demo.Port)$page" } }
if ($NoBrowser) { Warn 'Skipped (-NoBrowser)' }
else {
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($edge) { Start-Process $edge -ArgumentList (@('--new-window') + $tabs) } else { $tabs | ForEach-Object { Start-Process $_ } }
    Ok "Opened $($tabs.Count) tabs in presentation order"
}

Write-Host "`nPresentation order and URLs" -ForegroundColor Cyan
Write-Host '  1. Demo 01 Klinik Cockpit      http://127.0.0.1:8020/            (F11, Zuruecksetzen ist erledigt)'
Write-Host '  2. Demo 03 Entlass-Assistent   http://127.0.0.1:8010/  +  /team'
Write-Host '  3. Demo 04 Empfangs-Avatar     http://127.0.0.1:8030/  +  /team'
Write-Host '  4. Demo 02 Forschungsnavigator Microsoft Teams (Presenter-Konto, neues Gespraech)'
Write-Host "`nBefore the audience arrives" -ForegroundColor Cyan
Write-Host '  - Headset/microphone selected; notifications off; second screen layout checked.'
Write-Host '  - If you rehearsed the avatar: wait at least one minute before the live start (rate limit).'
Write-Host '  - Teams: correct tenant/profile, Forschungsnavigator opens, Fabric capacity running.'
Write-Host '  - Walkthrough with expected results: docs\PROBELAUF-DE.md. Stop servers afterwards: .\Prepare-Demos.ps1 -Stop'
if ($script:Failures) { Write-Host "`n$($script:Failures) problem(s) found - see above." -ForegroundColor Red; exit 1 }
Write-Host "`nAll local demos are ready." -ForegroundColor Green
