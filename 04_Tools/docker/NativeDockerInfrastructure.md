# Shared Native Docker Infrastructure

Docker Desktop VHD deletion-readiness evidence is maintained separately in
`DesktopVhdForensicInventory.md`. Native runtime independence does not itself
authorize deletion of the Desktop VHD or its assets.

## Ownership

DeveloperOS owns the local native Docker boundary shared by bTest, OA, and
Gaia. Project repositories own their Compose files, service definitions,
project lifecycle commands, data rules, and remote deployment behavior. They
must not install, replace, or independently restart the shared local daemon or
change its socket, data root, credential store, CLI, or Compose plugin.

## Canonical Local Boundary

The local Windows-to-Linux execution chain is fixed:

```text
Windows project command
  -> X:/Projects/DeveloperOS/04_Tools/bin/devos-native-docker.cmd
  -> Python argument-array launcher
  -> wsl.exe -d Ubuntu --cd <mapped project directory>
  -> DOCKER_HOST=unix:///run/docker-wsl.sock
  -> DOCKER_CONFIG=/home/devops/.docker-native
  -> /usr/bin/docker
     or /usr/libexec/docker/cli-plugins/docker-compose
```

The launcher rejects `--host`, `--context`, and `--config` overrides and
context mutations. It removes ambient context and TLS-selection variables and
preserves the working directory, argument ordering, standard streams, and
process exit code. A `compose` first argument is routed directly to the
packaged native Compose binary; all other commands use the packaged Docker CLI.

Windows tools that require a command literally named `docker` may opt in for
one process by prepending
`X:/Projects/DeveloperOS/04_Tools/docker/windows-cli` to `PATH`. Its
`docker.cmd` shim delegates every argument to the canonical launcher above. Do
not add this directory to machine-wide `PATH`; process-local use keeps command
resolution explicit and prevents unrelated tools from silently changing Docker
authority.

Canonical native assets:

- Ubuntu WSL2 distribution
- Docker CLI `/usr/bin/docker` (29.7.2 at sealing time)
- Compose `/usr/libexec/docker/cli-plugins/docker-compose` (5.4.0)
- systemd unit `docker-wsl.service`
- socket `unix:///run/docker-wsl.sock`
- data root `/var/lib/docker-wsl`
- config `/home/devops/.docker-native/config.json`

Windows Docker contexts and the user's ambient `~/.docker/config.json` are not
authorities for local project commands.

## Desktop Symlink Removal Record

The initial 2026-08-15 seal removed these unowned `root:root:777` symlinks from
`/usr/local/lib/docker/cli-plugins`: `docker-agent`, `docker-ai`,
`docker-buildx`, `docker-compose`, `docker-debug`, `docker-desktop`,
`docker-dhi`, `docker-extension`, `docker-init`, `docker-mcp`, `docker-model`,
`docker-offload`, `docker-pass`, `docker-sandbox`, and `docker-scout`.

Every link targeted the `/mnt/wsl/docker-desktop/` tree and `dpkg-query`
reported it as unowned. The first audit's per-link target strings were lost
when an idempotency check overwrote the latest audit snapshot; they are not
reconstructed by inference. Audit schema 2 appends every future run to
`.console/native-docker-infrastructure-audit.jsonl` before updating the latest
snapshot. The native Docker CLI, Compose and Buildx plugins, daemon socket, and
data root were retained.

## Credentials

The canonical local config contains only `credsStore=pass`. The existing
`docker-credential-pass`, GPG secret key, and initialized password store are
reused. No registry entry existed when this boundary was sealed; a future
interactive `login` through the shared launcher will store credentials in the
native helper without exposing them to project scripts.

Remote servers use server-local, least-privilege registry credentials. Local
credential files, Desktop helpers, tokens, and passwords must never be read by
a deployment script and forwarded to a server. Remote `ssh` scripts continue
to run the server's own Docker CLI and must not be rewritten to call the local
WSL launcher.

## Project Integration Contract

Each project performs a repository-scoped migration after this shared boundary
is available:

1. Remove project-local `DEVOS_DOCKER` overrides and use the shared Make
   default, or explicitly set it to
   `X:/Projects/DeveloperOS/04_Tools/bin/devos-native-docker.cmd`.
2. Replace local Windows wrappers and direct local `docker` or
   `docker compose` calls with the shared launcher. Preserve working directory,
   arguments, no-build policy, output, and exit status.
3. Keep remote deployment commands unchanged when they run Docker after SSH on
   the remote host.
4. Do not copy the shared launcher, config, socket policy, or credential helper
   into a project repository.
5. Verify project Compose config, existing-image startup with `--no-build`,
   health checks, database connectivity, volume identities, and Git cleanliness
   through the shared launcher before reopening that project's Desktop deletion
   gate.

Current integration status at sealing time:

- bTest shared Make targets inherit the DeveloperOS launcher, but direct local
  Docker calls still require project audit.
- OA overrides `DEVOS_DOCKER` with `scripts/docker_native.py`; it must converge
  on the shared launcher while retaining remote-only commands.
- Gaia overrides `DEVOS_DOCKER` with `scripts/docker-native.cmd`; it must
  converge on the shared launcher while retaining remote-only commands.

## Independent Project Runtime Policy

The shared daemon is a prerequisite, not a project orchestrator. OA, Gaia,
bTest-Elliott, and bTest-Ever may independently start and stop their own
development runtime without a per-operation DeveloperOS approval.

- `docker-wsl.service start` and the idempotent `ensure-running` operation are
  pre-approved shared infrastructure prerequisites.
- A project may ensure the daemon is running and then start only its own
  Compose project or explicitly selected services with `--no-build`.
- A project must not stop or restart the daemon. Those operations can affect
  every project and remain DeveloperOS/user-authorized operations.
- Prune, global volume or network deletion, daemon configuration changes, and
  cross-project volume operations remain approval-bound.
- Local development Compose services must use `restart: "no"` (or omit a
  restart policy). Production and remote deployment policies remain owned by
  the project and are not changed by this local rule.

The invariant is:

```text
daemon start != project runtime start
```

Daemon startup must not implicitly start OA, Gaia, bTest-Elliott, or
bTest-Ever containers. The operating system and project agents must audit
systemd/project auto-start units, Compose startup hooks, `restart:` policies,
scheduled tasks, and supervisor configurations to remove such side effects.

Each project owns an explicit Compose namespace and its lifecycle commands
must be scoped to that namespace. `up`, `down`, `logs`, and service selection
must not use global container, network, or volume operations and must not
remove resources belonging to another namespace. Ever's development contract
is specifically: ensure the daemon is running, then start only the Ever
development runtime with `--no-build` on `127.0.0.1:8091`.

The migration and policy checks must prove, without deleting or migrating
existing data:

1. daemon-only start leaves all project runtimes stopped;
2. each project's start creates or starts only its own services;
3. each project's stop removes or stops only its own services/resources; and
4. the other project namespaces have zero state change.

Project repositories remain responsible for applying the local `restart: "no"`
and namespace changes in their own Compose files. DeveloperOS defines and
verifies the shared boundary; it does not copy project Compose files into this
repository.

## Operations

```powershell
make native-docker-audit
make native-docker-seal
make native-docker-test
make native-docker-check
```

Only DeveloperOS coordinates `docker-wsl.service` restart. Before a restart it
must record bTest, OA, and Gaia container health and prove that no migration,
seed, reset, volume replacement, or data write is part of the operation. If all
runtimes are healthy and no daemon configuration changed, do not restart.

The seal removes only unowned `docker-*` symlinks under
`/usr/local/lib/docker/cli-plugins` whose targets are inside the Docker Desktop
WSL mount. It does not uninstall Docker Desktop, unregister a distribution,
delete a VHD, prune Docker state, or modify native images, volumes, networks,
containers, the socket, data root, CLI, or Compose package.
