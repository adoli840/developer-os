# Tools

## Purpose

DeveloperOS automation tools live here.

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

