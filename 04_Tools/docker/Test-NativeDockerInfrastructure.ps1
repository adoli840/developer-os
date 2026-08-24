$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$developerOSRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$launcher = Join-Path $developerOSRoot "04_Tools\bin\devos-native-docker.cmd"
$config = "\\wsl.localhost\Ubuntu\home\devops\.docker-native\config.json"
$failures = New-Object System.Collections.Generic.List[string]

function Test-Condition {
    param([bool]$Condition, [string]$Name, [string]$Detail)
    if ($Condition) {
        Write-Host "PASS ${Name}: $Detail"
    } else {
        Write-Host "FAIL ${Name}: $Detail"
        $script:failures.Add("${Name}: $Detail")
    }
}

$info = @(& $launcher info --format "Server={{.ServerVersion}} Root={{.DockerRootDir}}" 2>&1)
Test-Condition ($LASTEXITCODE -eq 0 -and ($info -join "`n") -match "Root=/var/lib/docker-wsl") "Native daemon" "launcher uses /var/lib/docker-wsl"

$compose = @(& $launcher compose version 2>&1)
Test-Condition ($LASTEXITCODE -eq 0 -and ($compose -join "`n") -match "v5\.4\.0") "Native Compose" "launcher uses the packaged native plugin"

$context = @(& docker context show 2>$null)
Test-Condition (($context -join "").Trim() -eq "desktop-linux") "Context isolation" "native launcher works while the Windows context remains desktop-linux"

if (Test-Path -LiteralPath $config -PathType Leaf) {
    $configValue = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
    $keys = @($configValue.PSObject.Properties.Name)
    Test-Condition ($keys.Count -eq 1 -and $keys[0] -eq "credsStore" -and $configValue.credsStore -eq "pass") "Canonical config" "only the native pass helper is configured"
    $modes = @(& wsl.exe -d Ubuntu -- stat -c %a /home/devops/.docker-native /home/devops/.docker-native/config.json 2>$null)
    Test-Condition ($modes.Count -eq 2 -and $modes[0] -eq "700" -and $modes[1] -eq "600") "Canonical config permissions" "directory is 700 and config is 600"
} else {
    Test-Condition $false "Canonical config" "config is missing"
}

$symlinks = @(& wsl.exe -d Ubuntu -- find /usr/local/lib/docker/cli-plugins -maxdepth 1 -type l -print 2>$null)
$desktopSymlinks = @()
foreach ($path in $symlinks) {
    $target = @(& wsl.exe -d Ubuntu -- readlink -- $path 2>$null)
    if (($target -join "").StartsWith("/mnt/wsl/docker-desktop/", [StringComparison]::Ordinal)) {
        $desktopSymlinks += $path
    }
}
Test-Condition ($desktopSymlinks.Count -eq 0) "Desktop plugin isolation" "no Docker CLI plugin resolves through the Desktop WSL mount"

$helper = @(& wsl.exe -d Ubuntu -- command -v docker-credential-pass 2>$null)
$passwordStore = @(& wsl.exe -d Ubuntu -- test -f /home/devops/.password-store/.gpg-id 2>$null)
Test-Condition ($helper.Count -eq 1 -and $LASTEXITCODE -eq 0 -and ($passwordStore.Count -eq 0)) "Credential helper" "docker-credential-pass and initialized pass store are available"

if ($failures.Count -gt 0) {
    throw "Native Docker infrastructure check failed: $($failures -join '; ')"
}

Write-Host "Native Docker infrastructure check passed."
