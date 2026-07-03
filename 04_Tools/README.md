# Tools

## Purpose

DeveloperOS automation tools live here.

## Shared Make Targets

`04_Tools/make/DeveloperOS.mk` defines standard workspace commands.

Enable the shared make file once:

```powershell
X:\Projects\DeveloperOS\04_Tools\make\Enable-DeveloperOSMake.ps1
```

Once enabled, projects do not need duplicate local Makefiles just to expose common DeveloperOS commands.

Available workspace command:

```bash
make git-check
```

Docker projects can use these standard commands:

```bash
make run
make b-run
make down
make dh-b-push
make dh-pull
```

## Git Dashboard

The Git Dashboard shows the end-of-day Git status for active workspace repositories.

Run from any project directory when DeveloperOS Make targets are enabled:

```powershell
make git-check
```

Fallback direct command:

```powershell
X:\Projects\DeveloperOS\04_Tools\bin\devos.cmd git-check
```

The tool fetches `origin` when available and reports modified files, commit need, push need, pull need, and current branch.

## Codex Task Generator

`04_Tools/codex-task/New-CodexTask.ps1` creates a project-local `.codex/TASK.md` from the shared DeveloperOS task template.

Example:

```powershell
X:\Projects\DeveloperOS\04_Tools\codex-task\New-CodexTask.ps1 X:\Projects\oa -Shortcut "git-push" -Task "Perform a minimum-safety commit and push for the current project."
```

After generation, use this in Codex Desktop from the project:

```text
Read .codex/TASK.md
```

## Planned Tools

- Git Dashboard / end-of-day Git check
- Snapshot Manager
- Workspace inspection helpers
- Project bootstrap helpers
- Documentation maintenance helpers
- Daily Review generator
- Roadmap and ProjectStatus checker
- Developer Score calculator

## Snapshot Storage

Runtime snapshots should be stored under `04_Tools/snapshots/` or `.snapshots/` and must not be committed to Git.

## PM Tool Direction

Future tools should help DeveloperOS act as an invoked AI Project Manager.

Planned PM helpers:

- Generate a daily review from `Dashboard.md`, `WeeklyPlan.md`, `Roadmap.md`, `ProjectStatus.md`, and `Metrics.md`.
- Detect stale active projects.
- Recommend the next project based on priority, deadline, dependency, and weekly goals.
- Estimate Developer Score for weekly reflection.
