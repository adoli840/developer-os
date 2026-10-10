# Governance Model

## Purpose

DeveloperOS is the governance repository for its own work and for projects that explicitly opt in.

Project repositories should not copy DeveloperOS policy documents. They should reference DeveloperOS as the single source of truth.

## Core Principle

DeveloperOS is an **optional shared constitution**.

Each project may define a short **Project Constitution** through `PROJECT_CONTEXT.md`.

Opted-in shared rules live in one place. Independent projects may define their own constitution entirely inside the project.

## Self-Application Rule

DeveloperOS is also a project repository and must follow every applicable
policy it defines for other projects. This includes roadmap continuity, Git
safety, coding and language rules, verification, and
meaningful decision records.

DeveloperOS also applies the Docker image build minimization policy to itself.
Because it has no root container application, its applicable implementation is
zero routine Docker image builds and a non-containerized console deployment.

A capability may be excluded only when DeveloperOS structurally lacks the
corresponding application surface, such as a root Docker Compose stack or an
application PostgreSQL database. Every exclusion must be explicit in the root
`PROJECT_RULES.md`; convenience alone is not a valid reason.

DeveloperOS is a decision engine, not a project dashboard.

It defines how development decisions are made across the workspace. It should not collect project information simply because it can.

## Single Source Of Truth

Do not copy these documents into individual projects.

- `AI_Rules.md`
- `CodingStandards.md`
- `DockerImageBuildPolicy.md`
- `LanguagePolicy.md`
- `AI_Collaboration.md`
- `AI_Workflow_Safety_Policy.md`
- `Architecture.md`
- `Decisions.md`

Copying global rules creates drift over time.

DeveloperOS should remain the single source of truth for shared policy only where a project has opted in.

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

Otherwise, the project remains governed by its own local rules and conventions. DeveloperOS provides defaults only after explicit opt-in.

## Codex Startup Flow

Before making changes in an opted-in project, Codex should read documents in this order. Independent projects should follow their own startup flow.

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

The goal is stable optional governance without duplicated rules or forced adoption.

DeveloperOS defines optional defaults. Projects define their own purpose, current status, roadmap, implementation state, and rules.

