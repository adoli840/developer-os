# Workstation Git Reporting

Workstation reporting keeps local repository state separate by computer. Each
computer reports only its own state while it is powered on.

The Home installation:

```powershell
make workstation-home-install
```

It creates a current-user Windows Scheduled Task named
`DeveloperOS-Home-Git-Reporter`. The task runs every five minutes while the
current user session is available. It reads Git metadata only and uploads the
resulting JSON through the existing SSH connection to the Oracle server.

The server compares each local revision with both its repository checkout and
the running deployment revision. This avoids relying only on potentially stale
remote-tracking refs.

Manual reporting:

```powershell
make workstation-home-report
```

Office reporting is deliberately excluded from this installation. It should
be added and installed from the Office computer after its real workspace
layout is available.

## Home Server Terminal Tunnel

The Home computer can keep a private local forward to the Oracle server:

```powershell
make terminal-tunnel-install
```

The scheduled task `DeveloperOS-Home-Server-Terminal-Tunnel` checks the tunnel
every five minutes. It maps `127.0.0.1:8092` on Home to the server-only
terminal at `127.0.0.1:8022`.

No public terminal port is opened. The tunnel requires the existing
`X:/Settings/ssh/ssh-key-ops.key`, and the browser endpoint is available only
while that authenticated SSH connection is alive.
