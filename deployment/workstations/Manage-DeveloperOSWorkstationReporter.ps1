[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("Install", "Remove", "Status")]
  [string]$Action,
  [Parameter(Mandatory = $true)]
  [ValidateSet("home", "office")]
  [string]$Workstation,
  [ValidateRange(2, 60)]
  [int]$IntervalMinutes = 5,
  [string]$Server = "opc@168.107.18.16",
  [string]$SshKey = "X:/Settings/ssh/ssh-key-ops.key",
  [string]$WorkspaceRoot = "X:/Projects"
)

$ErrorActionPreference = "Stop"
$workstationNames = @{
  home = "Home"
  office = "Office"
}
$workstationName = $workstationNames[$Workstation]
$taskName = "DeveloperOS Workstation Report - $workstationName"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$reportScript = Join-Path $PSScriptRoot "Report-DeveloperOSGitStatus.ps1"
$hiddenLauncher = Join-Path $PSScriptRoot "Run-DeveloperOSWorkstationReporterHidden.vbs"

function Quote-TaskArgument {
  param([Parameter(Mandatory = $true)][string]$Value)

  if ($Value.Contains('"')) {
    throw "Task arguments cannot contain a double quote."
  }
  return '"' + $Value + '"'
}

function Get-ReporterTask {
  return Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}

switch ($Action) {
  "Install" {
    if (-not (Test-Path -LiteralPath $reportScript -PathType Leaf)) {
      throw "Workstation report script not found: $reportScript"
    }
    if (-not (Test-Path -LiteralPath $hiddenLauncher -PathType Leaf)) {
      throw "Hidden workstation launcher not found: $hiddenLauncher"
    }
    if (-not (Test-Path -LiteralPath $SshKey -PathType Leaf)) {
      throw "SSH key not found: $SshKey"
    }
    if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) {
      throw "Workspace root not found: $WorkspaceRoot"
    }

    $resolvedSshKey = (Resolve-Path -LiteralPath $SshKey).Path
    $resolvedWorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
    $powerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
    $scriptHost = (Get-Command wscript.exe -ErrorAction Stop).Source
    $taskArguments = @(
      (Quote-TaskArgument $hiddenLauncher)
      (Quote-TaskArgument $powerShell)
      "-NoLogo"
      "-NoProfile"
      "-NonInteractive"
      "-WindowStyle Hidden"
      "-ExecutionPolicy Bypass"
      "-File $(Quote-TaskArgument $reportScript)"
      "-Workstation $(Quote-TaskArgument $Workstation)"
      "-Server $(Quote-TaskArgument $Server)"
      "-SshKey $(Quote-TaskArgument $resolvedSshKey)"
      "-WorkspaceRoot $(Quote-TaskArgument $resolvedWorkspaceRoot)"
    ) -join " "

    $scheduledAction = New-ScheduledTaskAction `
      -Execute $scriptHost `
      -Argument $taskArguments `
      -WorkingDirectory $repositoryRoot
    $trigger = New-ScheduledTaskTrigger `
      -Once `
      -At (Get-Date).AddMinutes(1) `
      -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    $settings = New-ScheduledTaskSettingsSet `
      -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries `
      -StartWhenAvailable `
      -Hidden `
      -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
      -MultipleInstances IgnoreNew `
      -RestartCount 2 `
      -RestartInterval (New-TimeSpan -Minutes 1)
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-ScheduledTaskPrincipal `
      -UserId $identity.Name `
      -LogonType Interactive `
      -RunLevel Limited

    Register-ScheduledTask `
      -TaskName $taskName `
      -Action $scheduledAction `
      -Trigger $trigger `
      -Settings $settings `
      -Principal $principal `
      -Description "Upload $workstationName DeveloperOS repository status every $IntervalMinutes minutes while the user session is active." `
      -Force > $null
    Start-ScheduledTask -TaskName $taskName
    Write-Output "$taskName installed for $($identity.Name) and started."
  }

  "Remove" {
    $task = Get-ReporterTask
    if ($null -eq $task) {
      Write-Output "$taskName is not installed."
      break
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Output "$taskName removed."
  }

  "Status" {
    $task = Get-ReporterTask
    if ($null -eq $task) {
      [pscustomobject]@{
        TaskName = $taskName
        Installed = $false
      } | Format-List
      break
    }
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
    [pscustomobject]@{
      TaskName = $taskName
      Installed = $true
      State = $task.State
      LastRunTime = $taskInfo.LastRunTime
      LastTaskResult = $taskInfo.LastTaskResult
      NextRunTime = $taskInfo.NextRunTime
    } | Format-List
  }
}
