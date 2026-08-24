param(
    [string]$CodexHome = $(
        if ($env:CODEX_HOME) {
            $env:CODEX_HOME
        } else {
            Join-Path $HOME ".codex"
        }
    ),
    [switch]$RequireUserRegistration
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$developerOSRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sharedMakeFile = (Resolve-Path (Join-Path $developerOSRoot "04_Tools\make\DeveloperOS.mk")).Path
$commandDirectory = (Resolve-Path (Join-Path $developerOSRoot "04_Tools\bin")).Path
$failures = New-Object System.Collections.Generic.List[string]

function Add-CheckResult {
    param(
        [ValidateSet("PASS", "FAIL", "SKIP")]
        [string]$Status,
        [string]$Name,
        [string]$Detail
    )

    Write-Host ("{0,-4} {1}: {2}" -f $Status, $Name, $Detail)
    if ($Status -eq "FAIL") {
        $script:failures.Add("${Name}: $Detail")
    }
}

function Read-Text {
    param([string]$RelativePath)

    $path = Join-Path $developerOSRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $null
    }
    return Get-Content -Raw -LiteralPath $path
}

function Test-PathEntry {
    param(
        [string]$Value,
        [string]$ExpectedPath
    )

    if ([string]::IsNullOrWhiteSpace($value)) {
        return $false
    }
    return [bool]($value -split ";" | Where-Object { $_.TrimEnd("\") -ieq $ExpectedPath.TrimEnd("\") } | Select-Object -First 1)
}

Write-Host "DeveloperOS Self-Application Check"
Write-Host "=================================="

$requiredFiles = @(
    "AGENTS.md",
    "BOOT.md",
    "README.md",
    "PROJECT_CONTEXT.md",
    "PROJECT_AREAS.json",
    "PROJECT_RULES.md",
    "ROADMAP.md",
    "00_Master\ProjectRoadmapPolicy.md",
    "00_Master\ProjectOperationalAuthorityPolicy.md"
)
$missingFiles = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $developerOSRoot $_) -PathType Leaf) })
if ($missingFiles.Count -eq 0) {
    Add-CheckResult PASS "Project guidance" "local startup, context, rules, and roadmap files exist"
} else {
    Add-CheckResult FAIL "Project guidance" ("missing " + ($missingFiles -join ", "))
}

$roadmap = Read-Text "ROADMAP.md"
$roadmapHeadings = @("Updated:", "## Direction", "## Current Milestone", "## Roadmap Topics", "## Current Priority", "## Latest Status Change", "## Next Status Transitions", "## Risks And Blockers")
$missingRoadmapState = if ($roadmap) {
    @($roadmapHeadings | Where-Object { -not $roadmap.Contains($_) })
} else {
    $roadmapHeadings
}
if ($roadmap -and $missingRoadmapState.Count -eq 0) {
    Add-CheckResult PASS "Roadmap lifecycle" "DeveloperOS has the required topic-status state"
} else {
    Add-CheckResult FAIL "Roadmap lifecycle" ("missing " + ($missingRoadmapState -join ", "))
}

$roadmapPolicy = Read-Text "00_Master\ProjectRoadmapPolicy.md"
$roadmapTemplate = Read-Text "03_Blueprints\Project\ROADMAP.md"
$roadmapManifestTemplate = Read-Text "03_Blueprints\Project\ROADMAPS.example.json"
$roadmapRenderer = Read-Text "04_Tools\roadmap-web\assets\roadmap-view.js"
$standardTopicHeader = "| Topic | Status | Completion Signal | Next Transition |"
if (
    $roadmapPolicy -and
    $roadmapTemplate -and
    $roadmapManifestTemplate -and
    $roadmapRenderer -and
    $roadmapPolicy.Contains("## Canonical Standard Format") -and
    $roadmapPolicy.Contains("## Roadmap Web View") -and
    $roadmapPolicy.Contains("overview_topic") -and
    $roadmapPolicy.Contains("/roadmap") -and
    $roadmapTemplate.Contains($standardTopicHeader) -and
    $roadmapManifestTemplate.Contains('"schema_version": 2') -and
    $roadmapManifestTemplate.Contains('"overview_topic"') -and
    $roadmapRenderer.Contains('const VERSION = "3.1.0"')
) {
    Add-CheckResult PASS "Roadmap standard" "the card-first format, linked-track manifest, and read-only /roadmap contract are defined"
} else {
    Add-CheckResult FAIL "Roadmap standard" "the shared format, linked-track template, renderer, or /roadmap contract is missing"
}

$workflowPolicy = Read-Text "02_AI\AI_Workflow_Safety_Policy.md"
$modelRoutingPolicy = Read-Text "02_AI\ModelRoutingPolicy.md"
$developmentProtocol = Read-Text "02_AI\DevelopmentProtocol.md"
$gitIgnore = Read-Text ".gitignore"
$retiredSnapshotPaths = @(".snapshots", "05_Snapshots", "04_Tools\snapshots")
$existingSnapshotPaths = @(
    $retiredSnapshotPaths |
        Where-Object { Test-Path -LiteralPath (Join-Path $developerOSRoot $_) }
)
if (
    $workflowPolicy -and
    $workflowPolicy.Contains("Git is the sole recovery mechanism for source-code work") -and
    $gitIgnore -and
    -not $gitIgnore.Contains(".snapshots") -and
    -not $gitIgnore.Contains("05_Snapshots") -and
    $existingSnapshotPaths.Count -eq 0
) {
    Add-CheckResult PASS "Git recovery" "AI work snapshots are retired and source-code recovery is Git-only"
} else {
    Add-CheckResult FAIL "Git recovery" "legacy AI snapshot policy, ignore rules, or storage paths remain"
}

if (
    $modelRoutingPolicy -and
    $modelRoutingPolicy.Contains("### Luna") -and
    $modelRoutingPolicy.Contains("### Luna to Sol") -and
    $modelRoutingPolicy.Contains("### Sol") -and
    $modelRoutingPolicy.Contains("Required Startup Note") -and
    $modelRoutingPolicy.Contains("Route sequence:")
) {
    Add-CheckResult PASS "Model routing" "Luna, Luna-to-Sol, and Sol task recommendations are defined"
} else {
    Add-CheckResult FAIL "Model routing" "the task-based model routing policy is missing or incomplete"
}

if (
    $developmentProtocol -and
    $developmentProtocol.Contains("# GPT-User-Codex Seven-Step Development Protocol") -and
    $developmentProtocol.Contains("## Seven Steps") -and
    $developmentProtocol.Contains("## Roles And Peer Review") -and
    $developmentProtocol.Contains("## Planning And Result Reports")
) {
    Add-CheckResult PASS "Development protocol" "the high-impact GPT-User-Codex seven-step protocol is defined"
} else {
    Add-CheckResult FAIL "Development protocol" "the high-impact development protocol is missing or incomplete"
}

$operationalAuthorityPolicy = Read-Text "00_Master\ProjectOperationalAuthorityPolicy.md"
$boot = Read-Text "BOOT.md"
if (
    $operationalAuthorityPolicy -and
    $boot -and
    $operationalAuthorityPolicy.Contains("## Green: Project Autonomy") -and
    $operationalAuthorityPolicy.Contains("## Amber: User Decision") -and
    $operationalAuthorityPolicy.Contains("## Red: DeveloperOS Escalation") -and
    $operationalAuthorityPolicy.Contains("## Absolute Safety Boundaries") -and
    $operationalAuthorityPolicy.Contains("shared, host, and cross-project") -and
    $boot.Contains("ProjectOperationalAuthorityPolicy.md")
) {
    Add-CheckResult PASS "Project operational authority" "project autonomy and user/shared-infrastructure boundaries are routed and fail closed"
} else {
    Add-CheckResult FAIL "Project operational authority" "the Green/Amber/Red authority policy or BOOT route is missing or incomplete"
}

$null = & git -C $developerOSRoot check-ignore -q -- ".developer-os/context-index.json"
$contextCacheIgnored = $LASTEXITCODE -eq 0
$projectAreaTemplate = Read-Text "03_Blueprints\Project\PROJECT_AREAS.json"
$contextTool = Read-Text "04_Tools\context\project_context.py"
$contextGuide = Read-Text "04_Tools\context\README.md"
if (
    $contextCacheIgnored -and
    $projectAreaTemplate -and
    $projectAreaTemplate.Contains('"schema_version": 1') -and
    $contextTool -and
    $contextTool.Contains('GENERATOR_VERSION = "1.0.0"') -and
    $contextGuide -and
    $contextGuide.Contains("make context")
) {
    Add-CheckResult PASS "Context index contract" "the area Blueprint, incremental generator, and ignored cache are defined"
} else {
    Add-CheckResult FAIL "Context index contract" "the area Blueprint, generator, guide, or ignored cache is incomplete"
}

$globalAgents = Join-Path ([System.IO.Path]::GetFullPath($CodexHome)) "AGENTS.md"
$globalAgentsText = if (Test-Path -LiteralPath $globalAgents -PathType Leaf) { Get-Content -Raw -LiteralPath $globalAgents } else { "" }
if ($globalAgentsText.Contains("<!-- BEGIN DEVELOPEROS MANAGED GUIDANCE -->") -and $globalAgentsText.Contains("X:\Projects\DeveloperOS\BOOT.md") -and $globalAgentsText.Contains("DockerImageBuildPolicy.md") -and $globalAgentsText.Contains("ModelRoutingPolicy.md") -and $globalAgentsText.Contains("DevelopmentProtocol.md") -and $globalAgentsText.Contains("route sequence") -and $globalAgentsText.Contains("make context")) {
    Add-CheckResult PASS "Global Codex guidance" "DeveloperOS routing and image build minimization are installed in $globalAgents"
} else {
    Add-CheckResult FAIL "Global Codex guidance" "the managed DeveloperOS block or Docker policy routing is not installed"
}

$userMakeFiles = [Environment]::GetEnvironmentVariable("MAKEFILES", "User")
$registeredMakeFiles = @($userMakeFiles -split "\s+" | Where-Object { $_ })
$processMakeFiles = @($env:MAKEFILES -split "\s+" | Where-Object { $_ })
$userMakeRegistered = [bool]($registeredMakeFiles | Where-Object { $_ -ieq $sharedMakeFile } | Select-Object -First 1)
$processMakeRegistered = [bool]($processMakeFiles | Where-Object { $_ -ieq $sharedMakeFile } | Select-Object -First 1)
if ($userMakeRegistered) {
    Add-CheckResult PASS "Shared Make registration" "DeveloperOS.mk is installed for the Windows user"
} elseif ($processMakeRegistered -and -not $RequireUserRegistration) {
    Add-CheckResult PASS "Shared Make registration" "DeveloperOS.mk is active in the current process; user registration may be sandbox-hidden"
} else {
    Add-CheckResult FAIL "Shared Make registration" "DeveloperOS.mk is missing from the user MAKEFILES value"
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$userCommandRegistered = Test-PathEntry -Value $userPath -ExpectedPath $commandDirectory
$processCommandRegistered = Test-PathEntry -Value $env:Path -ExpectedPath $commandDirectory
if ($userCommandRegistered) {
    Add-CheckResult PASS "DeveloperOS command" "the devos command directory is installed in the user PATH"
} elseif ($processCommandRegistered -and -not $RequireUserRegistration) {
    Add-CheckResult PASS "DeveloperOS command" "the devos command is active in the current process; user registration may be sandbox-hidden"
} else {
    Add-CheckResult FAIL "DeveloperOS command" "04_Tools/bin is missing from the user PATH"
}

$previousMakeFiles = $env:MAKEFILES
try {
    $env:MAKEFILES = $sharedMakeFile
    $gitCheckOutput = @(& make --no-print-directory -n git-check -C $developerOSRoot 2>&1)
    $gitCheckExitCode = $LASTEXITCODE
    $consoleTestOutput = @(& make --no-print-directory -n console-test -C $developerOSRoot 2>&1)
    $consoleTestExitCode = $LASTEXITCODE
    $contextOutput = @(& make --no-print-directory context 'TASK=project context index' CONTEXT_FORMAT=json -C $developerOSRoot 2>&1)
    $contextExitCode = $LASTEXITCODE
} finally {
    $env:MAKEFILES = $previousMakeFiles
}

if ($gitCheckExitCode -eq 0 -and ($gitCheckOutput -join "`n").Contains("Invoke-GitDashboard.ps1")) {
    Add-CheckResult PASS "Shared Git command" "make git-check is active inside DeveloperOS"
} else {
    Add-CheckResult FAIL "Shared Git command" "make git-check is not available inside DeveloperOS"
}

if ($consoleTestExitCode -eq 0 -and ($consoleTestOutput -join "`n") -match "unittest") {
    Add-CheckResult PASS "Project verification" "make console-test is available"
} else {
    Add-CheckResult FAIL "Project verification" "make console-test is unavailable"
}

$contextPayload = $null
if ($contextExitCode -eq 0) {
    try {
        $contextPayload = ($contextOutput -join "`n") | ConvertFrom-Json
    } catch {
        $contextPayload = $null
    }
}
$selectedContextArea = @()
if ($contextPayload) {
    $selectedContextArea = @($contextPayload.selection.selected_areas | Where-Object { $_.id -eq "context-routing" })
}
if ($contextExitCode -eq 0 -and $contextPayload.selection.project -eq "DeveloperOS" -and $selectedContextArea.Count -eq 1) {
    Add-CheckResult PASS "Project context routing" "make context incrementally selects the DeveloperOS context-routing area"
} else {
    Add-CheckResult FAIL "Project context routing" "make context did not return the expected DeveloperOS area"
}

$gitDashboard = Read-Text "04_Tools\git\Invoke-GitDashboard.ps1"
if ($gitDashboard -and $gitDashboard.Contains('Name = "DeveloperOS"')) {
    Add-CheckResult PASS "Git dashboard" "DeveloperOS is included in end-of-work repository checks"
} else {
    Add-CheckResult FAIL "Git dashboard" "DeveloperOS is missing from the Git dashboard"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    Add-CheckResult FAIL "Console monitoring" "python is unavailable"
} else {
    $pythonCheck = "from console.devos_console.settings import DEFAULT_PROJECTS; p=next((x for x in DEFAULT_PROJECTS if x['slug']=='developer-os'), None); assert p is not None and p.get('backup_expected') is False"
    Push-Location $developerOSRoot
    try {
        $null = & $python.Source -c $pythonCheck 2>&1
        $pythonExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($pythonExitCode -eq 0) {
        Add-CheckResult PASS "Console monitoring" "DeveloperOS is monitored without a project PostgreSQL backup expectation"
    } else {
        Add-CheckResult FAIL "Console monitoring" "DeveloperOS console registration is invalid"
    }
}

$memoStore = Read-Text "console\devos_console\memos.py"
$memoBackup = Read-Text "deployment\console\backup-postgres.sh"
$memoDeployment = Read-Text "deployment\console\Manage-DeveloperOSConsole.ps1"
$memoMakefile = Read-Text "Makefile"
$projectRules = Read-Text "PROJECT_RULES.md"
if (
    $memoStore -and
    $memoStore.Contains("project_memos") -and
    $memoBackup -and
    $memoBackup.Contains("developer-os-memos") -and
    $memoBackup.Contains("PRAGMA integrity_check") -and
    $memoDeployment -and
    -not $memoDeployment.Contains("DEVOS_MEMO_TOKEN") -and
    -not ($memoMakefile -match '(?m)^console-memo-token:') -and
    $projectRules -and
    $projectRules.Contains("memos.sqlite3")
) {
    Add-CheckResult PASS "Memo database protection" "the scoped SQLite memo store has a daily consistent backup and integrity check"
} else {
    Add-CheckResult FAIL "Memo database protection" "the SQLite memo store or its recovery contract is incomplete"
}

$terminalConfigPath = Join-Path $developerOSRoot "console\terminal-config.example.json"
$terminalConfig = Get-Content -Raw -LiteralPath $terminalConfigPath | ConvertFrom-Json
if ($terminalConfig.projects | Where-Object { $_.slug -eq "developer-os" } | Select-Object -First 1) {
    Add-CheckResult PASS "Server terminal" "DeveloperOS is available through the private project terminal"
} else {
    Add-CheckResult FAIL "Server terminal" "DeveloperOS is missing from the terminal project list"
}

$workstationReporter = Read-Text "deployment\workstations\Report-DeveloperOSGitStatus.ps1"
$workstationManager = Read-Text "deployment\workstations\Manage-DeveloperOSWorkstationReporter.ps1"
$workstationLauncher = Read-Text "deployment\workstations\Run-DeveloperOSWorkstationReporterHidden.vbs"
$workstationMakefile = Read-Text "Makefile"
if (
    $workstationReporter -and
    $workstationReporter.Contains('slug = "developer-os"') -and
    $workstationReporter.Contains('remote_refresh_status = $remoteRefreshStatus') -and
    $workstationReporter.Contains('"fetch", "--quiet", "--no-tags", "--no-recurse-submodules"') -and
    $workstationReporter.Contains('$env:GIT_TERMINAL_PROMPT = "0"') -and
    $workstationReporter.Contains('$env:GIT_SSH_COMMAND = "$sshCommand -o BatchMode=yes -o ConnectTimeout=15"') -and
    $workstationManager -and
    $workstationManager.Contains('New-ScheduledTaskAction') -and
    $workstationManager.Contains('wscript.exe') -and
    $workstationManager.Contains('-WindowStyle Hidden') -and
    $workstationLauncher -and
    $workstationLauncher.Contains('shell.Run(command, 0, True)') -and
    $workstationMakefile -match '(?m)^workstation-home-auto-enable:' -and
    $workstationMakefile -match '(?m)^workstation-office-auto-enable:'
) {
    Add-CheckResult PASS "Workstation reporting" "DeveloperOS Git state supports verified remotes and manual or opt-in hidden scheduled reports"
} else {
    Add-CheckResult FAIL "Workstation reporting" "DeveloperOS workstation reporting or its hidden scheduler contract is incomplete"
}

$rootMakefile = Read-Text "Makefile"
if ($rootMakefile -and $rootMakefile -match "(?m)^console-deploy:" -and $rootMakefile -match "(?m)^console-status:") {
    Add-CheckResult PASS "Specialized deployment" "console deployment and status targets are available"
} else {
    Add-CheckResult FAIL "Specialized deployment" "DeveloperOS console deployment targets are missing"
}

$taskTemplate = Read-Text "04_Tools\codex-task\TASK.template.md"
if ((Test-Path -LiteralPath (Join-Path $developerOSRoot "04_Tools\codex-task\New-CodexTask.ps1")) -and $taskTemplate -and $taskTemplate.Contains("ProjectRoadmapPolicy.md") -and $taskTemplate.Contains("DockerImageBuildPolicy.md") -and $taskTemplate.Contains("ModelRoutingPolicy.md") -and $taskTemplate.Contains("DevelopmentProtocol.md") -and $taskTemplate.Contains("Route sequence:") -and $taskTemplate.Contains("make context")) {
    Add-CheckResult PASS "Codex task generation" "the shared task generator includes context routing, roadmap continuity, and image build minimization"
} else {
    Add-CheckResult FAIL "Codex task generation" "the task generator or required global policy instruction is missing"
}

$dockerBuildPolicy = Read-Text "00_Master\DockerImageBuildPolicy.md"
$consoleDeployment = Read-Text "deployment\console\Manage-DeveloperOSConsole.ps1"
if ($dockerBuildPolicy -and $dockerBuildPolicy.Contains("DeveloperOS Self-Application") -and $consoleDeployment -notmatch 'docker\s+(?:build|buildx\s+build)') {
    Add-CheckResult PASS "Image build minimization" "DeveloperOS defines the policy and its console performs zero routine image builds"
} else {
    Add-CheckResult FAIL "Image build minimization" "the self-application policy or zero-build console contract is missing"
}

$composeFiles = @("docker-compose.yml", "compose.yml", "docker-compose.yaml", "compose.yaml")
$rootCompose = @($composeFiles | Where-Object { Test-Path -LiteralPath (Join-Path $developerOSRoot $_) -PathType Leaf })
if ($rootCompose.Count -eq 0) {
    Add-CheckResult SKIP "Docker lifecycle" "no root Compose application; use console-run and systemd deployment"
} else {
    Add-CheckResult FAIL "Docker lifecycle" "a root Compose file now exists; review PROJECT_RULES.md and enable the shared Docker contract"
}

Add-CheckResult SKIP "PostgreSQL backup" "DeveloperOS owns no application PostgreSQL database and backup_expected is false"
Add-CheckResult SKIP "Generic Docker deployment" "DeveloperOS uses the specialized console systemd deployment"
Add-CheckResult SKIP "Root TODO and Decisions" "canonical records live in 00_Master/Backlog.md and 00_Master/Decisions.md"

Write-Host ""
if ($failures.Count -gt 0) {
    throw "DeveloperOS self-application check failed: $($failures -join '; ')"
}

Write-Host "DeveloperOS self-application check passed."
