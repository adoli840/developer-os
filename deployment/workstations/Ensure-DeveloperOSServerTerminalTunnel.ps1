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

function Resolve-OpenSsh {
  $fromPath = Get-Command "ssh.exe" -ErrorAction SilentlyContinue
  if ($null -ne $fromPath -and $fromPath.Path) {
    return $fromPath.Path
  }
  $windowsRoots = @($env:WINDIR, $env:SystemRoot, "C:\Windows") |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique
  foreach ($windowsRoot in $windowsRoots) {
    foreach ($systemDirectory in @("Sysnative", "System32")) {
      $candidate = Join-Path $windowsRoot "$systemDirectory\OpenSSH\ssh.exe"
      if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        return $candidate
      }
    }
  }
  throw "Could not find ssh.exe."
}

function Test-TerminalTunnel {
  param([int]$Port)

  try {
    $response = Invoke-RestMethod `
      -Uri "http://127.0.0.1:$Port/healthz" `
      -TimeoutSec 2 `
      -ErrorAction Stop
    return $response.status -eq "ok"
  }
  catch {
    return $false
  }
}

if ($Server -notmatch "^[A-Za-z0-9._-]+@[A-Za-z0-9.:-]+$") {
  throw "Server must use the user@host format."
}
if (-not (Test-Path -LiteralPath $SshKey -PathType Leaf)) {
  throw "SSH key not found: $SshKey"
}
if (Test-TerminalTunnel -Port $LocalPort) {
  Write-Output "Terminal tunnel ready: http://127.0.0.1:$LocalPort"
  return
}

$listener = Get-NetTCPConnection `
  -LocalAddress 127.0.0.1 `
  -LocalPort $LocalPort `
  -State Listen `
  -ErrorAction SilentlyContinue
if ($listener) {
  throw "Local port $LocalPort is already in use by another service."
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runtimeDirectory = Join-Path $repositoryRoot ".console\server-terminal"
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
$stdoutPath = Join-Path $runtimeDirectory "tunnel.out.log"
$stderrPath = Join-Path $runtimeDirectory "tunnel.err.log"
$pidPath = Join-Path $runtimeDirectory "tunnel.pid"
$ssh = Resolve-OpenSsh
$arguments = @(
  "-N",
  "-L", "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}",
  "-o", "BatchMode=yes",
  "-o", "ConnectTimeout=15",
  "-o", "ExitOnForwardFailure=yes",
  "-o", "ServerAliveInterval=30",
  "-o", "ServerAliveCountMax=3",
  "-i", $SshKey,
  $Server
)
$process = Start-Process `
  -FilePath $ssh `
  -ArgumentList $arguments `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdoutPath `
  -RedirectStandardError $stderrPath `
  -PassThru
Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii

$deadline = (Get-Date).AddSeconds(20)
do {
  Start-Sleep -Milliseconds 400
  if ($process.HasExited) {
    $detail = if (Test-Path -LiteralPath $stderrPath) {
      (Get-Content -LiteralPath $stderrPath -Tail 10) -join [Environment]::NewLine
    }
    else {
      "No SSH diagnostic output is available."
    }
    throw "SSH terminal tunnel stopped before it became ready.`n$detail"
  }
} while (-not (Test-TerminalTunnel -Port $LocalPort) -and (Get-Date) -lt $deadline)

if (-not (Test-TerminalTunnel -Port $LocalPort)) {
  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  throw "The SSH terminal tunnel did not become ready."
}

Write-Output "Terminal tunnel ready: http://127.0.0.1:$LocalPort"
