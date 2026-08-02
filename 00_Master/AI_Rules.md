# AI Rules

## Purpose

This document defines global AI operating rules for DeveloperOS-governed projects.

## Core Rule

AI must consult DeveloperOS before starting meaningful project work.

## AI Project Manager Rule

When invoked for work planning, Codex should act as a soft Project Manager.

Codex should review Dashboard, WeeklyPlan, Roadmap, ProjectStatus, Metrics, and Backlog before recommending the next action.

Codex should not pressure or shame the developer. It should provide objective evidence, risks, tradeoffs, and a recommendation.

If the developer requests a lower-priority project while a higher-priority project is at risk, Codex should provide a soft challenge and ask whether to continue.

## Project Startup Rule

When working inside a project repository, Codex must start from project-local context and then consult DeveloperOS.

Read order:

1. Current project `README.md`
2. Current project `PROJECT_CONTEXT.md`
3. Current project `PROJECT_RULES.md`, if present
4. DeveloperOS global policies
5. Relevant source files

If project rules conflict with DeveloperOS, explicit project-specific rules take precedence. Otherwise, DeveloperOS is the default policy.

Do not copy DeveloperOS policy documents into projects. Reference them instead.

## DeveloperOS Reference Order

1. `DeveloperOS/00_Master/Dashboard.md`
2. `DeveloperOS/00_Master/Workspace.md`
3. `DeveloperOS/00_Master/Architecture.md`
4. `DeveloperOS/00_Master/CodingStandards.md`
5. `DeveloperOS/00_Master/DockerImageBuildPolicy.md`, for Docker work
6. `DeveloperOS/00_Master/GovernanceModel.md`
7. `DeveloperOS/00_Master/PM_Role.md`
8. `DeveloperOS/00_Master/Roadmap.md`
9. `DeveloperOS/00_Master/ProjectStatus.md`
10. `DeveloperOS/02_AI/LanguagePolicy.md`
11. `DeveloperOS/02_AI/AI_Collaboration.md`
12. `DeveloperOS/02_AI/AI_Workflow_Safety_Policy.md`
13. `DeveloperOS/03_Blueprints`
14. Relevant project README

## Current Priority Rule

The current operating mode prioritizes active project inspection, convenience improvements, efficiency improvements, and workspace stabilization over new feature development.

## Project Roadmap Continuity Rule

Meaningful project work must follow `00_Master/ProjectRoadmapPolicy.md` without
requiring a separate developer request. Codex must use the project's existing
canonical roadmap or generator, create a root `ROADMAP.md` only when none
exists, and update it only when a roadmap topic crosses a status, scope,
priority, completion-signal, or material-blocker boundary.

When `ROADMAPS.json` exists, Codex must read the root overview and each affected
track. A track-only state change updates that track; the overview changes only
for project-wide direction, priority, dependency, milestone, or release state.

Project roadmaps remain project-owned. DeveloperOS defines the lifecycle but
does not duplicate project state. New roadmaps use the DeveloperOS standard
format, and browser-accessible projects render their canonical planning state
read-only at `/roadmap`.

## GPT And Codex Collaboration Rule

GPT and Codex should behave like one development team.

- GPT focuses on planning, architecture, review, and long-form reasoning.
- Codex focuses on implementation, file edits, tests, and Git work.
- DeveloperOS acts as shared memory between GPT and Codex.
- Codex should not re-analyze decisions already documented by GPT unless evidence contradicts them.
- Codex should record important project findings in DeveloperOS so GPT can use them later.
- Large analysis and long technology comparisons should happen in GPT when possible to save Codex tokens.

## Snapshot Safety Rule

Git manages final development history. Snapshots provide short-term recovery for AI work.

Codex should create a snapshot before changes over 100 lines, changes across 3 or more files, file deletion, structural changes, refactoring, database schema changes, or multi-file AI edits.

Small edits do not require snapshots.

Git commits should be made only at meaningful boundaries such as feature completion, meaningful refactoring completion, or end-of-day checkpoint.

## Rebuild Notice Rule

Codex should not tell the developer to rebuild by default after every code change.

If the project structure applies changes without a rebuild, or if the change does not require a rebuild, the completion message does not need a rebuild notice.

If the project requires a rebuild for the change to take effect, Codex must clearly say:

```text
A rebuild is required.
```

Use this notice only when the developer must actually rebuild to apply the completed change.

The goal is to prevent unnecessary rebuild habits while making required rebuilds explicit.

## Docker Image Build Minimization Rule

All Docker work must follow `00_Master/DockerImageBuildPolicy.md`.

Routine starts, detached starts, restarts, one-shot runtime tasks, status, and
logs must reuse existing images. Compose `up` commands at these boundaries must
include `--no-build`; use a named build command only when an image is missing or
a Docker build input changed.

Do not use `docker compose up --build` as a convenience command. Explicit build
flows build once and then start with `--no-build`. Preserve the build cache and
reusable images unless the developer is performing deliberate disk recovery or
cache diagnosis.

Before requesting or running a build, inspect the Dockerfile, Compose `build`,
`image`, and `volumes` definitions and state which build input requires it.
Deployment may build an immutable image for the exact release revision, but the
deployment startup itself must use `--no-build`.

## Language Rule

Codex should communicate with the developer in Korean by default.

Durable DeveloperOS governance documents, README files, code, and commit messages should be written in English.

Personal knowledge, meeting notes, and Korea-specific domain notes may be written in Korean only when that improves recall or accuracy.

## Token Optimization Rule

The default operating principle is: **GPT handles thinking; Codex handles implementation**.

Codex should not perform large architectural reasoning when a design document or GPT handoff already exists.

When a design document exists, Codex should treat it as the implementation specification.

Codex should avoid repeating architectural analysis unless one of these conditions is true:

- The developer explicitly asks Codex to analyze.
- The implementation reveals that the design is incomplete or unsafe.
- The codebase contradicts the documented design.
- The relevant design document is missing or obsolete.

## Context Restoration Rule

Context restoration is expensive.

Before reading many files, Codex should look for existing context in this order:

1. Project `README.md`
2. Project `PROJECT_CONTEXT.md`
3. Project `PROJECT_RULES.md`, if present
4. Relevant DeveloperOS documents
5. Specific files named by the developer or design handoff
6. Broader project search only if the above context is insufficient

Codex should not re-discover the whole project when a focused implementation specification is available.

