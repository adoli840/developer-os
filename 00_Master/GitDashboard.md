# Git Dashboard

## Purpose

Git Dashboard is the end-of-day Git status view for the workspace.

It helps the developer see which active repositories need commit, push, or pull before leaving work.

## Scope

The default dashboard checks these repositories:

- DeveloperOS
- Gaia Project
- bTest
- OA

## Dashboard Columns

| Project | Modified | Commit | Push | Pull | Branch |
|---|---:|---:|---:|---:|---|
| Example | 0 | ✅ | ✅ | ✅ | main |

## Column Meaning

- `Project`: project display name
- `Modified`: number of uncommitted changed files
- `Commit`: `✅` when the working tree is clean, `❌` when commit is needed
- `Push`: `Need Push` when the local branch is ahead of the remote branch
- `Pull`: `Need Pull` when the remote branch is ahead of the local branch
- `Branch`: current branch name

## End-of-Day Actions

The dashboard prints a follow-up action list below the table.

Example:

```text
End-of-Day Actions
------------------
1. Gaia Project: commit required.
2. DeveloperOS: push required.
3. bTest: pull required.
```

If all repositories are clean and synchronized:

```text
All projects are synchronized with their Git remotes. You can leave work.
```

## Terminal Usage

Run from any project directory after enabling DeveloperOS Make targets:

```powershell
make git-check
```

Enable the Make target once:

```powershell
X:\Projects\DeveloperOS\04_Tools\make\Enable-DeveloperOSMake.ps1
```

Fallback direct command:

```powershell
X:\Projects\DeveloperOS\04_Tools\bin\devos.cmd git-check
```

## Fetch Rule

The dashboard performs `git fetch --prune --quiet origin` before calculating ahead/behind state when the repository has an `origin` remote.

Use the underlying script with `-SkipFetch` only when offline or when a fetch is intentionally not desired.

## Constraint

This tool reports status only.

It does not commit, push, pull, or modify project repositories.
