# Project Operational Authority Policy

## Purpose

DeveloperOS manages shared, host, and cross-project infrastructure. A managed
project normally owns the non-destructive operation of its repository,
project-owned database, application runtime, artifacts, and project-local
infrastructure. DeveloperOS is not an approval hop for routine project work.

Project rules and risk constitutions may narrow this authority. They may not
weaken the absolute safety boundaries below.

## Green: Project Autonomy

A project agent may execute these actions without a separate DeveloperOS or
user approval when they are within an already approved project purpose and
contract:

- task-local implementation, tests, fixtures, contracts, deterministic
  artifacts, seals, caches, roadmap status updates, and task-local commits;
- project-owned database reads and normal writes, contract-defined append-only
  persistence, additive migrations, migration rehearsal and validation,
  trusted database clock use, backup and recovery verification;
- least-privilege project writer use and maintenance, project-owned credential
  rotation, and secret injection through an existing managed secret boundary;
- project-owned application or writer container lifecycle, stale lease
  fencing, contract-defined terminalization, bounded schedulers, readiness
  recovery, project-local network attachment, and disposable infrastructure;
- approved-provider source capture, canonical ingestion, forward-only recovery
  of source-confirmed missing data, and currentness or cutoff evidence;
- bounded implementation and validation of project evaluators, projections,
  and production wiring that do not make a new semantic or activation-policy
  choice.

Green authority includes the continuous sequence `audit -> implement ->
validate -> migrate -> run -> verify`. A database, credential, role, migration,
or container action is not an authority mutation merely because it changes
project-owned operational state.

## Amber: User Decision

The project agent asks the user when a choice changes product or research
meaning, including equally supported canonical alternatives, a new canonical
rule, guidance meaning, dialect, Human Review policy, forecast semantics,
trading behavior, or a policy value such as search budget, cadence, threshold,
or activation start that materially affects results. After the user decides,
the project agent executes within Green authority without routing the work back
through DeveloperOS.

## Red: DeveloperOS Escalation

DeveloperOS is required only for a Docker daemon, shared socket, shared data
root, shared network topology, shared or cross-project volume, host WSL or OS,
global secret infrastructure, cross-project credential or authority, or an
outage/recovery action that can affect another project. A project-owned
container, database, role, credential, or network attachment is not Red merely
because it uses the shared native Docker daemon.

## Explicit User Approval

The user must explicitly approve destructive data deletion, an irreversible or
destructive migration, migration-history rewrite, historical authority
fabrication or backfill-policy change, superuser-equivalent privilege
expansion, database or schema ownership architecture changes, canonical
semantic changes, Risk Constitution changes, live trading activation, and any
expansion of real-money or order authority.

## Absolute Safety Boundaries

No autonomy permits fixture-to-production impersonation, evidence backdating,
turning incomplete evidence into completion, turning missing data into
`NO_MATCH`, treating unresolved evidence as canonical absence, rewriting a
migration ledger, resetting or stashing unrelated dirty work, changing another
project's data, exposing or committing a secret, silent privilege escalation,
or destructive recovery without explicit approval. Uncertainty remains
fail-closed.

## Ownership Model

```text
USER
  -> product, semantic, and destructive authority

MANAGED PROJECT
  -> repository, project DB, project runtime, research, source-data operation,
     and forward-only materialization authority

DeveloperOS
  -> shared, host, and cross-project infrastructure authority
```

Model selection remains owned by `02_AI/ModelRoutingPolicy.md`; operational
autonomy does not lower a required Luna-to-Sol or Sol review boundary.
