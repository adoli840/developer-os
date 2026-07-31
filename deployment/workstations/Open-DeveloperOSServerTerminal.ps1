[CmdletBinding()]
param(
  [ValidateSet("developer-os", "oa", "gaia")]
  [string]$Project = "developer-os",
  [string]$Server = "opc@168.107.18.16",
  [string]$SshKey = "X:/Settings/ssh/ssh-key-ops.key",
  [ValidateRange(1024, 65535)]
  [int]$LocalPort = 8092,
  [ValidateRange(1024, 65535)]
  [int]$RemotePort = 8022
)

$ErrorActionPreference = "Stop"
$ensureScript = Join-Path $PSScriptRoot "Ensure-DeveloperOSServerTerminalTunnel.ps1"
& $ensureScript `
  -Server $Server `
  -SshKey $SshKey `
  -LocalPort $LocalPort `
  -RemotePort $RemotePort

Start-Process "http://127.0.0.1:$LocalPort/?project=$Project"
