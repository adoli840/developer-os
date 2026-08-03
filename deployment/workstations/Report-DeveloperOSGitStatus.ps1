[CmdletBinding()]
param(
  [ValidateSet("home", "office")]
  [string]$Workstation = "home",
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

function Resolve-OpenSshTool {
  param([Parameter(Mandatory = $true)][string]$Name)

  $toolName = "${Name}.exe"
  $fromPath = Get-Command $toolName -ErrorAction SilentlyContinue
  if ($null -ne $fromPath -and $fromPath.Path) {
    return $fromPath.Path
  }
  foreach ($windowsRoot in @($env:WINDIR, $env:SystemRoot, "C:\Windows") | Where-Object { $_ } | Select-Object -Unique) {
    foreach ($systemDirectory in @("Sysnative", "System32")) {
      $candidate = Join-Path $windowsRoot "$systemDirectory\OpenSSH\$toolName"
      if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        return $candidate
      }
    }
  }
  throw "Could not find $toolName."
}

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [Parameter(Mandatory = $true)][string[]]$Arguments
  )

  $output = @(& git -C $Repository @Arguments 2>$null)
  return [pscustomobject]@{
    Ok = $LASTEXITCODE -eq 0
    Lines = $output
    Text = ($output -join "`n").Trim()
  }
}

function Invoke-GitRemoteRefresh {
  param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [Parameter(Mandatory = $true)][string]$Remote,
    [Parameter(Mandatory = $true)][string]$Refspec
  )

  $previousTerminalPrompt = $env:GIT_TERMINAL_PROMPT
  $previousGcmInteractive = $env:GCM_INTERACTIVE
  $previousSshCommand = $env:GIT_SSH_COMMAND
  try {
    $env:GIT_TERMINAL_PROMPT = "0"
    $env:GCM_INTERACTIVE = "Never"
    $sshCommand = if ([string]::IsNullOrWhiteSpace($previousSshCommand)) { "ssh" } else { $previousSshCommand }
    $env:GIT_SSH_COMMAND = "$sshCommand -o BatchMode=yes -o ConnectTimeout=15"
    return Invoke-Git `
      -Repository $Repository `
      -Arguments @("fetch", "--quiet", "--no-tags", "--no-recurse-submodules", $Remote, $Refspec)
  }
  finally {
    if ($null -eq $previousTerminalPrompt) {
      Remove-Item Env:GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue
    } else {
      $env:GIT_TERMINAL_PROMPT = $previousTerminalPrompt
    }
    if ($null -eq $previousGcmInteractive) {
      Remove-Item Env:GCM_INTERACTIVE -ErrorAction SilentlyContinue
    } else {
      $env:GCM_INTERACTIVE = $previousGcmInteractive
    }
    if ($null -eq $previousSshCommand) {
      Remove-Item Env:GIT_SSH_COMMAND -ErrorAction SilentlyContinue
    } else {
      $env:GIT_SSH_COMMAND = $previousSshCommand
    }
  }
}

function Get-RepositoryStatus {
  param(
    [Parameter(Mandatory = $true)][string]$Slug,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Path
  )

  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    return [ordered]@{
      slug = $Slug
      name = $Name
      available = $false
      repository = $null
    }
  }
  $inside = Invoke-Git -Repository $Path -Arguments @("rev-parse", "--is-inside-work-tree")
  if (-not $inside.Ok) {
    return [ordered]@{
      slug = $Slug
      name = $Name
      available = $true
      repository = $null
    }
  }

  $branch = Invoke-Git -Repository $Path -Arguments @("branch", "--show-current")
  $revision = Invoke-Git -Repository $Path -Arguments @("rev-parse", "--short", "HEAD")
  $status = Invoke-Git -Repository $Path -Arguments @("status", "--porcelain")
  $upstream = Invoke-Git -Repository $Path -Arguments @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
  $upstreamRef = Invoke-Git -Repository $Path -Arguments @("rev-parse", "--symbolic-full-name", "@{u}")
  $lastCommit = Invoke-Git -Repository $Path -Arguments @("log", "-1", "--format=%cI")
  $statusLines = @($status.Lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $remoteRefreshStatus = "unknown"
  $remoteRevision = $null
  $ahead = 0
  $behind = 0
  if ($upstream.Ok) {
    $remote = if ($branch.Ok -and $branch.Text) {
      Invoke-Git -Repository $Path -Arguments @("config", "--get", "branch.$($branch.Text).remote")
    } else {
      $null
    }
    $mergeRef = if ($branch.Ok -and $branch.Text) {
      Invoke-Git -Repository $Path -Arguments @("config", "--get", "branch.$($branch.Text).merge")
    } else {
      $null
    }
    $canRefresh = (
      $null -ne $remote -and $remote.Ok -and $remote.Text -and
      $null -ne $mergeRef -and $mergeRef.Ok -and $mergeRef.Text -match "^refs/heads/" -and
      $upstreamRef.Ok -and $upstreamRef.Text -match "^refs/remotes/"
    )
    if ($canRefresh) {
      $refspec = "+$($mergeRef.Text):$($upstreamRef.Text)"
      $refresh = Invoke-GitRemoteRefresh -Repository $Path -Remote $remote.Text -Refspec $refspec
      if ($refresh.Ok) {
        $candidateRevision = Invoke-Git -Repository $Path -Arguments @("rev-parse", $upstreamRef.Text)
        $counts = Invoke-Git -Repository $Path -Arguments @("rev-list", "--left-right", "--count", "HEAD...$($upstreamRef.Text)")
        $parts = @($counts.Text -split "\s+" | Where-Object { $_ })
        if ($candidateRevision.Ok -and $candidateRevision.Text -and $counts.Ok -and $parts.Count -eq 2) {
          $remoteRefreshStatus = "success"
          $remoteRevision = $candidateRevision
          $ahead = [int]$parts[0]
          $behind = [int]$parts[1]
        } else {
          $remoteRefreshStatus = "failed"
        }
      } else {
        $remoteRefreshStatus = "failed"
      }
    } else {
      $remoteRefreshStatus = "failed"
    }
  }

  return [ordered]@{
    slug = $Slug
    name = $Name
    available = $true
    repository = [ordered]@{
      branch = if ($branch.Ok -and $branch.Text) { $branch.Text } else { "detached" }
      revision = if ($revision.Ok) { $revision.Text } else { $null }
      modified = $statusLines.Count
      staged = @($statusLines | Where-Object { $_.Length -ge 2 -and $_[0] -notin @(" ", "?") }).Count
      unstaged = @($statusLines | Where-Object { $_.Length -ge 2 -and $_[1] -notin @(" ", "?") }).Count
      untracked = @($statusLines | Where-Object { $_.StartsWith("??") }).Count
      upstream = if ($upstream.Ok) { $upstream.Text } else { $null }
      remote_revision = if ($null -ne $remoteRevision -and $remoteRevision.Ok) { $remoteRevision.Text } else { $null }
      remote_refresh_status = $remoteRefreshStatus
      ahead = $ahead
      behind = $behind
      last_commit_at = if ($lastCommit.Ok) { $lastCommit.Text } else { $null }
    }
  }
}

if ($Server -notmatch "^[A-Za-z0-9._-]+@[A-Za-z0-9.:-]+$") {
  throw "Server must use the user@host format."
}
if (-not (Test-Path -LiteralPath $SshKey -PathType Leaf)) {
  throw "SSH key not found: $SshKey"
}
if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) {
  throw "Workspace root not found: $WorkspaceRoot"
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runtimeDirectory = Join-Path $repositoryRoot ".console\workstation-reporter"
New-Item -ItemType Directory -Force -Path $runtimeDirectory > $null
$reportPath = Join-Path $runtimeDirectory "$Workstation.json"
$logPath = Join-Path $runtimeDirectory "$Workstation.log"
$ssh = Resolve-OpenSshTool -Name "ssh"
$scp = Resolve-OpenSshTool -Name "scp"
$projectDefinitions = @(
  @{ slug = "developer-os"; name = "DeveloperOS"; directory = "DeveloperOS" },
  @{ slug = "oa"; name = "OA"; directory = "oa" },
  @{ slug = "gaia"; name = "Gaia"; directory = "gaia" },
  @{ slug = "btest"; name = "bTest"; directory = "bTest" }
)

try {
  $projects = @(
    foreach ($project in $projectDefinitions) {
      Get-RepositoryStatus `
        -Slug $project.slug `
        -Name $project.name `
        -Path (Join-Path $WorkspaceRoot $project.directory)
    }
  )
  $report = [ordered]@{
    schema_version = 1
    workstation = $Workstation
    name = $workstationName
    hostname = $env:COMPUTERNAME
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    projects = $projects
  }
  $reportJson = $report | ConvertTo-Json -Depth 8
  [IO.File]::WriteAllText($reportPath, $reportJson, [Text.UTF8Encoding]::new($false))

  $inbox = "/home/opc/.developer-os-console/workstation-inbox"
  $remoteTemporary = "$inbox/$Workstation-$([guid]::NewGuid().ToString('N')).json"
  & $ssh -o BatchMode=yes -o ConnectTimeout=15 -i $SshKey $Server "install -d -m 700 $inbox"
  if ($LASTEXITCODE -ne 0) {
    throw "Could not prepare the workstation report inbox."
  }
  & $scp -o BatchMode=yes -o ConnectTimeout=15 -i $SshKey $reportPath "${Server}:$remoteTemporary"
  if ($LASTEXITCODE -ne 0) {
    throw "Could not upload the workstation report."
  }

  $validationScript = @'
set -eu
temporary='__TEMPORARY__'
target='/var/lib/developer-os-console/workstations/__WORKSTATION__.json'
python3 - "$temporary" '__WORKSTATION__' <<'PY'
import json
import sys

path, expected = sys.argv[1:]
with open(path, "r", encoding="utf-8-sig") as handle:
    value = json.load(handle)
if value.get("schema_version") != 1 or value.get("workstation") != expected:
    raise SystemExit("Invalid workstation report.")
if not isinstance(value.get("projects"), list):
    raise SystemExit("Invalid project report.")
PY
install -m 0640 "$temporary" "${target}.new"
mv -f "${target}.new" "$target"
rm -f "$temporary"
'@
  $validationScript = $validationScript.Replace("__TEMPORARY__", $remoteTemporary).Replace("__WORKSTATION__", $Workstation)
  $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($validationScript.Replace("`r`n", "`n")))
  & $ssh -o BatchMode=yes -o ConnectTimeout=15 -i $SshKey $Server "printf %s $encoded | base64 --decode | bash"
  if ($LASTEXITCODE -ne 0) {
    throw "The server rejected the workstation report."
  }
  "$(Get-Date -Format o) report uploaded" | Add-Content -LiteralPath $logPath -Encoding utf8
  Write-Output "$workstationName Git status uploaded at $($report.generated_at)."
}
catch {
  "$(Get-Date -Format o) ERROR $($_.Exception.Message)" | Add-Content -LiteralPath $logPath -Encoding utf8
  throw
}
