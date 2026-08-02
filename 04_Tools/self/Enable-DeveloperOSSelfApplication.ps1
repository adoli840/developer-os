param(
    [string]$CodexHome = $(
        if ($env:CODEX_HOME) {
            $env:CODEX_HOME
        } else {
            Join-Path $HOME ".codex"
        }
    )
)

$ErrorActionPreference = "Stop"

$developerOSRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

& (Join-Path $developerOSRoot "04_Tools\make\Enable-DeveloperOSMake.ps1")
& (Join-Path $developerOSRoot "04_Tools\bin\Enable-DeveloperOSCommands.ps1")
& (Join-Path $developerOSRoot "04_Tools\codex\Enable-DeveloperOSCodex.ps1") -CodexHome $CodexHome

Write-Host ""
Write-Host "DeveloperOS user integrations are installed."
Write-Host ""

& (Join-Path $PSScriptRoot "Test-DeveloperOSSelfApplication.ps1") -CodexHome $CodexHome -RequireUserRegistration
