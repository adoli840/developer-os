[CmdletBinding()]
param(
    [ValidateSet("Audit", "Apply")]
    [string]$Action = "Audit"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$distro = "Ubuntu"
$linuxUser = "devops"
$configLinuxPath = "/home/devops/.docker-native/config.json"
$configWindowsPath = "\\wsl.localhost\Ubuntu\home\devops\.docker-native\config.json"
$pluginRoot = "/usr/local/lib/docker/cli-plugins"
$desktopTargetPrefix = "/mnt/wsl/docker-desktop/"
$developerOSRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$auditDirectory = Join-Path $developerOSRoot ".console"
$auditPath = Join-Path $auditDirectory "native-docker-infrastructure-audit.json"
$auditHistoryPath = Join-Path $auditDirectory "native-docker-infrastructure-audit.jsonl"

function Invoke-Wsl {
    param([string[]]$Arguments, [switch]$AsRoot)
    $base = @("-d", $distro)
    if ($AsRoot) {
        $base += @("-u", "root")
    }
    $output = @(& wsl.exe @base -- @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "WSL_COMMAND_FAILED: $($Arguments[0])"
    }
    return $output
}

function Get-DesktopSymlinks {
    $paths = @(Invoke-Wsl -Arguments @(
        "find", $pluginRoot, "-maxdepth", "1", "-type", "l", "-print"
    )) | Where-Object { $_ }
    $items = @()
    foreach ($path in $paths) {
        $target = (@(Invoke-Wsl -Arguments @("readlink", "--", $path)) -join "").Trim()
        if (-not $target.StartsWith($desktopTargetPrefix, [StringComparison]::Ordinal)) {
            continue
        }
        $name = Split-Path -Leaf $path
        if (-not $name.StartsWith("docker-", [StringComparison]::Ordinal)) {
            throw "UNEXPECTED_DESKTOP_SYMLINK: $path"
        }
        $metadata = (@(Invoke-Wsl -Arguments @("stat", "-c", "%U:%G:%a", "--", $path)) -join "").Trim()
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $packageOwner = @(& wsl.exe -d $distro -- dpkg-query -S $path 2>$null)
            $packageExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($packageExitCode -ne 0) {
            $packageOwner = @("UNOWNED")
        }
        $items += [ordered]@{
            path = $path
            target = $target
            owner_mode = $metadata
            package_owner = ($packageOwner -join "`n")
        }
    }
    return @($items)
}

function Write-CanonicalConfig {
    $directory = Split-Path -Parent $configWindowsPath
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $directory -Force
    }
    $expected = [ordered]@{ credsStore = "pass" }
    if (Test-Path -LiteralPath $configWindowsPath -PathType Leaf) {
        $current = Get-Content -LiteralPath $configWindowsPath -Raw | ConvertFrom-Json
        $keys = @($current.PSObject.Properties.Name)
        if ($keys.Count -ne 1 -or $keys[0] -ne "credsStore" -or $current.credsStore -ne "pass") {
            throw "CANONICAL_CONFIG_CONFLICT"
        }
        $null = Invoke-Wsl -AsRoot -Arguments @("chown", "${linuxUser}:${linuxUser}", "/home/devops/.docker-native", $configLinuxPath)
        $null = Invoke-Wsl -AsRoot -Arguments @("chmod", "700", "/home/devops/.docker-native")
        $null = Invoke-Wsl -AsRoot -Arguments @("chmod", "600", $configLinuxPath)
        return
    }
    $temporary = "$configWindowsPath.tmp-$PID"
    $json = ($expected | ConvertTo-Json -Compress) + "`n"
    [System.IO.File]::WriteAllText($temporary, $json, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $configWindowsPath
    $null = Invoke-Wsl -AsRoot -Arguments @("chown", "${linuxUser}:${linuxUser}", $configLinuxPath)
    $null = Invoke-Wsl -AsRoot -Arguments @("chown", "${linuxUser}:${linuxUser}", "/home/devops/.docker-native")
    $null = Invoke-Wsl -AsRoot -Arguments @("chmod", "700", "/home/devops/.docker-native")
    $null = Invoke-Wsl -AsRoot -Arguments @("chmod", "600", $configLinuxPath)
}

$before = @(Get-DesktopSymlinks)
$configExisted = Test-Path -LiteralPath $configWindowsPath -PathType Leaf

if ($Action -eq "Apply") {
    Write-CanonicalConfig
    foreach ($item in $before) {
        $currentTarget = (@(Invoke-Wsl -Arguments @("readlink", "--", $item.path)) -join "").Trim()
        if ($currentTarget -ne $item.target -or -not $currentTarget.StartsWith($desktopTargetPrefix, [StringComparison]::Ordinal)) {
            throw "DESKTOP_SYMLINK_CHANGED_DURING_SEAL: $($item.path)"
        }
        $null = Invoke-Wsl -AsRoot -Arguments @("rm", "--", $item.path)
    }
}

$after = @(Get-DesktopSymlinks)
$config = $null
if (Test-Path -LiteralPath $configWindowsPath -PathType Leaf) {
    $value = Get-Content -LiteralPath $configWindowsPath -Raw | ConvertFrom-Json
    $config = [ordered]@{
        path = $configLinuxPath
        credsStore = $value.credsStore
        keys = @($value.PSObject.Properties.Name)
    }
}

$report = [ordered]@{
    schema_version = 2
    action = $Action
    distro = $distro
    canonical_config = $config
    config_existed_before = $configExisted
    desktop_symlinks_before = $before
    desktop_symlinks_after = $after
    native_assets_retained = @(
        "/usr/bin/docker",
        "/usr/libexec/docker/cli-plugins/docker-compose",
        "/run/docker-wsl.sock",
        "/var/lib/docker-wsl"
    )
    completed_at = [DateTimeOffset]::UtcNow.ToString("o")
}

if (-not (Test-Path -LiteralPath $auditDirectory -PathType Container)) {
    $null = New-Item -ItemType Directory -Path $auditDirectory -Force
}
$compactReport = $report | ConvertTo-Json -Depth 8 -Compress
Add-Content -LiteralPath $auditHistoryPath -Value $compactReport -Encoding utf8
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $auditPath -Encoding utf8
$report | ConvertTo-Json -Depth 8
