[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [switch]$Check
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath $ProjectPath).Path
$destinationRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Destination))
$projectPrefix = $projectRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if ($destinationRoot -ne $projectRoot -and
    -not $destinationRoot.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must remain inside the project repository."
}

$sourceRoot = Join-Path $PSScriptRoot "assets"
$files = @("roadmap-view.css", "roadmap-view.js")

if ($Check) {
    $problems = @()
    foreach ($file in $files) {
        $source = Join-Path $sourceRoot $file
        $destination = Join-Path $destinationRoot $file
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            $problems += "$file is missing"
            continue
        }
        $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
        $destinationHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
        if ($sourceHash -ne $destinationHash) {
            $problems += "$file does not match the DeveloperOS canonical asset"
        }
    }
    if ($problems.Count -gt 0) {
        $problems | ForEach-Object { Write-Error $_ }
        exit 1
    }
    Write-Host "Roadmap web assets match DeveloperOS version 3.0.1."
    exit 0
}

New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
foreach ($file in $files) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $file) -Destination (Join-Path $destinationRoot $file) -Force
}
Write-Host "Installed DeveloperOS roadmap web assets version 3.0.1 to $destinationRoot"
