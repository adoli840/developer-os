# DeveloperOS

## Purpose

DeveloperOS is the developer's long-term decision engine for software development work.

It is not an application project, project dashboard, or replacement for project-owned roadmaps. It is the governance, safety, planning philosophy, and AI collaboration layer for all projects in the workspace.

## Mission

DeveloperOS exists to:

- Keep project work consistent across many repositories.
- Reduce repeated project setup decisions.
- Preserve engineering decisions that affect future projects.
- Make GPT and Codex work like one AI development team.
- Minimize Codex token usage by separating planning from implementation.
- Use Git as the sole source-code recovery mechanism.
- Act as an invoked AI Project Manager that recommends priorities without owning project state.
- Become quieter as it matures.

## Workspace Model

```text
Developer
  -> GPT (planning, design, review)
  -> DeveloperOS (official memory and governance)
  -> Codex (implementation, edits, tests)
  -> Git (final history)
```

## Repository Structure

```text
DeveloperOS
+-- 00_Master       # Governance, decisions, roadmap, PM documents
+-- 01_Knowledge    # Lessons, troubleshooting, research, domain notes
+-- 02_AI           # AI collaboration, safety, language, review policy
+-- 03_Blueprints   # Project blueprints for future repositories
+-- 04_Tools        # Automation tools
+-- deployment      # Deployment standards, templates, and readiness checks
```

## Core Policies

- DeveloperOS is the single source of truth for global engineering policy.
- DeveloperOS is the constitution of the workspace, not the government of each project.
- Projects reference DeveloperOS instead of copying global policy documents.
- Projects own their own README, TODO, roadmap, implementation state, and current architecture.
- Every meaningful work unit evaluates roadmap transitions; the canonical roadmap changes only when a topic's status or other material planning state changes.
- Routine Docker lifecycle commands reuse existing images; builds occur only at explicit build or release boundaries.
- Source code uses Git; non-source data synchronization uses explicit project-owned authority, identity, conflict, and verification contracts.
- GPT handles thinking; Codex handles implementation.
- Codex treats existing design documents as implementation specifications.
- Git is the sole source-code recovery mechanism.
- DeveloperOS governance documents are written in English.
- The developer may communicate with GPT and Codex in Korean.

## DeveloperOS Self-Application

DeveloperOS is also a project repository. It follows its own applicable
governance, roadmap, Git, coding, language, verification, and
documentation rules. Root `PROJECT_RULES.md` records the narrow capabilities
that do not fit its system-management architecture.

Install and verify the complete self-application contract:

```powershell
make self-enable
make self-check
```

The self-check reports active capabilities as `PASS` and structurally
inapplicable capabilities as `SKIP` with a reason.

## Shared Developer Commands

DeveloperOS provides shared Make targets through `04_Tools/make/DeveloperOS.mk`.

Enable the shared targets once from PowerShell:

```powershell
X:\Projects\DeveloperOS\04_Tools\make\Enable-DeveloperOSMake.ps1
```

After enabling, any project directory can use:

```bash
make git-check
make context TASK="describe the current task"
```

`make context` reads the project's tracked `PROJECT_AREAS.json`, incrementally
refreshes the ignored `.developer-os/context-index.json`, and returns the
smallest declared source area, entrypoints, related files, tests, services,
data stores, and risks relevant to the request. It reuses Git blob identities
for unchanged files, skips files outside declared areas, and reads working-tree
contents only for changed files.

Docker projects can also use:

```bash
make run
make b-run
make down
make dh-b-push
make dh-pull
make sync
make deploy
```

`make run` and `make up` use `--no-build`. `make b-run` builds once with the
normal Docker cache and then starts without requesting another build. See
`00_Master/DockerImageBuildPolicy.md` for rebuild criteria and release rules.

The Docker targets auto-detect `docker-compose.yml`, `compose.yml`, `docker-compose.yaml`, or `compose.yaml` in the current project directory.
Projects configure exceptional Compose filenames and image workflows through
`docker-config`; project Makefiles must not redefine the shared public targets.
`make sync` has one direction, local to server, and changes nothing unless the
project explicitly configures a data-publish target. `make deploy` requires a
clean Git work tree, pushes existing commits, verifies the upstream revision,
and delegates to the project's deployment target. Commit selection and commit
messages remain a Codex or developer decision.

Verify the shared contract across DeveloperOS, OA, Gaia, and bTest:

```bash
make make-check
make docker-policy-check
```

## Project Context Routing

DeveloperOS avoids repeated whole-repository investigation through a small
project-owned area map and a shared generated index:

- `PROJECT_AREAS.json` is reviewed project state and maps task terms to source
  boundaries and focused verification.
- `.developer-os/context-index.json` is derived local cache and remains outside
  Git.
- `make context TASK="..."` selects the first files to inspect and states when
  the search should expand.

The index is advisory. Authentication, database, deployment, shared API, and
safety changes still expand across every real dependency boundary. See
`04_Tools/context/README.md` for the schema and operating contract.

## Git Dashboard

DeveloperOS provides an end-of-day Git Dashboard for active repositories.

Run from any project directory when DeveloperOS Make targets are enabled:

```powershell
make git-check
```

Fallback direct command:

```powershell
X:\Projects\DeveloperOS\04_Tools\bin\devos.cmd git-check
```

The dashboard reports modified files, commit need, push need, pull need, and current branch for DeveloperOS, Gaia Project, bTest, and OA.

## Project Data Synchronization

DeveloperOS separates Git synchronization from datasets, database records,
learning artifacts, models, and checkpoints. Projects that need non-source
synchronization define a project-owned `DATA_SYNC.md` contract from the optional
blueprint in `03_Blueprints/Project`.

The global policy permits bidirectional set-union synchronization only for
immutable records with stable unique identities, content checksums, idempotent
imports, and explicit conflict handling. Mutable databases, active models,
checkpoints, and aggregate state require one authority and directed transfer.
Database synchronization is default-deny: each project allowlists the exact
tables, export queries, and row scope worth transferring, while every omitted
database object remains local.

Projects may connect their reviewed local-to-server implementation to the
shared `make sync` facade. Deployment-time synchronization remains disabled
unless the project explicitly selects `after-deploy`.

See `00_Master/DataSynchronizationPolicy.md`.

## Deployment Standard Manager

DeveloperOS provides deployment templates and readiness checks through `deployment/`.

Check every configured project:

```powershell
.\deployment\scripts\check-project-deploy-ready.ps1
```

Generate one GitHub Actions workflow:

```powershell
.\deployment\scripts\generate-deploy-workflow.ps1 -Project bTest
```

Generate every configured workflow:

```powershell
.\deployment\scripts\generate-deploy-workflow.ps1 -All
```

Secret values are not stored in DeveloperOS. The scripts print required GitHub Secret names only.

## Browser Console

DeveloperOS includes a live browser console under `console/`. It derives status
from project repositories and the Oracle server without duplicating
project-owned state. Its read-only roadmap view is available at `/roadmap` and
derives standard fields from each project's root `ROADMAP.md` and any tracks
declared by `ROADMAPS.json`. The shared card-first presentation puts progress
immediately below project and track tabs; schema version 2 manifests keep each
Overall compact-card group identical to the linked track's large cards.

Run locally:

```powershell
make console-run
```

Deploy the public read-only console to the Oracle server:

```powershell
git add <files>
git commit -m "<message>"
make deploy
```

Deployment is accepted only from a clean `main` branch that exactly matches
`origin/main`. The release is built from the committed Git revision, never
from uncommitted local files.

The deployed service listens on port `8080`; append `/roadmap` to that access
address for the roadmap view. See `console/README.md` for its security boundary,
recovery evidence, private-terminal boundary, and provider usage snapshot
behavior.

OpenAI organization costs and Oracle Cloud costs plus Ampere A1 monthly free
usage are collected by a separate hourly server service. Oracle usage is shown
as consumed, remaining, and projected month-end quantities using Oracle's
public free ranges and overage rates. The OpenAI Admin key remains outside Git
in `X:/Settings/env/developer-os.env`; Oracle uses the server's instance
principal. Neither credential reaches the public console.

The Oracle deployment also installs:

- A private SQLite memo database with daily verified copies and 14-day retention.
- Daily OA and Gaia full PostgreSQL backups with 14-day retention.
- Daily bTest PostgreSQL backups with Kline rows excluded and 3-day retention.
- Weekly isolated restore verification in temporary PostgreSQL containers.
- Deployment revision and container image comparison.
- Git end-of-work checks and local operational alerts.

Inspect or run the backup controls from the DeveloperOS terminal:

```powershell
make console-backup-status
make console-backup
make console-backup-verify
```

The Home and Office computers report their local Git status to the server while
their Windows user session is active. Each report contains repository state
only and is transferred through SSH. Reporting can be sent once manually:

```powershell
make workstation-home-report
make workstation-office-report
```

Or enable the opt-in hidden Windows Scheduled Task once on each matching
computer:

```powershell
make workstation-home-auto-enable
make workstation-office-auto-enable
```

The task runs the DeveloperOS reporter every five minutes without requiring
Codex or a visible PowerShell window. Use the matching `-auto-status` and
`-auto-disable` targets to inspect or remove it. The console preserves the last
report and marks it offline after 15 minutes without a fresh report. Never
install both workstation identities on the same computer.

The server terminal is deliberately separate from the public console. It
listens only on server loopback and is reached from the Home computer through
the existing SSH key:

```powershell
make terminal-tunnel
make terminal-developer-os
make terminal-oa
make terminal-gaia
```

The Projects table Terminal heading opens the allowlisted Server context at
`/home/opc`. It is a workspace-root convenience, not a privileged root shell;
all commands continue to run as the `opc` service account.

The Home automatic workstation reporter maintains the tunnel silently every
five minutes. `make terminal-tunnel` remains available for immediate manual
startup. The Office reporter does not create a tunnel.

The project `Terminal` links in the browser console open the same private
endpoint at `http://127.0.0.1:8092`. No terminal port is opened in Oracle
firewall or OCI networking.

## Project Agent Entry Point

- `AGENTS.md`: repository-local DeveloperOS self-application entry point.
- `BOOT.md`: single entry point for AI agents working inside individual projects.
- `00_Master/ProjectRoadmapPolicy.md`: mandatory project-owned roadmap lifecycle at topic status boundaries.

Install the concise DeveloperOS entry rule in the user's global Codex guidance:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File X:\Projects\DeveloperOS\04_Tools\codex\Enable-DeveloperOSCodex.ps1
```

Existing project-specific roadmaps and generators remain canonical. Projects
without one receive a root `ROADMAP.md` at the close of their next meaningful
work unit. Browser-accessible projects expose their canonical planning state at
`/roadmap` according to the shared policy. Projects with independently
prioritizable workstreams keep the root roadmap as an overview and declare
their standard-format track files in `ROADMAPS.json`.

## Key Documents

- `00_Master/Dashboard.md`
- `00_Master/Workspace.md`
- `00_Master/GovernanceModel.md`
- `00_Master/PM_Role.md`
- `00_Master/ProjectRoadmapPolicy.md`
- `00_Master/Roadmap.md`
- `00_Master/ProjectStatus.md`
- `00_Master/Metrics.md`
- `00_Master/Decisions.md`
- `02_AI/AI_Collaboration.md`
- `02_AI/AI_Workflow_Safety_Policy.md`
- `02_AI/LanguagePolicy.md`

## Version

Current foundation version: `v0.1`

See `ROADMAP.md` for planned DeveloperOS evolution.
