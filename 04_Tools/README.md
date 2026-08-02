# Tools

## Purpose

DeveloperOS automation tools live here.

## DeveloperOS Self-Application

Install every durable user-level DeveloperOS integration and verify that this
repository receives its own applicable policies:

```powershell
make self-enable
make self-check
```

`self-enable` installs the shared Make file, the `devos` command path, and the
global Codex guidance block. `self-check` verifies project guidance, roadmap and
snapshot rules, shared Git commands, monitoring, terminal access, workstation
reporting, deployment controls, and Codex task generation. Structurally
inapplicable Docker lifecycle, database backup, and generic deployment
capabilities are reported as explicit skips. Docker image build minimization is
still checked as an active zero-build policy for DeveloperOS itself.

## Shared Make Targets

`04_Tools/make/DeveloperOS.mk` defines standard workspace commands.

Enable the shared make file once:

```powershell
X:\Projects\DeveloperOS\04_Tools\make\Enable-DeveloperOSMake.ps1
```

Once enabled, projects do not need duplicate local Makefiles just to expose common DeveloperOS commands.
The shared Docker target names are reserved and must not be redefined in project
Makefiles. Project-specific Compose filenames and image behavior belong in
`docker-config`.

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
make sync
make deploy
```

`make run` and `make up` always reuse existing images. `make b-run` performs one
cached build and then starts with `--no-build`. The complete policy lives in
`00_Master/DockerImageBuildPolicy.md`.

`make sync` is a fixed local-to-server facade and delegates only to a
project-configured data-publish target. `make deploy` pushes already committed
work, verifies the exact upstream revision, calls the configured project
deployment target, and performs post-deployment synchronization only after an
explicit project opt-in. Neither command invents a commit or selects database
content on the project's behalf.

Projects connect private hooks through `docker-config`:

```make
DEVOS_DEPLOY_TARGET=project-deploy
DEVOS_SYNC_PUSH_TARGET=sync-push
DEVOS_DEPLOY_SYNC=after-deploy
```

Omit `DEVOS_SYNC_PUSH_TARGET` when the project owns no approved synchronized
data. Keep `DEVOS_DEPLOY_SYNC=none` unless the project contract explicitly
allows a verified data publish after a successful code deployment.

Verify DeveloperOS, OA, Gaia, and bTest against the shared contract:

```bash
make make-check
make docker-policy-check
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

## Global Codex Guidance

Enable the DeveloperOS entry point and project-roadmap lifecycle for every
Codex repository under `X:\Projects`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File X:\Projects\DeveloperOS\04_Tools\codex\Enable-DeveloperOSCodex.ps1
```

The installer maintains a marked DeveloperOS block in
`$CODEX_HOME/AGENTS.md` and preserves unrelated personal guidance. Project
instructions may choose their own roadmap filename or generator, while
`00_Master/ProjectRoadmapPolicy.md` supplies the shared update lifecycle.

## Shared Roadmap Web Presentation

`04_Tools/roadmap-web` owns the versioned, framework-neutral roadmap renderer
used by the DeveloperOS console and project-local `/roadmap` routes. Its
installer copies the canonical CSS and JavaScript into a project, and `-Check`
verifies byte-for-byte parity. Projects own their roadmap content and parser;
they must not independently restyle or truncate the shared stage presentation.

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
