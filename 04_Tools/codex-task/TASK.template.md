# Codex Task

Read `X:\Projects\DeveloperOS\BOOT.md` before starting work.

## Shortcut

{{SHORTCUT}}

## Task

{{TASK}}

## Project Boundary

This file belongs to the current application project.

DeveloperOS is the global engineering constitution. The project repository owns its README, TODO, roadmap, current implementation state, architecture notes, and project-specific decisions.

Do not scan the entire DeveloperOS repository. Use `BOOT.md` as the routing entry point and read only the DeveloperOS documents relevant to this task.

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
