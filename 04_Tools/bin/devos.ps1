param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$binDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$developerOsRoot = Resolve-Path (Join-Path $binDir "..\..")

if ($Arguments.Count -eq 0) {
    Write-Host "DeveloperOS command"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  devos git-check"
    Write-Host ""
    Write-Host "Preferred workspace command:"
    Write-Host "  make git-check"
    exit 0
}

switch ($Arguments[0]) {
    "git-check" {
        & (Join-Path $developerOsRoot "04_Tools\git\Invoke-GitDashboard.ps1")
    }
    default {
        Write-Error "Unknown DeveloperOS command: $($Arguments[0])"
        exit 1
    }
}
