# Manual Workstation Git Reporting

Workstation reporting keeps local repository state separate by computer. Each
computer reports only its own state while it is powered on.

DeveloperOS does not install a Windows Scheduled Task. Run the matching command
on each computer when a fresh comparison is needed:

```powershell
make workstation-home-report
make workstation-office-report
```

The server compares each local revision with both its repository checkout and
the running deployment revision. This avoids relying only on potentially stale
remote-tracking refs.
Run each report only from its matching computer so Home and Office remain
separate sources of local repository state.

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
