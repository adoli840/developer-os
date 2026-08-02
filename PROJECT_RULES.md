# DeveloperOS Project Rules

These rules record narrow self-application boundaries. Every DeveloperOS policy
not listed here applies to this repository itself.

## Docker Lifecycle Exclusion

The shared `make run`, `make b-run`, `make down`, Docker Hub image, and generic
container deployment targets apply to Docker Compose application projects.
DeveloperOS has no root Compose application and must not add one only to imitate
other projects.

Use `make console-run`, `make console-test`, and the specialized console service
commands instead. If DeveloperOS intentionally gains a root Compose application
later, this exclusion must be reviewed.

The Docker image build minimization policy still applies. Because the console
runs directly under Python and systemd, DeveloperOS satisfies it with zero
routine image builds. Its deployment path must not add a Docker build unless a
real container application is introduced and this exception is reviewed.

## PostgreSQL Backup Exclusion

DeveloperOS owns no application PostgreSQL database. Its source and durable
policy are preserved by Git; console runtime snapshots, workstation reports,
usage snapshots, and logs are derived operational state. Keep
`backup_expected=false` for DeveloperOS and do not create an empty database only
for backup parity.

Secrets and machine-specific environment files remain outside Git and follow
their own workstation or server recovery procedures.

## Deployment Path Exclusion

The generic Docker project workflow generator in `deployment/projects.yml` is
not the DeveloperOS deployment source. DeveloperOS uses
`deployment/console/Manage-DeveloperOSConsole.ps1` and the `console-*` Make
targets because its server runtime is a specialized systemd deployment.

The shared `make deploy` facade delegates to `console-deploy`. DeveloperOS has
no data synchronization target, so `make sync` and post-deployment sync are
explicit no-ops.

The same clean-branch, pushed-revision, verification, and audit expectations
still apply.

## Document Location Exclusion

Do not create duplicate root `TODO.md` or `Decisions.md` files. DeveloperOS owns
those records in `00_Master/Backlog.md` and `00_Master/Decisions.md`.
