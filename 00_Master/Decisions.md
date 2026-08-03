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

Status: Accepted

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

The console runs independently from governance documents, binds to port 8080,
and may display a local OpenAI usage snapshot. OpenAI credentials and live
billing integration are outside the default console scope.

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

The operations console should display current OpenAI API cost and remaining
monthly budget. Organization cost access requires a privileged Admin key that
must not enter Git, a browser response, or the long-running public console
process.

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
permissions, and the public console reads only aggregate cost, budget,
remaining amount, period, and update time.

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
roadmap state, snapshot recovery, Git checks, verification, monitoring, and
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
