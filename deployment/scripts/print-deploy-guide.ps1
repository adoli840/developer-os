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

$config = Read-DeploymentConfig -Path $ConfigPath

Write-Host "DeveloperOS deployment guide"
Write-Host ""
Write-Host "1. Register these common GitHub Secrets in each project repository:"
Write-Host ""
foreach ($secret in $config.RequiredSecrets.Common) {
    Write-Host "   - $secret"
}

Write-Host ""
Write-Host "2. Register each project's production path secret:"
Write-Host ""
foreach ($name in $config.Projects.Keys) {
    $project = $config.Projects[$name]
    Write-Host "   - $name -> $($project.server_path_secret)"
}

Write-Host ""
Write-Host "3. Generate workflow files:"
Write-Host ""
Write-Host "   .\deployment\scripts\generate-deploy-workflow.ps1 -Project bTest"
Write-Host "   .\deployment\scripts\generate-deploy-workflow.ps1 -All"

Write-Host ""
Write-Host "4. Check readiness:"
Write-Host ""
Write-Host "   .\deployment\scripts\check-project-deploy-ready.ps1"

Write-Host ""
Write-Host "5. Standard deployment flow:"
Write-Host ""
Write-Host "   main push"
Write-Host "   -> GitHub Actions"
Write-Host "   -> Docker Hub login"
Write-Host "   -> Docker image build and push"
Write-Host "   -> production SSH"
Write-Host "   -> git pull origin main"
Write-Host "   -> docker compose pull"
Write-Host "   -> project deploy_command"

Write-Host ""
Write-Host "DeveloperOS stores Secret names only. Never store Secret values here."
