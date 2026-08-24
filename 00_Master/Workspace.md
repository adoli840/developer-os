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
- Git safety and recovery policy

## Top-Level Structure

```text
X:\Projects

+-- DeveloperOS
|   +-- 00_Master
|   +-- 01_Knowledge
|   +-- 02_AI
|   +-- 03_Blueprints
|   +-- 04_Tools
|   +-- .git
+-- <Project A>
+-- <Project B>
+-- <Project C>
```

## Local Drive Allocation Policy

DeveloperOS uses these default roles for local workstation storage:

| Drive | Role | Default contents |
|---|---|---|
| `X:` | Development workspace and temporary data | Source repositories, working trees, development tools and materials, build output, caches, scratch data, disposable validation data, and other reproducible intermediate state |
| `D:` | Durable development output | Backups, archives, exported datasets, released artifacts, retained evidence, model bundles, and other development outputs that must persist independently of a working tree |
| `C:` | Restricted fallback | Operating-system or application-managed state, or data that cannot reasonably be placed on `X:` or `D:` because of a verified platform or tool constraint |

Use `X:` for active development and reproducible temporary state. Use `D:`
when the output is intended for durable retention. Do not place a new
repository, temporary workload, cache, backup, archive, or durable project
artifact on `C:` when `X:` or `D:` can satisfy the requirement.

An exception for `C:` must be based on an actual operating-system,
application, permission, compatibility, or bootstrapping constraint. Tool
defaults alone should be redirected when the tool safely supports an explicit
location.

This policy does not authorize automatic relocation or deletion of existing
data. Existing paths are migrated only through a separate bounded plan that
identifies ownership, integrity checks, rollback, and every consumer that must
be updated. Drive placement also does not replace project-specific authority,
retention, backup, secret-handling, or data-synchronization contracts.

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

### 04_Tools

DeveloperOS automation tools such as project inspection helpers and blueprint generators.

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


