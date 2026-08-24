# DeveloperOS Browser Console

## Purpose

The browser console is a live operational view of the workspace. It does not
store project roadmaps, duplicate project documentation, or become the source
of truth for project state. `/roadmap` derives a read-only standard view from
project-owned root `ROADMAP.md` files.

For bTest orchestration, the Initial Request form is a no-network preparation
boundary. It requires the managed API Mainline authority, seals the exact user
input with current canonical state, and stops at `USER_APPROVAL_REQUIRED`.
Changing the input creates a new candidate and stales the prior candidate; the
form never creates an OpenAI conversation or sends a Codex dispatch.

Completed Codex reports may be sealed for both native and API Mainline routes.
Native ChatGPT delivery remains user-assisted. The API route creates only a
stateless, exact-result PREPARED candidate bound to current canonical state and
keeps live Mainline send separately locked.

The stage presentation is loaded directly from the canonical, versioned bundle
under `04_Tools/roadmap-web`. Project-local `/roadmap` routes install and use
the same bundle; projects continue to own their roadmap parser and content.
The bundle starts with progress cards, places its legend below them, and omits
title and milestone summary blocks from the first viewport. Multi-track schema
version 2 manifests link each Overall compact-card group to the exact large
cards shown by its track tab.

The console reads:

- Git working-tree and upstream status from project repositories.
- Docker Compose container state.
- Repository HEAD compared with running Docker image revisions.
- Home and Office local Git status reported separately over SSH while each computer is online.
- Oracle Linux CPU, memory, and disk capacity with always-visible project and host attribution.
- Daily database backup and weekly isolated restore-verification status.
- Optional local OpenAI and Oracle Cloud usage snapshots.
- A Recovery view limited to backup, restore-verification, and schedule evidence.
- A server-database memo workspace for DeveloperOS, bTest, OA, and Gaia ideas.
- Standard roadmap fields for configured projects, without raw files or source
  paths.

The landing `Resources` view uses the full workspace with CPU, memory, and disk
columns ordered from left to right. Each column lists project and host usage
vertically from the largest category to the smallest. Registered project usage
is separated from host usage. The
`Server & other` row further identifies required services, operating-system
baseline, shared Docker data, protected backups, reviewable usage, and the
remaining measurement or attribution boundary. Category values are bounded by
the observed host total so a detailed estimate never exceeds actual usage.

The `Projects` view is a single full-width comparison table. Project identity,
GitHub state, server state, service health, port, and terminal are shared columns;
Home and Office each contribute only their Local state. A green or red light
beside each workstation name replaces the repeated status cards and headings.
Project names expand an inline server-container view with runtime status, image,
ports, and start time. The Terminal column heading opens the private terminal's
Server context rooted at `/home/opc`; commands still run as `opc`, never as root.
The `Resources` view uses the same edge-to-edge workspace without a repeated
page title or outer padding.

The selected primary menu, roadmap project, and per-project roadmap track are
kept for the lifetime of the current browser tab. Reloading the page refreshes
the operational data without resetting those valid selections. If a saved
project or track no longer exists, the view safely falls back to its default.

## Security Model

- Production requires `DEVOS_CONSOLE_TOKEN`.
- The browser console has no project mutation or shell-command API.
- Project commands use the separate loopback terminal reached through an
  authenticated SSH local-forward.
- The direct public HTTP deployment uses `DEVOS_PUBLIC_READ_ONLY=1`; it hides
  project paths and audit history and disables the full console login.
- The public roadmap API returns only parsed standard fields. It does not return
  raw Markdown, source paths, or parser diagnostics.
- Memo text is stored in the server's private SQLite database. A separate memo
  login uses a memo-only token and creates a cookie accepted only by
  the memo API; it cannot unlock project paths, logs, or terminal access.
- The current direct deployment is plain HTTP. Its memo token exchange is
  suitable only on a trusted network path; HTTPS is required for transport
  confidentiality on an untrusted network.
- A separate command console binds to server loopback only and is reachable
  through an SSH local-forward from a trusted workstation.

## Local Development

```powershell
make console-run
```

Open `http://127.0.0.1:8080`. The roadmap view is
`http://127.0.0.1:8080/roadmap`. Development mode does not require an access
token.

Run tests:

```powershell
make console-test
```

## Oracle Server Deployment

```powershell
git add <files>
git commit -m "<message>"
git push origin main
make console-deploy
make console-status
make console-logs
make console-backup-status
make console-usage-status
```

The deployment script:

1. Requires a clean `main` working tree whose commit exactly matches
   `origin/main` after fetching the remote.
2. Packages only the committed `HEAD` revision with `git archive`; ignored,
   untracked, and secret files cannot enter the release.
3. Transfers the package to `opc@168.107.18.16`.
4. Generates a persistent random console token when one does not exist.
5. Installs and starts `developer-os-console.service`.
6. Binds the service to `0.0.0.0:8080` in public read-only mode.
7. Opens `8080/tcp` in Oracle Linux `firewalld`.
8. Verifies `http://127.0.0.1:8080/healthz`.
9. Installs daily managed database backup and weekly PostgreSQL
   restore-verification timers.
10. Runs an initial memo, OA, Gaia, and bTest backup plus the applicable
    integrity or isolated restore tests.
11. Installs an hourly provider usage collector using the protected, Git-ignored
    `X:/Projects/DeveloperOS/.env` file and a dedicated Python environment.
12. Installs `developer-os-terminal.service` on `127.0.0.1:8022` without
    opening a firewall port.

OCI Network Security List or NSG rules must also permit the desired source
addresses to reach TCP port 8080.

## Database Recovery Protection

`developer-os-backup.timer` creates compressed full-cluster backups for the
`oa_db` and `gaia_db` containers every day. Those backups are retained for 14
days. It also creates one combined bTest backup containing a full dump of
`btest_db` and a selective dump of `btest-elliott-db`; all Elliott schemas and
data are included except rows in `market.klines`, which can be downloaded again
from the market-data source. bTest backups are retained for 3 days because of
their larger size and the server's limited root disk.
Backups are stored under `/var/backups/developer-os` and are readable only by
root.

DeveloperOS memos live in
`/var/lib/developer-os-console/memos.sqlite3`, outside versioned release
directories. The same daily timer uses SQLite's online backup API, runs an
integrity check against the copy, and retains 14 days under
`/var/backups/developer-os/developer-os-memos`. Its result appears in Recovery
as `DeveloperOS memos`.

The Memo view reads and writes these four bounded records directly without a
separate token. Anyone who can reach the console address can view and edit
them; the rest of the private console APIs keep their existing authentication.

OA database backups preserve job, log, generated-file metadata, configuration,
and mapping knowledge. Files referenced by OA metadata under host-mounted
`storage` or output directories are not PostgreSQL data and require a separate
file-backup policy.

`developer-os-backup-verify.timer` starts temporary network-isolated
PostgreSQL containers each week and restores the latest backups into them.
For bTest it also verifies that the Kline table schema exists with no restored
rows and that the legacy bTest database and schema were restored. The
verification never connects to or writes into the production databases.

Manual checks remain available:

```powershell
make console-backup
make console-backup-verify
make console-backup-status
```

## Workstation Reporting

The Home and Office workstation reporters refresh the configured upstreams for
DeveloperOS, OA, Gaia, and bTest, then send separate small JSON summaries
through SSH to the Oracle server. Fetch updates Git metadata without changing
the checked-out branch, index, or working tree. Send a one-time report with:

```powershell
make workstation-home-report
make workstation-office-report
```

Or install the matching opt-in hidden Windows Scheduled Task once with
`make workstation-home-auto-enable` or
`make workstation-office-auto-enable`. The task runs every five minutes while
the registered Windows user session is active and does not require Codex. A
windowless Windows Script Host launcher starts the PowerShell reporter fully in
the background, avoiding a visible console flash at each trigger.

The public console does not expose local paths or the Windows hostname. A
report older than 15 minutes is displayed as offline. Run each report command
only from its matching computer. Local revisions are compared directly with
the server checkout and the running deployment image. Automatic reporting is
disabled until explicitly enabled on that workstation, and the scheduled
PowerShell process uses a hidden, non-interactive window.

When a report becomes offline, its revision values remain visible as historical
context, but GitHub and server comparisons are labeled stale and excluded from
the mismatch total until a fresh report arrives.

GitHub Match, Pull, Push, and Diverged states require a successful upstream
refresh in that same report run. A failed refresh leaves the workstation report
online but labels that repository `Refresh failed`; reports from an older
reporter without refresh proof are labeled `Unverified`.

## Provider Usage Collection

The public console never receives a provider credential. A separate hardened
oneshot service collects provider data and writes credential-free snapshots
under `/var/lib/developer-os-console`.

The browser console keeps the latest complete server inspection in memory for
60 seconds. Expired data is returned immediately while Git, Docker stats,
container image, disk, and backup inspection refresh in the background. The
roadmap payload is loaded only when its view is opened. This keeps page reloads
responsive without presenting partial project state.

OpenAI collection reads `OPENAI_ADMIN_API_KEY` and
`OPENAI_MONTHLY_BUDGET_USD`, calls the supported organization Costs API, and
writes `openai-usage.json` for protected internal reuse. The console does not
publish an OpenAI cost, budget, or prepaid-credit view. The supported OpenAI
API does not expose the Billing Credit Grants balance; users check prepaid
balance directly in the OpenAI Billing web console. The `$1.95` observation is
not stored or hard-coded.

Oracle Cloud collection uses the Compute instance principal rather than an OCI
API private key. It calls the Usage API for month-to-date cost and actual
Ampere A1 OCPU-hour and GB-hour consumption, then writes
`oracle-usage.json`. The console compares those quantities with Oracle's
public price list, which currently returns monthly A1 free quantities of 3,000
OCPU-hours and 18,000 GB-hours plus the billing-currency overage rates. Enable
it with this non-secret value in the same external environment file:

```text
DEVOS_OCI_ENABLED=1
```

Oracle usage is the only provider-usage view exposed in the browser console. It
is available from the `Oracle` navigation tab and `/oracle` route. OpenAI
Billing, prepaid credit, month-to-date cost, and monthly-limit views are not
user-facing.

Future DeveloperOS orchestration model calls use a separate project-level
credential contract. The canonical variables are
`OPENAI_ORCHESTRATION_API_KEY` and `OPENAI_ORCHESTRATION_PROJECT_ID`.
`OPENAI_ADMIN_API_KEY` remains limited to the Costs API collector. No live
orchestration call is permitted until the user provisions the canonical key in
the Git-ignored `X:/Projects/DeveloperOS/.env`; tracked repository files do not store or validate
the secret value.

### Orchestration Phase 1A

Phase 1A is local-only. It provides versioned orchestration state, strict
review-output and Gate validation, mock reviewer injection, Decimal pricing and
preflight estimation, historical fixture evidence hashing, immutable local run
artifacts, and manual-comparison packet scaffolding. The default path performs
zero network calls, never dispatches a generated instruction, and never edits
bTest. The live OpenAI adapter is intentionally disabled until a later,
explicitly approved phase.

Run the focused checks with:

```powershell
make orchestration-test
```

The local CLI exposes only bounded preparation commands:

```powershell
python -m console.devos_orchestration credential-status
python -m console.devos_orchestration fixture-discover --root X:/Projects/bTest
```

### Cycle Handoff capture

The canonical fixture source is an immutable Cycle Handoff packet for the
`MAINLINE_CODEX_REVIEW` lane. A capture source supplies exact message records
with global sequence, session and message identifiers, source context, role,
cycle ID, and unmodified string content. Selection is explicit: one MAINLINE
task, zero or more applied user decisions, one CODEX report, and the immediately
following MAINLINE manual review.

```powershell
python -m console.devos_orchestration cycle-capture `
  --messages-file X:/cycle-message-capture.json `
  --project bTest `
  --cycle-id <cycle-id> `
  --task-message-id <task-message-id> `
  --report-message-id <report-message-id> `
  --manual-review-message-id <review-message-id> `
  --user-decision-message-id <optional-decision-id> `
  --output X:/cycle-handoff-v1.json

python -m console.devos_orchestration cycle-verify `
  --packet X:/cycle-handoff-v1.json
```

The packet seals exact content, ordered message metadata, source sessions, and
its own canonical SHA-256. It defaults to `approved_for_external_api=false`.
Reviewer input contains only task, explicitly selected intermediate user
decisions, and report. The manual review remains local-comparison-only;
FUTURE_DESIGN and unrelated messages cannot be selected implicitly. Existing
packets are never overwritten. A changed capture creates a separate revision
that identifies the superseded packet.

The three-file `fixture-import` command remains a legacy/manual fallback.
Equivalence with a packet can be checked without changing either artifact:

```powershell
python -m console.devos_orchestration cycle-legacy-equivalence `
  --packet X:/cycle-handoff-v1.json `
  --task-file X:/01_codex_task.txt `
  --report-file X:/02_codex_report.txt `
  --baseline-file X:/03_manual_mainline_review.txt `
  --project bTest --historical-date 2026-08-14
```

When and only when the exact remote ChatGPT source is confirmed blocked, the
user may explicitly supply the unmodified Mainline manual-review text through
the temporary `cycle-capture-user-assisted` command. The resulting immutable
packet uses `capture_mode=USER_ASSISTED_EXACT_CAPTURE`, records
`source_retrieval_status=REMOTE_SOURCE_BLOCKED`, and derives its manual-review
identifier from the exact UTF-8 content hash. It does not search similar or
adjacent messages, select the latest message, or invoke the legacy importer.
The manual review remains local-comparison-only. A later recovered exact remote
message can be compared by content hash without modifying the sealed packet;
direct Session Handoff retrieval remains the canonical first choice.

### Synthetic routing evidence

Synthetic Gate cases live under
`console/devos_orchestration/synthetic_fixtures/` and are always labeled
`SYNTHETIC_ROUTING_EVIDENCE`. They test deterministic routing contracts without
claiming historical validation or making a model call:

```powershell
python -m console.devos_orchestration synthetic-routing-suite
```

The suite covers threshold, authority, architecture, scope, and destructive
migration decisions plus SAFE_CONTINUE, BLOCKED, and STOP controls. A synthetic
PASS is never reported as `REAL_WORLD_EVIDENCE`.

After a real direct Session Handoff capture and its manual review, the local
candidate classifier can mark an unambiguous USER_REQUIRED cycle for later
user-approved holdout preparation:

```powershell
python -m console.devos_orchestration cycle-user-required-candidate `
  --packet X:/cycle-handoff.json `
  --manual-review-gate USER_REQUIRED `
  --decision-kind AUTHORITY
```

Only direct non-legacy, non-synthetic `MAINLINE_CODEX_REVIEW` packets classified
as `REAL_WORLD_EVIDENCE` can set `genuine_user_required_candidate=true`.
Candidate marking never calls an API or starts a holdout automatically.

### Codex App Server transport boundary

The Phase 2B adapter uses the authenticated Linux-native Codex CLI in Ubuntu
WSL as its orchestration-only runtime. Windows starts it through
`wsl.exe -d Ubuntu -- /home/devops/.local/bin/codex app-server`; the Windows
Store executable is not a transport candidate. The adapter discovers the
installed schema with `codex app-server generate-json-schema --experimental`,
declares the generated `experimentalApi` initialize capability, and verifies
the exact thread, turn, event, and approval methods before reporting support.
The office implementation is currently bound to `codex-cli 0.147.0`; future
versions are checked from their generated schema rather than assumed to share
that contract.

CODEX_THREAD references are backend-only JSON objects. Existing thread
bindings contain `thread_id` and an absolute workspace; a project worker may
instead use a workspace-only binding before any orchestration thread exists.
That binding seals the Windows/WSL path mapping plus Git branch, HEAD, and
status fingerprints. The console reports the development client, WSL runtime,
binding, protocol, capability, dispatch lock, and external-change guard without
returning a thread identifier. A future turn must reject a changed fingerprint
as `WORKSPACE_CHANGED_EXTERNALLY`, and only one DeveloperOS turn may hold a
workspace lease at once. These guards do not lock the Codex Desktop client.

A route to a bound CODEX_THREAD node can create a Dispatch Preview. A
workspace-only worker is reverified against its sealed Git state before the
preview is written; any branch, HEAD, status, path, or identity change fails as
`WORKSPACE_CHANGED_EXTERNALLY`. Its immutable envelope binds the route and
logical nodes, Windows/WSL workspace mapping, Git state, discovered runtime
protocol, and task. `task_content_sha256` hashes the exact task text,
`payload_sha256` hashes the rendered logical handoff, and `envelope_sha256`
hashes the complete dispatch contract. The exactly-once ledger stops at
PREPARED until an authenticated user explicitly approves or rejects it.
Approval reverifies the artifact, route, destination, workspace Git seal, and
runtime protocol before writing a separate immutable record bound to all of
those values. Its ledger history becomes PREPARED, APPROVED, DISPATCHABLE;
rejection becomes terminal REJECTED and requires a new envelope. The console
shows the task and binding summary with Approve and Reject controls. Automatic
send remains locked in SHADOW_REVIEW and SEMI_AUTO. The bounded one-shot Codex
dispatch runner is the only live path: it consumes a newly approved envelope by
writing an immutable ATTEMPT_STARTED record before transport, permits one WSL
thread and turn with no retry or fallback, captures a terminal result, and
rechecks the workspace seal. It does not return the result to Mainline or start
another cycle. Raw thread and turn identifiers remain backend-only.

Completed Codex output can be sealed into one immutable return envelope for a
validated CODEX_WORKER-to-MAINLINE REPORT route. The envelope binds the source
dispatch and result artifact, exact result-content hash, originating task,
workspace seal, and runtime protocol. Duplicate envelopes for the same result
are rejected. CHATGPT_SESSION read, write, and resume remain unsupported, so
the current bTest return stops at USER_ASSISTED_EXACT_DELIVERY_CANDIDATE. The
console exposes only capture, destination, capability, and envelope status;
there is no Mainline send or automatic fallback path.

The user-assisted exact-delivery layer can create one immutable packet per
return envelope. Its authenticated console controls copy only the sealed Codex
result, then record PREPARED to COPIED to DELIVERED, or a terminal CANCELLED
decision. Copy, delivery, and cancellation records bind the packet, result
hash, and BTEST_MAINLINE destination. Native Mainline write, browser
automation, session impersonation, and automatic fallback remain absent.

The bTest control plane also registers a managed `BTEST_MAINLINE_API` node.
OFF keeps `NATIVE_MAINLINE` as the native canonical authority; any enabled mode
makes the API node canonical and rejects native routes or results as inactive.
DeveloperOS canonical Mainline state is separate from private OpenAI
conversation linkage. The UI exposes only initialization status, current Gate,
current destination, and locked READ/WRITE/RESUME capability status. No live
API call or conversation creation is enabled by this model.

The CLI prints only boolean credential presence and fixture metadata. It never
prints secret values. A sealed Cycle Handoff packet is the canonical fixture
boundary. The historical task/report/baseline file triplet is accepted only as
a legacy/manual fallback and does not replace packet approval.

Usage and cost are queried through the latest completed UTC day. The console
linearly projects those observations across the number of days in the current
month. Projected A1 overage is priced with Oracle's public rate, and the larger
of that estimate or the current total-cost run rate is shown. The projection is
an operational estimate, not an Oracle forecast or invoice. Account service
limits and additional paid capacity are intentionally not displayed. The
collector obtains tenancy and region from the instance;
`OCI_TENANCY_OCID` and `OCI_REGION` are optional troubleshooting overrides.

The instance must belong to an OCI dynamic group with these tenancy policies:

```text
Allow dynamic-group DeveloperOSUsageCollectors to read usage-report in tenancy
```

The source environment file is kept outside Git at
`X:/Projects/DeveloperOS/.env`. Deployment transfers it separately from
the Git release, filtering the server payload to `OPENAI_ADMIN_API_KEY` and
`OPENAI_MONTHLY_BUDGET_USD` before installing it with restricted permissions. The refresh runs
once during deployment and then hourly through
`developer-os-openai-usage.timer`.

Inspect the collector without displaying its key:

```powershell
make console-usage-status
```

On Windows this command checks the server through the configured SSH wrapper.
Inside the DeveloperOS server checkout on Linux, the same target reads the
local systemd timer, service log, and snapshot presence directly.

## Private Server Terminal

Start the Home SSH tunnel immediately when it is needed:

```powershell
make terminal-tunnel
```

Open a project:

```powershell
make terminal-developer-os
make terminal-oa
make terminal-gaia
```

The tunnel maps Home `127.0.0.1:8092` to server `127.0.0.1:8022`. The public
project view links to this Home-only address. The terminal service opens an
actual Linux PTY running Bash in the selected allowlisted project directory as
`opc`. ANSI applications and interactive keyboard input work through the
bundled xterm.js client, including `nano`, search, save, exit, passwordless
interactive tools, and terminal resize. PTY session open and close metadata are
audited without recording typed commands or terminal contents.

Selected terminal text can be copied with the `Copy` button,
`Ctrl+Shift+C`, or `Ctrl+Insert`. Clipboard text can be pasted with the `Paste`
button, `Ctrl+Shift+V`, or `Shift+Insert`. Plain `Ctrl+C` remains the normal
Linux interrupt signal.

When Home automatic reporting is enabled, the same hidden task checks the
tunnel every five minutes and restores it after login or a dropped SSH
connection. Tunnel failure is logged separately and does not prevent the Git
status report from being uploaded. Office reporting never creates this tunnel.

The browser terminal is a persistent shell session rather than a sequence of
isolated command requests. Switching the project tab closes the previous PTY
and opens a new one at the selected project path. The shell has the permissions
of `opc`; it does not provide root access or expose the terminal service secret
inside the shell environment.

Inspect the private service:

```powershell
make terminal-status
make terminal-logs
```
