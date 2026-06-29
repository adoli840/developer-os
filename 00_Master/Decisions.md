# Decisions

## Purpose

This document records important DeveloperOS decisions.

## Format

```text
## YYYY-MM-DD - Decision Title

Status: Proposed | Accepted | Deprecated | Replaced

Context:
Decision:
Reason:
Impact:
Follow-up:
```

## 2026-06-29 - Use DeveloperOS As The Workspace Operating System

Status: Accepted

Context:

`X:\Projects` is not just a collection of project folders. It is the top-level workspace for the developer's long-term development activity.

Decision:

Use `DeveloperOS` as the governance repository. Keep `00_Master`, `01_Knowledge`, `02_AI`, `03_Blueprints`, and `04_Tools` inside it. Keep application projects outside DeveloperOS.

Reason:

The largest productivity bottleneck is not only project management. It is repeated project bootstrapping, technology selection, AI collaboration, and missing Blueprints.

Impact:

Before starting new projects or features, consult DeveloperOS governance, AI rules, and Blueprints.

## 2026-06-29 - Manage DeveloperOS As A Single Git Repository

Status: Accepted

Context:

Keeping DeveloperOS folders directly under `X:\Projects` makes Git boundaries unclear.

Decision:

Move all DeveloperOS folders under `X:\Projects\DeveloperOS` and initialize Git only inside DeveloperOS.

Reason:

These folders all belong to development operations: governance, rules, knowledge, Blueprints, and tools.

Impact:

DeveloperOS is the development operations repository. Application projects remain independent repositories.

## 2026-06-29 - Prioritize Active Project Inspection

Status: Accepted

Context:

Discarded projects were removed. Before starting new development, the remaining active projects should be inspected for quality, convenience, and efficiency.

Decision:

Use inspection-first mode for the near term.

Reason:

A stable base requires clear setup, documentation, configuration, tests, structure, and automation.

Impact:

Project inspection, improvement candidates, and commonization review take priority over new feature proposals.

## 2026-06-29 - Operate GPT And Codex As One AI Development Team

Status: Accepted

Context:

The developer uses GPT and Codex together to save Codex tokens and separate design from implementation.

Decision:

GPT acts like a planning and review lead. Codex acts like a senior developer responsible for implementation, file edits, tests, and Git work.

Reason:

Long design discussions are cheaper and more effective in GPT. Codex should focus on actual project changes and verification.

Impact:

Use `DeveloperOS/02_AI/AI_Collaboration.md` as the shared collaboration guide. Important context must be captured in DeveloperOS, not only in chat.

## 2026-06-29 - Separate Git History From AI Snapshots

Status: Accepted

Context:

AI can modify several files or restructure projects. Recovery must be simple, but Git history should stay readable.

Decision:

Use Git for meaningful final development history. Use snapshots for short-term AI recovery.

Reason:

Git history should remain human-readable. Snapshots should provide fast rollback for risky AI work.

Impact:

Codex creates snapshots before large or risky changes. Git commits happen at meaningful boundaries such as feature completion, meaningful refactoring completion, or end-of-day checkpoint.

## 2026-06-29 - Use English As The Official DeveloperOS Documentation Language

Status: Accepted

Context:

DeveloperOS is a long-term knowledge base for GPT, Codex, future AI coding agents, IDEs, and developer tools.

Decision:

All governance documents under DeveloperOS shall be written in English. Existing Korean governance documents must be migrated to English to maintain a single documentation language.

Reason:

English is the most compatible language for the software ecosystem, search, IDEs, technical terminology, and AI coding agents. The developer may still communicate with AI in Korean.

Impact:

New long-term DeveloperOS documents are written in English. Existing governance documents are migrated to AI-first technical English. Personal knowledge notes may use Korean only when that preserves important local or personal context.

## 2026-06-29 - Use DeveloperOS As The Single Source Of Truth For Global Policy

Status: Accepted

Context:

Copying DeveloperOS policy documents into projects causes policy drift over time.

Decision:

DeveloperOS is the single source of truth for global engineering policy. Projects reference DeveloperOS instead of copying policy documents. Project-specific exceptions live in `PROJECT_CONTEXT.md` or `PROJECT_RULES.md`.

Reason:

Duplicated rules become inconsistent and confuse AI agents.

Impact:

Before project work, Codex reads `README.md`, `PROJECT_CONTEXT.md`, optional `PROJECT_RULES.md`, and then DeveloperOS global policies. Explicit project rules override DeveloperOS only when they clearly say so.

## 2026-06-29 - Operate DeveloperOS As An AI Project Manager

Status: Accepted

Context:

The developer wants DeveloperOS to help with schedule awareness, priorities, progress, and productivity without becoming a harsh taskmaster.

Decision:

DeveloperOS should act as an AI Project Manager when invoked. It should review roadmap, weekly goals, project status, metrics, backlog, and decisions before recommending work.

Reason:

Codex and GPT do not run continuously or remember future dates by themselves. DeveloperOS should therefore work as an invoked PM system that evaluates current state whenever the developer starts a work session.

Impact:

DeveloperOS now includes `PM_Role.md`, `Roadmap.md`, `ProjectStatus.md`, `Metrics.md`, and `DailyReview.md`. Codex should provide soft challenges when the requested work conflicts with higher-priority roadmap evidence, while leaving final control to the developer.

## 2026-06-29 - Optimize Codex Tokens Through Role Separation

Status: Accepted

Context:

Codex token usage grows when it performs broad project analysis, long architectural reasoning, or context restoration from vague requests.

Decision:

Use GPT for expensive reasoning and design. Use Codex for implementation, scoped refactoring, verification, and Git work. When a design document exists, Codex treats it as the implementation specification.

Reason:

This reduces repeated reasoning, limits broad source exploration, and keeps Codex focused on changes that require direct workspace access.

Impact:

Codex should avoid large architectural analysis unless explicitly requested, required by missing design, or needed because the code contradicts the design. Project README, PROJECT_CONTEXT, DeveloperOS decisions, and GPT handoff documents become the preferred context restoration path.


## 2026-06-29 - Rename Templates To Blueprints

Status: Accepted

Context:

`03_Templates` suggested isolated file templates, but the intended role is a reusable project starting point that includes structure, documentation, Docker, Git defaults, and AI context.

Decision:

Rename `03_Templates` to `03_Blueprints` and move generic project starter files under `03_Blueprints/Project`.

Reason:

Blueprint better represents a complete project design rather than a single reusable file. This also prevents confusion between DeveloperOS root `.gitignore` and project blueprint `.gitignore`.

Impact:

DeveloperOS has one root `.gitignore` for itself. Blueprint-specific `.gitignore` files live inside individual blueprints and are copied only when creating new projects.
