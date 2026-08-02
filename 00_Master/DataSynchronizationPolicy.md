# Project Data Synchronization Policy

## Purpose

This policy defines how projects compare and transfer non-source state between
workstations, servers, and durable artifact stores without placing that state in
Git.

It applies to datasets, learning observations, replay shards, generated
artifacts, model bundles, checkpoints, and selected database records. It does
not turn DeveloperOS into the owner of project data.

## Core Decision

Source synchronization and data synchronization are separate systems.

- Git owns source code, reviewed configuration, migrations, and documentation.
- A project-owned synchronization contract owns non-source transfer behavior.
- Backups protect recovery; synchronization distributes state. One does not
  replace the other.
- Model promotion and production deployment remain explicit operations after
  synchronization.

## Data Classes

| Class | Examples | Default Synchronization Model |
|---|---|---|
| Source | Code, migrations, documentation | Git only |
| Merge-safe records | Immutable games, observations, replay shards | Bidirectional set union when every merge requirement is met |
| Authoritative mutable state | Active model, learner checkpoint, aggregate table | One authoritative writer and directed pull or push |
| Published artifacts | Reviewed model bundle, benchmark package | Immutable versioned publication from an authority |
| Transactional production state | Accounts, rooms, messages, live game state | Production remains authoritative; use backup or explicit migration |
| Derived cache | Build output, indexes, temporary batches | Recreate; do not synchronize |
| Secrets | Keys, tokens, credentials | Never synchronize through project data tooling |

## Merge-Safe Bidirectional Synchronization

A globally unique ID is necessary but not sufficient. Bidirectional transfer is
allowed only when a synchronization set has all of these properties:

1. Every record or artifact has a stable globally unique identity.
2. The payload is immutable after creation.
3. The payload has a cryptographic content checksum.
4. Re-importing the same identity and checksum is idempotent.
5. The same identity with a different checksum is a hard conflict, never an
   overwrite.
6. Deletion is either prohibited or represented by an explicit immutable
   tombstone with a defined retention rule.
7. Schema and producer versions are recorded and validated before import.
8. Referential dependencies are transferred or verified as one consistent
   unit.

When these conditions hold, synchronization is a set-union operation:

```text
local missing  = remote identities - local identities
remote missing = local identities - remote identities
merged state   = local identities union remote identities
```

A UUID identifies a record. A checksum proves that both locations agree about
its content. Both are required.

## Directed Synchronization

Mutable state must declare one authority for each synchronization set.

Use one of these modes:

- `pull-mirror`: the local copy follows a remote authority.
- `push-publish`: a reviewed local artifact is published to a remote authority.
- `bidirectional-union`: both sides contribute immutable merge-safe records.
- `export-import`: a bounded database transfer with validation and recovery.
- `none`: state is local, ephemeral, sensitive, or reproducible.

Do not use automatic last-write-wins merging for databases, models, aggregate
tables, or checkpoints. Timestamps alone are not conflict resolution because
clocks drift and concurrent updates can both be valid.

## Database Synchronization Selection

Database synchronization is opt-in and project-owned.

The global default is `synchronize nothing`. DeveloperOS must never infer that
an entire database, every table, or every row should move merely because a
project enables one synchronization set.

Each project decides which database state is worth transferring through an
explicit allowlist in its project-owned contract. The allowlist must identify a
logical synchronization set rather than rely on a broad database name. A set
may select:

- One or more named tables
- A stable query or export view
- A partition, tenant, model version, time window, or other bounded row filter
- Required referenced rows that form the declared dependency closure

Everything not selected is excluded. An explicit exclusion list is recommended
for large, sensitive, operational, or easily reconstructed tables so future
maintainers do not accidentally broaden the scope.

Prefer excluding database state when it is:

- Cheap or deterministic to download, regenerate, or rebuild
- A cache, index, materialized aggregate, or temporary queue
- Large relative to its recovery or reuse value
- Production-only transactional state
- Sensitive or outside the receiving location's authorization boundary
- Missing stable identities, immutable payloads, or a safe authority rule

The selection contract must also define:

- Database and schema names at a logical level
- Included tables, views, or export queries
- Row scope and dependency closure
- Explicit exclusions
- Stable primary identity and content checksum
- Merge mode or authoritative direction
- Schema compatibility check
- Import transaction and rollback behavior
- Sequence handling when generated numeric keys are involved

Foreign-key relationships do not automatically authorize additional tables.
The project must either include the required dependency closure explicitly or
reject records whose dependencies are unavailable.

Whole-database dumps remain appropriate for backup, disaster recovery, and
bounded migration. They are not the default routine synchronization format.
Routine synchronization should export only the allowlisted logical sets.

## Project-Owned Contract

A project that needs non-source synchronization must own a `DATA_SYNC.md` file
or an equivalent explicit specification. Projects that do not synchronize data
must not add an empty contract merely for uniformity.

Each synchronization set must declare:

- Purpose and data class
- Authoritative location or merge-safe status
- Local and remote logical stores without credentials
- Direction
- Identity and checksum format
- Schema or producer version
- Conflict and deletion policy
- Pre-transfer consistency requirement
- Verification and rollback procedure
- Retention policy

For database synchronization, the contract must additionally declare the exact
allowlisted tables or export query, row scope, dependency closure, and explicit
exclusions. A database object omitted from the allowlist is not synchronized.

DeveloperOS owns this policy and the blueprint. The project owns its current
stores, identifiers, commands, and operational state.

## Command Contract

Projects may expose these project-owned commands when synchronization is
implemented:

```text
make sync-status   Compare manifests without changing either side
make sync-plan     Show exact uploads, downloads, conflicts, and skipped data
make sync-pull     Download only data allowed by the declared direction
make sync-push     Upload only data allowed by the declared direction
make sync-verify   Recompute identities and checksums after transfer
```

DeveloperOS reserves `make sync` as a convenience facade with one fixed
meaning: publish the project-approved local data set to the server. It may only
delegate to an explicitly configured project-owned `sync-push` implementation.
When no implementation is configured, it must report that synchronization was
skipped and change nothing. It must never infer a whole database, reverse the
direction, or perform a bidirectional merge.

Status and plan operations must be read-only. Project-owned push and pull
commands must identify their direction in both the command and output. The
shared `make deploy` command may invoke `make sync` after deployment only when
the project explicitly opts into `after-deploy` synchronization; the default
is no deployment-time data transfer.

## Transfer Safety

- Default to dry-run and disable remote deletion.
- Write downloads to a temporary location, verify them, then publish atomically.
- Never copy a live PostgreSQL data directory or Docker volume between hosts.
- For occasional database movement, use a logical export/import or a
  project-owned record exporter with schema validation.
- Stop or coordinate writers when a consistent database snapshot is required.
- Create and verify a recovery point before replacing authoritative mutable
  state.
- Reject incompatible schema, producer, model, or protocol versions.
- Record counts, bytes, manifest identity, checksum results, direction, and
  completion time without recording credentials or sensitive payloads.
- Treat a transfer interruption as incomplete until verification succeeds.

## Learning Data Pattern

For AI or simulation training, prefer this separation:

```text
Immutable observations and replay shards
  -> merge-safe bidirectional union when the contract proves it

Derived aggregates and indexes
  -> rebuild from immutable inputs

Learner checkpoints
  -> one writer; directed recovery copies only

Reviewed model bundles
  -> immutable, checksummed, versioned publication

Production activation
  -> separate approval, deployment, monitoring, and rollback
```

Synchronization may make an artifact available at another location. It must not
silently make that artifact active in production.

## Technology Guidance

Choose tools by data semantics rather than using one tool for every class:

- Object storage synchronization is the default for large immutable files and
  reviewed bundles.
- DVC is appropriate when datasets need versions tied to source revisions while
  the data itself remains in remote storage.
- MLflow or an equivalent registry is appropriate when experiment metadata,
  metrics, model lineage, and reviewed artifacts need a dedicated lifecycle.
- PostgreSQL logical replication is appropriate only for a deliberately
  designed continuous directional database flow. It is not the default for
  workstation-to-production exchange.
- Logical dumps or project-owned exports are preferred for occasional bounded
  database transfers.

No technology choice removes the need for identity, authority, conflict,
verification, and recovery rules.

## Console Visibility

DeveloperOS may display derived synchronization evidence, but it must not store
project data or become a transfer proxy. A project may report:

- Synchronization set name and mode
- Authority or merge-safe classification
- Local-only and remote-only item counts
- Conflict count
- Last verified manifest identity and time
- Last transfer direction and result

Credentials, paths, payloads, and unrestricted transfer controls must not be
exposed on the public console.

## Adoption Sequence

1. Inventory non-source state.
2. Keep every database object excluded until a project explicitly selects it.
3. Classify each selected set as merge-safe, authoritative, published, ephemeral, or
   secret.
4. Write the project-owned synchronization contract.
5. Implement manifest generation and read-only status comparison.
6. Verify conflicts and recovery behavior with disposable data.
7. Add explicit pull and push operations.
8. Automate only after repeated manual transfers are deterministic and safe.
