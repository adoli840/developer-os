# Project Data Synchronization Contract

Status: Disabled

This optional project-owned contract applies only when the project transfers
non-source state between locations. Follow
`X:\Projects\DeveloperOS\00_Master\DataSynchronizationPolicy.md`.

Delete this file when the project has no synchronization requirement.

## Purpose

Describe why synchronization is needed and which project workflow it supports.

## Synchronization Sets

| Sync Set | Data Class | Authority Or Merge Rule | Direction | Identity And Checksum | Schema Version | Conflict Policy |
|---|---|---|---|---|---|---|
| Example observations | Merge-safe records | Immutable set union | Bidirectional | UUID plus SHA-256 | example-v1 | Reject identity/hash mismatch |

## Stores

Describe logical stores without credentials or personal filesystem paths.

| Sync Set | Local Store | Remote Store | Retention |
|---|---|---|---|
| Example observations | Project-managed local data root | Project-managed artifact store | Define explicitly |

## Database Selection

Default: No database objects are synchronized.

Add a row only for a logical database set the project has deliberately chosen.
Everything absent from this allowlist remains excluded.

| Database Sync Set | Included Tables Or Export Query | Row Scope | Dependency Closure | Explicit Exclusions | Mode And Authority | Identity And Checksum |
|---|---|---|---|---|---|---|
| Example completed observations | `completed_observations` | Completed rows only | Required model-version row | Raw market cache, temporary queue | Bidirectional immutable union | Observation UUID plus SHA-256 |

Record why each included set is valuable enough to transfer and why each major
exclusion should remain local or reconstructible. Do not select an entire
database by default.

## Consistency And Safety

- Writer coordination:
- Deletion policy:
- Atomic publication method:
- Pre-transfer recovery point:
- Interrupted-transfer behavior:

## Commands

```text
make sync-status
make sync-plan
make sync-pull
make sync-push
make sync-verify
make sync
```

Document only commands that are implemented. Status and plan must remain
read-only. The shared `make sync` facade may be enabled only as a fixed
local-to-server alias for the implemented `sync-push` command. Do not provide
an ambiguous automatic bidirectional command.

## Verification

- Manifest comparison:
- Count comparison:
- Checksum verification:
- Schema compatibility:
- Recovery test:
- Included-set and exclusion verification:

## Production Boundary

State whether synchronized artifacts remain review-only or may enter a separate
production promotion workflow. Synchronization must never imply activation.
