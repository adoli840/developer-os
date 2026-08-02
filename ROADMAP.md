# DeveloperOS Roadmap

Updated: 2026-08-02

## Direction

This roadmap defines the planned evolution of DeveloperOS as a long-term development platform.

DeveloperOS should grow gradually. Each version should add a meaningful operating capability without making the system unnecessarily complex.

## Current Milestone

- Objective: Prepare the v0.2 Snapshot Manager after completing and observing
  the v0.1 workspace foundation across active projects.
- Status: Planned
- Completion signal: Snapshot create, inspect, restore, and cleanup operations
  protect scoped risky work without adding generated state to project Git.

## Roadmap Topics

| Topic | Status | Completion Signal | Next Transition |
|---|---|---|---|
| Workspace foundation | Done | Self-application and roadmap lifecycle and publication contracts are confirmed across active projects | Observe the shared contracts for regressions |
| Project roadmap continuity | Done | Global policy, templates, task guidance, and DeveloperOS self-use follow topic status boundaries | Observe project-specific generators for conflicts |
| Roadmap web publication | Done | Single and multi-track formats, validated public fields, and DeveloperOS `/roadmap` view are implemented and tested | Monitor adapters without duplicating project state |
| Managed project roadmap adoption | Done | OA, Gaia, and bTest expose canonical overall and track fields at their own `/roadmap` routes | Maintain each track at status boundaries |
| Docker image build minimization | Done | Shared and project-specific starts reuse images, explicit build boundaries build once, and policy checks pass across all managed projects | Monitor lifecycle and deployment commands for regressions |
| Snapshot Manager | Planned | Create and restore tooling protects risky AI work without Git noise | Move to In Progress after workspace foundation stabilizes |

## Current Priority

1. Observe the first ordinary status-boundary update in each new project track.
2. Keep overall roadmaps limited to cross-track priority and release state.
3. Define Snapshot Manager scope before moving its topic to `In Progress`.

## Latest Status Change

- Topic: Docker image build minimization
- Change: Added -> Done
- Evidence or reason: The global policy, shared no-build Make lifecycle,
  project-specific command alignment, deployment no-build starts, user-facing
  guidance, and cross-project static checks are implemented and passing.

## Next Status Transitions

1. Reopen `Docker image build minimization` only if routine startup can build,
   build and startup become ambiguous again, or deployment omits `--no-build`.
2. Reopen `Managed project roadmap adoption` only if a route, manifest, or
   canonical ownership contract regresses.
3. Move `Snapshot Manager` from `Planned` to `In Progress` when its scoped
   create and restore contract begins implementation.
4. Update an individual project track without changing its overall roadmap
   unless a cross-track milestone, priority, dependency, or release boundary
   also changes.

## Risks And Blockers

- Codex sessions already running before the global guidance installation may
  need a new session before they load it automatically.
- A sandbox may hide Windows user environment registry values; `self-enable`
  performs the strict user-registration check outside that boundary, while the
  routine self-check accepts an active process registration.
- Newly split tracks need ordinary project work to demonstrate that future
  status transitions stay concise and do not drift back into duplicate logs.
- No active blocker is known for new project sessions.

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
- Project-owned roadmap continuity at topic status boundaries

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
