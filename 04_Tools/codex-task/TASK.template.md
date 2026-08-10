# Codex Task

Read `X:\Projects\DeveloperOS\BOOT.md` before starting work.

## Shortcut

{{SHORTCUT}}

## Task

{{TASK}}

## Model Routing

Read `X:\Projects\DeveloperOS\02_AI\ModelRoutingPolicy.md` and begin with:

```text
Model recommendation: Luna | Luna to Sol | Sol
Route sequence: <recommended route for each natural work stage>
Reason: <complexity, risk, clarity, and rework evidence>
Review boundary: <what must be checked before completion>
```

Raise the recommendation when project-local rules or a Sol trigger applies.
For multi-stage work, present the route sequence before editing. Wait for the
developer's `luna` or `sol` confirmation before a route change, complete the
useful work for the confirmed route, and request the next handoff only at a
natural boundary. Do not batch unrelated Luna work merely to avoid a handoff.

## High-Impact Development Protocol

For architecture, data models, migrations, recursive algorithms, automated
trading paths, production safety, authentication, authorization, security,
large refactors, core contract changes, irreversible changes, or ambiguous
requirements, follow
`X:\Projects\DeveloperOS\02_AI\DevelopmentProtocol.md`.

Before irreversible implementation, report the current state, interpretation,
affected files, dependencies, risks, reusable capabilities, implementation
plan, tests, migration or database impact, and production impact. Afterward,
report changed files, evidence, remaining scope, unperformed work, and the Sol
review result. Small, clear, reversible changes may use the abbreviated path.

## Project Boundary

This file belongs to the current application project.

DeveloperOS is the global engineering constitution. The project repository owns its README, TODO, roadmap, current implementation state, architecture notes, and project-specific decisions.

Do not scan the entire DeveloperOS repository. Use `BOOT.md` as the routing entry point and read only the DeveloperOS documents relevant to this task.

## Project Context Rule

When this repository has `PROJECT_AREAS.json`, run
`make context TASK="{{TASK}}"` before broad source inspection. Begin with the
selected entrypoints, files, and focused verification. Expand only when imports,
shared contracts, database or authentication boundaries, deployment behavior,
safety rules, or failing evidence cross the selected area.

## Roadmap Completion Rule

Follow `X:\Projects\DeveloperOS\00_Master\ProjectRoadmapPolicy.md` without
waiting for a separate roadmap request. For meaningful work, read the project's
canonical roadmap before implementation. Before finishing, evaluate whether a
topic's status, scope, priority, completion signal, or material blocker changed,
and update the roadmap only when one of those boundaries changed. Use an
existing project-specific roadmap or generator; create root `ROADMAP.md` only
when the project has no canonical roadmap.

## Docker Image Build Rule

For Docker, Compose, image, deployment, or container lifecycle work, follow
`X:\Projects\DeveloperOS\00_Master\DockerImageBuildPolicy.md`. Routine starts
and restarts must use existing images. Build only at an explicit build or
release boundary after identifying the changed build input or missing image.

## Safety Rule

For commit and push work:

- Check `git status`.
- Review the changed file list and diff summary.
- Stop if merge conflicts, secrets, suspicious files, missing upstream, or unrelated changes are found.
- Stage only appropriate project changes.
- Create a concise commit message based on the actual diff.
- Push the current branch.
