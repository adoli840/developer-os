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
- Provide safe recovery through snapshots before risky AI work.
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
+-- 05_Snapshots    # Snapshot location; runtime contents ignored by Git
+-- deployment      # Deployment standards, templates, and readiness checks
```

## Core Policies

- DeveloperOS is the single source of truth for global engineering policy.
- DeveloperOS is the constitution of the workspace, not the government of each project.
- Projects reference DeveloperOS instead of copying global policy documents.
- Projects own their own README, TODO, roadmap, implementation state, and current architecture.
- GPT handles thinking; Codex handles implementation.
- Codex treats existing design documents as implementation specifications.
- Git is for meaningful final history; snapshots are for short-term AI recovery.
- DeveloperOS governance documents are written in English.
- The developer may communicate with GPT and Codex in Korean.

## Shared Developer Commands

DeveloperOS provides shared Make targets through `04_Tools/make/DeveloperOS.mk`.

Enable the shared targets once from PowerShell:

```powershell
X:\Projects\DeveloperOS\04_Tools\make\Enable-DeveloperOSMake.ps1
```

After enabling, any project directory can use:

```bash
make git-check
```

Docker projects can also use:

```bash
make run
make b-run
make down
make dh-b-push
make dh-pull
```

The Docker targets auto-detect `docker-compose.yml`, `compose.yml`, `docker-compose.yaml`, or `compose.yaml` in the current project directory.

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
project-owned state.

Run locally:

```powershell
make console-run
```

Deploy the public read-only console to the Oracle server:

```powershell
git add <files>
git commit -m "<message>"
git push origin main
make console-deploy
```

Deployment is accepted only from a clean `main` branch that exactly matches
`origin/main`. The release is built from the committed Git revision, never
from uncommitted local files.

The deployed service listens on port `8080`. See `console/README.md` for its
security boundary, management command allowlist, and OpenAI usage snapshot
behavior.

The Oracle deployment also installs:

- Daily OA and Gaia PostgreSQL backups with 14-day retention.
- Weekly isolated restore verification in temporary PostgreSQL containers.
- Deployment revision and container image comparison.
- Git end-of-work checks and local operational alerts.

Inspect or run the backup controls from the DeveloperOS terminal:

```powershell
make console-backup-status
make console-backup
make console-backup-verify
```

The Home computer reports its local Git status to the server while powered on.
The report contains repository state only and is transferred through SSH:

```powershell
make workstation-home-install
make workstation-home-report
```

The scheduled reporter runs every five minutes while the current Windows user
session is available. When the Home computer is off, the console preserves the
last report and marks it offline. Office reporting is intentionally not
configured from the Home computer.

The server terminal is deliberately separate from the public console. It
listens only on server loopback and is reached from the Home computer through
the existing SSH key:

```powershell
make terminal-tunnel-install
make terminal-developer-os
make terminal-oa
make terminal-gaia
```

The project `Terminal` links in the browser console open the same private
endpoint at `http://127.0.0.1:8092`. No terminal port is opened in Oracle
firewall or OCI networking.

## Project Agent Entry Point

- `BOOT.md`: single entry point for AI agents working inside individual projects.

## Key Documents

- `00_Master/Dashboard.md`
- `00_Master/Workspace.md`
- `00_Master/GovernanceModel.md`
- `00_Master/PM_Role.md`
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
