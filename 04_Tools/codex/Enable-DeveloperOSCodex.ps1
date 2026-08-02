param(
    [string]$CodexHome = $(
        if ($env:CODEX_HOME) {
            $env:CODEX_HOME
        } else {
            Join-Path $HOME ".codex"
        }
    )
)

$ErrorActionPreference = "Stop"

$sourcePath = Join-Path $PSScriptRoot "AGENTS.global.md"
$targetDirectory = [System.IO.Path]::GetFullPath($CodexHome)
$targetPath = Join-Path $targetDirectory "AGENTS.md"
$startMarker = "<!-- BEGIN DEVELOPEROS MANAGED GUIDANCE -->"
$endMarker = "<!-- END DEVELOPEROS MANAGED GUIDANCE -->"

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "DeveloperOS global guidance was not found: $sourcePath"
}

$managedContent = (Get-Content -Raw -LiteralPath $sourcePath).Trim()
if (-not $managedContent.Contains($startMarker) -or -not $managedContent.Contains($endMarker)) {
    throw "DeveloperOS global guidance markers are missing."
}

New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null

if (Test-Path -LiteralPath $targetPath) {
    $existingContent = Get-Content -Raw -LiteralPath $targetPath
    $startIndex = $existingContent.IndexOf($startMarker, [System.StringComparison]::Ordinal)
    $endIndex = $existingContent.IndexOf($endMarker, [System.StringComparison]::Ordinal)

    if (($startIndex -ge 0) -xor ($endIndex -ge 0)) {
        throw "The existing Codex AGENTS.md contains an incomplete DeveloperOS managed block: $targetPath"
    }

    if ($startIndex -ge 0) {
        if ($endIndex -lt $startIndex) {
            throw "The existing Codex AGENTS.md has invalid DeveloperOS marker order: $targetPath"
        }

        $afterIndex = $endIndex + $endMarker.Length
        $before = $existingContent.Substring(0, $startIndex).TrimEnd()
        $after = $existingContent.Substring($afterIndex).TrimStart()
        $parts = @($before, $managedContent, $after) | Where-Object { $_ }
        $updatedContent = ($parts -join "`r`n`r`n") + "`r`n"
    } else {
        $updatedContent = $existingContent.TrimEnd() + "`r`n`r`n" + $managedContent + "`r`n"
    }
} else {
    $updatedContent = $managedContent + "`r`n"
}

$encoding = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($targetPath, $updatedContent, $encoding)

Write-Host "DeveloperOS Codex guidance enabled:"
Write-Host "  $targetPath"
