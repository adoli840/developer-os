[CmdletBinding()]
param(
  [ValidateSet("home")]
  [string]$Workstation = "home",
  [string]$Server = "opc@168.107.18.16",
  [string]$SshKey = "X:/Settings/ssh/ssh-key-ops.key",
  [string]$WorkspaceRoot = "X:/Projects"
)

$ErrorActionPreference = "Stop"
$reporter = (Resolve-Path (Join-Path $PSScriptRoot "Report-DeveloperOSGitStatus.ps1")).Path
$powershell = (Get-Command powershell.exe).Source
$taskName = "DeveloperOS-Home-Git-Reporter"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runtimeDirectory = Join-Path $repositoryRoot ".console\workstation-reporter"
$wrapper = Join-Path $runtimeDirectory "home-task.ps1"
New-Item -ItemType Directory -Force -Path $runtimeDirectory > $null
$wrapperContent = @"
& '$reporter' -Workstation '$Workstation' -Server '$Server' -SshKey '$SshKey' -WorkspaceRoot '$WorkspaceRoot'
"@
Set-Content -LiteralPath $wrapper -Value $wrapperContent -Encoding utf8

$taskCommand = "`"$powershell`" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$wrapper`""
& schtasks.exe /Create `
  /TN $taskName `
  /TR $taskCommand `
  /SC MINUTE `
  /MO 5 `
  /RL LIMITED `
  /F > $null
if ($LASTEXITCODE -ne 0) {
  throw "Could not install the Home Git reporter scheduled task."
}
$registeredTask = Get-ScheduledTask -TaskName $taskName
$taskSettings = $registeredTask.Settings
$taskSettings.DisallowStartIfOnBatteries = $false
$taskSettings.StopIfGoingOnBatteries = $false
$taskSettings.ExecutionTimeLimit = "PT2M"
$taskSettings.Hidden = $true
Set-ScheduledTask -TaskName $taskName -Settings $taskSettings > $null
& $reporter `
  -Workstation $Workstation `
  -Server $Server `
  -SshKey $SshKey `
  -WorkspaceRoot $WorkspaceRoot
if ($LASTEXITCODE -ne 0) {
  throw "The initial Home Git status report failed."
}

Write-Output "Scheduled task installed: $taskName"
Write-Output "Reporting interval: every 5 minutes while the current user session is available"
