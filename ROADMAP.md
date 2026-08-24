# DeveloperOS Roadmap

Updated: 2026-08-15

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
| Shared native Docker infrastructure | Done | One Desktop-independent launcher fixes Ubuntu, native CLI/Compose, socket, config, and credential helper while preserving all native runtime and data assets | Keep daemon restart coordinated and monitor the sealed boundary for drift |
| Managed project native Docker adoption | In Progress | bTest, OA, and Gaia local repository commands use the shared launcher and pass runtime/data verification without changing remote server Docker behavior | Migrate each project-owned local wrapper and direct invocation, then reopen its deletion gate independently |
| Docker Desktop deletion readiness | Done | Every Desktop VHD asset is classified, unique persistent data is externally preserved, and bTest, OA, and Gaia return explicit project votes | Await a separate global removal authorization; do not perform destructive cleanup from roadmap status alone |
| Project data synchronization governance | Done | Global policy and an optional project contract distinguish merge-safe immutable unions, authoritative directed state, and project-owned database allowlists | Pilot read-only manifest comparison in a project only after its own roadmap authorizes synchronization |
| Managed project operational authority | Done | Green project operations, Amber user decisions, Red shared-infrastructure escalation, and absolute fail-closed boundaries are explicit | Observe bTest 2.12.3 and refine only if a real ownership ambiguity recurs |
| Workspace release commands | Done | Shared deploy and local-to-server sync facades delegate only to explicit project-owned hooks and preserve Git revision identity | Add project hooks only after their deployment or data contracts are verified |
| Provider usage visibility | Done | Oracle actual A1 free-tier consumption, remaining quantities, and transparent month-end projections are available through the credential-free `/oracle` view; OpenAI Costs snapshots remain internal | Monitor Oracle collector freshness and projection accuracy; reserve OpenAI Costs data for future orchestration measurement |
| AI model routing guidance | Done | Meaningful work receives a documented Luna, Luna-to-Sol, or Sol recommendation, and multi-stage work uses explicit user-confirmed handoffs at natural boundaries | Observe recommendations and refine thresholds only when evidence shows repeated misrouting |
| High-impact development protocol | Done | High-failure-cost work uses the shared GPT-User-Codex seven-step process with peer review and final user decision, while low-risk work remains lightweight | Observe protocol use and refine only when review evidence shows a recurring gap |
| GPT-Codex review orchestration | In Progress | Session Handoff, guarded exactly-once transports, version-bound AUTO validation, and token-efficient Mainline continuations are implemented; further orchestration development is explicitly paused | Resume only after an explicit user instruction; do not run new pilots or expand transports while paused |

## Roadmap Details

| Stage | Item | Status | Blocker Type | Description |
|---|---|---|---|---|
| Workspace foundation | Governance entry point | Done | None | BOOT and project guidance route agents to durable workspace policies. |
| Project context routing | Area map contract | Done | None | A concise project-owned map declares source boundaries, entrypoints, focused verification, services, data stores, and risks. |
| Project context routing | Incremental Git index | Done | None | Clean files reuse Git blob IDs while only dirty and untracked files are read again. |
| Project context routing | Task selector | Done | None | The shared Make command returns a bounded first-read set and explicit expansion rule. |
| Project context routing | DeveloperOS self-application | Done | None | DeveloperOS owns a real area map and verifies its generated cache and selected context. |
| Project context routing | Context identity substrate | Done | None | Versioned non-authoritative context seals and dirty-tree scope manifests bind project, lane, canonical sources, selected content, and workspace identities with source-wins fail-closed validation while leaving selection and orchestration behavior unchanged. |
| Project context routing | Context efficiency observability baseline | Done | None | A project-and-lane-isolated metrics sidecar measures unchanged context selection, source repetition, identity reuse, dirty scanning, build duration, and packet/output sizes without persisting source content or inferred token usage. |
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
| Shared native Docker infrastructure | Canonical launcher and config | Done | None | The argument-array launcher fixes Ubuntu, `/run/docker-wsl.sock`, native Docker and Compose paths, and the private `pass`-backed config while rejecting endpoint overrides. |
| Shared native Docker infrastructure | Desktop plugin isolation | Done | None | Fifteen unowned Desktop-mount Docker CLI plugin symlinks were recorded and removed without changing native packages, runtime, data, or the Docker Desktop installation. |
| Managed project native Docker adoption | bTest repository command migration | In Progress | None | Shared Make uses the canonical launcher, but remaining direct local Docker calls require project-owned classification and migration before deletion approval. |
| Managed project native Docker adoption | OA repository command migration | Blocked | Dev | Replace the project-local `scripts/docker_native.py` boundary with the shared launcher while preserving remote server commands and revalidate runtime/data. |
| Managed project native Docker adoption | Gaia repository command migration | Blocked | Dev | Replace the project-local `scripts/docker-native.cmd` boundary with the shared launcher while preserving remote server commands and revalidate runtime/data. |
| Docker Desktop deletion readiness | Cross-project VHD inventory | Done | None | Eighty-two Desktop assets are individually inventoried; the stopped VHD has a read-only hash-identical forensic copy and no destructive action was performed. |
| Docker Desktop deletion readiness | bTest persistent-data vote | Done | None | All 679 user tables were compared; the 4,709 meaningful Desktop-only provenance rows are sealed in a checksum-verified, successfully restored logical archive. |
| Docker Desktop deletion readiness | OA persistent-data vote | Done | None | No OA container, volume, or database exists in the Desktop inventory; OA Desktop unique persistent data count is zero. |
| Docker Desktop deletion readiness | Gaia rollback vote | Done | None | Physical and logical backups, roles, comparison evidence, checksums, and an isolated PostgreSQL 17 restore are verified; the Desktop-only 32 rows are obsolete. |
| Project data synchronization governance | Opt-in data ownership | Done | None | Each project explicitly selects transferable data and authority direction. |
| Managed project operational authority | Green, Amber, and Red ownership boundary | Done | None | Projects own bounded Green operations, users decide Amber policy and authority changes, and DeveloperOS coordinates Red shared infrastructure while absolute safety boundaries remain fail closed. |
| Workspace release commands | Shared release facade | Done | None | Common commands delegate to verified project-owned deployment and synchronization hooks. |
| Provider usage visibility | Oracle credential-free view | Done | None | The `/oracle` view consumes the protected Oracle snapshot without receiving provider credentials; OpenAI cost and prepaid-credit data are not user-facing. |
| AI model routing guidance | Task-based route policy | Done | None | Complexity, risk, clarity, rework cost, and token budget determine the recommended route before meaningful work. |
| AI model routing guidance | Interactive handoff workflow | Done | None | Multi-stage work uses confirmed Luna and Sol handoffs at natural implementation and review boundaries. |
| High-impact development protocol | Seven-step work boundary | Done | None | High-impact work separates problem definition, GPT design, Codex planning and implementation, Sol review, GPT review, and the user's final decision. |
| GPT-Codex review orchestration | Local review framework | Done | None | Historical task and report evidence can be reviewed through a strict, captured, no-dispatch orchestration pipeline. |
| GPT-Codex review orchestration | Gate Contract v2 | Done | None | Review completeness and next-action routing are separate strict fields with fail-closed deterministic invariants. |
| GPT-Codex review orchestration | Same-fixture v2 calibration | Done | None | The consumed v2 run returned INCOMPLETE plus SAFE_CONTINUE, passed every parsing and routing stage, and matched the manual baseline without dispatch. |
| GPT-Codex review orchestration | Independent holdout validation | Done | None | The exactly-once holdout returned INCOMPLETE plus SAFE_CONTINUE, passed capture, parsing, and deterministic routing validation, and matched the manual Gate without dispatch. |
| GPT-Codex review orchestration | Task alignment contract v2.2 | Done | None | Unresolved original requirements remain primary unless each deferred item and promoted prerequisite carries exact blocker evidence. |
| GPT-Codex review orchestration | Task Alignment 2.2 holdout validation | Done | None | The independent run passed capture, schema, routing, and priority validation; it kept four unresolved original requirements primary and dispatched nothing. |
| GPT-Codex review orchestration | Evidence sufficiency contract | Done | None | Task-defined acceptance criteria bound mandatory evidence; optional assurance cannot reopen satisfied requirements or delay implementable original work. |
| GPT-Codex review orchestration | Evidence sufficiency holdout | Done | None | The exactly-once independent run returned FAIL plus SAFE_CONTINUE, passed capture, parsing, routing, task-alignment, and evidence-sufficiency validation, and dispatched nothing. |
| GPT-Codex review orchestration | Session Handoff capture | Done | None | Canonical MAINLINE review fixtures seal exact task, applied user decisions, Codex report, and local-only manual review messages in immutable hash-bound packets; text-file import remains a legacy fallback. |
| GPT-Codex review orchestration | Session Handoff E2E | Done | None | The first legacy-fallback mainline cycle passed immutable packet verification, exact semantic equivalence, reviewer-input isolation, and packet-bound no-network candidate preflight. |
| GPT-Codex review orchestration | Synthetic USER_REQUIRED suite | Done | None | Five user-decision cases route to USER_REQUIRED with decision packets and no next instruction; SAFE_CONTINUE, BLOCKED, and STOP controls prevent USER_REQUIRED overfitting. |
| GPT-Codex review orchestration | Genuine USER_REQUIRED capture | In Progress | None | Only a direct, real-world MAINLINE cycle with a completed task, report, manual review, and semantic, policy, threshold, authority, architecture, or scope decision can become a user-approved holdout candidate. |
| GPT-Codex review orchestration | Phase 2A multi-prompt control plane | Done | None | The authenticated console persists project modes, logical nodes, validated directed routes, Pause/Resume/Stop state, capability truth, and redacted audit events while all network execution and dispatch remain disabled. |
| GPT-Codex review orchestration | Phase 2B Codex thread transport | Done | None | Installed App Server schemas govern handshake, thread/turn, streaming, terminal, and approval handling; general and automatic send remain locked while the separately approved one-shot runner may consume one immutable dispatch envelope. |
| GPT-Codex review orchestration | Phase 2B-1 exactly-once smoke | Done | None | A fresh authenticated WSL scratch handoff completed exactly one Codex turn, captured `turn/started`, the assistant response, and `turn/completed`, blocked duplicate dispatch, requested no approval, and changed neither scratch nor bTest files. |
| GPT-Codex review orchestration | Phase 2B-2 bTest worker binding | Done | None | `BTEST_CODEX_WORKER` is bound without a thread to the verified Windows/WSL bTest workspace and locked WSL App Server runtime; bidirectional Mainline routes, Git fingerprint checks, and single-active-turn protection are ready while dispatch remains disabled. |
| GPT-Codex review orchestration | Phase 2B-3A workspace-bound envelope | Done | None | A bTest workspace-only route can create an immutable PREPARED envelope binding task, route, nodes, Windows/WSL paths, Git state, and runtime protocol after a fresh external-change check; thread, turn, approval, and dispatch remain disabled. |
| GPT-Codex review orchestration | Phase 2B-3B dispatch approval gate | Done | None | Authenticated Approve or Reject actions create immutable envelope-bound decision records after fresh route, workspace, Git, and protocol checks; approved work is only DISPATCHABLE and actual send remains locked. |
| GPT-Codex review orchestration | Phase 2B-3C exactly-once Codex dispatch | Done | None | A newly sealed and explicitly approved bTest read-only audit wrote its durable attempt marker before transport, completed exactly one WSL Codex thread and turn, captured the response, blocked reuse, and preserved the exact pre-dispatch workspace fingerprint; retries, fallback, follow-up, automatic Mainline return, and bTest mutation remained zero. |
| GPT-Codex review orchestration | Phase 2B-3D Codex result return handoff | Done | None | The captured 3C result is sealed once with its originating task, dispatch, workspace, route, and runtime provenance for BTEST_MAINLINE; ChatGPT read/write/resume remain unsupported, so delivery stops at a user-assisted exact-delivery candidate with zero Mainline sends. |
| GPT-Codex review orchestration | Phase 2B-3E user-assisted exact delivery | Done | None | A single immutable manual-delivery packet exposes only the sealed Codex result to authenticated clipboard retrieval, records explicit copied, delivered, or cancelled actions, blocks duplicate packets and terminal reuse, and performs no native Mainline write. |
| GPT-Codex review orchestration | Phase 2C-1 API-managed Mainline model | Done | None | bTest switches between native authority when orchestration is off and a managed Responses API authority when on, while canonical policy state stays separate from private conversation linkage and structured routing remains local and locked. |
| GPT-Codex review orchestration | Phase 2C-2A API Mainline bootstrap candidate | Done | None | A no-network candidate seals one minimal first user turn with canonical state, strict routing output, allowlisted state deltas, protocol hashes, and an independently calculated cost cap while live initialization remains approval-locked. |
| GPT-Codex review orchestration | Phase 2C-2B user-initiated API Mainline start | Done | None | With orchestration ON, an exact Initial Request now creates a new immutable no-network candidate bound to active API authority, canonical state, input hash, and a fresh cost preflight; changed input or state stales prior work, while live initialization remains separately approval-locked. |
| GPT-Codex review orchestration | Phase 2C-2C exactly-once API Mainline start | Done | None | The first exact user-prepared and approved request completed one Responses call, preserved its structured HANDOFF_CODEX result across reload, applied only validated state changes, and performed no Codex dispatch. |
| GPT-Codex review orchestration | Phase 2C-2D prepared Mainline dispatch preview | Done | None | The completed Mainline result is bound without regeneration to BTEST_CODEX_WORKER, its exact task and current Windows/WSL bTest Git state are sealed in one immutable PREPARED preview, and the frontend requires explicit user approval while actual send remains locked. |
| GPT-Codex review orchestration | Phase 2C-2E workspace-bound semi-auto dispatch | Done | None | The user-approved path completed a workspace-sealed Mainline-to-Codex turn and an exactly-once Codex-to-Mainline return, captured the next SAFE_CONTINUE handoff as PREPARED, and performed no automatic second Codex turn. |
| GPT-Codex review orchestration | Phase 2B-4 programmatic Mainline return | Done | None | The completed Codex result can be sealed independently for native and API Mainline destinations; the API path binds the exact result, canonical state, route, runtime, schema, pricing, and cost in a pristine PREPARED stateless candidate while live send remains locked. |
| GPT-Codex review orchestration | Phase 2B-5 exactly-once Mainline return | Done | None | The explicitly approved sealed Codex result completed one Responses call, captured and validated `HANDOFF_CODEX` with `SAFE_CONTINUE`, applied the bounded canonical delta, consumed the return, and created only an unapproved PREPARED next handoff; retries, fallback, automatic dispatch, and additional Codex turns remained zero. |
| GPT-Codex review orchestration | Phase 2C bounded AUTO_SAFE_CONTINUE pilot | In Progress | None | Reviewer schema 2.4 separates unresolved-task continuation, canonically authorized plan advance, and user-decision routing; a pristine no-network retry candidate is bound to the current canonical next-step catalog and requires separate approval. |
| GPT-Codex review orchestration | Orchestration token optimization finalization | Done | None | Stable and dynamic Mainline context are separated, full history and manual baselines are excluded, Codex handoffs are delta-oriented, exact validated evaluations are reusable by identity, objective prechecks fail closed, and continuation output is capped at 6,144 tokens without changing routing semantics. |

## Roadmap Dependencies

| From | To | Description |
|---|---|---|
| Governance entry point | Area map contract | Project context boundaries depend on agents loading the workspace governance entry point. |
| Governance entry point | Task-based route policy | AI route recommendations depend on the same startup guidance and precedence rules. |
| Task-based route policy | Interactive handoff workflow | The route sequence and handoff boundaries depend on the initial task classification. |
| Governance entry point | Seven-step work boundary | High-impact protocol selection depends on the common startup and precedence rules. |
| Seven-step work boundary | Task-based route policy | The protocol uses model routing to select implementation and independent review stages. |
| Seven-step work boundary | Local review framework | The orchestration framework implements the independent review and user-decision boundaries of the shared protocol. |
| Local review framework | Gate Contract v2 | Deterministic routing depends on a captured and validated reviewer result. |
| Gate Contract v2 | Same-fixture v2 calibration | The corrected schema and prompt must be calibrated against the known historical case. |
| Same-fixture v2 calibration | Independent holdout validation | The matched calibration result permits planning a distinct holdout, which still requires separate user approval. |
| Independent holdout validation | Task alignment contract v2.2 | The holdout and consumed 2.1 calibration established the requirement-priority gap addressed by v2.2. |
| Task alignment contract v2.2 | Task Alignment 2.2 holdout validation | The repaired primary-task and defer-evidence contract must be checked on an independent fixture without reusing any consumed manifest. |
| Task Alignment 2.2 holdout validation | Evidence sufficiency contract | The safe but material holdout difference established the need to bind evidence thresholds to task-defined acceptance criteria. |
| Evidence sufficiency contract | Evidence sufficiency holdout | The acceptance-threshold repair must be validated on an independent mainline cycle before any autonomous routing decision. |
| Local review framework | Session Handoff capture | Canonical fixture provenance depends on selecting and sealing one exact cross-session review cycle before reviewer preflight. |
| Session Handoff capture | Session Handoff E2E | The canonical capture contract must prove one real legacy cycle can be sealed, compared, isolated, and bound to a no-network candidate. |
| Session Handoff E2E | Synthetic USER_REQUIRED suite | Synthetic routing coverage establishes decision and negative-control invariants without substituting for a historical holdout. |
| Synthetic USER_REQUIRED suite | Genuine USER_REQUIRED capture | Passing synthetic controls permits monitoring real direct captures but does not authorize an API call or historical validation claim. |
| Session Handoff capture | Phase 2A multi-prompt control plane | The control plane references the canonical capture boundary without duplicating or weakening its immutable packet contract. |
| Gate Contract v2 | Phase 2A multi-prompt control plane | Mode and last-Gate state can be represented only after deterministic review and routing semantics are established. |
| Phase 2B-1 exactly-once smoke | Phase 2B-2 bTest worker binding | A real project workspace can be bound only after the isolated WSL send/receive path proves exactly-once completion and approval handling. |
| Phase 2B-2 bTest worker binding | Phase 2B-3A workspace-bound envelope | A PREPARED dispatch contract can bind the real workspace only after its node, path mapping, Git state, and WSL runtime are sealed. |
| Phase 2B-3A workspace-bound envelope | Phase 2B-3B dispatch approval gate | User authority can be recorded only after the complete immutable dispatch envelope is sealed and can be reverified. |
| Phase 2B-3B dispatch approval gate | Phase 2B-3C exactly-once Codex dispatch | A real project turn may begin only after a fresh approval-bound workspace check and an immutable attempt marker consumes the envelope. |
| Phase 2B-3C exactly-once Codex dispatch | Phase 2B-3D Codex result return handoff | A return handoff can be sealed only from a completed, hash-verified Codex result and the matching reverse route. |
| Phase 2B-3D Codex result return handoff | Phase 2B-3E user-assisted exact delivery | Unsupported native Mainline transport can offer a manual packet only after the exact return content and destination are immutably sealed. |
| Phase 2B-3E user-assisted exact delivery | Phase 2C-1 API-managed Mainline model | A managed Mainline authority can be modeled only after the unsupported native write path has a complete manual return boundary. |
| Phase 2C-1 API-managed Mainline model | Phase 2C-2A API Mainline bootstrap candidate | The first request can be sealed only after canonical policy authority and private provider conversation state are separated. |
| Phase 2C-2A API Mainline bootstrap candidate | Phase 2C-2B user-initiated API Mainline start | The final start UX reuses the sealed routing and state-delta contract but requires an exact user purpose before preparing a paid-call candidate. |
| Phase 2C-2B user-initiated API Mainline start | Phase 2C-2C exactly-once API Mainline start | A paid first turn can execute only after the exact input, canonical state, authority, request, protocol, and cost-bound candidate is sealed and explicitly approved. |
| Phase 2C-2C exactly-once API Mainline start | Phase 2C-2D prepared Mainline dispatch preview | Only a completed and validated HANDOFF_CODEX result can become a workspace-sealed approval-required Codex dispatch preview. |
| Phase 2C-2D prepared Mainline dispatch preview | Phase 2C-2E workspace-bound semi-auto dispatch | A Codex turn can be user-approved only after the exact Mainline task, destination, runtime protocol, and current bTest Git state are sealed in one immutable preview. |
| Phase 2B-3C exactly-once Codex dispatch | Phase 2B-4 programmatic Mainline return | Programmatic return requires a completed hash-verified Codex result rather than a regenerated report. |
| Phase 2C-2C exactly-once API Mainline start | Phase 2B-4 programmatic Mainline return | The API authority and its canonical state must be initialized before a Codex result can become a Mainline continuation candidate. |
| Phase 2B-4 programmatic Mainline return | Phase 2B-5 exactly-once Mainline return | A paid return may execute only after the exact Codex result, canonical state, request, protocol, and cost-bound candidate is sealed and explicitly approved. |
| Phase 2B-5 exactly-once Mainline return | Phase 2C bounded AUTO_SAFE_CONTINUE pilot | Bounded automation can be proposed only after one complete user-approved Mainline-to-Codex-to-Mainline loop is captured and validated. |
| Task-based route policy | Shared parser contract | Shared implementation work uses the route recommendation before changing parser contracts. |
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
| Canonical launcher and config | Desktop plugin isolation | The fixed native path and config must exist before higher-priority Desktop-backed plugin links can be removed safely. |
| Desktop plugin isolation | bTest repository command migration | bTest can migrate local calls only after the shared native boundary is sealed and Desktop-independent. |
| Desktop plugin isolation | OA repository command migration | OA can migrate its local wrapper only after the shared native boundary is sealed and Desktop-independent. |
| Desktop plugin isolation | Gaia repository command migration | Gaia can migrate its local wrapper only after the shared native boundary is sealed and Desktop-independent. |
| bTest repository command migration | Managed project native Docker adoption | Workspace adoption requires bTest runtime and data verification through the shared launcher. |
| OA repository command migration | Managed project native Docker adoption | Workspace adoption requires OA runtime and data verification through the shared launcher. |
| Gaia repository command migration | Managed project native Docker adoption | Workspace adoption requires Gaia runtime and data verification through the shared launcher. |

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
8. Monitor new direct MAINLINE_CODEX_REVIEW captures and mark the first genuine
   USER_REQUIRED cycle as a candidate without executing it.
9. Retain the three-file importer only for legacy/manual recovery and
   equivalence checks; never execute the completed E2E candidate bound to
   `e11cb8e3d5bdb4fe6a98362a22ebea288be53f2d41878c2cf12c7badf62be950`.
10. Keep autonomous routing disabled while choosing the next validation boundary;
   source adjudication found the API's two disputed findings correct and the
   manual baseline's immediate implementation route under-reviewed.
11. Keep orchestration development paused. Do not run another AUTO pilot,
   expand transports, or add orchestration features until the user explicitly
   resumes this track; never reuse consumed approvals or infer authority.
12. Migrate bTest, OA, and Gaia repository-local Docker calls to the shared
   native launcher, preserving remote server commands, and verify each project
   before reopening its Docker Desktop deletion gate.

## Latest Status Change

**ORCHESTRATION DEVELOPMENT: PAUSED**

- Topic: GPT-Codex review orchestration
- Previous status: In Progress / active bounded optimization
- Current status: In Progress / development paused by explicit user decision
- Reason: Token-efficient stable/dynamic continuation context, delta-oriented
  Codex handoff guidance, exact validated-evaluation reuse, and objective
  deterministic prechecks completed without changing Gate semantics.
- Resume condition: explicit user instruction to resume orchestration work.

- Topic: Project context routing
- Change: Added a no-write context efficiency observability baseline without
  changing context selection or orchestration runtime behavior.
- Evidence or reason: Four representative project builds now report selection,
  repetition, identity reuse, dirty-scan, duration, and packet-size metrics in
  `ContextEfficiencySnapshotV1`; exact-selection regression remains green.

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
6. Keep the consumed Gate Contract v2 calibration immutable and require a
   distinct matched holdout plus separate approval before changing
   autonomous-routing policy.
7. Move `Managed project native Docker adoption` to `Done` only after bTest,
   OA, and Gaia each remove or delegate repository-local native wrappers,
   distinguish remote commands, and pass launcher-bound runtime/data checks.

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
- Gate Contract v2 calibration and independent holdout validation are complete.
  The consumed Task Alignment 2.1 run failed closed and 2.2 is locally repaired.
  The independent 2.2 holdout and local Evidence Sufficiency repair are complete.
  The independent Evidence Sufficiency holdout is complete. Its material
  semantic difference still requires review before autonomous routing can be
  considered.

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
