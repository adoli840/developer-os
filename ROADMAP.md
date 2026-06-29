# DeveloperOS Roadmap

## Purpose

This roadmap defines the planned evolution of DeveloperOS as a long-term development platform.

DeveloperOS should grow gradually. Each version should add a meaningful operating capability without making the system unnecessarily complex.

## Version Plan

| Version | Theme | Goal |
|---|---|---|
| v0.1 | Workspace Foundation | Establish governance, AI collaboration, safety policy, blueprints, and PM documents |
| v0.2 | Snapshot Manager | Add create/restore tooling for AI work snapshots |
| v0.3 | AI Project Manager | Generate daily reviews, priority recommendations, stale project warnings, and developer score summaries |
| v0.4 | Blueprint Generator | Generate new project folders from approved blueprints |
| v0.5 | Automatic Project Review | Inspect project README, structure, configuration, tests, and improvement candidates |
| v1.0 | Stable DeveloperOS Platform | Provide a stable, repeatable operating model for all projects in the workspace |

## v0.1 Scope

DeveloperOS v0.1 establishes the foundation.

Included capabilities:

- Workspace governance
- Global engineering standards
- AI collaboration model
- GPT/Codex role separation
- Token optimization policy
- Snapshot safety policy
- Language policy
- Blueprint system
- AI Project Manager documents
- Initial roadmap and metrics structure

## v0.2 Candidate Scope

Snapshot Manager should provide:

- Snapshot creation before risky AI work
- Snapshot metadata including purpose, timestamp, and target files
- Simple restore command
- Git-independent recovery
- Snapshot cleanup policy

## v0.3 Candidate Scope

AI Project Manager should provide:

- Daily review generation
- Roadmap alignment check
- Project staleness detection
- Priority recommendation
- Developer Score summary
- Soft challenge when requested work conflicts with higher-priority evidence

## v0.4 Candidate Scope

Blueprint Generator should provide:

- Project creation from `03_Blueprints`
- README and PROJECT_CONTEXT generation
- Initial `.gitignore`, Docker, and decision files
- Optional language/database presets

## v0.5 Candidate Scope

Automatic Project Review should provide:

- README quality inspection
- Setup and run command inspection
- Configuration and environment variable review
- Test or verification review
- Structure and maintainability review
- Convenience and efficiency improvement proposals

## v1.0 Definition

DeveloperOS v1.0 should be considered stable when:

- New projects can be created from blueprints.
- Risky AI work can be snapshotted and restored.
- Active projects can be reviewed consistently.
- AI Project Manager summaries can guide daily work.
- GPT and Codex can collaborate through DeveloperOS with minimal repeated context restoration.
