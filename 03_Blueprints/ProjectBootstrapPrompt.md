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
```

## Short Invocation

```text
Read X:\Projects\DeveloperOS\BOOT.md before starting work.
```