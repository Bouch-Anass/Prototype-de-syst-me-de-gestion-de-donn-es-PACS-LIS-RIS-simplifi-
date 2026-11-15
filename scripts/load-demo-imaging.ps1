# Prepare the native PACS, reconnect the local backend, and import public test images.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$backendSource = Join-Path $projectRoot 'backend\src'
$localDirectory = Join-Path $projectRoot 'data\local'
$databaseCredentialPath = Join-Path $localDirectory 'postgres-app-5432.credential.xml'
$accountPath = Join-Path $localDirectory 'demo-login.credential.xml'
if (-not (Test-Path -LiteralPath $databaseCredentialPath) -or -not (Test-Path -LiteralPath $accountPath)) {
    throw 'Initialize the native application and its saved demo credentials before loading the images.'
}
$accounts = Import-Clixml -LiteralPath $accountPath
$credentials = @{}
foreach ($role in @('physician', 'radiologist', 'imaging_technician')) {
    $account = ($accounts | Where-Object Role -eq $role).Credential
    if ($null -eq $account) { throw "Saved demo credentials are missing for role $role." }
    $credentials[$role] = @{ username = $account.UserName; password = $account.GetNetworkCredential().Password }
}

& (Join-Path $PSScriptRoot 'start-orthanc.ps1')
$orthanc = Get-Content -LiteralPath (Join-Path $localDirectory 'orthanc\orthanc.json') -Raw | ConvertFrom-Json
$orthancAccount = $orthanc.RegisteredUsers.PSObject.Properties | Select-Object -First 1
$env:ORTHANC_BASE_URL = "http://127.0.0.1:$($orthanc.HttpPort)"
$env:ORTHANC_USERNAME = $orthancAccount.Name
$env:ORTHANC_PASSWORD = $orthancAccount.Value
$databaseCredential = Import-Clixml -LiteralPath $databaseCredentialPath
$databasePassword = [uri]::EscapeDataString($databaseCredential.GetNetworkCredential().Password)
$env:DATABASE_URL = "postgresql+psycopg://app:${databasePassword}@127.0.0.1:5432/pacs_lis_ris"
$env:HL7_SERVICE_SECRET = (Get-Content -LiteralPath (Join-Path $localDirectory 'hl7_service_secret.txt') -Raw).Trim()
$env:APP_ENV = 'development'
$env:APP_ORIGIN = 'http://127.0.0.1:8000'
$env:PYTHONPATH = $backendSource

$listeners = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
foreach ($processId in @($listeners.OwningProcess | Select-Object -Unique)) {
    if ($null -eq $processId) { continue }
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
    if ($existing.CommandLine -notmatch 'uvicorn' -or -not $existing.CommandLine.Contains($projectRoot)) {
        throw 'Port 8000 belongs to another application; it was left untouched.'
    }
    Write-Host 'Reconnecting the local backend to Orthanc.'
    Stop-Process -Id $processId
    Wait-Process -Id $processId -Timeout 10 -ErrorAction SilentlyContinue
}
$serverArguments = @('-m', 'uvicorn', 'app.main:app', '--app-dir', ('"' + $backendSource + '"'), '--host', '127.0.0.1', '--port', '8000', '--no-access-log')
$server = Start-Process -FilePath $python -ArgumentList $serverArguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localDirectory 'app-stdout.log') -RedirectStandardError (Join-Path $localDirectory 'app-stderr.log')
$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/ready' -TimeoutSec 1
        if ($response.status -eq 'ready') { $ready = $true; break }
    }
    catch { }
    if ($server.HasExited) { throw 'The backend stopped. See data/local/app-stderr.log.' }
    Start-Sleep -Milliseconds 250
}
if (-not $ready) { throw 'The backend did not become ready. See data/local/app-stderr.log.' }
$server.Id | Set-Content -LiteralPath (Join-Path $localDirectory 'app-process-id.txt')
Push-Location -LiteralPath $projectRoot
try {
    $credentials | ConvertTo-Json -Depth 4 | & $python (Join-Path $PSScriptRoot 'seed_public_dicom.py') --import
    if ($LASTEXITCODE -ne 0) { throw 'The public DICOM import failed. Review the error above.' }
}
finally { Pop-Location }
Write-Host 'Images are ready: DEMO-P001, Imagerie, Afficher l apercu.'
