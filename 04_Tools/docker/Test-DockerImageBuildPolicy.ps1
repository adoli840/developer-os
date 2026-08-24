$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$developerOSRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$workspaceRoot = Split-Path -Parent $developerOSRoot
$policyPath = Join-Path $developerOSRoot "00_Master\DockerImageBuildPolicy.md"
$failures = New-Object System.Collections.Generic.List[string]

$repositories = @(
    @{ Name = "DeveloperOS"; Path = $developerOSRoot },
    @{ Name = "OA"; Path = (Join-Path $workspaceRoot "OA") },
    @{ Name = "Gaia"; Path = (Join-Path $workspaceRoot "Gaia") },
    @{ Name = "bTest"; Path = (Join-Path $workspaceRoot "bTest") }
)

function Add-Result {
    param(
        [ValidateSet("PASS", "FAIL")]
        [string]$Status,
        [string]$Name,
        [string]$Detail
    )

    Write-Host ("{0,-4} {1}: {2}" -f $Status, $Name, $Detail)
    if ($Status -eq "FAIL") {
        $script:failures.Add("${Name}: $Detail")
    }
}

function Get-RelativeDisplayPath {
    param([string]$RepositoryPath, [string]$Path)

    return $Path.Substring($RepositoryPath.Length).TrimStart('\', '/')
}

function Test-MakeFile {
    param([hashtable]$Repository, [string]$Path)

    $currentTargets = @()
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $Path) {
        $lineNumber++
        if ($line -match '^([A-Za-z0-9_.%/-]+(?:\s+[A-Za-z0-9_.%/-]+)*)\s*:(?!=)') {
            $currentTargets = @($matches[1] -split '\s+')
            continue
        }
        if ($line -notmatch '^\s+') {
            $currentTargets = @()
            continue
        }
        if ($line.TrimStart() -match '^@?echo(?:\s|$)') {
            continue
        }

        $relative = Get-RelativeDisplayPath $Repository.Path $Path
        if ($line -match '(?:^|\s)--no-cache(?:\s|$)') {
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber disables the build cache")
        }
        if ($line -match 'docker\s+system\s+prune.*(?:\s-a|\s--all)(?:\s|$)') {
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber performs system-wide pruning")
        }

        $isComposeCommand = $line -match 'docker\s+compose|\$\([^)]*COMPOSE[^)]*\)'
        $isComposeUp = $isComposeCommand -and $line -match '(?:^|\s)up(?:\s|$)'
        if ($isComposeUp -and $line -notmatch '(?:^|\s)--no-build(?=\s|$|["''])') {
            $target = if ($currentTargets.Count -gt 0) { $currentTargets -join "," } else { "unknown target" }
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber target '$target' starts Compose without --no-build")
        }

        $isDirectBuild = $isComposeCommand -and (
            $line -match '(?:^|\s)build(?:\s|$)' -or
            $line -match '(?:^|\s)--build(?:\s|$)'
        )
        if ($isDirectBuild) {
            $allowedTarget = $currentTargets | Where-Object {
                $_ -match '(^|[-_])(build|rebuild)([-_]|$)'
            } | Select-Object -First 1
            if (-not $allowedTarget) {
                $target = if ($currentTargets.Count -gt 0) { $currentTargets -join "," } else { "unknown target" }
                $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber target '$target' contains an unnamed Docker build")
            }
        }
    }
}

function Test-OperationalFile {
    param([hashtable]$Repository, [string]$Path)

    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $Path) {
        $lineNumber++
        $relative = Get-RelativeDisplayPath $Repository.Path $Path
        $isComposeUp = $line -match '(docker\s+compose|\bcompose)\b.*\bup\b'
        if ($isComposeUp -and $line -notmatch '(?:^|\s)--no-build(?=\s|$|["''])') {
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber starts Compose without --no-build")
        }

        $isBuildCommand = $line -match 'docker\s+(?:build(?=\s|$)|buildx\s+build(?=\s|$))' -or $line -match '"buildx"\s*,\s*"build"'
        if ($isBuildCommand -and (Split-Path -Leaf $Path) -notmatch 'deploy') {
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber builds outside an explicit deployment helper")
        }
        if ($line -match '(?:^|\s)--no-cache(?:\s|$)') {
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber disables the build cache")
        }
        if ($line -match 'docker\s+system\s+prune.*(?:\s-a|\s--all)(?:\s|$)') {
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber performs system-wide pruning")
        }
    }
}

function Test-GuidanceFile {
    param([hashtable]$Repository, [string]$Path)

    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $Path) {
        $lineNumber++
        if ($line -match '\bup\b[^\r\n]*--build\b') {
            $relative = Get-RelativeDisplayPath $Repository.Path $Path
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber still recommends build-on-start")
        }
        if ($line -match '(?:docker\s+)?system\s+prune[^\r\n]*(?:\s-a|\s--all)(?:\s|$)') {
            $relative = Get-RelativeDisplayPath $Repository.Path $Path
            $script:failures.Add("$($Repository.Name): ${relative}:$lineNumber recommends system-wide pruning")
        }
    }
}

if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) {
    Add-Result FAIL "Global policy" "00_Master/DockerImageBuildPolicy.md is missing"
} else {
    $policy = Get-Content -Raw -LiteralPath $policyPath
    if ($policy.Contains("--no-build") -and $policy.Contains("DeveloperOS Self-Application")) {
        Add-Result PASS "Global policy" "no-build lifecycle and DeveloperOS self-application are defined"
    } else {
        Add-Result FAIL "Global policy" "required no-build or self-application rules are incomplete"
    }
}

foreach ($repository in $repositories) {
    if (-not (Test-Path -LiteralPath $repository.Path -PathType Container)) {
        Add-Result FAIL $repository.Name "repository directory is missing"
        continue
    }

    $beforeCount = $failures.Count
    $makeFiles = @(Get-ChildItem -LiteralPath $repository.Path -File -Filter "Makefile*")
    if ($repository.Name -eq "DeveloperOS") {
        $makeFiles += Get-Item -LiteralPath (Join-Path $developerOSRoot "04_Tools\make\DeveloperOS.mk")
        $makeFiles += Get-Item -LiteralPath (Join-Path $developerOSRoot "deployment\templates\make\Makefile.deploy.template")
    }
    foreach ($makeFile in $makeFiles) {
        Test-MakeFile -Repository $repository -Path $makeFile.FullName
    }

    $operationalFiles = @()
    foreach ($directoryName in @("scripts", "deploy", "deployment")) {
        $directory = Join-Path $repository.Path $directoryName
        if (Test-Path -LiteralPath $directory -PathType Container) {
            $operationalFiles += Get-ChildItem -LiteralPath $directory -Recurse -File | Where-Object {
                $_.Extension -in @(".ps1", ".sh")
            }
        }
    }
    if ($repository.Name -eq "DeveloperOS") {
        $operationalFiles += Get-Item -LiteralPath (Join-Path $developerOSRoot "deployment\projects.yml")
    }
    foreach ($operationalFile in $operationalFiles | Sort-Object -Property FullName -Unique) {
        Test-OperationalFile -Repository $repository -Path $operationalFile.FullName
    }

    $guidanceFiles = @()
    if ($repository.Name -ne "DeveloperOS") {
        $guidanceFiles += Get-ChildItem -LiteralPath $repository.Path -File | Where-Object {
            $_.Extension -in @(".md", ".txt")
        }
        foreach ($directoryName in @("docs", "deploy")) {
            $directory = Join-Path $repository.Path $directoryName
            if (Test-Path -LiteralPath $directory -PathType Container) {
                $guidanceFiles += Get-ChildItem -LiteralPath $directory -Recurse -File | Where-Object {
                    $_.Extension -in @(".md", ".txt")
                }
            }
        }
        foreach ($guidanceFile in $guidanceFiles | Sort-Object -Property FullName -Unique) {
            Test-GuidanceFile -Repository $repository -Path $guidanceFile.FullName
        }
    }

    $scannedFiles = @($makeFiles).Count + @($operationalFiles).Count + @($guidanceFiles).Count
    if ($failures.Count -eq $beforeCount) {
        Add-Result PASS $repository.Name "$scannedFiles operational files follow explicit no-build startup"
    } else {
        Write-Host ("{0,-4} {1}: {2}" -f "FAIL", $repository.Name, "$($failures.Count - $beforeCount) policy violation(s) found")
    }
}

$unsafePatterns = @(
    @{ Name = "cache bypass"; Pattern = '(?:^|\s)--no-cache(?:\s|$)' },
    @{ Name = "system-wide prune"; Pattern = 'docker\s+system\s+prune.*(?:\s-a|\s--all)(?:\s|$)' }
)
$sharedMakePath = Join-Path $developerOSRoot "04_Tools\make\DeveloperOS.mk"
$sharedMake = Get-Content -Raw -LiteralPath $sharedMakePath
foreach ($unsafe in $unsafePatterns) {
    if ($sharedMake -match $unsafe.Pattern) {
        Add-Result FAIL "Shared Make safety" "$($unsafe.Name) is present in the routine shared contract"
    }
}

$rootComposeNames = @("docker-compose.yml", "compose.yml", "docker-compose.yaml", "compose.yaml")
$rootCompose = @($rootComposeNames | Where-Object {
    Test-Path -LiteralPath (Join-Path $developerOSRoot $_) -PathType Leaf
})
$consoleDeployment = Get-Content -Raw -LiteralPath (Join-Path $developerOSRoot "deployment\console\Manage-DeveloperOSConsole.ps1")
if ($rootCompose.Count -eq 0 -and $consoleDeployment -notmatch 'docker\s+(?:build|buildx\s+build)') {
    Add-Result PASS "DeveloperOS self-use" "console lifecycle performs zero routine Docker image builds"
} else {
    Add-Result FAIL "DeveloperOS self-use" "root container lifecycle or console image build requires policy review"
}

Write-Host ""
if ($failures.Count -gt 0) {
    foreach ($failure in $failures) {
        Write-Host "  - $failure"
    }
    throw "Docker image build minimization policy check failed."
}

Write-Host "Docker image build minimization policy passed for all managed projects."
