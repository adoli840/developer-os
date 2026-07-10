param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot "..\projects.yml")
)

$ErrorActionPreference = "Stop"

function Read-DeploymentConfig {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Deployment config not found: $Path"
    }

    $config = @{
        Projects = [ordered]@{}
        RequiredSecrets = @{
            Common = @()
            ProjectPath = @()
        }
    }

    $section = $null
    $secretGroup = $null
    $currentProject = $null

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*$' -or $line -match '^\s*#') {
            continue
        }

        if ($line -match '^projects:\s*$') {
            $section = "projects"
            $secretGroup = $null
            continue
        }

        if ($line -match '^required_secrets:\s*$') {
            $section = "required_secrets"
            $currentProject = $null
            continue
        }

        if ($section -eq "projects" -and $line -match '^  ([A-Za-z0-9_-]+):\s*$') {
            $currentProject = $Matches[1]
            $config.Projects[$currentProject] = [ordered]@{}
            continue
        }

        if ($section -eq "projects" -and $line -match '^    ([A-Za-z0-9_-]+):\s*"(.*)"\s*$') {
            if (-not $currentProject) {
                throw "Project property found before project name: $line"
            }
            $config.Projects[$currentProject][$Matches[1]] = $Matches[2]
            continue
        }

        if ($section -eq "required_secrets" -and $line -match '^  ([A-Za-z0-9_-]+):\s*$') {
            $secretGroup = $Matches[1]
            continue
        }

        if ($section -eq "required_secrets" -and $line -match '^    -\s*"(.*)"\s*$') {
            switch ($secretGroup) {
                "common" { $config.RequiredSecrets.Common += $Matches[1] }
                "project_path" { $config.RequiredSecrets.ProjectPath += $Matches[1] }
            }
            continue
        }
    }

    return $config
}

function Get-GitValue {
    param(
        [string]$RepoPath,
        [string[]]$Arguments
    )

    try {
        $output = & git -C $RepoPath @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return ($output -join "`n").Trim()
    } catch {
        return $null
    }
}

function Format-Flag {
    param([bool]$Value)
    if ($Value) { return "OK" }
    return "NO"
}

$config = Read-DeploymentConfig -Path $ConfigPath
$rows = @()

foreach ($name in $config.Projects.Keys) {
    $project = $config.Projects[$name]
    $repoPath = $project.repo_path
    $exists = Test-Path -LiteralPath $repoPath
    $gitRepo = $false
    $branch = "N/A"
    $gitClean = $false
    $origin = $false
    $dockerfile = $false
    $compose = $false
    $makefile = $false
    $workflow = $false

    if ($exists) {
        $gitRepo = Test-Path -LiteralPath (Join-Path $repoPath ".git")
        $dockerfile = Test-Path -LiteralPath (Join-Path $repoPath $project.dockerfile)
        $compose = Test-Path -LiteralPath (Join-Path $repoPath $project.compose_file)
        $makefile = (Test-Path -LiteralPath (Join-Path $repoPath "Makefile")) -or
            (Test-Path -LiteralPath (Join-Path $repoPath "makefile")) -or
            (Test-Path -LiteralPath (Join-Path $repoPath "GNUmakefile"))
        $workflow = Test-Path -LiteralPath (Join-Path $repoPath ".github\workflows\deploy-prod.yml")

        if ($gitRepo) {
            $branchValue = Get-GitValue -RepoPath $repoPath -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
            if ($branchValue) {
                $branch = $branchValue
            }

            $statusValue = Get-GitValue -RepoPath $repoPath -Arguments @("status", "--porcelain")
            $gitClean = [string]::IsNullOrWhiteSpace($statusValue)

            $originValue = Get-GitValue -RepoPath $repoPath -Arguments @("remote", "get-url", "origin")
            $origin = -not [string]::IsNullOrWhiteSpace($originValue)
        }
    }

    $ready = $exists -and $gitRepo -and $gitClean -and $origin -and $dockerfile -and $compose -and $makefile -and $workflow

    $rows += [pscustomobject]@{
        Project = $name
        Branch = $branch
        Git = if ($gitClean) { "clean" } else { "dirty" }
        Dockerfile = Format-Flag $dockerfile
        Compose = Format-Flag $compose
        Makefile = Format-Flag $makefile
        Workflow = Format-Flag $workflow
        Origin = Format-Flag $origin
        Ready = if ($ready) { "YES" } else { "NO" }
    }
}

Write-Host "Deployment readiness"
Write-Host ""
$rows | Format-Table -AutoSize

Write-Host ""
Write-Host "Required GitHub Secrets"
Write-Host ""
foreach ($secret in $config.RequiredSecrets.Common) {
    Write-Host "  $secret"
}
foreach ($name in $config.Projects.Keys) {
    $secret = $config.Projects[$name].server_path_secret
    Write-Host "  $secret"
}

Write-Host ""
Write-Host "Secret values are not stored in DeveloperOS. Register them manually in GitHub."
