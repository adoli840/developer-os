# DeveloperOS Browser Console

## Purpose

The browser console is a live operational view of the workspace. It does not
store project roadmaps, duplicate project documentation, or become the source
of truth for project state.

The console reads:

- Git working-tree and upstream status from project repositories.
- Docker Compose container state.
- Repository HEAD compared with running Docker image revisions.
- End-of-work checks for uncommitted and unpushed changes.
- Home-computer Git status reported over SSH while that computer is online.
- Oracle Linux CPU, memory, disk, uptime, and Docker health.
- Daily database backup and weekly isolated restore-verification status.
- Local actionable alerts for delivery and recovery conditions.
- An optional local OpenAI cost snapshot.
- A local audit log for allowlisted management commands.

## Security Model

- Production requires `DEVOS_CONSOLE_TOKEN`.
- Browser mutations require an authenticated session and CSRF token.
- The public console never accepts arbitrary shell input.
- Only fixed `git pull --ff-only`, Compose start, restart, and stop actions are
  available on the authenticated console API.
- The direct public HTTP deployment uses `DEVOS_PUBLIC_READ_ONLY=1`; it hides
  project paths and audit history and disables login and commands.
- A separate command console binds to server loopback only and is reachable
  through an SSH local-forward from a trusted workstation.

## Local Development

```powershell
make console-run
```

Open `http://127.0.0.1:8080`. Development mode does not require an access token.

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
10. Runs an initial OA and Gaia backup and isolated restore test.
11. Installs `developer-os-terminal.service` on `127.0.0.1:8022` without
    opening a firewall port.

OCI Network Security List or NSG rules must also permit the desired source
addresses to reach TCP port 8080.

## Database Recovery Protection

`developer-os-backup.timer` creates compressed `pg_dumpall` backups for the
`oa_db` and `gaia_db` containers every day. Backups are stored under
`/var/backups/developer-os`, readable only by root, and retained for 14 days.

`developer-os-backup-verify.timer` starts temporary network-isolated
PostgreSQL containers each week and restores the latest backups into them.
The verification never connects to or writes into the production databases.

Manual checks remain available:

```powershell
make console-backup
make console-backup-verify
make console-backup-status
```

## Home Workstation Reporting

The Home workstation reporter executes read-only Git commands for
DeveloperOS, OA, Gaia, and bTest. It sends a small JSON summary through SSH to
the Oracle server every five minutes while the current Windows user session is
available.

```powershell
make workstation-home-install
make workstation-home-report
```

The public console does not expose local paths or the Windows hostname. A
report older than 15 minutes is displayed as offline. Office is not registered
by the Home installation. Local revisions are compared directly with the
server checkout and the running deployment image.

## OpenAI Usage Snapshot

The console does not request or store an OpenAI API key. If another trusted
process later writes a JSON snapshot to
`.console/openai-usage.json`, the console displays it.

Use `console/openai-usage.example.json` as the schema.

## Private Server Terminal

Install the Home SSH tunnel task once:

```powershell
make terminal-tunnel-install
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

This is a command-oriented shell rather than a full PTY. Interactive programs
such as editors, password prompts, and `top` are not supported. Commands that
work without an interactive prompt, including Git, Make, Docker, and Compose,
run normally with the permissions of `opc`.

Inspect the private service:

```powershell
make terminal-status
make terminal-logs
```
