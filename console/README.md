# DeveloperOS Browser Console

## Purpose

The browser console is a live operational view of the workspace. It does not
store project roadmaps, duplicate project documentation, or become the source
of truth for project state. `/roadmap` derives a read-only standard view from
project-owned root `ROADMAP.md` files.

The console reads:

- Git working-tree and upstream status from project repositories.
- Docker Compose container state.
- Repository HEAD compared with running Docker image revisions.
- End-of-work checks for uncommitted and unpushed changes.
- Home-computer Git status reported over SSH while that computer is online.
- Oracle Linux CPU, memory, disk, uptime, and Docker health.
- Daily database backup and weekly isolated restore-verification status.
- Local actionable alerts for delivery and recovery conditions.
- Optional local OpenAI and Oracle Cloud usage snapshots.
- A local audit log for allowlisted management commands.
- Standard roadmap fields for configured projects, without raw files or source
  paths.

## Security Model

- Production requires `DEVOS_CONSOLE_TOKEN`.
- Browser mutations require an authenticated session and CSRF token.
- The public console never accepts arbitrary shell input.
- Only fixed `git pull --ff-only`, Compose start, restart, and stop actions are
  available on the authenticated console API.
- The direct public HTTP deployment uses `DEVOS_PUBLIC_READ_ONLY=1`; it hides
  project paths and audit history and disables login and commands.
- The public roadmap API returns only parsed standard fields. It does not return
  raw Markdown, source paths, or parser diagnostics.
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
9. Installs daily PostgreSQL backup and weekly restore-verification timers.
10. Runs an initial OA, Gaia, and bTest backup and isolated restore test.
11. Installs an hourly provider usage collector using the protected local
    `X:/Settings/env/developer-os.env` file and a dedicated Python environment.
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

## Home Workstation Reporting

The Home workstation reporter executes read-only Git commands for
DeveloperOS, OA, Gaia, and bTest. It sends a small JSON summary through SSH to
the Oracle server only when explicitly requested.

```powershell
make workstation-home-report
```

The public console does not expose local paths or the Windows hostname. A
report older than 15 minutes is displayed as offline. Office is not registered
from the Home computer. Local revisions are compared directly with the server
checkout and the running deployment image. No Windows Scheduled Task is
installed, so reporting never starts PowerShell periodically.

## Provider Usage Collection

The public console never receives a provider credential. A separate hardened
oneshot service collects provider data and writes credential-free snapshots
under `/var/lib/developer-os-console`.

OpenAI collection reads `OPENAI_ADMIN_API_KEY` and
`OPENAI_MONTHLY_BUDGET_USD`, calls the organization Costs API, and writes
`openai-usage.json`.

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

The source environment file remains outside every repository at
`X:/Settings/env/developer-os.env`. Deployment transfers it separately from
the Git release and installs it with restricted permissions. The refresh runs
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

Start the Home SSH tunnel explicitly when it is needed:

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
project view links to this Home-only address. The terminal service runs actual
Bash commands in the selected allowlisted project directory as `opc`, limits
each command to 120 seconds, caps returned output, and records only a command
hash and result metadata in its audit log.

DeveloperOS does not install a tunnel Scheduled Task. The tunnel remains a
manual, user-initiated process.

This is a command-oriented shell rather than a full PTY. Interactive programs
such as editors, password prompts, and `top` are not supported. Commands that
work without an interactive prompt, including Git, Make, Docker, and Compose,
run normally with the permissions of `opc`.

Inspect the private service:

```powershell
make terminal-status
make terminal-logs
```
