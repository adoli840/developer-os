# Workstation Git Reporting

Workstation reporting keeps local repository state separate by computer. Each
computer reports only its own state while it is powered on.

Run the matching command on each computer when a one-time fresh comparison is
needed:

```powershell
make workstation-home-report
make workstation-office-report
```

For automatic reporting, install the matching hidden Windows Scheduled Task
once:

```powershell
make workstation-home-auto-enable
make workstation-office-auto-enable
```

The task runs every five minutes under the current Windows user with least
privilege. It starts the existing reporter with no profile, no interactive
input, and a hidden PowerShell window. Windows supplies only the periodic
trigger; DeveloperOS owns the report contents, SSH transfer, logging, and task
management. Codex is not involved after installation.

Inspect or remove the matching task with:

```powershell
make workstation-home-auto-status
make workstation-home-auto-disable
make workstation-office-auto-status
make workstation-office-auto-disable
```

The server compares each local revision with both its repository checkout and
the running deployment revision. This avoids relying only on potentially stale
remote-tracking refs.
Run each report only from its matching computer so Home and Office remain
separate sources of local repository state. Do not install both scheduled
identities on one computer. A task runs only while its registered Windows user
has an active session; the console marks the preserved report offline after 15
minutes without a successful upload.

## Home Server Terminal Tunnel

The Home computer can start a private local forward to the Oracle server:

```powershell
make terminal-tunnel
```

The command maps `127.0.0.1:8092` on Home to the server-only terminal at
`127.0.0.1:8022`. It runs only when explicitly requested; no scheduled tunnel
maintenance is installed.

No public terminal port is opened. The tunnel requires the existing
`X:/Settings/ssh/ssh-key-ops.key`, and the browser endpoint is available only
while that authenticated SSH connection is alive.
