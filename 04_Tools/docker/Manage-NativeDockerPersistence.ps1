[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Install", "Status", "EnsureRunning", "Start", "Stop", "KeepAlive")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$taskName = "DeveloperOS-WSL-Docker-Keepalive"
$distribution = "Ubuntu"
$serviceName = "docker-wsl.service"
$socketPath = "/run/docker-wsl.sock"
$scriptPath = $PSCommandPath
$runtimeDirectory = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) ".console"
$logPath = Join-Path $runtimeDirectory "native-docker-persistence.log"
$wslExecutable = (Get-Command wsl.exe -ErrorAction Stop).Source
$powershellExecutable = (Get-Command powershell.exe -ErrorAction Stop).Source

function Write-PersistenceLog {
    param([string]$Message)

    if (-not (Test-Path -LiteralPath $runtimeDirectory)) {
        New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
    }
    $timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
    Add-Content -LiteralPath $logPath -Value "$timestamp $Message" -Encoding UTF8
}

function Invoke-Ubuntu {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )

    & $wslExecutable -d $distribution --exec @Arguments
    $exitCode = $LASTEXITCODE
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "Ubuntu command failed with exit code ${exitCode}: $($Arguments -join ' ')"
    }
    return $exitCode
}

function Test-UbuntuRunning {
    $runningDistributions = @(& $wslExecutable --list --running --quiet 2>$null)
    foreach ($entry in $runningDistributions) {
        if (($entry -replace "`0", "").Trim() -eq $distribution) {
            return $true
        }
    }
    return $false
}

function Get-KeeperProcessCount {
    $escapedScriptPath = [regex]::Escape($scriptPath)
    return @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -match $escapedScriptPath -and
                $_.CommandLine -match '(?i)-Action\s+KeepAlive'
            }
    ).Count
}

function Wait-ForTaskState {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("Ready", "Running")]
        [string]$ExpectedState,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $state = (Get-ScheduledTask -TaskName $taskName -ErrorAction Stop).State.ToString()
        if ($state -eq $ExpectedState) {
            return
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    throw "Scheduled Task $taskName did not reach $ExpectedState within $TimeoutSeconds seconds."
}

function Wait-ForNativeHealth {
    param([int]$TimeoutSeconds = 60)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-UbuntuRunning) {
            & $wslExecutable -d $distribution --exec /bin/bash -lc "systemctl is-active --quiet $serviceName && test -S $socketPath && docker -H unix://$socketPath info >/dev/null 2>&1"
            if ($LASTEXITCODE -eq 0) {
                return
            }
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)

    throw "Native Docker did not become healthy within $TimeoutSeconds seconds."
}

function Get-PersistenceStatus {
    $scheduledTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $scheduledTask) {
        Write-Output "TASK=ABSENT"
        Write-Output "KEEPER_PROCESS_COUNT=0"
        Write-Output "UBUNTU=UNKNOWN"
        Write-Output "SERVICE=UNKNOWN"
        Write-Output "SOCKET=UNKNOWN"
        Write-Output "SERVER=UNKNOWN"
        return
    }

    $taskInfo = $scheduledTask | Get-ScheduledTaskInfo
    $keeperCount = Get-KeeperProcessCount
    $ubuntuRunning = Test-UbuntuRunning
    $serviceState = "unavailable"
    $socketState = "unavailable"
    $serverVersion = "unavailable"

    if ($ubuntuRunning) {
        $serviceState = (& $wslExecutable -d $distribution --exec systemctl is-active $serviceName 2>$null | Select-Object -First 1)
        & $wslExecutable -d $distribution --exec test -S $socketPath
        if ($LASTEXITCODE -eq 0) {
            $socketState = "healthy"
            $serverVersion = (& $wslExecutable -d $distribution --exec docker -H "unix://$socketPath" info --format '{{.ServerVersion}}' 2>$null | Select-Object -First 1)
        }
    }

    Write-Output "TASK=$($scheduledTask.State)"
    Write-Output "LAST_RESULT=$($taskInfo.LastTaskResult)"
    Write-Output "KEEPER_PROCESS_COUNT=$keeperCount"
    Write-Output "UBUNTU=$(if ($ubuntuRunning) { 'Running' } else { 'Stopped' })"
    Write-Output "SERVICE=$serviceState"
    Write-Output "SOCKET=$socketState"
    Write-Output "SERVER=$serverVersion"
    Write-Output "LOG=$logPath"
}

function Start-Persistence {
    $scheduledTask = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    if ($scheduledTask.State -ne "Running") {
        Start-ScheduledTask -TaskName $taskName
    }
    Wait-ForTaskState -ExpectedState Running
    Wait-ForNativeHealth

    $keeperCount = Get-KeeperProcessCount
    if ($keeperCount -ne 1) {
        throw "Expected exactly one keeper process, found $keeperCount."
    }
    Get-PersistenceStatus
}

function Stop-Persistence {
    $scheduledTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($scheduledTask -and $scheduledTask.State -eq "Running") {
        Stop-ScheduledTask -TaskName $taskName
        Wait-ForTaskState -ExpectedState Ready
    }

    if (Test-UbuntuRunning) {
        Invoke-Ubuntu -Arguments @("systemctl", "stop", $serviceName) | Out-Null
        & $wslExecutable --terminate $distribution | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to terminate $distribution."
        }
    }
    Write-PersistenceLog "canonical persistence stopped"
    Get-PersistenceStatus
}

function Install-Persistence {
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask -and $existingTask.State -eq "Running") {
        Stop-ScheduledTask -TaskName $taskName
        Wait-ForTaskState -ExpectedState Ready
    }

    Invoke-Ubuntu -Arguments @("systemctl", "disable", "--now", "docker.service", "docker.socket") | Out-Null
    Invoke-Ubuntu -Arguments @("systemctl", "enable", $serviceName) | Out-Null

    $taskArguments = "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`" -Action KeepAlive"
    $taskAction = New-ScheduledTaskAction -Execute $powershellExecutable -Argument $taskArguments
    $userId = "$env:USERDOMAIN\$env:USERNAME"
    $taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
    $taskSettings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -Hidden

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $taskAction `
        -Trigger $taskTrigger `
        -Principal $taskPrincipal `
        -Settings $taskSettings `
        -Description "DeveloperOS-owned canonical persistence for Ubuntu native Docker; starts no project Compose runtime." `
        -Force | Out-Null

    Write-PersistenceLog "canonical Scheduled Task installed or repaired"
    Start-Persistence
}

function Invoke-KeepAlive {
    Write-PersistenceLog "keeper started pid=$PID"
    & $wslExecutable -d $distribution --exec /bin/bash -lc "systemctl start $serviceName && exec /bin/sleep infinity"
    $exitCode = $LASTEXITCODE
    Write-PersistenceLog "keeper exited unexpectedly code=$exitCode pid=$PID"
    exit 1
}

switch ($Action) {
    "Install" { Install-Persistence }
    "Status" { Get-PersistenceStatus }
    "EnsureRunning" { Start-Persistence }
    "Start" { Start-Persistence }
    "Stop" { Stop-Persistence }
    "KeepAlive" { Invoke-KeepAlive }
}
