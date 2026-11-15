# Start a project-local Orthanc without installing a Windows service.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDirectory = Join-Path $projectRoot 'data\local\orthanc-runtime'
$stateDirectory = Join-Path $projectRoot 'data\local\orthanc'
$executable = Join-Path $runtimeDirectory 'Orthanc.exe'
$configurationPath = Join-Path $stateDirectory 'orthanc.json'

New-Item -ItemType Directory -Path $runtimeDirectory, $stateDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $executable)) {
    Write-Host 'Downloading Orthanc 1.13.0 from the official distribution.'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://orthanc.uclouvain.be/downloads/windows-64/orthanc/1.13.0/Orthanc.exe' -OutFile $executable
}
if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant() -ne '2d507df95dcabb479d3931992f5a2607cde105dbe38b4562f43653e7ce10c424') {
    throw 'The Orthanc executable does not match the pinned official download.'
}
if (-not (Test-Path -LiteralPath $configurationPath)) {
    $randomBytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
    $configuration = @{
        Name = 'PACS-LIS-RIS local'
        StorageDirectory = (Join-Path $stateDirectory 'storage')
        IndexDirectory = (Join-Path $stateDirectory 'storage')
        HttpPort = 8042
        RemoteAccessAllowed = $false
        AuthenticationEnabled = $true
        RegisteredUsers = @{ app = [Convert]::ToBase64String($randomBytes) }
        DicomServerEnabled = $false
        HttpDescribeErrors = $false
    }
    $configurationJson = $configuration | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($configurationPath, $configurationJson, (New-Object Text.UTF8Encoding($false)))
}
$configuration = Get-Content -LiteralPath $configurationPath -Raw | ConvertFrom-Json
$account = $configuration.RegisteredUsers.PSObject.Properties | Select-Object -First 1
$basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$($account.Name):$($account.Value)"))
$headers = @{ Authorization = "Basic $basic" }
$url = "http://127.0.0.1:$($configuration.HttpPort)/system"
try {
    $system = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 2
    if ($system.Name -eq $configuration.Name) { Write-Host 'Local Orthanc is ready.'; return }
    throw 'The Orthanc port belongs to another installation.'
}
catch {
    if ([System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
            Where-Object { $_.Port -eq $configuration.HttpPort }) {
        throw 'Port 8042 is already in use. The existing service was left untouched.'
    }
}
$process = Start-Process -FilePath $executable -ArgumentList @('"' + $configurationPath + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDirectory 'stdout.log') -RedirectStandardError (Join-Path $stateDirectory 'stderr.log')
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $system = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 1
        if ($system.Name -eq $configuration.Name) {
            $process.Id | Set-Content -LiteralPath (Join-Path $stateDirectory 'process-id.txt')
            Write-Host 'Local Orthanc is ready on port 8042.'
            return
        }
    }
    catch { }
    if ($process.HasExited) { throw 'Orthanc stopped during startup. See data/local/orthanc/stderr.log.' }
    Start-Sleep -Milliseconds 250
}
throw 'Orthanc did not become ready. See data/local/orthanc/stderr.log.'
