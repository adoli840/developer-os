$ErrorActionPreference = "Stop"

$binDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()

if ($currentPath) {
    $parts = $currentPath -split ";"
}

if ($parts -notcontains $binDir) {
    $newPath = if ($currentPath) { "$currentPath;$binDir" } else { $binDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "DeveloperOS command directory added to the user PATH:"
    Write-Host $binDir
    Write-Host ""
    Write-Host "Open a new terminal, then run:"
    Write-Host "  devos git-check"
} else {
    Write-Host "DeveloperOS command directory is already in the user PATH:"
    Write-Host $binDir
}
