# DeveloperOS Roadmap

Updated: 2026-08-06

## Direction

This roadmap defines the planned evolution of DeveloperOS as a long-term development platform.

DeveloperOS should grow gradually. Each version should add a meaningful operating capability without making the system unnecessarily complex.

## Current Milestone

- Objective: Complete context routing and shared roadmap 3.1 adoption across
  the active application projects.
- Status: In Progress
- Completion signal: OA, Gaia, and bTest pass their project-owned context
  routing checks and local roadmap dependency, card-parity, interaction, and
  presentation checks with the current shared bundle.

## Roadmap Topics

| Topic | Status | Completion Signal | Next Transition |
|---|---|---|---|
| Workspace foundation | Done | Self-application and roadmap lifecycle and publication contracts are confirmed across active projects | Observe the shared contracts for regressions |
| Project context routing | In Progress | DeveloperOS, OA, Gaia, and bTest use project-owned area maps, ignored incremental indexes, and the shared task context selector | Move to Done after all three application projects pass focused routing checks |
| Roadmap web publication | Done | Version 3.1 publishes compact expandable topic cards, validated dependency flows, exact linked-track identity, and accessible blocker presentation at `/roadmap` | Monitor project adapters without duplicating project state |
| Managed project roadmap adoption | In Progress | OA, Gaia, and bTest use the current shared bundle, schema version 2 track linkage, exact Overall-to-track card parity, dependency flows, and current blocker semantics at their own `/roadmap` routes | Move to Done after all three local routes pass data, interaction, and visual parity checks |
| Docker image build minimization | In Progress | Shared and project-specific starts reuse images, explicit build boundaries build once, and policy checks pass across all managed projects | Resolve or explicitly classify bTest build-cache cleanup findings, then rerun the workspace policy check |
| Project data synchronization governance | Done | Global policy and an optional project contract distinguish merge-safe immutable unions, authoritative directed state, and project-owned database allowlists | Pilot read-only manifest comparison in a project only after its own roadmap authorizes synchronization |
| Workspace release commands | Done | Shared deploy and local-to-server sync facades delegate only to explicit project-owned hooks and preserve Git revision identity | Add project hooks only after their deployment or data contracts are verified |
| Provider usage visibility | Done | OpenAI cost plus Oracle cost, actual A1 free-tier consumption, remaining quantities, and transparent month-end projections are published through credential-free snapshots | Monitor collector freshness and projection accuracy without exposing account service limits |

## Roadmap Details

| Stage | Item | Status | Blocker Type | Description |
|---|---|---|---|---|
| Workspace foundation | Governance entry point | Done | None | BOOT and project guidance route agents to durable workspace policies. |
| Project context routing | Area map contract | Done | None | A concise project-owned map declares source boundaries, entrypoints, focused verification, services, data stores, and risks. |
| Project context routing | Incremental Git index | Done | None | Clean files reuse Git blob IDs while only dirty and untracked files are read again. |
| Project context routing | Task selector | Done | None | The shared Make command returns a bounded first-read set and explicit expansion rule. |
| Project context routing | DeveloperOS self-application | Done | None | DeveloperOS owns a real area map and verifies its generated cache and selected context. |
| Project context routing | OA area adoption | Blocked | Dev | Define OA plugin and automation areas in the OA repository and verify representative task routing. |
| Project context routing | Gaia area adoption | Blocked | Dev | Define Gaia game, persistence, simulation, and AI areas in the Gaia repository and verify representative task routing. |
| Project context routing | bTest area adoption | Blocked | Dev | Define Elliott, Ever, data, execution, and recovery areas in the bTest repository and verify representative task routing. |
| Roadmap web publication | Shared parser contract | Done | None | The console validates canonical topics, details, dependency endpoints, statuses, blockers, and safe public fields. |
| Roadmap web publication | Shared browser renderer | Done | None | Version 3.1 renders compact expandable cards, dependency flows, and accessible blocker states with common responsive behavior. |
| Roadmap web publication | Overall and track card identity | Done | None | Schema version 2 rejects linked compact and large cards that differ in count, order, name, status, or description. |
| Roadmap web publication | Hover and focus descriptions | Done | None | Every detail item exposes its short explanation to pointer and keyboard users. |
| Managed project roadmap adoption | OA local route migration | Blocked | Dev | Apply the current policy and bundle, then complete dependency, desktop, mobile, hover, and keyboard parity checks in OA. |
| Managed project roadmap adoption | Gaia local route migration | Blocked | Dev | Apply the current policy, bundle, dependency flow, and schema version 2 linked-card parity in Gaia. |
| Managed project roadmap adoption | bTest local route migration | Blocked | Dev | Apply the current policy, bundle, dependency flow, and schema version 2 linked-card parity in bTest. |
| Docker image build minimization | Shared lifecycle contract | Done | None | Routine starts reuse images and explicit build or release boundaries build once. |
| Docker image build minimization | bTest cache cleanup compliance | In Progress | None | Determine whether the scheduled build-cache cleanup is an allowed maintenance boundary or must be changed to satisfy the shared policy. |
| Project data synchronization governance | Opt-in data ownership | Done | None | Each project explicitly selects transferable data and authority direction. |
| Workspace release commands | Shared release facade | Done | None | Common commands delegate to verified project-owned deployment and synchronization hooks. |
| Provider usage visibility | Credential-free snapshots | Done | None | Public usage views consume protected server snapshots without receiving provider credentials. |

## Roadmap Dependencies

| From | To | Description |
|---|---|---|
| Governance entry point | Area map contract | Project context boundaries depend on agents loading the workspace governance entry point. |
| Area map contract | Incremental Git index | The cache can index selectively only after a project declares its source areas. |
| Area map contract | Task selector | Task routing requires reviewed project-owned area definitions. |
| Incremental Git index | Task selector | The selector uses the incremental index to avoid repeated broad inspection. |
| Task selector | OA area adoption | OA adoption is verified through representative task selections. |
| Task selector | Gaia area adoption | Gaia adoption is verified through representative task selections. |
| Task selector | bTest area adoption | bTest adoption is verified through representative task selections. |
| Shared parser contract | Shared browser renderer | The renderer depends on validated and safely escaped roadmap data. |
| Shared parser contract | Overall and track card identity | Linked-card identity is enforced while canonical roadmap data is parsed. |
| Shared browser renderer | OA local route migration | OA needs the shared renderer before its local route can claim presentation parity. |
| Shared browser renderer | Gaia local route migration | Gaia needs the shared renderer before its local route can claim presentation parity. |
| Shared browser renderer | bTest local route migration | bTest needs the shared renderer before its local route can claim presentation parity. |
| Overall and track card identity | OA local route migration | OA migration must preserve exact Overall-to-track card identity. |
| Overall and track card identity | Gaia local route migration | Gaia migration must preserve exact Overall-to-track card identity. |
| Overall and track card identity | bTest local route migration | bTest migration must preserve exact Overall-to-track card identity. |
| OA local route migration | Managed project roadmap adoption | Workspace adoption completes only after OA passes its project-owned route checks. |
| Gaia local route migration | Managed project roadmap adoption | Workspace adoption completes only after Gaia passes its project-owned route checks. |
| bTest local route migration | Managed project roadmap adoption | Workspace adoption completes only after bTest passes its project-owned route checks. |
| Shared lifecycle contract | bTest cache cleanup compliance | bTest maintenance must preserve the shared rule that ordinary lifecycle operations never build images. |

## Current Priority

1. Adopt project-owned context areas and verify representative routing in OA,
   Gaia, and bTest without copying their project state into DeveloperOS.
2. Migrate OA, Gaia, and bTest local roadmap routes to shared bundle 3.1,
   dependency flows, current blocker semantics, schema version 2 track linkage,
   and exact Overall-to-track card parity.
3. Observe the first ordinary status-boundary update in each new project track.
4. Keep overall roadmaps limited to cross-track priority and release state.
5. Apply data synchronization first as read-only manifest comparison when a
   project explicitly adopts a contract.
6. Resolve or explicitly classify bTest's build-cache cleanup policy findings.
7. Observe bTest's newly enabled project deployment hook for regressions while
   its database and kline synchronization remain explicitly disabled.

## Latest Status Change

- Topic: Docker image build minimization
- Change: Reopened from Done to In Progress
- Evidence or reason: The shared Make contract passes for DeveloperOS, OA,
  Gaia, and bTest, but the workspace Docker policy check reports four bTest
  build-cache cleanup files outside its recognized deployment boundary.

## Next Status Transitions

1. Move `Docker image build minimization` back to `Done` after bTest's scheduled
   build-cache cleanup is either brought inside an allowed maintenance contract
   or safely changed, and the workspace policy check passes.
2. Move `Project context routing` to `Done` after OA, Gaia, and bTest each own a
   valid area map, ignore the generated cache, and pass representative
   `make context` checks without unrelated area expansion.
3. Move `Managed project roadmap adoption` to `Done` after OA, Gaia, and bTest
   pass dependency validation, linked-card data parity, shared-asset parity,
   desktop, mobile, hover, expansion, and keyboard checks.
4. Update an individual project track without changing its overall roadmap
   unless a cross-track milestone, priority, dependency, or release boundary
   also changes.
5. Reopen `Project data synchronization governance` only if a project cannot
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
- Dependency arrows remain absent in a project until its canonical roadmap
  explicitly records real prerequisite relationships.
- The bTest build-cache cleanup service, timer, script, and test currently fail
  the shared Docker policy check and require project-owned review.
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
| v0.2 | AI Project Manager | Generate daily reviews, priority recommendations, stale project warnings, and developer score summaries |
| v0.3 | Blueprint Generator | Generate new project folders from approved blueprints |
| v0.4 | Automatic Project Review | Inspect project README, structure, configuration, tests, and improvement candidates |
| v1.0 | Stable DeveloperOS Platform | Provide a stable, repeatable operating model for all projects in the workspace |

## v0.1 Scope

DeveloperOS v0.1 establishes the foundation.

Included capabilities:

- Workspace governance
- Global engineering standards
- AI collaboration model
- GPT/Codex role separation
- Token optimization policy
- Git safety policy
- Language policy
- Blueprint system
- AI Project Manager documents
- Initial roadmap and metrics structure
- Project-owned roadmap continuity at topic status boundaries

## v0.2 Candidate Scope

AI Project Manager should provide:

- Daily review generation
- Roadmap alignment check
- Project staleness detection
- Priority recommendation
- Developer Score summary
- Soft challenge when requested work conflicts with higher-priority evidence

## v0.3 Candidate Scope

Blueprint Generator should provide:

- Project creation from `03_Blueprints`
- README and PROJECT_CONTEXT generation
- Initial `.gitignore`, Docker, and decision files
- Optional language/database presets

## v0.4 Candidate Scope

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
- Source-code recovery is handled entirely through Git.
- Active projects can be reviewed consistently.
- AI Project Manager summaries can guide daily work.
- GPT and Codex can collaborate through DeveloperOS with minimal repeated context restoration.
