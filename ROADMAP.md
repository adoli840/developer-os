# DeveloperOS Roadmap

Updated: 2026-08-03

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
| Project context routing | In Progress | DeveloperOS, OA, Gaia, and bTest use project-owned area maps, ignored incremental indexes, and the shared task context selector | Move to Done after all three application projects pass focused routing checks |
| Project roadmap continuity | Done | Global policy, templates, task guidance, and DeveloperOS self-use follow topic status boundaries | Observe project-specific generators for conflicts |
| Roadmap web publication | Done | Card-first single and linked multi-track formats plus the versioned shared renderer are implemented for project-owned `/roadmap` routes | Monitor project adapters without aggregating their planning state in DeveloperOS |
| Managed project roadmap adoption | In Progress | OA, Gaia, and bTest use bundle 3.0.0, schema version 2 track linkage, and exact Overall-to-track card parity at their own `/roadmap` routes | Move to Done after all three local routes pass data and visual parity checks |
| Docker image build minimization | Done | Shared and project-specific starts reuse images, explicit build boundaries build once, and policy checks pass across all managed projects | Monitor lifecycle and deployment commands for regressions |
| Project data synchronization governance | Done | Global policy and an optional project contract distinguish merge-safe immutable unions, authoritative directed state, and project-owned database allowlists | Pilot read-only manifest comparison in a project only after its own roadmap authorizes synchronization |
| Workspace release commands | Done | Shared deploy and local-to-server sync facades delegate only to explicit project-owned hooks and preserve Git revision identity | Add project hooks only after their deployment or data contracts are verified |
| Provider usage visibility | Done | OpenAI cost plus Oracle cost, actual A1 free-tier consumption, remaining quantities, and transparent month-end projections are published through credential-free snapshots | Monitor collector freshness and projection accuracy without exposing account service limits |
| Snapshot Manager | Planned | Create and restore tooling protects risky AI work without Git noise | Move to In Progress after workspace foundation stabilizes |

## Roadmap Details

| Stage | Item | Status | Blocker Type | Description |
|---|---|---|---|---|
| Workspace foundation | Governance entry point | Done | None | BOOT and project guidance route agents to durable workspace policies. |
| Project context routing | Area map contract | Done | None | A concise project-owned map declares source boundaries, entrypoints, focused verification, services, data stores, and risks. |
| Project context routing | Incremental Git index | Done | None | Clean files reuse Git blob IDs while only dirty and untracked files are read again. |
| Project context routing | Task selector | Done | None | The shared Make command returns a bounded first-read set and explicit expansion rule. |
| Project context routing | DeveloperOS self-application | Done | None | DeveloperOS owns a real area map and verifies its generated cache and selected context. |
| Project context routing | OA area adoption | Blocked | Operator | Define OA plugin and automation areas in the OA repository and verify representative task routing. |
| Project context routing | Gaia area adoption | Blocked | Operator | Define Gaia game, persistence, simulation, and AI areas in the Gaia repository and verify representative task routing. |
| Project context routing | bTest area adoption | Blocked | Operator | Define Elliott, Ever, data, execution, and recovery areas in the bTest repository and verify representative task routing. |
| Project roadmap continuity | Status-boundary lifecycle | Done | None | Projects update canonical roadmap state only when a defined transition occurs. |
| Roadmap web publication | Project-owned parser contract | Done | None | Each project emits canonical topics, details, statuses, blockers, and safe public fields for its own route. |
| Roadmap web publication | Shared browser renderer | Done | None | The versioned renderer displays all declared items with common responsive behavior. |
| Roadmap web publication | Overall and track card identity | Done | None | Schema version 2 rejects linked compact and large cards that differ in count, order, name, status, or description. |
| Roadmap web publication | Hover and focus descriptions | Done | None | Every detail item exposes its short explanation to pointer and keyboard users. |
| Managed project roadmap adoption | OA local route migration | Blocked | Operator | Adopt bundle 3.0.0, card-first layout, and schema version 2 linked-card parity in the OA project task. |
| Managed project roadmap adoption | Gaia local route migration | Blocked | Operator | Adopt bundle 3.0.0, card-first layout, and schema version 2 linked-card parity in the Gaia project task. |
| Managed project roadmap adoption | bTest local route migration | Blocked | Operator | Adopt bundle 3.0.0, card-first layout, and schema version 2 linked-card parity in the bTest project task. |
| Docker image build minimization | Shared lifecycle contract | Done | None | Routine starts reuse images and explicit build or release boundaries build once. |
| Project data synchronization governance | Opt-in data ownership | Done | None | Each project explicitly selects transferable data and authority direction. |
| Workspace release commands | Shared release facade | Done | None | Common commands delegate to verified project-owned deployment and synchronization hooks. |
| Provider usage visibility | Credential-free snapshots | Done | None | Public usage views consume protected server snapshots without receiving provider credentials. |
| Snapshot Manager | Scope definition | In Progress | None | Define the smallest safe create, inspect, restore, and cleanup contract before implementation. |
| Snapshot Manager | Unscoped automatic restore | Prohibited | None | Restore remains unavailable until explicit scope and verification rules are approved. |

## Current Priority

1. Adopt project-owned context areas and verify representative routing in OA,
   Gaia, and bTest without copying their project state into DeveloperOS.
2. Migrate OA, Gaia, and bTest local roadmap routes to shared bundle 3.0.0,
   schema version 2 track linkage, and exact Overall-to-track card parity.
3. Observe the first ordinary status-boundary update in each new project track.
4. Keep overall roadmaps limited to cross-track priority and release state.
5. Apply data synchronization first as read-only manifest comparison when a
   project explicitly adopts a contract.
6. Observe bTest's newly enabled project deployment hook for regressions while
   its database and kline synchronization remain explicitly disabled.
7. Define Snapshot Manager scope before moving its topic to `In Progress`.

## Latest Status Change

- Topic: Roadmap web publication
- Change: Scope narrowed while remaining Done
- Evidence or reason: DeveloperOS retains the shared policy, schema, renderer,
  and project-local route contract but no longer aggregates project roadmaps in
  its operational console.

## Next Status Transitions

1. Reopen `Docker image build minimization` only if routine startup can build,
   build and startup become ambiguous again, or deployment omits `--no-build`.
2. Move `Project context routing` to `Done` after OA, Gaia, and bTest each own a
   valid area map, ignore the generated cache, and pass representative
   `make context` checks without unrelated area expansion.
3. Move `Managed project roadmap adoption` to `Done` after OA, Gaia, and bTest
   pass linked-card data parity, shared-asset parity, desktop, mobile, hover,
   and keyboard checks.
4. Move `Snapshot Manager` from `Planned` to `In Progress` when its scoped
   create and restore contract begins implementation.
5. Update an individual project track without changing its overall roadmap
   unless a cross-track milestone, priority, dependency, or release boundary
   also changes.
6. Reopen `Project data synchronization governance` only if a project cannot
   express its identity, authority, conflict, verification, or promotion
   boundary through the standard contract.

## Risks And Blockers

- Codex sessions already running before the global guidance installation may
  need a new session before they load it automatically.
- A sandbox may hide Windows user environment registry values; `self-enable`
  performs the strict user-registration check outside that boundary, while the
  routine self-check accepts an active process registration.
- Newly split tracks need ordinary project work to demonstrate that future
  status transitions stay concise and do not drift back into duplicate logs.
- Existing schema version 1 manifests remain readable but cannot guarantee
  Overall-to-track card identity until each project completes its v2 migration.
- A stale or overly broad project area map can misroute the first inspection;
  the generated index remains advisory and shared-contract or safety evidence
  must expand the search beyond the declared area.
- Bidirectional transfer remains unsafe for any data set that lacks immutable
  payloads, stable identities, content checksums, and hard conflict detection.
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
