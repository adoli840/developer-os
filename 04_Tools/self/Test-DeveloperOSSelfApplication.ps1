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
    "PROJECT_RULES.md",
    "ROADMAP.md",
    "00_Master\ProjectRoadmapPolicy.md"
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
$standardTopicHeader = "| Topic | Status | Completion Signal | Next Transition |"
if (
    $roadmapPolicy -and
    $roadmapTemplate -and
    $roadmapPolicy.Contains("## Canonical Standard Format") -and
    $roadmapPolicy.Contains("## Roadmap Web View") -and
    $roadmapPolicy.Contains("/roadmap") -and
    $roadmapTemplate.Contains($standardTopicHeader)
) {
    Add-CheckResult PASS "Roadmap standard" "the shared format and read-only /roadmap contract are defined"
} else {
    Add-CheckResult FAIL "Roadmap standard" "the shared format, template, or /roadmap contract is missing"
}

$null = & git -C $developerOSRoot check-ignore -q -- ".snapshots/developer-os-self-check.tmp"
if ($LASTEXITCODE -eq 0) {
    Add-CheckResult PASS "Snapshot recovery" "runtime snapshots are available and ignored by Git"
} else {
    Add-CheckResult FAIL "Snapshot recovery" ".snapshots is not ignored by Git"
}

$globalAgents = Join-Path ([System.IO.Path]::GetFullPath($CodexHome)) "AGENTS.md"
$globalAgentsText = if (Test-Path -LiteralPath $globalAgents -PathType Leaf) { Get-Content -Raw -LiteralPath $globalAgents } else { "" }
if ($globalAgentsText.Contains("<!-- BEGIN DEVELOPEROS MANAGED GUIDANCE -->") -and $globalAgentsText.Contains("X:\Projects\DeveloperOS\BOOT.md") -and $globalAgentsText.Contains("DockerImageBuildPolicy.md")) {
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
        Add-CheckResult PASS "Console monitoring" "DeveloperOS is monitored and correctly has no database-backup expectation"
    } else {
        Add-CheckResult FAIL "Console monitoring" "DeveloperOS console registration is invalid"
    }
}

$terminalConfigPath = Join-Path $developerOSRoot "console\terminal-config.example.json"
$terminalConfig = Get-Content -Raw -LiteralPath $terminalConfigPath | ConvertFrom-Json
if ($terminalConfig.projects | Where-Object { $_.slug -eq "developer-os" } | Select-Object -First 1) {
    Add-CheckResult PASS "Server terminal" "DeveloperOS is available through the private project terminal"
} else {
    Add-CheckResult FAIL "Server terminal" "DeveloperOS is missing from the terminal project list"
}

$workstationReporter = Read-Text "deployment\workstations\Report-DeveloperOSGitStatus.ps1"
if ($workstationReporter -and $workstationReporter.Contains('slug = "developer-os"')) {
    Add-CheckResult PASS "Workstation reporting" "DeveloperOS Git state is included in workstation reports"
} else {
    Add-CheckResult FAIL "Workstation reporting" "DeveloperOS is missing from workstation reports"
}

$rootMakefile = Read-Text "Makefile"
if ($rootMakefile -and $rootMakefile -match "(?m)^console-deploy:" -and $rootMakefile -match "(?m)^console-status:") {
    Add-CheckResult PASS "Specialized deployment" "console deployment and status targets are available"
} else {
    Add-CheckResult FAIL "Specialized deployment" "DeveloperOS console deployment targets are missing"
}

$taskTemplate = Read-Text "04_Tools\codex-task\TASK.template.md"
if ((Test-Path -LiteralPath (Join-Path $developerOSRoot "04_Tools\codex-task\New-CodexTask.ps1")) -and $taskTemplate -and $taskTemplate.Contains("ProjectRoadmapPolicy.md") -and $taskTemplate.Contains("DockerImageBuildPolicy.md")) {
    Add-CheckResult PASS "Codex task generation" "the shared task generator includes roadmap continuity and image build minimization"
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

Add-CheckResult SKIP "PostgreSQL backup" "DeveloperOS owns no application database and backup_expected is false"
Add-CheckResult SKIP "Generic Docker deployment" "DeveloperOS uses the specialized console systemd deployment"
Add-CheckResult SKIP "Root TODO and Decisions" "canonical records live in 00_Master/Backlog.md and 00_Master/Decisions.md"

Write-Host ""
if ($failures.Count -gt 0) {
    throw "DeveloperOS self-application check failed: $($failures -join '; ')"
}

Write-Host "DeveloperOS self-application check passed."
