$ErrorActionPreference = "Stop"

$makeFilePath = Join-Path $PSScriptRoot "DeveloperOS.mk"

if (-not (Test-Path -LiteralPath $makeFilePath)) {
    throw "DeveloperOS shared make file was not found: $makeFilePath"
}

$resolvedMakeFilePath = (Resolve-Path -LiteralPath $makeFilePath).Path
$currentValue = [Environment]::GetEnvironmentVariable("MAKEFILES", "User")

$entries = @()
if (-not [string]::IsNullOrWhiteSpace($currentValue)) {
    $entries = $currentValue -split "\s+" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}

$alreadyRegistered = $entries | Where-Object { $_ -ieq $resolvedMakeFilePath } | Select-Object -First 1

if (-not $alreadyRegistered) {
    $entries += $resolvedMakeFilePath
}

$newValue = ($entries -join " ").Trim()
[Environment]::SetEnvironmentVariable("MAKEFILES", $newValue, "User")
$env:MAKEFILES = $newValue

Write-Host "DeveloperOS MAKEFILES registered for the current Windows user:"
Write-Host "  $resolvedMakeFilePath"
Write-Host ""
Write-Host "Open a new terminal to inherit it automatically."
Write-Host "For this PowerShell session, run:"
Write-Host "  `$env:MAKEFILES = '$newValue'"
