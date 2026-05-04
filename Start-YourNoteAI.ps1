$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"

function Assert-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Name directory was not found: $Path"
    }
}

function Escape-SingleQuoted {
    param([Parameter(Mandatory = $true)][string] $Value)
    return $Value.Replace("'", "''")
}

function Test-Ollama {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Select-LaunchMode {
    Write-Host ""
    Write-Host "What do you want to start?"
    Write-Host "1. Backend"
    Write-Host "2. Frontend"
    Write-Host "3. Both"
    Write-Host ""

    while ($true) {
        $Choice = Read-Host "Choose 1, 2, or 3"

        switch ($Choice.Trim()) {
            "1" { return "Backend" }
            "2" { return "Frontend" }
            "3" { return "Both" }
            default { Write-Warning "Please choose 1, 2, or 3." }
        }
    }
}

$LaunchMode = Select-LaunchMode
$StartBackend = $LaunchMode -eq "Backend" -or $LaunchMode -eq "Both"
$StartFrontend = $LaunchMode -eq "Frontend" -or $LaunchMode -eq "Both"

if ($StartBackend) {
    Assert-Directory -Path $BackendDir -Name "Backend"
}

if ($StartFrontend) {
    Assert-Directory -Path $FrontendDir -Name "Frontend"
}

if ($StartBackend -and -not (Test-Ollama)) {
    $OllamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($OllamaCommand) {
        Write-Host "Starting Ollama..."
        Start-Process -FilePath $OllamaCommand.Source -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    } else {
        Write-Warning "Ollama was not found. Install Ollama or add it to PATH before generating summaries."
    }
}

$LanAddress = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and
        $_.PrefixOrigin -ne 'WellKnown'
    } |
    Sort-Object {
        if ($_.InterfaceAlias -match 'Wi-Fi|Ethernet') { 0 } else { 1 }
    } |
    Select-Object -First 1 -ExpandProperty IPAddress

if (-not $LanAddress) {
    $LanAddress = "127.0.0.1"
}

$BackendUrl = "http://${LanAddress}:8000"
$BackendDirForCommand = Escape-SingleQuoted -Value $BackendDir
$FrontendDirForCommand = Escape-SingleQuoted -Value $FrontendDir
$BackendUrlForCommand = Escape-SingleQuoted -Value $BackendUrl

$BackendCommand = @"
`$ErrorActionPreference = 'Stop'
`$Host.UI.RawUI.WindowTitle = 'YourNoteAI Backend'
Set-Location -LiteralPath '$BackendDirForCommand'

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    Write-Host 'Creating backend virtual environment...'
    python -m venv .venv
}

`$DependencyMarker = '.venv\.requirements-installed'
if (
    -not (Test-Path -LiteralPath `$DependencyMarker) -or
    (Get-Item -LiteralPath 'requirements.txt').LastWriteTime -gt (Get-Item -LiteralPath `$DependencyMarker).LastWriteTime
) {
    Write-Host 'Installing/updating backend dependencies...'
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    New-Item -ItemType File -Path `$DependencyMarker -Force | Out-Null
}

Write-Host ''
Write-Host 'Starting YourNoteAI backend at http://127.0.0.1:8000'
Write-Host 'Network URL for phone/Expo: $BackendUrlForCommand'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Write-Host ''
Read-Host 'Backend stopped. Press Enter to close this window'
"@

$FrontendCommand = @"
`$ErrorActionPreference = 'Stop'
`$Host.UI.RawUI.WindowTitle = 'YourNoteAI Frontend'
Set-Location -LiteralPath '$FrontendDirForCommand'
`$env:EXPO_PUBLIC_BACKEND_URL = '$BackendUrlForCommand'

if (-not (Test-Path -LiteralPath 'node_modules')) {
    Write-Host 'Installing frontend dependencies...'
    npm install
}

Write-Host ''
Write-Host 'Starting YourNoteAI frontend with Expo'
Write-Host 'Default backend URL: $BackendUrlForCommand'
npm run start

Write-Host ''
Read-Host 'Frontend stopped. Press Enter to close this window'
"@

$BackendEncodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($BackendCommand))
$FrontendEncodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($FrontendCommand))

if ($StartBackend) {
    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-EncodedCommand", $BackendEncodedCommand
    )
}

if ($StartBackend -and $StartFrontend) {
    Start-Sleep -Seconds 2
}

if ($StartFrontend) {
    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-EncodedCommand", $FrontendEncodedCommand
    )
}

Write-Host "YourNoteAI is starting."
Write-Host "Mode: $LaunchMode"
if ($StartBackend) {
    Write-Host "Backend window: http://127.0.0.1:8000"
    Write-Host "Backend dashboard: http://127.0.0.1:8000/"
}
Write-Host "Phone/Expo backend URL: $BackendUrl"
if ($StartFrontend) {
    Write-Host "Frontend window: Expo Metro / QR code"
}
Write-Host ""
Write-Host "Close the opened YourNoteAI window or windows when you want to stop the app."
