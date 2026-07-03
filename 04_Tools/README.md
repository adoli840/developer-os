# Tools

## Purpose

DeveloperOS automation tools live here.


## Shared Make Targets

`04_Tools/make/DeveloperOS.mk` defines standard Docker project commands for workspace projects:

```bash
make run
make b-run
make down
make dh-b-push
make dh-pull
```

Use `04_Tools/make/Enable-DeveloperOSMake.ps1` to register the shared make file in the user `MAKEFILES` environment variable. Once enabled, projects do not need to keep duplicate local Makefiles just to expose the standard Docker commands.

## Codex Task Generator

`04_Tools/codex-task/New-CodexTask.ps1` creates a project-local `.codex/TASK.md` from the shared DeveloperOS task template.

Example:

```powershell
X:\Projects\DeveloperOS\04_Tools\codex-task\New-CodexTask.ps1 X:\Projects\oa -Shortcut "깃푸시" -Task "Perform a minimum-safety commit and push for the current project."
```

After generation, use this in Codex Desktop from the project:

```text
Read .codex/TASK.md
```

## Planned Tools

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


