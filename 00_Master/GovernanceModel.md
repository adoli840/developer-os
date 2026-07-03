# Governance Model

## Purpose

DeveloperOS is the global governance repository for this workspace.

Project repositories should not copy DeveloperOS policy documents. They should reference DeveloperOS as the single source of truth.

## Core Principle

DeveloperOS is the **Global Constitution**.

Each project may define a short **Project Constitution** through `PROJECT_CONTEXT.md`.

Global rules live in one place. Project-specific exceptions live inside the project.

DeveloperOS is a decision engine, not a project dashboard.

It defines how development decisions are made across the workspace. It should not collect project information simply because it can.

## Single Source Of Truth

Do not copy these documents into individual projects.

- `AI_Rules.md`
- `CodingStandards.md`
- `LanguagePolicy.md`
- `AI_Collaboration.md`
- `AI_Workflow_Safety_Policy.md`
- `Architecture.md`
- `Decisions.md`

Copying global rules creates drift over time.

DeveloperOS should remain the single source of truth for global engineering policy.

## Project State Ownership

Projects own their own current state.

Each project repository is responsible for its own:

- README
- TODO
- Current implementation
- Current architecture
- Current roadmap
- Project-specific decisions

DeveloperOS should not duplicate this information. If a project's status changes, update the project repository instead of copying that state into DeveloperOS.

DeveloperOS may keep only lightweight references or inspection criteria when those references help apply global governance.

## Maintenance Boundary

Every DeveloperOS document should pass this test:

```text
Will this still be valuable in three years?
```

If the answer is probably not, the content likely belongs inside a project repository.

DeveloperOS should become quieter as it matures. A mature DeveloperOS changes rarely because constitutional principles are more stable than project execution details.

## Recommended Project Files

Each project should keep only small local governance files.

```text
<Project>
+-- README.md
+-- PROJECT_CONTEXT.md
+-- PROJECT_RULES.md
```

`PROJECT_CONTEXT.md` is the project-level entry point for AI agents.

`PROJECT_RULES.md` is optional and should be used only for explicit project-specific exceptions.

## Precedence Rule

When rules conflict:

1. Explicit project-specific rules in `PROJECT_CONTEXT.md` or `PROJECT_RULES.md`
2. DeveloperOS global policies
3. Existing codebase conventions
4. AI judgment

Project-specific rules take precedence only when they explicitly override a global rule.

Otherwise, DeveloperOS provides the default engineering policy for all projects in the workspace.

## Codex Startup Flow

Before making changes in any project, Codex should read documents in this order.

```text
1. Current project README.md
2. Current project PROJECT_CONTEXT.md
3. Current project PROJECT_RULES.md, if present
4. DeveloperOS global policies
5. Relevant source files
6. Implementation
```

## DeveloperOS Policies To Check

- `DeveloperOS/00_Master/AI_Rules.md`
- `DeveloperOS/00_Master/CodingStandards.md`
- `DeveloperOS/02_AI/LanguagePolicy.md`
- `DeveloperOS/02_AI/AI_Collaboration.md`
- `DeveloperOS/02_AI/AI_Workflow_Safety_Policy.md`
- `DeveloperOS/00_Master/Architecture.md`, if applicable

## Goal

The goal is stable governance without duplicated rules.

DeveloperOS defines global defaults. Projects define their own purpose, current status, roadmap, implementation state, and explicit exceptions.

