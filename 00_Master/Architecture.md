# Workspace Architecture

## Purpose

This document defines the target architecture of DeveloperOS as a long-term development operating system.

## Architecture Goal

DeveloperOS should manage multiple independent projects as one coherent development ecosystem.

## Principles

- Preserve project independence.
- Centralize global rules.
- Automate repeated project-start tasks.
- Identify common module candidates only after repeated patterns appear.
- Make AI collaboration deterministic through clear documentation.

## Current Architecture

```text
Workspace
+-- DeveloperOS
|   +-- Master Governance
|   +-- Knowledge Base
|   +-- AI Collaboration Layer
|   +-- Project Blueprints
|   +-- Automation Tools
+-- Independent Project Repositories
```

## Integration Principles

- Do not merge projects prematurely.
- Extract common modules only after repeated use is confirmed.
- Keep shared modules independent, reusable, and documented.
- Track authentication, logging, configuration, deployment, and database patterns as long-term platform candidates.
- Apply AI automation first to documentation, tests, review, and repetitive workflows.

## State And Synchronization Architecture

DeveloperOS distinguishes source state from operational and learning state.

```text
Git remote
  <-> project source and reviewed metadata

Project-owned data contract
  <-> immutable datasets and artifacts through verified manifests
   -> authoritative mutable state through directed transfer

DeveloperOS
  -> policy, blueprint, validation guidance, and derived status only
```

DeveloperOS does not hold project payloads or mediate transfers. Each project
declares whether a synchronization set is an immutable merge-safe union, an
authoritative directed flow, a published artifact, or state that must not be
synchronized. See `DataSynchronizationPolicy.md`.

## Governance Architecture

DeveloperOS is the global policy layer.

Project repositories remain independent and reference DeveloperOS instead of copying global policies.

```text
DeveloperOS
  -> Global rules, standards, Blueprints, AI policy

Project repository
  -> README.md
  -> PROJECT_CONTEXT.md
  -> optional PROJECT_RULES.md
  -> source code
```

This keeps global rules centralized while allowing explicit project-level exceptions.

## Common Platform Candidates

Review these candidates after inspecting active projects:

- Shared authentication patterns
- Shared configuration management
- Shared logging and monitoring
- Shared database access patterns
- Shared UI components
- Shared API clients
- Shared AI prompts and agent rules
- Shared deployment blueprints
- Shared data synchronization contracts and manifest validation

## Shared Native Docker Infrastructure

DeveloperOS owns one local native Docker execution boundary for OA, Gaia,
bTest-Elliott, and bTest-Ever. Windows commands enter Ubuntu through an
argument-array launcher that
fixes `DOCKER_HOST=unix:///run/docker-wsl.sock`,
`DOCKER_CONFIG=/home/devops/.docker-native`, `/usr/bin/docker`, and the native
Compose binary under `/usr/libexec`. Docker Desktop, Windows contexts, and
ambient user Docker configuration are outside this authority.

Project repositories retain their Compose files, service lifecycle, data
contracts, and remote deployment commands. They integrate local calls with the
shared launcher but do not copy or independently modify the daemon, socket,
data root, CLI, Compose plugin, or credential helper. Remote commands executed
after SSH continue to use server-local Docker and server-local least-privilege
registry credentials.

Only DeveloperOS coordinates `docker-wsl.service` stop/restart and daemon
configuration. Starting the pre-approved service, or idempotently ensuring it
is running, is allowed to each project agent. Project runtimes are explicitly
scoped to their own Compose namespaces and daemon startup must not auto-start
any project. Plugin cleanup is limited to unowned Docker Desktop
mount symlinks in the higher-priority local CLI plugin directory. Native
packages, images, containers, networks, volumes, `/var/lib/docker-wsl`, and the
socket are preserved. See `04_Tools/docker/NativeDockerInfrastructure.md`.

## Operational Cost Visibility

Provider credentials must remain outside the public console process.

```text
OpenAI Admin key -> hardened hourly collector -> credential-free JSON
OCI instance principal -> hardened hourly collector -> credential-free JSON
credential-free JSON -> public read-only Usage view
```

The console may display derived monthly costs, operator-defined budgets,
service breakdowns, and provider-reported resource usage, account limits, and
available capacity. It must not expose provider credentials, tenancy
identifiers, private key material, or unrestricted billing APIs. A provider
service limit must not be presented as a free-tier entitlement.

## Orchestration Control Plane

The authenticated console owns a local control-plane document for each managed
project. It records the selected orchestration mode, lifecycle status, logical
prompt nodes, directed routes, current cycle metadata, and last routing state.
Logical roles are separate from transport references; session and thread
identifiers stay in backend-only `transport_ref` fields and are not prompt
content.

Transport adapters expose capability metadata and explicit capture/send method
boundaries. Capability reporting must reflect real support: unreliable remote
ChatGPT reads are degraded, Codex and Responses writes remain locked, and only
the local mock adapter is fully ready in Phase 2A. Mode selection and graph
editing do not start background capture, review, handoff, or dispatch.

For bTest, the control plane separates Mainline policy authority from provider
conversation continuity. When orchestration is OFF, `NATIVE_MAINLINE` is the
canonical native authority. When orchestration is enabled,
`BTEST_MAINLINE_API` is the sole canonical authority; native Mainline output
cannot be promoted automatically. Canonical purpose, frozen decisions, scope,
authority, routing, user decisions, Gate, and latest handoff remain in the
DeveloperOS state. OpenAI conversation and response linkage remain private
transport state and never become policy authority. The API Mainline declares
READ, WRITE, and RESUME as a future capability contract while all three remain
operationally locked until a separately approved live phase.

API Mainline output uses an explicit structured routing action:
`HANDOFF_CODEX`, `USER_REQUIRED`, `CONTINUE_USER_DIALOGUE`, `BLOCKED`, or
`STOP`. Deterministic validation binds Codex handoffs to an enabled worker and
active route, requires the corresponding decision or blocker packet, and
rejects output from an inactive Mainline authority. DeveloperOS does not infer
destinations from prose.

The first managed Mainline turn is prepared as a no-network bootstrap
candidate. Its request contains only the DeveloperOS canonical state, the
authority and routing contract, and one exact user input; native ChatGPT
history, FUTURE_DESIGN history, unrelated cycles, conversation identifiers,
and credentials are excluded. The model may propose only an allowlisted state
delta. Frozen decisions, authority, and routing remain controller-owned and
cannot be replaced by model output. Request, prompt, schema, canonical state,
user input, runtime protocol, pricing, and cost ceiling are hash-bound before
any later one-time approval.

The empty-purpose bootstrap remains an immutable safe fallback and is marked
`DO_NOT_EXECUTE`. Normal startup is user initiated: after orchestration enables
`BTEST_MAINLINE_API`, the authenticated console accepts one exact initial
request and prepares a new no-network candidate from that text plus the current
canonical state. The input hash, state hash, request, protocol, and cost ceiling
are sealed together. Editing the input or changing canonical authority/state
makes the prior candidate stale; preparing a candidate never creates a provider
conversation or grants live-call approval.

Captured Codex results use destination-bound return envelopes. Native
`BTEST_MAINLINE` remains a user-assisted exact-delivery path because ChatGPT
session write is unsupported. `BTEST_MAINLINE_API` can instead prepare a
programmatic return candidate that places the sealed Codex result unchanged in
the user content and replays current DeveloperOS canonical state. Because the
Responses requests use `store=false`, this preview does not claim provider-side
resume or transmit `previous_response_id`; private response linkage is hash-bound
as provenance while DeveloperOS remains the state authority. Candidate creation
stops at `PREPARED` with no approval, attempt, result, network call, or dispatch.

Executing that return is a distinct user-authority boundary. The authenticated
console revalidates the immutable return artifact, candidate and approval
manifest hashes, exact result hash, active API Mainline authority, canonical
state hash, and cost cap before writing one immutable approval record and a
durable `ATTEMPT_STARTED` marker. It then permits exactly one Responses call
with zero retries and fallback, captures provider bytes before parsing, and
consumes the return on every terminal outcome. `USER_REQUIRED` stops in
`WAITING_FOR_USER`; `HANDOFF_CODEX` may create only an unapproved `PREPARED`
next handoff. Neither outcome can automatically start another Codex turn.

The bounded `AUTO_SAFE_CONTINUE` pilot is a deterministic policy layer, not a
general background loop. It may advance only a validated `SAFE_CONTINUE` plus
`BOUNDED_TASK` result when deterministic routing, task alignment, evidence
sufficiency, workspace identity, transport state, and the cumulative budget
all pass. User decisions, blockers, approval/input requests, contract
conflicts, external workspace changes, transport failures, and destructive,
database, infrastructure, authority, threshold, or scope changes stop the
pilot. The first pilot is limited to two cycles with no retries, fallback, or
automatic approvals; reaching the limit always yields
`AUTO_CYCLE_LIMIT_REACHED`. Its live runner remains disabled until a separate
cumulative cost-cap approval.

The console derives an activity timeline from immutable dispatch and API
Mainline-return ledgers. Compact rows expose only timestamp, logical source and
destination, event, and status; expanded detail may show the handoff, Gate,
bounded message preview, usage/cost, and hashes. Timeline rendering performs no
transport action and highlights `USER_REQUIRED` without advancing the cycle.

Mainline continuation requests use `OrchestrationTokenEfficiencyV1`. A stable
developer prefix and strict schema are separated from a dynamic payload that
contains only compact canonical state, the current task, latest Codex report,
requirement identities, and authorized next-step references. Conversation
history, manual reviews, completed-cycle prose, repository history, and the
activity timeline remain durable artifacts but are not request context. Codex
handoffs are instructed to carry only the task delta, required checks, changed
constraints, and authority references. This is an efficiency rule, not an
authority shortcut: source references, Gate validation, task alignment,
evidence sufficiency, and next-step authority remain unchanged.

Before a continuation call, deterministic checks may reject stale canonical or
workspace state, consumed handoffs, absent credentials, invalid routes, or
protocol mismatches. They never choose a semantic Gate. A validated evaluation
may be reused only for an exact canonical-state, task, report, protocol, and
reviewer-schema identity; failed or consumed attempts are not reusable. Prompt
caching is supported by the stable layout but is never required for correctness.

Phase 2B discovers the installed Codex App Server contract from the
orchestration-only Ubuntu WSL CLI before reporting protocol support. Windows
controls the Linux-native runtime through bounded `wsl.exe` stdio; the Codex
Desktop remains the primary development client and its Windows Store executable
is not a backend transport candidate. The adapter
implements the initialize/initialized handshake, thread read/start/resume,
turn start/interrupt, ordered event consumption, terminal turn states, and
server approval/input requests. Protocol support and execution permission are
separate: all Codex thread and turn starts remain locked, and approval requests
are surfaced without an automatic response.

Logical CODEX_THREAD bindings hold only a thread identifier and an absolute
workspace. Neither identifier is rendered into the prompt. A validated route
may create an immutable dispatch-preview artifact and a PREPARED ledger entry;
the exactly-once ledger reserves SENT, COMPLETED, and FAILED transitions, but
the console exposes no send endpoint in Phase 2B.

For a project worker that has not started an orchestration thread, the binding
is workspace-only. It records the Windows and WSL paths plus a sealed Git root,
branch, HEAD, and status fingerprint; no Desktop thread is reused or inferred.
Before a future orchestration turn, the controller must compare the current
fingerprint with the seal and fail closed as `WORKSPACE_CHANGED_EXTERNALLY` if
another client changed the repository. This guard does not lock or disable the
Codex Desktop development client.

The workspace-bound PREPARED envelope seals route and logical node identities,
both workspace paths, branch, HEAD, status fingerprint, discovered runtime
protocol, exact task-content hash, and rendered payload hash. Task content,
rendered handoff payload, and the full envelope have separate SHA-256 meanings.
Envelope preparation performs the workspace comparison again and does not
start a thread, turn, or dispatch.

Dispatch approval is a separate immutable authority boundary. An authenticated
Approve action binds the envelope ID and hash, task hash, route, destination,
workspace fingerprint, branch, HEAD, and runtime protocol hash after repeating
the live checks. The ledger records PREPARED, APPROVED, and DISPATCHABLE while
keeping actual send locked. Reject is terminal for that envelope. Any changed
binding invalidates the old approval instead of updating or reusing it.

Control-plane state uses the existing runtime-file boundary and atomic writes.
User mode, graph, Pause, Resume, and Stop actions produce metadata-only audit
events. Audit records must not contain transport references, session content,
messages, or secrets.

## Managed Project Operational Authority

Managed projects own routine, non-destructive operation of their repositories,
databases, application runtimes, project credentials, and project-local
infrastructure. DeveloperOS owns only shared, host, and cross-project
boundaries; it is not an approval hop for ordinary project operations. Product
or research meaning remains a user decision, and destructive or privilege-
expanding work remains explicitly approval-bound. The complete Green, Amber,
Red, and absolute safety contract is in
`ProjectOperationalAuthorityPolicy.md`.


