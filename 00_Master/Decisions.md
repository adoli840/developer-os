# Decisions

## Purpose

This document records important DeveloperOS decisions.

## Format

```text
## YYYY-MM-DD - Decision Title

Status: Proposed | Accepted | Deprecated | Replaced

Context:
Decision:
Reason:
Impact:
Follow-up:
```

## 2026-06-29 - Use DeveloperOS As The Workspace Operating System

Status: Accepted

Context:

`X:\Projects` is not just a collection of project folders. It is the top-level workspace for the developer's long-term development activity.

Decision:

Use `DeveloperOS` as the governance repository. Keep `00_Master`, `01_Knowledge`, `02_AI`, `03_Blueprints`, and `04_Tools` inside it. Keep application projects outside DeveloperOS.

Reason:

The largest productivity bottleneck is not only project management. It is repeated project bootstrapping, technology selection, AI collaboration, and missing Blueprints.

Impact:

Before starting new projects or features, consult DeveloperOS governance, AI rules, and Blueprints.

## 2026-06-29 - Manage DeveloperOS As A Single Git Repository

Status: Accepted

Context:

Keeping DeveloperOS folders directly under `X:\Projects` makes Git boundaries unclear.

Decision:

Move all DeveloperOS folders under `X:\Projects\DeveloperOS` and initialize Git only inside DeveloperOS.

Reason:

These folders all belong to development operations: governance, rules, knowledge, Blueprints, and tools.

Impact:

DeveloperOS is the development operations repository. Application projects remain independent repositories.

## 2026-06-29 - Prioritize Active Project Inspection

Status: Accepted

Context:

Discarded projects were removed. Before starting new development, the remaining active projects should be inspected for quality, convenience, and efficiency.

Decision:

Use inspection-first mode for the near term.

Reason:

A stable base requires clear setup, documentation, configuration, tests, structure, and automation.

Impact:

Project inspection, improvement candidates, and commonization review take priority over new feature proposals.

## 2026-06-29 - Operate GPT And Codex As One AI Development Team

Status: Accepted

Context:

The developer uses GPT and Codex together to save Codex tokens and separate design from implementation.

Decision:

GPT acts like a planning and review lead. Codex acts like a senior developer responsible for implementation, file edits, tests, and Git work.

Reason:

Long design discussions are cheaper and more effective in GPT. Codex should focus on actual project changes and verification.

Impact:

Use `DeveloperOS/02_AI/AI_Collaboration.md` as the shared collaboration guide. Important context must be captured in DeveloperOS, not only in chat.

## 2026-06-29 - Separate Git History From AI Snapshots

Status: Superseded by `2026-08-04 - Use Git As The Sole Source-Code Recovery Mechanism`

Context:

AI can modify several files or restructure projects. Recovery must be simple, but Git history should stay readable.

Decision:

Use Git for meaningful final development history. Use snapshots for short-term AI recovery.

Reason:

Git history should remain human-readable. Snapshots should provide fast rollback for risky AI work.

Impact:

Codex creates snapshots before large or risky changes. Git commits happen at meaningful boundaries such as feature completion, meaningful refactoring completion, or end-of-day checkpoint.

## 2026-06-29 - Use English As The Official DeveloperOS Documentation Language

Status: Accepted

Context:

DeveloperOS is a long-term knowledge base for GPT, Codex, future AI coding agents, IDEs, and developer tools.

Decision:

All governance documents under DeveloperOS shall be written in English. Existing Korean governance documents must be migrated to English to maintain a single documentation language.

Reason:

English is the most compatible language for the software ecosystem, search, IDEs, technical terminology, and AI coding agents. The developer may still communicate with AI in Korean.

Impact:

New long-term DeveloperOS documents are written in English. Existing governance documents are migrated to AI-first technical English. Personal knowledge notes may use Korean only when that preserves important local or personal context.

## 2026-06-29 - Use DeveloperOS As The Single Source Of Truth For Global Policy

Status: Accepted

Context:

Copying DeveloperOS policy documents into projects causes policy drift over time.

Decision:

DeveloperOS is the single source of truth for global engineering policy. Projects reference DeveloperOS instead of copying policy documents. Project-specific exceptions live in `PROJECT_CONTEXT.md` or `PROJECT_RULES.md`.

Reason:

Duplicated rules become inconsistent and confuse AI agents.

Impact:

Before project work, Codex reads `README.md`, `PROJECT_CONTEXT.md`, optional `PROJECT_RULES.md`, and then DeveloperOS global policies. Explicit project rules override DeveloperOS only when they clearly say so.

## 2026-06-29 - Operate DeveloperOS As An AI Project Manager

Status: Accepted

Context:

The developer wants DeveloperOS to help with schedule awareness, priorities, progress, and productivity without becoming a harsh taskmaster.

Decision:

DeveloperOS should act as an AI Project Manager when invoked. It should review roadmap, weekly goals, project status, metrics, backlog, and decisions before recommending work.

Reason:

Codex and GPT do not run continuously or remember future dates by themselves. DeveloperOS should therefore work as an invoked PM system that evaluates current state whenever the developer starts a work session.

Impact:

DeveloperOS now includes `PM_Role.md`, `Roadmap.md`, `ProjectStatus.md`, `Metrics.md`, and `DailyReview.md`. Codex should provide soft challenges when the requested work conflicts with higher-priority roadmap evidence, while leaving final control to the developer.

## 2026-06-29 - Optimize Codex Tokens Through Role Separation

Status: Accepted

Context:

Codex token usage grows when it performs broad project analysis, long architectural reasoning, or context restoration from vague requests.

Decision:

Use GPT for expensive reasoning and design. Use Codex for implementation, scoped refactoring, verification, and Git work. When a design document exists, Codex treats it as the implementation specification.

Reason:

This reduces repeated reasoning, limits broad source exploration, and keeps Codex focused on changes that require direct workspace access.

Impact:

Codex should avoid large architectural analysis unless explicitly requested, required by missing design, or needed because the code contradicts the design. Project README, PROJECT_CONTEXT, DeveloperOS decisions, and GPT handoff documents become the preferred context restoration path.


## 2026-06-29 - Rename Templates To Blueprints

Status: Accepted

Context:

`03_Templates` suggested isolated file templates, but the intended role is a reusable project starting point that includes structure, documentation, Docker, Git defaults, and AI context.

Decision:

Rename `03_Templates` to `03_Blueprints` and move generic project starter files under `03_Blueprints/Project`.

Reason:

Blueprint better represents a complete project design rather than a single reusable file. This also prevents confusion between DeveloperOS root `.gitignore` and project blueprint `.gitignore`.

Impact:

DeveloperOS has one root `.gitignore` for itself. Blueprint-specific `.gitignore` files live inside individual blueprints and are copied only when creating new projects.

## 2026-07-28 - Add A Derived Browser Operations Console

Status: Accepted

Context:

The developer needs one browser view for active repository status, common
operations, Oracle server resources, and optional API cost visibility.

Decision:

Add a small browser console as a DeveloperOS tool. The console derives live
state from project repositories, Docker, and the host operating system. It does
not store project roadmaps or become the owner of project state. Browser
commands are limited to an explicit allowlist and audited. Direct public HTTP
access is read-only; management requires a secure authenticated endpoint.

Reason:

A derived operational view reduces repeated terminal inspection without
turning DeveloperOS into a project dashboard or duplicating repository-owned
documents.

Impact:

The console runs independently from governance documents and binds to port
8080. OpenAI credentials and live billing integration are outside the default
user-facing console scope.

## 2026-08-12 - Remove OpenAI Billing And Usage From The Console

Status: Accepted

Context:

The supported OpenAI API exposes organization Costs data but does not expose
the prepaid Credit Grants balance shown in the Billing web console. Showing a
partial cost and credit surface in DeveloperOS could be mistaken for a live
balance view.

Decision:

Remove the user-facing OpenAI Billing and Usage navigation entry, page, cards,
labels, and route behavior. Users check prepaid Credit Balance directly in
OpenAI Billing. Preserve the server-side Costs API collector, its protected
snapshot, systemd service and timer, and external secret-management path for
future internal orchestration cost measurement. Do not store or hard-code the
observed `$1.95` value. `OPENAI_MONTHLY_BUDGET_USD` remains unchanged and its
orchestration budget contract is deferred to a separate Phase 1 design.

Reason:

An unavailable or partial provider surface is less useful than a clear
ownership boundary. DeveloperOS can retain cost evidence internally without
claiming to represent prepaid billing state.

Impact:

The browser no longer renders or navigates to an OpenAI billing or usage page.
The collector and snapshot remain available to backend consumers, but the
public console does not display OpenAI cost, monthly limit, or prepaid credit.

## 2026-08-12 - Establish A Dedicated Orchestration Credential Contract

Status: Accepted

Context:

Future DeveloperOS orchestration reviews may call the OpenAI Responses API, but
the existing server `OPENAI_API_KEY` has unknown provenance and must not be
reused. The existing Admin key is scoped to organization cost collection.

Decision:

Use a new DeveloperOS orchestration project and dedicated service-account key.
The canonical variables are `OPENAI_ORCHESTRATION_API_KEY` and
`OPENAI_ORCHESTRATION_PROJECT_ID`. Keep `OPENAI_ADMIN_API_KEY` exclusively for
the Costs API. Do not modify, copy, or delete the existing server
`OPENAI_API_KEY` during this phase. Do not make a live model call until the
user stores the new key in `X:/Settings/env/developer-os.env`.

Reason:

Explicit project ownership and separate credentials prevent an administration
key, an unknown legacy key, or an incidental workstation secret from becoming
the authority for orchestration model calls.

Impact:

Credential provisioning is pending. The key value is never stored in Git,
logged, returned in reports, or sent to the frontend. Orchestration Phase 1,
Responses API calls, and key lifecycle changes remain disabled until a later
explicit approval.

## 2026-08-12 - Keep Orchestration Phase 1A Local And Fixture-Bound

Status: Accepted

Context:

The first orchestration implementation needs to validate state, reviewer Gate
outputs, pricing, preflight, and historical evidence without creating an
automatic execution path or making a live model call.

Decision:

Phase 1A is a local-only Python package under `console/devos_orchestration`.
It may create strict versioned state, mock reviewer responses, Decimal cost
estimates, local immutable run artifacts, and manual-comparison packets. It
must not call OpenAI, dispatch a generated instruction, edit a repository,
modify bTest, deploy, commit, push, or create a server worker. Historical
fixtures require an existing Codex report and manual baseline pair; the tool
must report `HISTORICAL_FIXTURE_REQUIRED` instead of inventing one.

Reason:

Separating deterministic contract validation from model access makes accidental
live calls and automatic execution structurally unavailable during preflight.

Impact:

The live adapter remains disabled, credential fallback is prohibited, and all
Phase 1A artifacts remain local and ignored by Git. A later phase requires a
separate user decision and explicit live-run approval.

## 2026-07-28 - Automate Recoverability Evidence

Status: Accepted

Context:

The existence of a database volume does not prove that application data can be
recovered. Manual backups also become unreliable when they depend on memory or
end-of-day discipline.

Decision:

The DeveloperOS operations tool may install project-aware database backup and
restore-verification automation on a managed host. Backup data remains outside
DeveloperOS governance documents. The console records only derived evidence:
last success, integrity, age, and isolated restore result.

Reason:

Recoverability is an engineering property that should be continuously tested,
not a project status field maintained by hand.

Impact:

OA and Gaia PostgreSQL containers receive daily compressed logical backups,
14-day retention, and weekly restores into temporary network-isolated
containers. Production databases are never restore targets. Failures appear as
local console alerts without requiring an external notification credential.

## 2026-07-28 - Let Workstations Report Their Own Git State

Status: Accepted

Context:

The Oracle host cannot observe uncommitted or unpushed work stored only on a
Home or Office computer. Treating the server repository as the state of every
computer would hide local work and create false confidence.

Decision:

Each workstation reports its own derived Git summary while powered on.
Reports use outbound SSH, contain no source files or credentials, and expire
into an offline state. A workstation must not be configured from assumptions
about another computer.

Reason:

Repository state belongs to the machine that holds the working tree. A
self-reporting model preserves that boundary and works without opening a
public write API.

Impact:

Home reporting is run explicitly from the Home computer. DeveloperOS does not
install a periodic Windows Scheduled Task. Office remains unconfigured until
work is performed from the Office computer. The browser console displays the
last reported state, report freshness, branch, dirty count, and ahead/behind
counts without exposing local paths or hostnames publicly.

## 2026-07-28 - Keep Arbitrary Server Commands Behind SSH

Status: Accepted

Context:

Project operations sometimes require real shell commands from a browser.
Exposing an arbitrary command endpoint on the public console would turn one
HTTP service compromise into host-level control.

Decision:

The public DeveloperOS console remains read-only. A separate terminal service
may execute commands only for explicitly configured project directories, must
bind to server loopback, and must be reached through an authenticated SSH
local-forward from a trusted workstation. No terminal port is opened in host
or cloud firewalls.

Reason:

SSH already owns host authentication, key rotation, and network encryption.
Reusing that boundary avoids inventing a weaker public terminal
authentication system.

Impact:

Home can open project command consoles through an explicitly started local
tunnel. DeveloperOS does not install a periodic tunnel Scheduled Task.
Commands execute as the unprivileged server account, receive time and output
limits, and write audit metadata without storing command text. Other
workstations start their own tunnels explicitly.

## 2026-07-31 - Isolate OpenAI Cost Collection From The Public Console

Status: Accepted

Context:

DeveloperOS needs protected internal OpenAI cost collection. Organization cost
access requires a privileged Admin key that must not enter Git, a browser
response, or the long-running public console process.

Decision:

Run OpenAI cost collection as a separate hardened oneshot service. Keep its
environment file outside all repositories, transfer it independently from the
Git release, and expose only a credential-free JSON snapshot to the console.
Refresh the snapshot during deployment and hourly afterward.

Reason:

Separating collection from presentation limits credential exposure while
still providing timely operational visibility.

Impact:

DeveloperOS deployments require the local
`X:/Settings/env/developer-os.env` file with `OPENAI_ADMIN_API_KEY` and
`OPENAI_MONTHLY_BUDGET_USD`. The server installs it with restricted
permissions, and the protected snapshot is available to backend consumers.
The public console does not display OpenAI cost, budget, remaining amount, or
prepaid credit.

## 2026-08-02 - Require Project-Owned Roadmap Continuity

Status: Accepted

Context:

Some repositories maintain detailed roadmaps while others depend on transient
chat context. Requiring a separate roadmap request for each task produces
inconsistent project memory and makes later context restoration expensive.

Decision:

Treat roadmap maintenance as part of the definition of done for every
meaningful work unit. DeveloperOS defines one lifecycle policy and a fallback
template. Each project keeps its own canonical roadmap; an established local
roadmap or generator takes precedence over the fallback `ROADMAP.md`. Install a
concise global Codex guidance block so the policy is loaded without a separate
prompt.

Reason:

A small roadmap update at verified work boundaries preserves current direction,
results, blockers, and the next action without turning every command into
documentation work.

Impact:

Codex reads the project roadmap before meaningful implementation and updates it
after verification. Read-only work and trivial edits do not create roadmap
churn. DeveloperOS remains the policy owner and does not duplicate
project-local roadmap state.

## 2026-08-02 - Apply DeveloperOS Policies To DeveloperOS Itself

Status: Accepted

Context:

DeveloperOS provides automatic governance and tooling to application
repositories, but implicit self-application leaves gaps that are difficult to
detect. Treating the governance repository as exempt would weaken the rules it
defines for every other project.

Decision:

Treat DeveloperOS as a project governed by every applicable DeveloperOS policy.
Maintain repository-local agent guidance, project context, explicit exceptions,
roadmap state, Git safety, verification, monitoring, and
deployment controls. Provide one installer and one self-check for durable local
integrations.

Reason:

The governance source should demonstrate the operating model it requires.
Explicit checks make omissions visible, while explicit exclusions prevent fake
Docker stacks, empty databases, or duplicate project documents created only for
symmetry.

Impact:

`make self-enable` installs the user-level integrations and `make self-check`
audits the self-application contract. Root `PROJECT_RULES.md` records why Docker
Compose lifecycle, PostgreSQL backup, generic Docker deployment, and duplicate
root TODO or decision files do not apply.

## 2026-08-02 - Update Roadmaps At Topic Status Boundaries

Status: Accepted

Context:

Updating a roadmap after every meaningful implementation unit makes it behave
like a changelog and creates documentation noise even when project direction is
unchanged.

Decision:

Supersede the work-unit update cadence in the earlier roadmap continuity
decision. A meaningful work unit is now an evaluation point. Update the
canonical roadmap only when a topic is created or restructured, changes status,
changes priority or material scope, changes its completion signal, or gains or
resolves a blocker that affects its next transition.

Reason:

A roadmap should expose planning state rather than narrate implementation
activity. Topic status boundaries are stable enough to restore direction while
ordinary implementation details remain in Git and focused project documents.

Impact:

Codex reads the roadmap before meaningful work and evaluates transition triggers
before finishing. It does not edit the roadmap when work progresses inside the
same status. Projects without a roadmap still create an initial one during their
first meaningful work unit.

## 2026-08-02 - Standardize Roadmap Format And Web Publication

Status: Accepted

Context:

Project-owned roadmap continuity defines when planning state changes, but new
repositories still need a predictable shape and browser-accessible projects
need one stable location where people can inspect that state.

Decision:

Define one standard `ROADMAP.md` field set and table shape for new roadmaps.
Require browser-accessible projects to render their canonical roadmap read-only
at `/roadmap`. Preserve existing project-specific generators and map their
canonical output to the standard web fields rather than creating a duplicate
roadmap. DeveloperOS provides a parsed cross-project view in its console.

Reason:

A stable format makes status recoverable by both people and tooling. A derived
web view makes that state easy to inspect while repository ownership prevents
the display layer from becoming a second source of truth.

Impact:

The public API exposes only validated standard fields and omits raw Markdown,
filesystem paths, and parser diagnostics. DeveloperOS implements the first
`/roadmap` view. Existing projects without a standard root roadmap or adapter
remain visibly unavailable until their project-specific rollout is completed.

## 2026-08-02 - Minimize Docker Image Builds By Default

Status: Accepted

Context:

Compose can build implicitly when an image is absent, and several routine
project commands used `up --build`. This made ordinary starts and restarts
potentially expensive and obscured whether a source change actually affected an
image layer.

Decision:

Make no-build startup the workspace default. Shared `make run` and `make up`,
project-specific runtime commands, restarts, and deployment startup must reuse
existing images with `--no-build`. Named build and release commands may perform
one cached build, then start separately without another build request. Preserve
images, volumes, and cache during ordinary cleanup.

Reason:

Separating build from startup makes resource use predictable, keeps development
loops fast for bind-mounted projects, and still provides a clear path when a
Dockerfile, dependency layer, copied artifact, architecture, or immutable
release revision requires a new image.

Impact:

`00_Master/DockerImageBuildPolicy.md` is the global source of truth. The shared
Make contract enforces no-build starts, `make docker-policy-check` audits all
managed projects, and DeveloperOS applies the policy as a non-containerized
console with zero routine image builds.

## 2026-08-02 - Separate Source And Project Data Synchronization

Status: Accepted

Context:

Projects may generate valuable state outside Git on more than one computer.
Examples include immutable learning observations, replay shards, model bundles,
learner checkpoints, and selected database records. Treating all of this as a
database copy problem either prevents useful exchange or creates unsafe
bidirectional mutation.

Decision:

Keep Git as the source synchronization system and define a separate project data
synchronization contract. Permit bidirectional set-union transfer only for
immutable records with stable globally unique identities, content checksums,
idempotent imports, compatible schemas, and hard conflict detection. Require one
authority and directed transfer for mutable databases, aggregate state, active
models, and checkpoints. Keep synchronization separate from backup, model
promotion, and production deployment.

Reason:

Unique identities make missing-set comparison efficient, but identity alone
does not resolve divergent content, deletion, concurrent mutation, or schema
drift. Classifying data by merge semantics allows safe bidirectional exchange
where it is mathematically valid without weakening production boundaries.

Impact:

`00_Master/DataSynchronizationPolicy.md` defines the global rules and the
optional `03_Blueprints/Project/DATA_SYNC.md` captures project-specific stores,
directions, identities, conflicts, and verification. Projects adopt status-only
comparison before transfer automation. DeveloperOS may display derived evidence
but does not store payloads or become a transfer proxy. Database selection is
default-deny: each project owns an explicit allowlist of logical tables, export
queries, row scopes, and dependency closure. Enabling one set never authorizes
whole-database synchronization.

## 2026-08-02 - Standardize Deployment And Data-Publish Make Facades

Status: Accepted

Context:

Application projects had different local deployment target names, while data
synchronization needed a simple command without allowing DeveloperOS to infer
which database content should move. Automatically committing an entire working
tree from Make would also bypass meaningful commit selection and could publish
unrelated or sensitive files.

Decision:

Reserve `make deploy` and `make sync` in the shared DeveloperOS Make contract.
`make deploy` accepts only a clean branch, pushes already reviewed commits,
verifies the exact upstream revision, and delegates to a project-owned deploy
target. `make sync` has the fixed meaning local-to-server and delegates only to
an explicitly configured project-owned data-publish target. Deployment-time
sync is disabled unless a project selects `after-deploy`.

Reason:

One public vocabulary reduces operator memory while project-owned hooks retain
the deployment and data semantics that cannot be inferred globally. Keeping
commit judgment outside Make preserves coherent history and ensures every
deployed revision can be identified and rolled back through Git.

Impact:

DeveloperOS, OA, and Gaia route their existing deployments through the shared
facade. Projects without a production deploy target fail clearly. Projects
without a synchronization target report a no-op. A future project may opt into
post-deploy sync only after its `DATA_SYNC.md` allowlist and directional push
implementation are verified.

## 2026-08-02 - Generalize Usage Visibility Without Browser Credentials

Status: Superseded by the 2026-08-03 free-tier consumption decision

Context:

The console already displayed an OpenAI cost snapshot. Oracle Cloud cost and
compute account capacity require different OCI APIs and should not introduce
an OCI user private key into the repository or public web process.

Decision:

Treat Usage as a provider-neutral read-only view. Keep each provider collector
outside the console process and expose only credential-free snapshots. Use the
Oracle Compute instance principal for OCI authentication. Query billing cost
and resource availability separately. Present the A1 values returned by OCI as
usage, account limit, and available capacity. Do not label a service limit as
an Always Free entitlement.

Reason:

Instance principals avoid another long-lived private key. Provider-reported
capacity is more reliable than manually copied values, but later observation
showed that account capacity does not answer the operator's cost question.

Impact:

This initial implementation established the credential isolation boundary. Its
account-capacity presentation was replaced the following day without changing
that boundary.

## 2026-08-03 - Show Free-Tier Consumption Instead of Account Capacity

Status: Accepted

Context:

The console already displayed OpenAI and Oracle cost snapshots. OCI Service
Limits reported the tenancy's maximum A1 capacity, which is much larger than
the monthly free quantity and is not useful for routine cost awareness.

Decision:

Treat Usage as a provider-neutral read-only view. Keep each provider collector
outside the console process and expose only credential-free snapshots. Use the
Oracle Compute instance principal for OCI authentication. Query billing cost
and actual SKU usage through the Usage API. Read A1 part numbers B93297 and
B93298, their monthly free ranges, and their overage rates from Oracle's public
price list. Show consumed and remaining free quantities, not account service
limits or paid headroom. Project month-end usage from completed UTC days and
estimate cost from the observed cost run rate and projected A1 overage. Label
the result as an estimate rather than an invoice.

Reason:

Instance principals avoid another long-lived private key. Provider-reported
SKU consumption is the relevant evidence for free-tier awareness, while a paid
tenancy's service limit is not a free allowance. A simple disclosed projection
is useful for early warning without pretending to reproduce Oracle billing.

Impact:

The `Usage` tab shows OpenAI and Oracle Cloud independently. OCI collection
requires only the read-only dynamic-group policy for `usage-report`. The public
console never receives the OpenAI Admin key, OCI identity material, or tenancy
identifiers. The previously granted `resource-availability` permission is no
longer required and may remain harmlessly or be removed by the operator.

## 2026-08-03 - Standardize Roadmap Presentation Across Projects

Status: Accepted

Context:

DeveloperOS, OA, bTest, and Gaia read equivalent canonical roadmap documents,
but each application implemented its own HTML and CSS. The resulting project
routes diverged from the more useful stage view in the DeveloperOS console.

Decision:

DeveloperOS owns a framework-neutral roadmap presentation bundle and a versioned
detail contract. Projects continue to own roadmap content and parsing adapters.
Each stage may declare every sibling detail item with one of four presentation
states: done, in progress, blocked, or prohibited. Blocked items distinguish
operator response, historical processing, and future observation. Descriptions
are available on hover and keyboard focus. Legacy documents remain readable
through derived completion and transition items during migration.

Reason:

Central ownership keeps visual semantics and accessibility consistent without
moving project state into DeveloperOS or forcing all projects onto one web
framework.

Impact:

DeveloperOS uses the canonical renderer directly. Individual projects vendor
the versioned assets and adapt their project-owned parser output to the same
JSON shape. Updating a shared visual contract requires deliberate project
adoption and verification rather than silent cross-repository mutation.

## 2026-08-03 - Make Linked Progress Cards The Primary Roadmap View

Status: Accepted

Context:

The shared roadmap route spent most of its first viewport on a repeated title,
direction, milestone, completion signal, and legend even though project and
track tabs already established context. Multi-track projects also maintained
independent Overall detail rows and track topics, allowing the compact cards to
drift from the large cards shown after selecting a track.

Decision:

Begin every roadmap detail view with its large progress cards. Keep project and
track tabs directly above the renderer, omit the visible title and milestone
summary blocks, and place a compact legend below the cards. Retain the omitted
fields in canonical roadmap documents and structured data for planning use.
Adopt `ROADMAPS.json` schema version 2 for multi-track card parity: every track
declares one unique `overview_topic`, and the parser rejects differences in the
linked card count, order, name, presentation status, or description. Schema
version 1 remains readable only as a migration format.

Reason:

Progress state is the roadmap's highest-frequency visual question. A linked
contract makes Overall a truthful compact index of the track cards instead of a
second summary that can silently diverge, while preserving detailed planning
fields outside the first viewport.

Impact:

DeveloperOS roadmap bundle 3.0.0 implements the card-first layout and linked
card metadata. OA, Gaia, and bTest must upgrade their manifests, overview rows,
track adapters, and vendored assets in their own repositories. Their project
tasks remain responsible for resolving content-specific mismatches.

## 2026-08-03 - Route Codex Through Project-Owned Context Areas

Status: Accepted

Context:

Repeated project work spent substantial time rediscovering source boundaries,
test commands, services, data stores, and risk rules. Full repository scans were
especially expensive in bTest, while static summaries could become stale and
silently misroute work.

Decision:

Each project may own one concise `PROJECT_AREAS.json` that maps task language to
source globs, entrypoints, related documents, focused verification, services,
data stores, and risks. DeveloperOS owns a shared `make context TASK="..."`
command. It generates `.developer-os/context-index.json`, uses Git blob IDs for
unchanged tracked files, hashes only dirty or untracked files, and recalculates
area assignments from the current map. The generated cache is ignored by Git
and contains structural metadata rather than file contents or runtime data.

Reason:

A small reviewed routing map removes repeated broad investigation without
turning DeveloperOS into the owner of project state. Git-aware incremental
indexing stays fast and detects working-tree changes, while explicit expansion
rules preserve correctness for shared contracts and safety boundaries.

Impact:

DeveloperOS applies the contract to itself and provides the map Blueprint,
indexer, tests, shared Make command, startup guidance, and self-check. OA, Gaia,
and bTest must define their own real areas and focused tests in project-local
tasks. The index remains advisory; source code and explicit project rules are
still authoritative.

## 2026-08-03 - Narrow The Browser Console To Evidence

Status: Superseded by the 2026-08-03 roadmap-view clarification

Context:

The browser console exposed a Commands section whose project controls were
disabled on the public deployment and duplicated the safer SSH-tunneled
terminal. Its Operations section also repeated deployment and end-of-work
state already available in Projects and Overview.

Decision:

Remove browser project-command controls and their API. Replace Operations with
a Recovery view limited to database backup, isolated restore-verification, and
automation-schedule evidence. Keep project commands behind the separate
loopback terminal reached through SSH. This decision supersedes the browser
command portion of the 2026-07-28 operations-console decision.

Reason:

A smaller read-only surface makes the security boundary and ownership clearer,
removes duplicated status, and follows the principle that DeveloperOS should
become quieter as its contracts mature.

Impact:

The primary navigation is Overview, Projects, Roadmap, and Recovery.
Deployment and delivery signals remain derived in their existing views, while
recoverability evidence retains a dedicated view. The console no longer emits
project actions or accepts `/api/actions` requests.

## 2026-08-03 - Remove Centralized Roadmap Aggregation

Status: Superseded by the 2026-08-03 roadmap-view clarification

Context:

The browser console aggregated DeveloperOS, OA, Gaia, and bTest planning state
under one Roadmap tab. Even when read-only, that presentation made DeveloperOS
behave like a project dashboard and blurred project ownership.

Decision:

Remove the console Roadmap tab, `/api/roadmaps`, `/roadmap-assets`, and the
console-owned roadmap parser. Keep the DeveloperOS internal `ROADMAP.md`, the
global roadmap lifecycle policy, Blueprints, canonical renderer assets, and
project-local `/roadmap` contract. Each project owns its parser and published
planning state. This decision narrows the navigation established by the earlier
2026-08-03 console decision.

Reason:

DeveloperOS is an engineering constitution and decision engine, not the owner
or aggregator of application-project planning state.

Impact:

The primary console navigation is Overview, Projects, Roadmap, and Recovery.
Roadmap standards remain shared, while roadmap content and web publication stay
inside each project repository and application.

## 2026-08-03 - Preserve The Roadmap View Without A Roadmap Lifecycle Stage

Status: Accepted

Context:

A request to remove roadmap as a specific DeveloperOS progress stage was
misread as a request to remove the browser Roadmap view and aggregation API.
The resulting change removed useful read-only planning visibility rather than
only the self-referential `Project roadmap continuity` card.

Decision:

Restore the console Roadmap tab, `/roadmap`, `/api/roadmaps`, the validated
parser, and the canonical shared renderer. Remove `Project roadmap continuity`
from the DeveloperOS roadmap topics and details so roadmap lifecycle remains a
governance baseline rather than appearing as a product-development stage.

Reason:

The roadmap is necessary planning evidence. A read-only derived view does not
take ownership away from project repositories, while presenting roadmap
maintenance itself as a roadmap stage creates a self-referential card with no
useful product transition.

Impact:

The primary console navigation is Resources, Projects, Roadmap, and Recovery.
Each project remains the canonical owner of its roadmap content; the
console validates and renders that content without storing a second copy.

## 2026-08-03 - Make Resources The Console Landing View

Status: Accepted

Context:

The Overview landing view mixed server capacity with alerts, workstation
summaries, Docker metadata, and recent activity. Those summaries repeated
evidence available in Projects or Recovery while hiding the useful resource
attribution behind one-at-a-time expansion controls. Its residual `Server &
other` value also combined required operating-system usage with potentially
reviewable data.

Decision:

Replace Overview with a resource-only `Resources` landing view. Show CPU,
memory, and root-disk attribution simultaneously across the available page.
Split residual host use into measured service, shared, protected, reviewable,
baseline, and unattributed categories, and explain the reduction boundary for
each category. Bound every residual component by the observed host total.

Reason:

The console should expose evidence that supports a concrete capacity decision,
not accumulate low-value summaries. Always-visible attribution makes large
residual usage inspectable and distinguishes safe investigation targets from
usage that is required for the server to operate or recover.

Impact:

The primary console navigation is Resources, Projects, Roadmap, and Recovery.
Projects retains workstation and repository comparisons; Recovery retains
backup and schedule evidence. Resource collection adds aggregate host-process,
shared-Docker, system-file, log, and backup attribution without exposing
individual process command lines or filesystem paths in the public payload.

## 2026-08-04 - Use Git As The Sole Source-Code Recovery Mechanism

Status: Accepted

Context:

The mandatory AI work snapshot rule produced 27 small DeveloperOS file-copy
sets, no recorded restore, and no implemented create or restore manager. OA,
Gaia, and bTest had no corresponding snapshots while their Git histories
already provided frequent recovery boundaries.

Decision:

Abolish AI work snapshots and the planned Snapshot Manager. Git is the sole
source-code recovery mechanism. Agents inspect the working tree, preserve
unrelated developer changes, and commit meaningful verified work. They do not
create parallel pre-edit file copies.

Reason:

An untested duplicate recovery mechanism adds policy and cleanup overhead
without demonstrated recovery value. Git already provides reviewed history,
branching, comparison, and restoration for source files.

Impact:

Remove AI snapshot directories, ignore rules, creation triggers, self-checks,
and roadmap work. Database backups, deployment rollback artifacts, provider
usage records, and other project-owned operational recovery data are unchanged.

## 2026-08-04 - Store Console Memos In A Scoped SQLite Service

Status: Accepted

Context:

Development ideas for DeveloperOS, bTest, OA, and Gaia must survive browser
changes and be available from more than one workstation. Browser-local storage
cannot provide that continuity, while enabling the full console session on the
public endpoint would expose unrelated private APIs.

Decision:

Store one bounded text memo per registered project in a SQLite database under
the persistent console state directory. Expose only these four fixed records
through a narrow public read/write API; this does not authenticate or expose
the general console APIs. Include a consistent SQLite copy and integrity check in
the daily managed database backup job with 14-day retention.

Reason:

Four small text records do not justify a PostgreSQL service. SQLite provides
durable transactional storage with no new daemon, while the fixed project list
and bounded content keep memo editing separate from private console data.

Impact:

The Memo view opens directly and auto-saves to server storage. Recovery reports
the memo backup beside project database protection. Anyone who can reach the
public console can read or replace memo text, so memos must not contain secrets.

## 2026-08-09 - Use A Seven-Step GPT-User-Codex Protocol For High-Impact Work

Status: Accepted

Context:

High-impact work can fail when one AI carries an initial assumption through
design, implementation, and approval without an independent challenge. The
developer needs GPT's domain-level reasoning, Codex's repository-grounded
implementation evidence, Sol's adversarial review, and a clear final decision
boundary.

Decision:

Use the shared seven-step protocol for work with high failure cost or material
design judgment: problem and purpose definition, GPT design, Codex plan, Codex
implementation and report, independent Sol review, independent GPT review, and
the user's final decision. Keep small, clear, reversible changes lightweight.
Treat GPT and Codex/Sol as peer reviewers and treat the user as final design
owner. Project-specific rules and stricter safety policies take precedence.

Reason:

Independent context and explicit human arbitration reduce self-reinforcing
assumptions while avoiding unnecessary ceremony for low-risk work.

Impact:

The canonical policy is `02_AI/DevelopmentProtocol.md`. `BOOT.md`, global
Codex guidance, and the Codex task template route high-impact work to it. New
projects under `X:\Projects` inherit the default through DeveloperOS guidance;
their local rules may strengthen or specialize it.

## 2026-08-14 - Use Immutable Cycle Handoff Packets As Canonical Review Fixtures

Status: Accepted

Context:

Manually assembled task, report, and baseline text files preserve content but
do not prove which session messages formed one real GPT-Codex review cycle.
They also make it easier to include unrelated history or omit an intermediate
user decision without an explicit trace.

Decision:

Use an immutable `MAINLINE_CODEX_REVIEW` Cycle Handoff packet as the canonical
orchestration fixture. Select exactly one MAINLINE task, every applied user
decision between task and report, one CODEX report, and the immediately
following MAINLINE manual review by message identifier. Seal exact content,
message order, source sessions, and packet content with SHA-256. Send only the
task, selected user decisions, and report to a reviewer; reserve the manual
review for local comparison. Never merge FUTURE_DESIGN or unrelated session
history automatically. Keep the three-file importer as a legacy/manual
fallback with an explicit semantic-equivalence check.

Reason:

Message-level provenance makes cycle boundaries reproducible while preserving
the reviewer-blinding contract. Immutable revisions prevent a captured source
change from silently rewriting an already reviewed fixture.

Impact:

Future canonical candidates begin from a verified Cycle Handoff packet with
`approved_for_external_api=false`. Changed source content creates a new packet
revision and hash. Existing holdout, response, comparison, and consumed
approval artifacts remain unchanged.

The first end-to-end validation is accepted as `SESSION_HANDOFF_E2E_COMPLETE`.
The no-network candidate with approval manifest `e11cb8e3d5bdb4fe6a98362a22ebea288be53f2d41878c2cf12c7badf62be950`
is retained as an unapproved artifact and must not be executed. The next
validation must start from a new independent `MAINLINE_CODEX_REVIEW` cycle
captured directly as a Cycle Handoff packet, with a clear `USER_REQUIRED`
manual baseline.

## 2026-08-14 - Separate Synthetic Routing Evidence From Historical Holdouts

Status: Accepted

Context:

No completed historical `MAINLINE_CODEX_REVIEW` cycle currently provides an
unambiguous USER_REQUIRED baseline. Inventing one as historical evidence would
weaken fixture provenance, while leaving USER_REQUIRED untested would leave a
material routing branch uncovered.

Decision:

Maintain deterministic threshold, authority, architecture, scope, and
destructive-migration cases in a dedicated synthetic fixture area. Label every
result `SYNTHETIC_ROUTING_EVIDENCE` and require SAFE_CONTINUE, BLOCKED, and STOP
negative controls in the same suite. Never present a synthetic PASS as
historical validation. Mark a future genuine USER_REQUIRED candidate only when
a direct, non-legacy, non-synthetic MAINLINE Cycle Handoff packet has a complete
task, report, and manual review and the unresolved choice belongs to semantic,
policy, threshold, authority, architecture, or scope ownership.

Reason:

Synthetic cases provide immediate deterministic contract coverage without
fabricating provenance. Negative controls prevent the suite from simply routing
every case to USER_REQUIRED.

Impact:

Candidate marking remains local and never triggers an API call or dispatch.
The first genuine real-world candidate still requires explicit user approval
before it can become a historical holdout.

## 2026-08-14 - Establish A Non-Executing Multi-Prompt Control Plane

Status: Accepted

Context:

Phase 1 proved local capture, review, routing, task-alignment, and evidence
contracts, but the console had no project-level place to define logical GPT and
Codex participants or the routes between them. Binding UI concepts directly to
session identifiers would also mix orchestration intent with unreliable remote
transport details.

Decision:

Add an authenticated per-project orchestration control plane with OFF,
SHADOW_REVIEW, and SEMI_AUTO modes; lifecycle controls; logical prompt nodes;
directed route validation; backend-only transport references; capability-aware
transport adapters; and redacted user-action audit events. Persist it through
the existing console runtime-file boundary rather than introducing a database.
Keep AUTO_SAFE_CONTINUE locked and keep all background capture, reviewer calls,
handoff writes, Codex execution, and generated-instruction dispatch disabled.

Reason:

Separating policy state, logical routing, and transport capability creates a
usable operator surface without overstating remote connectivity or weakening
the Phase 1 approval and immutable-artifact contracts.

Impact:

The console can configure and inspect multi-prompt graphs and operator state,
but no selected mode performs work in Phase 2A. CHATGPT_SESSION is reported as
degraded, Codex and Responses transports remain locked, USER_ASSISTED preserves
exact local capture, and MOCK supports local routing tests only. Transport
references are omitted from API responses and audit records.

## bTest Uses One Mainline Authority Per Orchestration State

Status: Accepted

Context:

The native bTest GPT remains useful during manual development, while managed
orchestration needs an API-addressable Mainline. Treating both as simultaneous
authorities would permit conflicting policy, routing, and user-decision state.
Provider conversation history also cannot replace DeveloperOS canonical state.

Decision:

When orchestration is OFF, `NATIVE_MAINLINE` is canonical. When orchestration is
enabled, `BTEST_MAINLINE_API` is canonical. Every transition records the old
and new authority in the redacted control-plane audit. Output from the inactive
Mainline cannot update canonical routing or resolve an active route. Keep
purpose, frozen decisions, scope, authority, routing, user decisions, current
Gate, and latest handoff in DeveloperOS; keep conversation IDs, response links,
and model interaction history as private OpenAI transport state.

API Mainline output must select one structured action from `HANDOFF_CODEX`,
`USER_REQUIRED`, `CONTINUE_USER_DIALOGUE`, `BLOCKED`, or `STOP`. Validate its
destination and required packet deterministically rather than interpreting
natural language. READ, WRITE, and RESUME remain declared but locked; this
decision authorizes no OpenAI call, conversation creation, dispatch, or loop.

Reason:

One explicit authority and a fail-closed routing contract preserve user control
and make provider conversation continuity replaceable without changing project
policy.

Impact:

The console can display the active Mainline authority and API readiness without
exposing conversation or transport identifiers. A later live phase must obtain
separate approval and reuse the existing Gate, task-alignment, evidence,
handoff, workspace, approval, and duplicate guards.

The first API Mainline interaction must begin from a separately sealed,
no-network bootstrap candidate. Send only canonical state and one exact user
input, require a strict structured routing action, and accept only an
allowlisted state delta. Model output cannot directly change frozen decisions,
authority, or routing. The candidate remains `approved_for_external_api=false`
and exposes only model, cost cap, and a shortened canonical-state hash in the
console until the user approves a later live phase.

The purpose-free Phase 2C-2A candidate is retained as
`DO_NOT_EXECUTE / SAFE_BOOTSTRAP_FALLBACK`. Do not spend a model call merely to
ask for the user's missing purpose. The normal path requires orchestration ON
with `BTEST_MAINLINE_API` as the active authority and an exact user-entered
Initial Request. Start creates an immutable, no-network candidate and binds its
user-input hash to the approval manifest. A changed input or canonical state
invalidates the earlier candidate. Live initialization remains a separate
explicit approval boundary.

Codex return handoffs are exactly-once per captured result and destination, not
globally per result. This permits the native user-assisted path and the managed
API Mainline path to coexist without reusing either envelope. API Mainline
returns replay canonical state plus the exact sealed Codex result in a
`STATELESS_CANONICAL_CONTINUATION`; with `store=false`, they do not represent
`previous_response_id` as a supported resume mechanism. The preview remains
`approved_for_external_api=false` and cannot create an approval, attempt, live
Responses call, or next cycle.

## AUTO_SAFE_CONTINUE Begins As A Two-Cycle Approval-Locked Pilot

Status: Accepted

Decision:

Implement the AUTO_SAFE_CONTINUE eligibility and stop policy as a local,
deterministic pilot with a hard maximum of two cycles, zero retries or model
fallbacks, and no automatic approval. Permit eligibility only for validated
`SAFE_CONTINUE` plus `BOUNDED_TASK` results that pass task alignment, evidence
sufficiency, workspace, transport, blocker, and user-authority checks. Always
stop on conflicts, external workspace changes, approval/input requests, budget
failure, or changes involving destructive work, databases, infrastructure,
authority, thresholds, or scope.

Keep the mode non-selectable and live execution disabled until the user
separately approves a cumulative pilot cost cap. Use the newest sealed API
Mainline return preflight as the cost basis, but do not mutate or reuse its
approval. Expose immutable-ledger activity as a read-only timeline.

Impact:

The controller and UI can explain exactly why an automatic step would proceed
or stop and can show the bounded cost envelope. No API call, Codex turn,
dispatch, or background cycle is enabled by this decision.

## 2026-08-19 - Finalize Orchestration Token Efficiency And Pause Development

Status: Accepted

Decision:

Use `OrchestrationTokenEfficiencyV1` for managed Mainline continuations. Keep a
stable prompt/schema prefix separate from a dynamic payload limited to compact
canonical state, the current task, latest Codex report, requirement identities,
and authorized source references. Do not automatically include full history,
manual reviews, completed cycles, the activity timeline, or repository history.
Generate Codex handoffs as bounded deltas and cap continuation output at 6,144
tokens while preserving every existing Gate, authority, alignment, evidence,
and routing field.

Block an identical validated evaluation by exact canonical-state, task, report,
protocol, and reviewer-schema identity. Deterministic prechecks may stop stale,
consumed, credential-missing, workspace-mismatched, route-invalid, or
protocol-invalid execution, but may not perform semantic judgment. Prompt cache
availability is never a correctness dependency.

Impact:

No live call, Codex turn, dispatch, or project mutation is authorized by this
decision. Orchestration development is paused after this bounded optimization;
new pilots, transports, or orchestration features require an explicit user
resume instruction.

## 2026-08-15 - Assign Shared Native Docker Infrastructure To DeveloperOS

Status: Accepted

Context:

bTest, OA, and Gaia migrated substantial runtime and database state from Docker
Desktop to one native Ubuntu daemon, but local commands still depended on
project wrappers, ambient Windows contexts, Desktop-backed CLI plugin links,
and inconsistent Docker configuration. Any project changing that shared layer
independently could break all three runtimes.

Decision:

DeveloperOS owns the canonical Windows-to-Ubuntu launcher, native CLI and
Compose paths, `/run/docker-wsl.sock`, `/var/lib/docker-wsl`,
`docker-wsl.service`, `/home/devops/.docker-native`, native `pass` credential
storage, Desktop plugin-link cleanup, and coordinated daemon restart. The
launcher rejects socket, context, and config overrides. Projects own only their
repository commands and must integrate local calls with the shared launcher;
remote Docker commands and credentials stay server-local.

Reason:

One explicit infrastructure authority prevents Desktop state, Windows context,
plugin search order, and credential helper drift from changing which daemon or
Compose implementation a project command uses.

Impact:

Fifteen unowned Docker Desktop plugin symlinks were removed after their targets
and ownership were recorded. Native Docker and Compose packages, containers,
volumes, networks, data root, and socket were retained. The canonical config
uses `credsStore=pass` with private permissions. Docker Desktop deletion remains
blocked until bTest, OA, and Gaia each migrate repository-local commands and
repeat runtime and data verification through the shared launcher.

## 2026-08-15 - Centralize Docker Desktop VHD Deletion-Readiness Evidence

Status: Accepted

Context:

bTest, OA, and Gaia proved native runtime/tooling independence but could not
vote on Docker Desktop deletion until persistent data inside the shared Desktop
VHD was classified across project boundaries.

Decision:

DeveloperOS owns the read-only cross-project inventory, immutable forensic-copy
hashes, ownership and persistence matrix, native-counterpart reconciliation,
and project handoff evidence for the shared Docker Desktop VHD. Project Codex
instances retain authority over their database semantics and final deletion
votes. A full VHD copy is forensic preservation, not an application backup or
deletion authorization.

Reason:

The VHD is one shared storage boundary. Independent project inventories could
miss anonymous volumes, duplicate preservation work, or make conflicting
claims about shared assets.

Impact:

All 82 Desktop assets have an exact machine-readable row. A read-only,
hash-matched VHD copy and dedicated bTest PostgreSQL archive exist outside
Docker Desktop. No VHD, volume, container, image, network, or cache was deleted.
Docker Desktop deletion remains closed pending bTest and Gaia project acceptance
and an explicit user-approved destructive phase.

## 2026-08-15 - Pass The Docker Desktop Global Asset Gate

Status: Accepted

Context:

Later project forensics closed the two database questions left open by the
initial shared VHD inventory. bTest preserved and restored 4,709 meaningful
Desktop-only provenance rows; Gaia preserved and restored its Desktop database
and classified 32 stale rows as obsolete; OA confirmed no unique Desktop data.

Decision:

Record `PROJECT_APPROVAL_GATE=PASS (3/3)`, `GLOBAL_ASSET_GATE=PASS`, and
`READY_FOR_GLOBAL_AUTHORIZATION=YES`. Of 82 Desktop assets, 76 are directly
safe with Desktop removal and six are externally preserved then safe to delete.
No asset remains VETO or UNKNOWN. External forensic artifacts and every native
Ubuntu/Docker/project asset are outside the deletion set.

Reason:

The final gate now has project-owned semantic evidence, checksum-bound external
preservation, and restore verification rather than name-based equivalence.

Impact:

This decision freezes readiness evidence and an exact cleanup plan. It does not
issue `AUTHORIZE_GLOBAL_DOCKER_DESKTOP_REMOVAL`; no application, distribution,
VHD, container, image, network, volume, cache, startup entry, or helper is
deleted by this decision.

## 2026-08-20 - Delegate Routine Operations To Managed Projects

Status: Accepted

Context:

bTest and Elliott repeatedly routed project-owned database, credential,
migration, and container operations through DeveloperOS even when no shared or
cross-project resource changed. The extra approval hop obscured the real user
decision boundaries and interrupted bounded development cycles.

Decision:

Adopt `ProjectOperationalAuthorityPolicy.md`. A managed project owns routine,
non-destructive repository, database, runtime, credential, source-ingestion,
and forward-materialization operations inside an already approved purpose.
Users retain semantic, policy, destructive, privilege-expansion, and live-risk
authority. DeveloperOS retains shared Docker daemon/socket/data-root/network,
host/WSL, global secret, and cross-project authority.

Reason:

Authority should follow the resource and the meaning being changed. Routine
project operation does not become a cross-project authority mutation merely
because it uses DeveloperOS-managed shared infrastructure.

Impact:

Elliott may continue bTest 2.12.3 operations, including shared-kline runtime
recovery, additive migrations, least-privilege writer maintenance, credential
rotation, and forward-only source recovery, without an OS round trip. A new
production search budget, cadence, activation start, guidance meaning, or
canonical research rule remains a user decision. Shared-daemon or host changes
still escalate to DeveloperOS.

## 2026-08-20 - Keep DeveloperOS Environment In Its Working Directory

Status: Accepted

Context:

DeveloperOS credentials were split across shared files under
`X:/Settings/env`, while the repository already excludes a root `.env` from
Git. The shared location made the active source harder to identify and tied
DeveloperOS startup to a separate settings directory.

Decision:

Use `X:/Projects/DeveloperOS/.env` as the canonical local DeveloperOS
environment file. Runtime, deployment, and orchestration defaults resolve that
file directly. The file remains untracked and secret values must never enter
logs, artifacts, documentation, or Git.

Reason:

Keeping the machine-local environment beside the working tree makes the active
configuration explicit while retaining Git isolation and existing secret
handling boundaries.

Impact:

The former `X:/Settings/env` files are no longer DeveloperOS runtime inputs.
They remain preserved until the user separately decides their retention or
deletion policy.

## 2026-08-25 - Permit Independent Native Docker Runtime Starts

Status: Accepted

Context:

OA, Gaia, bTest-Elliott, and bTest-Ever share one native WSL Docker daemon,
but routine project development should not require a separate DeveloperOS
approval merely because the daemon is currently stopped. Conversely, starting
the daemon must not unexpectedly start another project's containers.

Decision:

Starting `docker-wsl.service` and idempotently ensuring it is running are
pre-approved shared prerequisites. Each project may then start or stop only
its own Compose namespace and services with `--no-build`. Daemon stop/restart,
daemon configuration, prune, global volume/network deletion, and
cross-project resource operations remain DeveloperOS/user-authorized.
Local development Compose services must not use restart policies that make
daemon startup start project runtimes. The four project namespaces are
independent, and Ever development owns loopback port `8091`.

Reason:

This separates availability of the shared engine from application lifecycle,
so one project's routine development does not become an approval hop or
accidentally affect another project's containers, networks, or volumes.

Impact:

Project repositories must audit restart policies, systemd and supervisor
units, scheduled tasks, Compose hooks, namespace names, and scoped start/stop
commands. Existing data and volumes are preserved; this decision authorizes
no migration, deletion, prune, or daemon restart by itself.
