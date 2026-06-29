# DeveloperOS

## Purpose

DeveloperOS is the developer's long-term operating system for software development work.

It is not an application project. It is the governance, memory, safety, planning, and AI collaboration layer for all projects in the workspace.

## Mission

DeveloperOS exists to:

- Keep project work consistent across many repositories.
- Reduce repeated project setup decisions.
- Preserve engineering decisions and lessons.
- Make GPT and Codex work like one AI development team.
- Minimize Codex token usage by separating planning from implementation.
- Provide safe recovery through snapshots before risky AI work.
- Act as an invoked AI Project Manager that recommends priorities with evidence.

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
+-- 04_Tools        # Future automation tools
+-- 05_Snapshots    # Snapshot location; runtime contents ignored by Git
```

## Core Policies

- DeveloperOS is the single source of truth for global engineering policy.
- Projects reference DeveloperOS instead of copying global policy documents.
- GPT handles thinking; Codex handles implementation.
- Codex treats existing design documents as implementation specifications.
- Git is for meaningful final history; snapshots are for short-term AI recovery.
- DeveloperOS governance documents are written in English.
- The developer may communicate with GPT and Codex in Korean.

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
