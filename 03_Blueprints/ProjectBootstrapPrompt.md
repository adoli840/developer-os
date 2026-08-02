# Project Bootstrap Prompt

Use this prompt when starting a Codex or AI-agent session inside an individual project repository under `X:\Projects`.

```text
Read `X:\Projects\DeveloperOS\BOOT.md` before starting work.

DeveloperOS exists at `X:\Projects\DeveloperOS`.

Do not scan the entire DeveloperOS repository by default. Use `BOOT.md` as the routing entry point and read only the DeveloperOS documents relevant to the current task.

After reading `BOOT.md`, read this project's `README.md`, then `PROJECT_CONTEXT.md` if present, then `PROJECT_RULES.md` if present.

Project-specific documents override DeveloperOS only when they explicitly say so. Otherwise, DeveloperOS is the global engineering constitution.

Preserve the separation between DeveloperOS and this project repository:

- DeveloperOS owns global engineering policy, AI collaboration rules, safety policy, coding standards, language policy, and reusable blueprints.
- This project owns its README, TODO, roadmap, current implementation state, architecture notes, and project-specific decisions.
- Do not copy DeveloperOS governance documents into this project.
- Do not update DeveloperOS with project-local state unless the finding changes future engineering decisions across projects.

Use the task routing rules in `BOOT.md` to decide which DeveloperOS documents to read before implementation.

For Docker, Compose, image, deployment, or container lifecycle work, follow `DeveloperOS/00_Master/DockerImageBuildPolicy.md`. Routine starts and restarts must reuse existing images; use an explicit build command only when a build input changed or an image is missing.

For meaningful project work, follow `DeveloperOS/00_Master/ProjectRoadmapPolicy.md` without waiting for a separate request. Use this project's existing roadmap or generator, and create a root `ROADMAP.md` from the DeveloperOS blueprint only when no canonical roadmap exists. When `ROADMAPS.json` exists, read the root overview and each affected track. Before finishing, update an affected track only when its status, scope, priority, completion signal, or material blocker changed, and update the overview only for a project-wide boundary.
```

## Short Invocation

```text
Read X:\Projects\DeveloperOS\BOOT.md before starting work.
```
