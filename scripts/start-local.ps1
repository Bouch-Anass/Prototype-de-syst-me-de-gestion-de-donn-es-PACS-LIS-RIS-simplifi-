# Restart an already initialized native Windows installation without Docker.
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [ValidateRange(1, 65535)]
    [int]$DatabasePort = 5432,
    [switch]$ResetDatabasePassword,
    [switch]$UpgradeDatabase,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$localDirectory = Join-Path $projectRoot 'data\local'
$credentialPath = Join-Path $localDirectory "postgres-app-$DatabasePort.credential.xml"
$origin = "http://127.0.0.1:$Port"
$browserJob = $null

function Test-AppReady {
    param([string]$BaseUrl)
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 1
        return $response.status -eq 'ready'
    }
    catch {
        return $false
    }
}

Push-Location -LiteralPath $projectRoot
try {
    $orthancConfigurationPath = Join-Path $localDirectory 'orthanc\orthanc.json'
    if (Test-Path -LiteralPath $orthancConfigurationPath) {
        & (Join-Path $PSScriptRoot 'start-orthanc.ps1')
        $orthancConfiguration = Get-Content -LiteralPath $orthancConfigurationPath -Raw | ConvertFrom-Json
        $orthancAccount = $orthancConfiguration.RegisteredUsers.PSObject.Properties | Select-Object -First 1
        $env:ORTHANC_BASE_URL = "http://127.0.0.1:$($orthancConfiguration.HttpPort)"
        $env:ORTHANC_USERNAME = $orthancAccount.Name
        $env:ORTHANC_PASSWORD = $orthancAccount.Value
    }

    if ($ResetDatabasePassword -and (Test-Path -LiteralPath $credentialPath)) {
        Remove-Item -LiteralPath $credentialPath
    }

    if (Test-AppReady -BaseUrl $origin) {
        Write-Host "The project is already running: $origin/frontend/"
        if (-not $NoBrowser) { Start-Process "$origin/frontend/" }
        exit 0
    }

    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    if ($listeners | Where-Object { $_.Port -eq $Port }) {
        throw "Port $Port is occupied, but the app is not ready. Check the existing server, or use -Port 8001."
    }
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Python environment missing. Complete the initial Python installation first.'
    }
    $postgres = Get-Service -Name 'postgresql-x64-*' -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -eq 'Running' }
    if (-not $postgres) {
        throw 'PostgreSQL is not running. Start its Windows service, then launch this file again.'
    }

    $secretPath = Join-Path $localDirectory 'hl7_service_secret.txt'
    if (-not (Test-Path -LiteralPath $secretPath)) {
        throw 'data\local\hl7_service_secret.txt is missing. Complete the initial local setup first.'
    }
    $env:HL7_SERVICE_SECRET = (Get-Content -LiteralPath $secretPath -Raw).Trim()
    if ($env:HL7_SERVICE_SECRET.Length -lt 32) {
        throw 'The local HL7 secret must contain at least 32 characters.'
    }

    $saveCredential = -not (Test-Path -LiteralPath $credentialPath)
    if ($saveCredential) {
        $password = Read-Host 'PostgreSQL password for account app (saved encrypted for future starts)' -AsSecureString
        $credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList 'app', $password
    }
    else {
        $credential = Import-Clixml -LiteralPath $credentialPath
    }

    $encodedPassword = [uri]::EscapeDataString($credential.GetNetworkCredential().Password)
    $env:DATABASE_URL = "postgresql+psycopg://app:${encodedPassword}@127.0.0.1:$DatabasePort/pacs_lis_ris"
    $env:APP_ENV = 'development'
    $env:APP_ORIGIN = $origin
    $env:PYTHONPATH = Join-Path $projectRoot 'backend\src'

    $databaseProbe = @'
import os
import sys
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

expected_heads = set(ScriptDirectory("backend/migrations").get_heads())
try:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
    engine.dispose()
except SQLAlchemyError:
    print("Database connection failed. Verify the app password and database settings.", file=sys.stderr)
    sys.exit(1)

if current_heads != expected_heads:
    print("The database schema is out of date. Apply the Alembic migrations before restarting.", file=sys.stderr)
    sys.exit(2)
'@
    $databaseProbe | & $python -
    if ($LASTEXITCODE -eq 2) {
        if (-not $UpgradeDatabase) {
            throw 'Run .\start-local.cmd -UpgradeDatabase to apply the migrations and start the server.'
        }

        Write-Host 'Applying Alembic migrations.'
        Push-Location -LiteralPath (Join-Path $projectRoot 'backend')
        try {
            & $python -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) { throw 'The database migration failed.' }
        }
        finally {
            Pop-Location
        }
    }
    elseif ($LASTEXITCODE -ne 0) {
        throw 'Database not ready. To enter the password again, run: .\start-local.cmd -ResetDatabasePassword'
    }
    if ($saveCredential) {
        # Windows encrypts PSCredential passwords for this Windows user and PC.
        $credential | Export-Clixml -LiteralPath $credentialPath
    }
    $credential = $null
    $password = $null
    $encodedPassword = $null

    if (-not $NoBrowser) {
        $browserJob = Start-Job -ArgumentList $origin -ScriptBlock {
            param($BaseUrl)
            for ($attempt = 0; $attempt -lt 40; $attempt++) {
                try {
                    $response = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 1
                    if ($response.status -eq 'ready') {
                        Start-Process "$BaseUrl/frontend/"
                        return
                    }
                }
                catch { }
                Start-Sleep -Milliseconds 250
            }
        }
    }

    Write-Host "Starting the project: $origin/frontend/"
    Write-Host 'Keep this window open. Press Ctrl+C to stop the server.'
    & $python -m uvicorn app.main:app --app-dir $env:PYTHONPATH --host 127.0.0.1 --port $Port --no-access-log
    if ($LASTEXITCODE -ne 0) { throw 'The application server stopped with an error.' }
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
finally {
    if ($null -ne $browserJob) {
        Stop-Job -Job $browserJob -ErrorAction SilentlyContinue
        Remove-Job -Job $browserJob -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}
