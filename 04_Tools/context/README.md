# Project Context Routing

## Purpose

Project context routing narrows Codex investigation before source reading. It
does not replace source code, project instructions, or the canonical roadmap.

Each project owns a concise `PROJECT_AREAS.json`. DeveloperOS owns the indexer
and the shared `make context` command. The generated index stays local at
`.developer-os/context-index.json` and must be ignored by Git.

## Files

- `PROJECT_AREAS.json`: tracked, human-maintained area boundaries
- `.developer-os/context-index.json`: ignored, generated symbol and file index
- `04_Tools/context/project_context.py`: shared incremental generator and task
  selector
- `04_Tools/context/context_identity.py`: project-and-lane-isolated context seal
  and dirty-tree identity contracts
- `04_Tools/context/context_observability.py`: opt-in metrics-only context build
  observer

Start a project map from
`03_Blueprints/Project/PROJECT_AREAS.json`.

## Area Contract

The root object uses schema version 1 and contains a project name, optional
exclusion globs, and one or more areas. Each area requires:

- `id`: lowercase words separated by single hyphens
- `name` and `description`: short human-readable identity
- `keywords`: task terms that select the area
- `path_globs`: project-relative files owned by the area
- `entrypoints`: source or configuration files to inspect first
- `related_docs`: project-owned context documents
- `test_commands`: smallest relevant verification commands
- `services`, `data_stores`, and `risk_tags`: optional operating context

Paths may belong to more than one area. That overlap is intentional for shared
contracts. Keep the map concise; do not list every file manually.

## Usage

With the shared DeveloperOS Make file enabled:

```powershell
make context TASK="WEHAGO voucher injection"
make context AREA="wehago"
make context TASK="game recovery" CONTEXT_LIMIT=20
```

The command refreshes the index, selects at most three matching areas, and
prints entrypoints, relevant files, focused verification, services, data
stores, and risk tags. Start with that set. Expand only when imports, shared
contracts, or failing evidence cross an area boundary.

Set `CONTEXT_FORMAT=json` for machine-readable selection or
`CONTEXT_REFRESH=1` to rebuild every indexed text file.

## Observability Sidecar

`ContextEfficiencySnapshotV1` measures the existing selector without changing
its result, order, or cache. It records counts, byte and line totals, inclusion
reasons, repeated selection, identity reuse, dirty scanning, validation status,
duration, and packet/output sizes. It stores task and packet hashes but never
source content, task text, session text, credentials, or inferred token usage.

```powershell
python -m 04_Tools.context.context_observability `
  --project-root . `
  --lane MAINLINE_CODEX_REVIEW `
  --task "audit context routing" `
  --output .developer-os/context-efficiency/sample.json
```

The observer performs a non-persisting index build, so it does not rewrite the
normal `.developer-os/context-index.json`. Provider token counts are accepted
only when explicitly identified as actual provider usage.

## Incremental Behavior

Clean tracked files use the Git blob ID as their cache signature. Only dirty or
untracked files are hashed from the working tree. Unchanged symbol data is
reused, while area assignments are recalculated from the current map. Files
outside every declared area are skipped. This keeps a map edit correct without
rereading every source file.

The index contains paths, kinds, symbols, imports, headings, routes, Git state,
and area assignments. It does not copy file contents, credentials, database
rows, backups, generated assets, or large binary files.

## Safety

The command fails when `PROJECT_AREAS.json` is invalid or when
`.developer-os/context-index.json` is not ignored. The generated index is
advisory. Codex must still inspect the selected source and broaden its search
for cross-cutting database, authentication, deployment, shared API, or safety
changes.
