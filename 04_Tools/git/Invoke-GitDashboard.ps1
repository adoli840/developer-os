param(
    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$developerOsRoot = Resolve-Path (Join-Path $toolDir "..\..")
$workspaceRoot = Split-Path -Parent $developerOsRoot
$okMark = [string][char]0x2705
$failMark = [string][char]0x274C

$projects = @(
    [pscustomobject]@{ Name = "DeveloperOS"; Path = $developerOsRoot.Path },
    [pscustomobject]@{ Name = "Gaia Project"; Path = Join-Path $workspaceRoot "gaia" },
    [pscustomobject]@{ Name = "bTest"; Path = Join-Path $workspaceRoot "bTest" },
    [pscustomobject]@{ Name = "OA"; Path = Join-Path $workspaceRoot "oa" }
)

function Invoke-Git {
    param(
        [string]$RepoPath,
        [string[]]$GitArgs,
        [switch]$AllowFailure
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & git -C $RepoPath @GitArgs 2>$null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "git $($GitArgs -join ' ') failed in $RepoPath"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

function Get-FirstOutputLine {
    param($Output)

    $lines = @($Output)
    if ($lines.Count -eq 0) {
        return ""
    }

    return [string]$lines[0]
}

function Get-RepoStatus {
    param([pscustomobject]$Project)

    if (-not (Test-Path -LiteralPath $Project.Path)) {
        return [pscustomobject]@{
            Project = $Project.Name
            Modified = "-"
            Commit = "Missing"
            Push = "-"
            Pull = "-"
            Branch = "-"
            ModifiedCount = 0
            Ahead = 0
            Behind = 0
            Missing = $true
            NoUpstream = $false
        }
    }

    $gitDir = Invoke-Git -RepoPath $Project.Path -GitArgs @("rev-parse", "--git-dir") -AllowFailure
    if ($gitDir.ExitCode -ne 0) {
        return [pscustomobject]@{
            Project = $Project.Name
            Modified = "-"
            Commit = "Not Git"
            Push = "-"
            Pull = "-"
            Branch = "-"
            ModifiedCount = 0
            Ahead = 0
            Behind = 0
            Missing = $false
            NoUpstream = $false
        }
    }

    $remotes = Invoke-Git -RepoPath $Project.Path -GitArgs @("remote") -AllowFailure
    if (-not $SkipFetch -and $remotes.Output -contains "origin") {
        [void](Invoke-Git -RepoPath $Project.Path -GitArgs @("fetch", "--prune", "--quiet", "origin") -AllowFailure)
    }

    $branchResult = Invoke-Git -RepoPath $Project.Path -GitArgs @("rev-parse", "--abbrev-ref", "HEAD") -AllowFailure
    $branch = if ($branchResult.ExitCode -eq 0 -and $branchResult.Output) { Get-FirstOutputLine -Output $branchResult.Output } else { "DETACHED" }

    $status = Invoke-Git -RepoPath $Project.Path -GitArgs @("status", "--porcelain") -AllowFailure
    $modifiedCount = if ($status.Output) { @($status.Output).Count } else { 0 }
    $commitState = if ($modifiedCount -eq 0) { $okMark } else { $failMark }

    $upstreamResult = Invoke-Git -RepoPath $Project.Path -GitArgs @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") -AllowFailure
    $noUpstream = $upstreamResult.ExitCode -ne 0
    $ahead = 0
    $behind = 0

    if (-not $noUpstream) {
        $upstream = Get-FirstOutputLine -Output $upstreamResult.Output
        $counts = Invoke-Git -RepoPath $Project.Path -GitArgs @("rev-list", "--left-right", "--count", "HEAD...$upstream") -AllowFailure
        if ($counts.ExitCode -eq 0 -and $counts.Output) {
            $parts = (Get-FirstOutputLine -Output $counts.Output) -split "\s+"
            if ($parts.Count -ge 2) {
                $ahead = [int]$parts[0]
                $behind = [int]$parts[1]
            }
        }
    }

    $pushState = if ($noUpstream) { "No Upstream" } elseif ($ahead -gt 0) { "Need Push" } else { $okMark }
    $pullState = if ($noUpstream) { "No Upstream" } elseif ($behind -gt 0) { "Need Pull" } else { $okMark }

    return [pscustomobject]@{
        Project = $Project.Name
        Modified = $modifiedCount
        Commit = $commitState
        Push = $pushState
        Pull = $pullState
        Branch = $branch
        ModifiedCount = $modifiedCount
        Ahead = $ahead
        Behind = $behind
        Missing = $false
        NoUpstream = $noUpstream
    }
}

$rows = foreach ($project in $projects) {
    Get-RepoStatus -Project $project
}

Write-Host ""
Write-Host "Git Dashboard / End-of-Day Check"
Write-Host "================================"
Write-Host ""

$rows |
    Select-Object Project, Modified, Commit, Push, Pull, Branch |
    Format-Table -AutoSize

$actions = New-Object System.Collections.Generic.List[string]

foreach ($row in $rows) {
    if ($row.Missing) {
        $actions.Add("$($row.Project): repository folder is missing.")
        continue
    }

    if ($row.Commit -eq "Not Git") {
        $actions.Add("$($row.Project): not a Git repository.")
        continue
    }

    if ($row.ModifiedCount -gt 0) {
        $actions.Add("$($row.Project): commit required ($($row.ModifiedCount) modified file(s)).")
    }

    if ($row.NoUpstream) {
        $actions.Add("$($row.Project): upstream branch is not configured.")
    } else {
        if ($row.Ahead -gt 0) {
            $actions.Add("$($row.Project): push required ($($row.Ahead) commit(s) ahead).")
        }
        if ($row.Behind -gt 0) {
            $actions.Add("$($row.Project): pull required ($($row.Behind) commit(s) behind).")
        }
    }
}

Write-Host ""
Write-Host "End-of-Day Actions"
Write-Host "------------------"

if ($actions.Count -eq 0) {
    Write-Host "All projects are synchronized with their Git remotes."
} else {
    for ($i = 0; $i -lt $actions.Count; $i++) {
        Write-Host ("{0}. {1}" -f ($i + 1), $actions[$i])
    }
}

Write-Host ""

