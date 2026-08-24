[CmdletBinding()]
param(
  [ValidateSet("Deploy", "Status", "Logs", "Restart", "Stop", "Backup", "VerifyBackup", "BackupStatus", "UsageStatus", "TerminalStatus", "TerminalLogs")]
  [string]$Action = "Deploy",
  [string]$Server = "opc@168.107.18.16",
  [string]$SshKey = "X:/Settings/ssh/ssh-key-ops.key",
  [string]$OpenAiEnv = "X:/Projects/DeveloperOS/.env"
)

$ErrorActionPreference = "Stop"

function Resolve-OpenSshTool {
  param([Parameter(Mandatory = $true)][string]$Name)

  $toolName = "${Name}.exe"
  $fromPath = Get-Command $toolName -ErrorAction SilentlyContinue
  if ($null -ne $fromPath -and $fromPath.Path) {
    return $fromPath.Path
  }
  $windowsRoots = @($env:WINDIR, $env:SystemRoot, "C:\Windows") |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique
  foreach ($windowsRoot in $windowsRoots) {
    foreach ($systemDirectory in @("Sysnative", "System32")) {
      $candidate = Join-Path $windowsRoot "$systemDirectory\OpenSSH\$toolName"
      if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        return $candidate
      }
    }
  }
  throw "Could not find $toolName."
}

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [Parameter(Mandatory = $true)][string]$FailureMessage
  )

  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$FailureMessage (exit code $LASTEXITCODE)."
  }
}

function Invoke-RemoteScript {
  param(
    [Parameter(Mandatory = $true)][string]$Script,
    [Parameter(Mandatory = $true)][string]$FailureMessage
  )

  $normalized = $Script.Replace("`r`n", "`n").Replace("`r", "`n")
  $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($normalized))
  Invoke-Checked -Command $script:ssh -Arguments @(
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15",
    "-i", $SshKey,
    $Server,
    "printf %s $encoded | base64 --decode | bash"
  ) -FailureMessage $FailureMessage
}

if ($Server -notmatch "^[A-Za-z0-9._-]+@[A-Za-z0-9.:-]+$") {
  throw "Server must use the user@host format."
}
if (-not (Test-Path -LiteralPath $SshKey -PathType Leaf)) {
  throw "SSH key not found: $SshKey"
}

$script:ssh = Resolve-OpenSshTool -Name "ssh"
$scp = Resolve-OpenSshTool -Name "scp"

if ($Action -ne "Deploy") {
  $command = switch ($Action) {
    "Status" { "sudo systemctl --no-pager --full status developer-os-console developer-os-terminal; systemctl list-timers developer-os-backup.timer developer-os-backup-verify.timer developer-os-openai-usage.timer --no-pager; curl --fail --silent http://127.0.0.1:8080/healthz; echo; curl --fail --silent http://127.0.0.1:8022/healthz" }
    "Logs" { "sudo journalctl -u developer-os-console --no-pager -n 120" }
    "Restart" { "sudo systemctl restart developer-os-console; sudo systemctl is-active developer-os-console" }
    "Stop" { "sudo systemctl stop developer-os-console; sudo systemctl is-active developer-os-console || true" }
    "Backup" { "sudo systemctl start developer-os-backup.service; sudo systemctl --no-pager --full status developer-os-backup.service" }
    "VerifyBackup" { "sudo systemctl start developer-os-backup-verify.service; sudo systemctl --no-pager --full status developer-os-backup-verify.service" }
    "BackupStatus" { "systemctl list-timers developer-os-backup.timer developer-os-backup-verify.timer --no-pager; sudo journalctl -u developer-os-backup.service -u developer-os-backup-verify.service --no-pager -n 80" }
    "UsageStatus" { "systemctl list-timers developer-os-openai-usage.timer --no-pager; sudo systemctl --no-pager --full status developer-os-openai-usage.service || true; sudo journalctl -u developer-os-openai-usage.service --no-pager -n 60; test -s /var/lib/developer-os-console/openai-usage.json && echo OPENAI_USAGE_SNAPSHOT=present || echo OPENAI_USAGE_SNAPSHOT=missing; test -s /var/lib/developer-os-console/oracle-usage.json && echo ORACLE_USAGE_SNAPSHOT=present || echo ORACLE_USAGE_SNAPSHOT=missing" }
    "TerminalStatus" { "sudo systemctl --no-pager --full status developer-os-terminal; curl --fail --silent http://127.0.0.1:8022/healthz" }
    "TerminalLogs" { "sudo journalctl -u developer-os-terminal --no-pager -n 120" }
  }
  Invoke-RemoteScript -Script $command -FailureMessage "Console action $Action failed"
  return
}

$adminKeyConfigured = $false
$budgetConfigured = $false
if (-not (Test-Path -LiteralPath $OpenAiEnv -PathType Leaf)) {
  throw "OpenAI environment file not found: $OpenAiEnv"
}
foreach ($line in [System.IO.File]::ReadLines($OpenAiEnv)) {
  if ($line -match '^\s*OPENAI_ADMIN_API_KEY\s*=\s*(.+?)\s*$') {
    $value = $matches[1].Trim().Trim('"').Trim("'")
    $adminKeyConfigured = $value.StartsWith("sk-admin-") -and $value.Length -gt 20
  }
  if ($line -match '^\s*OPENAI_MONTHLY_BUDGET_USD\s*=\s*(.+?)\s*$') {
    try {
      $budget = [decimal]::Parse($matches[1].Trim().Trim('"').Trim("'"), [Globalization.CultureInfo]::InvariantCulture)
      $budgetConfigured = $budget -ge 0
    }
    catch {
      $budgetConfigured = $false
    }
  }
}
if (-not $adminKeyConfigured) {
  throw "OPENAI_ADMIN_API_KEY is missing or invalid in $OpenAiEnv."
}
if (-not $budgetConfigured) {
  throw "OPENAI_MONTHLY_BUDGET_USD is missing or invalid in $OpenAiEnv."
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$worktreeChanges = @(& git -C $repositoryRoot status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
  throw "Could not inspect the DeveloperOS working tree."
}
if ($worktreeChanges.Count -gt 0) {
  throw "Deployment requires a clean working tree. Commit and push every intended change first."
}

$branch = (& git -C $repositoryRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
  throw "Deployment requires a checked-out Git branch."
}
if ($branch -ne "main") {
  throw "Deployment is allowed only from main; current branch is $branch."
}

$upstream = (& git -C $repositoryRoot rev-parse --abbrev-ref --symbolic-full-name "@{upstream}").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($upstream)) {
  throw "The main branch must track origin/main before deployment."
}
if ($upstream -ne "origin/main") {
  throw "The main branch must track origin/main; current upstream is $upstream."
}

Invoke-Checked -Command "git" -Arguments @(
  "-C", $repositoryRoot,
  "fetch", "--quiet", "origin", "main"
) -FailureMessage "Could not refresh origin/main"

$headRevision = (& git -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Could not determine the local DeveloperOS revision."
}
$upstreamRevision = (& git -C $repositoryRoot rev-parse "@{upstream}").Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Could not determine the upstream DeveloperOS revision."
}
if ($headRevision -ne $upstreamRevision) {
  throw "Local main and origin/main differ. Pull or push until they match before deployment."
}

$revision = (& git -C $repositoryRoot rev-parse --short HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Could not determine the DeveloperOS revision."
}
$revisionLabel = $revision
$archive = Join-Path ([System.IO.Path]::GetTempPath()) "developer-os-console-$timestamp.tar.gz"
$openAiTransferEnv = Join-Path ([System.IO.Path]::GetTempPath()) "developer-os-openai-$timestamp.env"
$remoteArchive = "/home/opc/.developer-os-console/transfer/$timestamp.tar.gz"
$remoteOpenAiEnv = "/home/opc/.developer-os-console/transfer/$timestamp-openai.env"

try {
  $allowedOpenAiNames = @("OPENAI_ADMIN_API_KEY", "OPENAI_MONTHLY_BUDGET_USD")
  $openAiTransferLines = @{}
  foreach ($line in [System.IO.File]::ReadLines($OpenAiEnv)) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
      $name = $matches[1]
      if ($allowedOpenAiNames -contains $name) {
        if ($openAiTransferLines.ContainsKey($name)) {
          throw "Duplicate $name entry in $OpenAiEnv."
        }
        $openAiTransferLines[$name] = $line
      }
    }
  }
  if ($openAiTransferLines.Count -ne $allowedOpenAiNames.Count) {
    throw "The OpenAI deployment environment is incomplete."
  }
  [System.IO.File]::WriteAllLines(
    $openAiTransferEnv,
    @($openAiTransferLines["OPENAI_ADMIN_API_KEY"], $openAiTransferLines["OPENAI_MONTHLY_BUDGET_USD"]),
    (New-Object System.Text.UTF8Encoding($false))
  )

  Invoke-Checked -Command "git" -Arguments @(
    "-c", "core.autocrlf=false",
    "-C", $repositoryRoot,
    "archive", "--format=tar.gz", "--output=$archive", "HEAD"
  ) -FailureMessage "Could not package the committed DeveloperOS revision"

  Invoke-RemoteScript -Script "set -eu; install -d -m 700 /home/opc/.developer-os-console/transfer" -FailureMessage "Could not prepare the server transfer directory"
  Invoke-Checked -Command $scp -Arguments @(
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15",
    "-i", $SshKey,
    $archive,
    "${Server}:$remoteArchive"
  ) -FailureMessage "Could not upload DeveloperOS"
  Invoke-Checked -Command $scp -Arguments @(
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15",
    "-i", $SshKey,
    $openAiTransferEnv,
    "${Server}:$remoteOpenAiEnv"
  ) -FailureMessage "Could not upload the OpenAI environment file"

  $projectConfig = @"
{
  "projects": [
    {"slug":"developer-os","name":"DeveloperOS","path":"/opt/developer-os-console/current","compose_project":"developer-os-console","port":8080,"backup_expected":false},
    {"slug":"btest","name":"bTest","path":"/home/opc/bTest-release","compose_project":"btest","port":8081,"backup_expected":true},
    {"slug":"oa","name":"OA","path":"/home/opc/oa","compose_project":"oa","port":8082,"backup_expected":true},
    {"slug":"gaia","name":"Gaia","path":"/home/opc/gaia","compose_project":"gaia","port":8083,"backup_expected":true}
  ],
  "workstations": [
    {"id":"home","name":"Home","offline_after_seconds":900},
    {"id":"office","name":"Office","offline_after_seconds":900}
  ]
}
"@
  $configBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($projectConfig.Replace("`r`n", "`n")))
  $terminalProjectConfig = @"
{
  "projects": [
    {"slug":"server","name":"Server","path":"/home/opc"},
    {"slug":"developer-os","name":"DeveloperOS","path":"/opt/developer-os-console/current"},
    {"slug":"btest","name":"bTest","path":"/home/opc/bTest-release"},
    {"slug":"oa","name":"OA","path":"/home/opc/oa"},
    {"slug":"gaia","name":"Gaia","path":"/home/opc/gaia"}
  ]
}
"@
  $terminalConfigBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($terminalProjectConfig.Replace("`r`n", "`n")))
  $remoteScript = @"
set -eu
release=/opt/developer-os-console/releases/$timestamp
shared=/home/opc/.developer-os-console
install -d -m 700 "`$shared" "`$shared/transfer"
sudo install -d -m 0755 /opt/developer-os-console/releases
sudo mkdir -p "`$release"
sudo tar -xzf $remoteArchive -C "`$release"
printf '%s\n' '$revisionLabel' | sudo tee "`$release/.devos-revision" >/dev/null
date -u +%Y-%m-%dT%H:%M:%SZ | sudo tee "`$release/.devos-deployed-at" >/dev/null
printf %s $configBase64 | base64 --decode > "`$shared/config.json"
chmod 600 "`$shared/config.json"
printf %s $terminalConfigBase64 | base64 --decode > "`$shared/terminal-projects.json"
chmod 600 "`$shared/terminal-projects.json"
token=""
if [ -f "`$shared/console.env" ]; then
  token=`$(sed -n 's/^DEVOS_CONSOLE_TOKEN=//p' "`$shared/console.env" | head -n 1)
fi
if [ -z "`$token" ]; then
  token=`$(openssl rand -hex 32)
fi
umask 077
{
  echo "DEVOS_CONSOLE_TOKEN=`$token"
  echo "DEVOS_WORKSPACE_ROOT=/home/opc"
  echo "DEVOS_RUNTIME_DIR=/var/lib/developer-os-console"
  echo "DEVOS_MEMO_DATABASE=/var/lib/developer-os-console/memos.sqlite3"
  echo "DEVOS_CONSOLE_CONFIG=/etc/developer-os-console/config.json"
  echo "DEVOS_BACKUP_STATUS_DIR=/var/lib/developer-os-console/backup-status"
  echo "DEVOS_WORKSTATION_STATUS_DIR=/var/lib/developer-os-console/workstations"
  echo "DEVOS_BIND=0.0.0.0"
  echo "DEVOS_PORT=8080"
  echo "DEVOS_PUBLIC_READ_ONLY=1"
  echo "DEVOS_SECURE_COOKIE=0"
} > "`$shared/console.env"
chmod 600 "`$shared/console.env"
terminal_secret=""
if [ -f "`$shared/terminal.env" ]; then
  terminal_secret=`$(sed -n 's/^DEVOS_TERMINAL_SECRET=//p' "`$shared/terminal.env" | head -n 1)
fi
if [ -z "`$terminal_secret" ]; then
  terminal_secret=`$(openssl rand -hex 32)
fi
{
  echo "DEVOS_TERMINAL_SECRET=`$terminal_secret"
  echo "DEVOS_TERMINAL_CONFIG=/etc/developer-os-terminal/projects.json"
  echo "DEVOS_TERMINAL_AUDIT=/var/lib/developer-os-terminal/audit.jsonl"
  echo "DEVOS_TERMINAL_BIND=127.0.0.1"
  echo "DEVOS_TERMINAL_PORT=8022"
  echo "DEVOS_TERMINAL_TIMEOUT=120"
  echo "DEVOS_TERMINAL_MAX_OUTPUT=131072"
} > "`$shared/terminal.env"
chmod 600 "`$shared/terminal.env"
sudo install -d -m 0750 -o root -g opc /etc/developer-os-console
sudo install -m 0640 -o root -g opc "`$shared/console.env" /etc/developer-os-console/console.env
sudo install -m 0640 -o root -g opc "`$shared/config.json" /etc/developer-os-console/config.json
sudo install -m 0640 -o root -g opc $remoteOpenAiEnv /etc/developer-os-console/openai.env
sudo install -d -m 0750 -o root -g opc /etc/developer-os-terminal
sudo install -m 0640 -o root -g opc "`$shared/terminal.env" /etc/developer-os-terminal/terminal.env
sudo install -m 0640 -o root -g opc "`$shared/terminal-projects.json" /etc/developer-os-terminal/projects.json
sudo ln -sfn "`$release" /opt/developer-os-console/current
if command -v restorecon >/dev/null 2>&1; then
  sudo restorecon -RF /opt/developer-os-console /etc/developer-os-console /etc/developer-os-terminal
fi
sudo usermod -aG docker opc
if [ ! -x /opt/developer-os-console/usage-venv/bin/python ]; then
  sudo python3 -m venv /opt/developer-os-console/usage-venv
fi
sudo /opt/developer-os-console/usage-venv/bin/python -m pip install --disable-pip-version-check --quiet -r "`$release/console/requirements-usage.txt"
sudo chgrp -R opc /opt/developer-os-console/usage-venv
sudo chmod -R g+rX,o-rwx /opt/developer-os-console/usage-venv
sudo install -m 0644 "`$release/deployment/console/developer-os-console.service" /etc/systemd/system/developer-os-console.service
sudo install -m 0644 "`$release/deployment/console/developer-os-terminal.service" /etc/systemd/system/developer-os-terminal.service
sudo install -m 0644 "`$release/deployment/console/developer-os-openai-usage.service" /etc/systemd/system/developer-os-openai-usage.service
sudo install -m 0644 "`$release/deployment/console/developer-os-openai-usage.timer" /etc/systemd/system/developer-os-openai-usage.timer
sed 's/\r`$//' "`$release/deployment/console/backup-postgres.sh" | sudo tee /usr/local/sbin/developer-os-backup-postgres >/dev/null
sed 's/\r`$//' "`$release/deployment/console/verify-postgres-backup.sh" | sudo tee /usr/local/sbin/developer-os-verify-postgres-backup >/dev/null
sudo chmod 0755 /usr/local/sbin/developer-os-backup-postgres /usr/local/sbin/developer-os-verify-postgres-backup
sudo install -m 0644 "`$release/deployment/console/developer-os-backup.service" /etc/systemd/system/developer-os-backup.service
sudo install -m 0644 "`$release/deployment/console/developer-os-backup.timer" /etc/systemd/system/developer-os-backup.timer
sudo install -m 0644 "`$release/deployment/console/developer-os-backup-verify.service" /etc/systemd/system/developer-os-backup-verify.service
sudo install -m 0644 "`$release/deployment/console/developer-os-backup-verify.timer" /etc/systemd/system/developer-os-backup-verify.timer
sudo systemctl daemon-reload
sudo systemctl enable developer-os-console developer-os-terminal
sudo systemctl enable --now developer-os-backup.timer developer-os-backup-verify.timer developer-os-openai-usage.timer
sudo systemctl reset-failed developer-os-console || true
sudo systemctl reset-failed developer-os-terminal || true
sudo systemctl restart developer-os-console developer-os-terminal
sudo systemctl start developer-os-openai-usage.service
sudo install -d -m 0750 -o opc -g opc /var/lib/developer-os-console/workstations
if [ ! -s /var/lib/developer-os-console/backup-status/developer-os-memos.json ]; then
  sudo /usr/local/sbin/developer-os-backup-postgres developer-os-memos
fi
if [ ! -s /var/lib/developer-os-console/backup-status/oa.json ] || [ ! -s /var/lib/developer-os-console/backup-status/gaia.json ] || [ ! -s /var/lib/developer-os-console/backup-status/btest.json ]; then
  sudo systemctl start developer-os-backup.service
  sudo systemctl start developer-os-backup-verify.service
fi
if sudo systemctl is-active --quiet firewalld; then
  sudo firewall-cmd --permanent --add-port=8080/tcp >/dev/null
  sudo firewall-cmd --reload >/dev/null
fi
for attempt in `$(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8080/healthz >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8080/healthz
for attempt in `$(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8022/healthz >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8022/healthz
rm -f $remoteArchive $remoteOpenAiEnv
echo
echo "DeveloperOS console deployed: $revisionLabel"
echo "Public read-only URL: http://168.107.18.16:8080"
echo "Private terminal endpoint: server loopback 127.0.0.1:8022"
"@
  Invoke-RemoteScript -Script $remoteScript -FailureMessage "Could not install the DeveloperOS console"
}
finally {
  if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
  }
  if (Test-Path -LiteralPath $openAiTransferEnv) {
    Remove-Item -LiteralPath $openAiTransferEnv -Force
  }
}
