[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Mount", "Unmount")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$ImagePath
)

$ErrorActionPreference = "Stop"
$allowedRoot = [System.IO.Path]::GetFullPath("X:\Docker\Forensics\vhd")
$resolved = [System.IO.Path]::GetFullPath($ImagePath)

if (-not $resolved.StartsWith($allowedRoot + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "FORENSIC_COPY_PATH_REQUIRED"
}
if ($resolved -ieq "X:\Docker\DockerDesktopWSL\disk\docker_data.vhdx") {
    throw "ORIGINAL_VHDX_FORBIDDEN"
}
if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
    throw "FORENSIC_COPY_NOT_FOUND"
}
if ($Action -eq "Mount" -and -not (Get-Item -LiteralPath $resolved).IsReadOnly) {
    throw "FORENSIC_COPY_MUST_BE_READ_ONLY"
}

if ($Action -eq "Mount") {
    & wsl.exe --mount $resolved --vhd --options "ro,noload" --name desktop-vhd-forensic
} else {
    & wsl.exe --unmount $resolved
}
if ($LASTEXITCODE -ne 0) {
    throw "WSL_FORENSIC_$($Action.ToUpperInvariant())_FAILED"
}
