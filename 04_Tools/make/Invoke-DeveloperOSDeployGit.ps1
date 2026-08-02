[CmdletBinding()]
param(
    [string]$Remote = "origin",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& git @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $detail = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw "$Description failed.`n$detail"
    }
    return @($output | ForEach-Object { $_.ToString() })
}

if ($Remote -notmatch '^[A-Za-z0-9._-]+$') {
    throw "Deployment Git remote contains unsupported characters."
}
if ($Branch -notmatch '^[A-Za-z0-9._/-]+$') {
    throw "Deployment Git branch contains unsupported characters."
}

$insideWorkTree = (Invoke-Git -Arguments @("rev-parse", "--is-inside-work-tree") -Description "Git repository check" | Select-Object -First 1).Trim()
if ($insideWorkTree -ne "true") {
    throw "Deployment requires a Git work tree."
}

$changes = @(Invoke-Git -Arguments @("status", "--porcelain", "--untracked-files=all") -Description "Git status check" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($changes.Count -gt 0) {
    throw "Deployment requires a clean Git work tree. Ask Codex to review, commit, and push the changes first."
}

$currentBranch = (Invoke-Git -Arguments @("branch", "--show-current") -Description "Git branch check" | Select-Object -First 1).Trim()
if ($currentBranch -ne $Branch) {
    throw "Deployment branch '$currentBranch' does not match configured branch '$Branch'."
}

$expectedUpstream = "$Remote/$Branch"
$upstream = (Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "--symbolic-full-name", '@{upstream}') -Description "Git upstream check" | Select-Object -First 1).Trim()
if ($upstream -ne $expectedUpstream) {
    throw "Deployment upstream '$upstream' does not match '$expectedUpstream'."
}

Write-Host "==> Pushing committed deployment revision to $expectedUpstream..."
$null = Invoke-Git -Arguments @("push", $Remote, $Branch) -Description "Git push"
$null = Invoke-Git -Arguments @("fetch", "--quiet", $Remote, $Branch) -Description "Git fetch"

$localRevision = (Invoke-Git -Arguments @("rev-parse", "HEAD") -Description "Local revision check" | Select-Object -First 1).Trim()
$remoteRevision = (Invoke-Git -Arguments @("rev-parse", "$Remote/$Branch") -Description "Remote revision check" | Select-Object -First 1).Trim()
if ($localRevision -ne $remoteRevision) {
    throw "Deployment blocked because local HEAD does not match $expectedUpstream after push."
}

Write-Host "Git deployment revision ready: $localRevision"
