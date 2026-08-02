$ErrorActionPreference = "Stop"

$sharedMakeFile = (Resolve-Path (Join-Path $PSScriptRoot "DeveloperOS.mk")).Path
$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$developerOSPath = Join-Path $workspaceRoot "DeveloperOS"

$projects = @(
    @{ Name = "OA"; Path = (Join-Path $workspaceRoot "oa"); Compose = "docker-compose.yml"; BuildCompose = "docker-compose.yml"; DeployTarget = "project-deploy"; SyncTarget = "sync-push" },
    @{ Name = "Gaia"; Path = (Join-Path $workspaceRoot "gaia"); Compose = "docker-compose.dev.yml"; BuildCompose = "docker-compose.dev.yml"; DeployTarget = "project-deploy"; SyncTarget = "sync-push" },
    @{ Name = "bTest"; Path = (Join-Path $workspaceRoot "bTest"); Compose = "docker-compose.yml"; BuildCompose = "docker-compose.yml"; DeployTarget = "project-deploy"; SyncTarget = "sync-push" }
)

$reservedTargets = @(
    "run", "run-b", "b-run", "up", "down", "logs", "docker-build",
    "docker-stop", "docker-logs", "docker-clean", "rebuild", "dh-tag",
    "dh-push", "dh-pull", "dh-b-push", "server-deploy", "sync", "deploy"
)
$targetPattern = "^(?:" + (($reservedTargets | ForEach-Object { [regex]::Escape($_) }) -join "|") + ")\s*:"
$failed = $false
$previousMakeFiles = $env:MAKEFILES

try {
    $env:MAKEFILES = $sharedMakeFile

    $developerOSFailed = $false
    $developerOSMakefile = Join-Path $developerOSPath "Makefile"
    $developerOSDefinitions = Select-String -LiteralPath $developerOSMakefile -Pattern $targetPattern
    if ($developerOSDefinitions) {
        $names = $developerOSDefinitions | ForEach-Object { $_.Line.Trim() }
        Write-Host "FAIL DeveloperOS: reserved Docker targets are defined locally: $($names -join ', ')"
        $developerOSFailed = $true
    }

    $gitCheckOutput = @(& make --no-print-directory -n git-check -C $developerOSPath 2>&1)
    if ($LASTEXITCODE -ne 0 -or ($gitCheckOutput -join "`n") -notmatch "Invoke-GitDashboard.ps1") {
        Write-Host "FAIL DeveloperOS: shared make git-check is unavailable."
        $developerOSFailed = $true
    }

    foreach ($target in @("self-check", "console-run", "console-test", "console-deploy", "sync", "deploy")) {
        $null = @(& make --no-print-directory -n $target -C $developerOSPath 2>&1)
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FAIL DeveloperOS: make $target is unavailable."
            $developerOSFailed = $true
        }
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $dockerRunOutput = @(& make --no-print-directory -n run -C $developerOSPath 2>&1)
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($LASTEXITCODE -eq 0 -or ($dockerRunOutput -join "`n") -notmatch "No Docker Compose file configured") {
        Write-Host "FAIL DeveloperOS: the non-Docker exclusion is not explicit."
        $developerOSFailed = $true
    }

    if ($developerOSFailed) {
        $failed = $true
    } else {
        Write-Host "PASS DeveloperOS: shared Git Make command and specialized non-Docker contract are active."
    }

    foreach ($project in $projects) {
        $projectFailed = $false
        if (-not (Test-Path -LiteralPath $project.Path -PathType Container)) {
            Write-Host "FAIL $($project.Name): project directory is missing."
            $failed = $true
            $projectFailed = $true
            continue
        }

        $localMakeFile = Join-Path $project.Path "Makefile"
        if (Test-Path -LiteralPath $localMakeFile -PathType Leaf) {
            $definitions = Select-String -LiteralPath $localMakeFile -Pattern $targetPattern
            if ($definitions) {
                $names = $definitions | ForEach-Object { $_.Line.Trim() }
                Write-Host "FAIL $($project.Name): reserved targets are defined locally: $($names -join ', ')"
                $failed = $true
                $projectFailed = $true
                continue
            }
        }

        $runOutput = @(& make --no-print-directory -n run -C $project.Path 2>&1)
        $runText = $runOutput -join "`n"
        if ($LASTEXITCODE -ne 0 -or $runText -notmatch [regex]::Escape($project.Compose)) {
            Write-Host "FAIL $($project.Name): make run did not select $($project.Compose)."
            $failed = $true
            $projectFailed = $true
            continue
        }
        if ($runText -notmatch "--no-build" -or $runText -match "(?:^|\s)--build(?:\s|$)") {
            Write-Host "FAIL $($project.Name): make run does not enforce no-build startup."
            $failed = $true
            $projectFailed = $true
            continue
        }

        $buildOutput = @(& make --no-print-directory -n docker-build -C $project.Path 2>&1)
        if ($LASTEXITCODE -ne 0 -or ($buildOutput -join "`n") -notmatch [regex]::Escape($project.BuildCompose)) {
            Write-Host "FAIL $($project.Name): make docker-build did not select $($project.BuildCompose)."
            $failed = $true
            $projectFailed = $true
            continue
        }

        $buildRunOutput = @(& make --no-print-directory -n b-run -C $project.Path 2>&1)
        $buildRunText = $buildRunOutput -join "`n"
        if ($LASTEXITCODE -ne 0 -or $buildRunText -notmatch "(?:^|\s)build(?:\s|$)" -or $buildRunText -notmatch "--no-build" -or $buildRunText -match "(?:^|\s)--build(?:\s|$)") {
            Write-Host "FAIL $($project.Name): make b-run must build once and start with --no-build."
            $failed = $true
            $projectFailed = $true
            continue
        }

        $upOutput = @(& make --no-print-directory -n up -C $project.Path 2>&1)
        if ($LASTEXITCODE -ne 0 -or ($upOutput -join "`n") -notmatch "--no-build") {
            Write-Host "FAIL $($project.Name): make up does not enforce no-build startup."
            $failed = $true
            $projectFailed = $true
            continue
        }

        foreach ($target in @("down", "logs", "dh-b-push", "dh-pull")) {
            $null = @(& make --no-print-directory -n $target -C $project.Path 2>&1)
            if ($LASTEXITCODE -ne 0) {
                Write-Host "FAIL $($project.Name): make $target is unavailable."
                $failed = $true
                $projectFailed = $true
                break
            }
        }

        if (-not $projectFailed) {
            $syncOutput = @(& make --no-print-directory -n sync -C $project.Path 2>&1)
            $syncText = $syncOutput -join "`n"
            $syncIsValid = if ($null -ne $project.SyncTarget) {
                $LASTEXITCODE -eq 0 -and $syncText -match [regex]::Escape($project.SyncTarget)
            } else {
                $LASTEXITCODE -eq 0 -and $syncText -match "not configured"
            }
            if (-not $syncIsValid) {
                $expectation = if ($null -ne $project.SyncTarget) {
                    "delegate to $($project.SyncTarget)"
                } else {
                    "be an explicit no-op"
                }
                Write-Host "FAIL $($project.Name): make sync must $expectation."
                $failed = $true
                $projectFailed = $true
            }
        }

        if (-not $projectFailed) {
            $previousErrorActionPreference = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                $deployOutput = @(& make --no-print-directory -n deploy -C $project.Path 2>&1)
                $deployExitCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $previousErrorActionPreference
            }
            $deployText = $deployOutput -join "`n"
            if ($null -ne $project.DeployTarget) {
                if ($deployExitCode -ne 0 -or $deployText -notmatch "Invoke-DeveloperOSDeployGit.ps1" -or $deployText -notmatch [regex]::Escape($project.DeployTarget)) {
                    Write-Host "FAIL $($project.Name): make deploy does not use the shared Git gate and configured deployment target."
                    $failed = $true
                    $projectFailed = $true
                }
            } elseif ($deployExitCode -eq 0 -or $deployText -notmatch "Deployment is not configured") {
                Write-Host "FAIL $($project.Name): unconfigured deployment must fail clearly."
                $failed = $true
                $projectFailed = $true
            }
        }

        if (-not $projectFailed) {
            Write-Host "PASS $($project.Name): shared Docker Make contract is active."
        }
    }
}
finally {
    $env:MAKEFILES = $previousMakeFiles
}

if ($failed) {
    throw "DeveloperOS shared Make contract check failed."
}

Write-Host "DeveloperOS and all project Make contracts passed."
