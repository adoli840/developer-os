# Workspace

## Purpose

This document defines how `X:\Projects` is organized and how DeveloperOS governs the workspace.

## Role

DeveloperOS is the global operating system for the developer's project workspace.

Individual projects remain independent. DeveloperOS manages shared development operations only.

## DeveloperOS Responsibilities

- Workspace-level planning
- Project priority management
- Long-term development direction
- Global engineering rules
- Shared Blueprints
- AI collaboration policy
- Project bootstrap standards
- Project inspection standards
- Snapshot and recovery policy

## Top-Level Structure

```text
X:\Projects

+-- DeveloperOS
|   +-- 00_Master
|   +-- 01_Knowledge
|   +-- 02_AI
|   +-- 03_Blueprints
|   +-- 04_Tools
|   +-- 05_Snapshots
|   +-- .git
+-- <Project A>
+-- <Project B>
+-- <Project C>
```

## Git Boundary

`DeveloperOS` is the dedicated repository for governance, Blueprints, AI policy, and development operations.

Projects must not be placed inside DeveloperOS. Each project may have its own Git repository inside its own project directory.

Avoid this structure:

```text
X:\Projects\.git
X:\Projects\<Project>\.git
```

Use this structure:

```text
X:\Projects\DeveloperOS\.git
X:\Projects\<Project>\.git
```

## Directory Responsibilities

### 00_Master

Workspace governance, architecture, decisions, dashboard, standards, and review documents.

### 01_Knowledge

Personal knowledge, lessons learned, troubleshooting notes, research notes, and domain context.

### 02_AI

AI collaboration rules, prompts, memory, safety policy, language policy, and review policy.

### 03_Blueprints

Reusable project blueprints. A blueprint can include documentation, governance context, Docker files, Git defaults, prompts, and project structure.

### 05_Snapshots

Reserved location for AI work snapshots. Snapshot contents are ignored by Git; only the directory README is tracked.

### 04_Tools

DeveloperOS automation tools such as Snapshot Manager, project inspection helpers, and blueprint generators.

## Governance Model

DeveloperOS is the global governance repository for this workspace.

Projects should not copy global DeveloperOS policy documents. Projects should reference DeveloperOS as the single source of truth and keep only short local files such as `PROJECT_CONTEXT.md` and optional `PROJECT_RULES.md`.

See `DeveloperOS/00_Master/GovernanceModel.md`.

## Operating Rule

Before starting a new feature or project, check documents in this order:

1. `DeveloperOS/00_Master`
2. `DeveloperOS/02_AI`
3. `DeveloperOS/03_Blueprints`
4. Existing project documentation
5. Relevant source files

During the current phase, project inspection and workspace stabilization take priority over new implementation.


