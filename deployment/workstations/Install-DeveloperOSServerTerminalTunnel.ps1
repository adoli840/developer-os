[CmdletBinding()]
param(
  [string]$Server = "opc@168.107.18.16",
  [string]$SshKey = "X:/Settings/ssh/ssh-key-ops.key",
  [ValidateRange(1024, 65535)]
  [int]$LocalPort = 8092,
  [ValidateRange(1024, 65535)]
  [int]$RemotePort = 8022
)

$ErrorActionPreference = "Stop"
$ensureScript = (Resolve-Path (Join-Path $PSScriptRoot "Ensure-DeveloperOSServerTerminalTunnel.ps1")).Path
$powershell = (Get-Command powershell.exe).Source
$taskName = "DeveloperOS-Home-Server-Terminal-Tunnel"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runtimeDirectory = Join-Path $repositoryRoot ".console\server-terminal"
$wrapper = Join-Path $runtimeDirectory "home-tunnel-task.ps1"
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
$wrapperContent = @"
& '$ensureScript' -Server '$Server' -SshKey '$SshKey' -LocalPort $LocalPort -RemotePort $RemotePort
"@
Set-Content -LiteralPath $wrapper -Value $wrapperContent -Encoding utf8

$taskCommand = "`"$powershell`" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$wrapper`""
& schtasks.exe /Create `
  /TN $taskName `
  /TR $taskCommand `
  /SC MINUTE `
  /MO 5 `
  /RL LIMITED `
  /F | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Could not install the Home server terminal tunnel task."
}
$registeredTask = Get-ScheduledTask -TaskName $taskName
$taskSettings = $registeredTask.Settings
$taskSettings.DisallowStartIfOnBatteries = $false
$taskSettings.StopIfGoingOnBatteries = $false
$taskSettings.ExecutionTimeLimit = "PT2M"
Set-ScheduledTask -TaskName $taskName -Settings $taskSettings | Out-Null

& $ensureScript `
  -Server $Server `
  -SshKey $SshKey `
  -LocalPort $LocalPort `
  -RemotePort $RemotePort

Write-Output "Scheduled task installed: $taskName"
Write-Output "Private terminal URL: http://127.0.0.1:$LocalPort"
