param(
    [string]$Project,
    [switch]$All,
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

function Expand-Template {
    param(
        [string]$Template,
        [hashtable]$ProjectConfig
    )

    $content = $Template
    $replacements = @{
        "{{GITHUB_BRANCH}}" = $ProjectConfig.github_branch
        "{{DOCKERHUB_IMAGE}}" = $ProjectConfig.dockerhub_image
        "{{DOCKERFILE}}" = $ProjectConfig.dockerfile
        "{{COMPOSE_FILE}}" = $ProjectConfig.compose_file
        "{{SERVER_PATH_SECRET}}" = $ProjectConfig.server_path_secret
        "{{DEPLOY_COMMAND}}" = $ProjectConfig.deploy_command
    }

    foreach ($key in $replacements.Keys) {
        $content = $content.Replace($key, $replacements[$key])
    }

    return $content
}

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$templatePath = Join-Path $root "templates\github-actions\deploy-docker-ssh.yml.template"

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Workflow template not found: $templatePath"
}

$config = Read-DeploymentConfig -Path $ConfigPath
$template = Get-Content -Raw -LiteralPath $templatePath
$targets = @()

if ($All) {
    $targets = @($config.Projects.Keys)
} elseif ($Project) {
    $targets = @($Project)
} else {
    Write-Host "Specify -Project <name> or -All."
    Write-Host ""
    Write-Host "Configured projects:"
    foreach ($name in $config.Projects.Keys) {
        Write-Host "  $name"
    }
    exit 1
}

$encoding = New-Object System.Text.UTF8Encoding($true)

foreach ($name in $targets) {
    if (-not $config.Projects.Contains($name)) {
        throw "Unknown project '$name'. Check deployment/projects.yml."
    }

    $projectConfig = $config.Projects[$name]
    $repoPath = $projectConfig.repo_path

    if (-not (Test-Path -LiteralPath $repoPath)) {
        throw "Project path does not exist for '$name': $repoPath"
    }

    $workflowDir = Join-Path $repoPath ".github\workflows"
    $workflowPath = Join-Path $workflowDir "deploy-prod.yml"
    $content = Expand-Template -Template $template -ProjectConfig $projectConfig

    New-Item -ItemType Directory -Force -Path $workflowDir | Out-Null
    [System.IO.File]::WriteAllText($workflowPath, $content, $encoding)

    Write-Host "Generated workflow for ${name}:"
    Write-Host "  $workflowPath"
}
