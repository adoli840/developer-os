[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pidPath = Join-Path $repositoryRoot ".console\server-terminal\tunnel.pid"
if (-not (Test-Path -LiteralPath $pidPath -PathType Leaf)) {
  Write-Output "No recorded terminal tunnel is running."
  return
}

$tunnelPid = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
$process = Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue
if ($null -eq $process) {
  Remove-Item -LiteralPath $pidPath -Force
  Write-Output "The recorded terminal tunnel has already stopped."
  return
}
if ($process.ProcessName -ne "ssh") {
  throw "Recorded PID $tunnelPid is not an SSH process. It was not stopped."
}
Stop-Process -Id $tunnelPid
Remove-Item -LiteralPath $pidPath -Force
Write-Output "DeveloperOS server terminal tunnel stopped."
