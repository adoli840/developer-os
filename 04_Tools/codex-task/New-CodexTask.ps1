param(
    [Parameter(Position = 0)]
    [string]$ProjectPath = (Get-Location).Path,

    [string]$Shortcut = "general",

    [string]$Task = "Read DeveloperOS BOOT.md and follow the project task."
)

$ErrorActionPreference = "Stop"

$developerOSRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$templatePath = Join-Path $PSScriptRoot "TASK.template.md"

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Codex task template was not found: $templatePath"
}

if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "Project path does not exist: $ProjectPath"
}

$resolvedProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
$codexDir = Join-Path $resolvedProjectPath ".codex"
$taskPath = Join-Path $codexDir "TASK.md"

New-Item -ItemType Directory -Force -Path $codexDir | Out-Null

$template = Get-Content -Raw -LiteralPath $templatePath
$content = $template.Replace("{{SHORTCUT}}", $Shortcut).Replace("{{TASK}}", $Task)

$encoding = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($taskPath, $content, $encoding)

Write-Host "Created Codex task file:"
Write-Host "  $taskPath"
Write-Host ""
Write-Host "Use this in Codex Desktop:"
Write-Host "  Read .codex/TASK.md"
