# Project Roadmap Continuity Policy

## Purpose

Every active repository must preserve a concise, project-owned roadmap without
turning the roadmap into an implementation diary.

DeveloperOS defines when roadmap state must change. Each project remains the
source of truth for its own roadmap and current state.

## Scope

This policy applies to every repository under `X:\Projects`, including
DeveloperOS itself.

## Roadmap Topic

A roadmap topic is a trackable project objective, milestone, capability, or
subproblem whose state helps determine project direction.

Use a small status set unless a project already has an established equivalent:

- `Planned`
- `In Progress`
- `Blocked`
- `Paused`
- `Done`
- `Cancelled`
- `Prohibited`

## Update Triggers

Update the canonical roadmap when at least one of these state boundaries is
crossed:

- A roadmap topic is added, removed, split, merged, or materially renamed.
- A topic changes status, such as `Planned` to `In Progress` or `In Progress` to
  `Done`.
- The active topic or ordered priority changes.
- A topic's scope or completion signal changes materially.
- A blocker, dependency, or risk appears or is resolved in a way that changes
  topic status or the next transition.
- Verified evidence establishes that a topic can move to its next status.

No separate roadmap request is required when a trigger occurs.

## Non-Triggers

Do not update the roadmap merely because a meaningful work unit ended. The end
of a work unit is an evaluation point, not an automatic document edit.

These events do not require a roadmap change when the topic remains in the same
state:

- More implementation completed inside an existing `In Progress` topic
- Tests rerun without changing readiness or status
- Read-only inspection, explanation, or status reporting
- Minor fixes, formatting, or typo corrections
- Intermediate commands, commits, or turns inside the same roadmap stage
- Verification evidence that does not yet satisfy or invalidate a transition

Keep detailed implementation history in Git, focused project documentation, or
handoff records rather than the roadmap.

## Roadmap Resolution

At the start of meaningful project work, resolve one canonical roadmap in this
order:

1. A roadmap path or generator explicitly named by project instructions
2. A repository-root `ROADMAPS.json` manifest and its declared roadmaps
3. An existing project-owned roadmap or roadmap-status artifact already used by
   the repository
4. The repository-root `ROADMAP.md`

If no roadmap exists, create `ROADMAP.md` from
`DeveloperOS/03_Blueprints/Project/ROADMAP.md` before the first meaningful work
unit closes. Establishing the initial topics and statuses is itself a roadmap
state change.

Do not create a competing `ROADMAP.md` when a project already maintains a
different canonical roadmap. Preserve its established format and generator.
When a generated roadmap has a source file or command, update the source and
run the existing generator instead of hand-editing generated output.

## Work Lifecycle

For meaningful project work, the AI agent must:

1. Read the canonical project roadmap before deciding implementation scope.
2. Identify the roadmap topic affected by the request.
3. Implement and verify the work without repeatedly editing the roadmap.
4. Before the final response, evaluate every update trigger.
5. Update the roadmap only when a trigger occurred, recording the topic's new
   state and the evidence or reason for the transition.
6. Include a required roadmap change with the same project changes when
   committing.

## Minimum Roadmap State

The canonical roadmap must make these facts easy to recover:

- Last roadmap update date
- Current milestone or direction
- Roadmap topics and their statuses
- Completion signal or next status transition for each active topic
- Current priority
- Active blockers, risks, or dependencies
- Most recent material status change and its evidence

Keep the roadmap concise. It is not a chat transcript, command log, complete
changelog, or duplicate of Git history. Summarize completed topics when the
document becomes noisy.

## Canonical Standard Format

New roadmaps and repositories without an established roadmap mechanism must
use the root `ROADMAP.md` format in
`DeveloperOS/03_Blueprints/Project/ROADMAP.md`.

The standard format uses these sections in this order:

1. `# <Project> Roadmap`
2. `Updated: YYYY-MM-DD`
3. `## Direction`
4. `## Current Milestone`
5. `## Roadmap Topics`
6. `## Current Priority`
7. `## Latest Status Change`
8. `## Next Status Transitions`
9. `## Risks And Blockers`
10. Optional `## Completed Topics`

Projects that publish a rich roadmap view should add `## Roadmap Details`
between `Roadmap Topics` and `Current Priority`. It uses this exact table:

```markdown
| Stage | Item | Status | Blocker Type | Description |
|---|---|---|---|---|
| Initial project foundation | Repository contract | In Progress | None | Establish the first reviewed project boundary. |
```

Every roadmap topic must appear as a `Stage` at least once. List every sibling
item that materially contributes to that stage; renderers must not truncate the
list to an arbitrary count. Item names must be unique within a stage.

Detail `Status` uses the presentation states `Done`, `In Progress`, `Blocked`,
or `Prohibited`. `Blocker Type` is `None` except for blocked items, which must
choose exactly one of:

- `Operator`: progress requires a developer decision, credential, approval, or
  other human response.
- `Processing`: progress waits for historical processing such as learning,
  backtesting, migration, or batch computation.
- `Future`: progress waits for future evidence such as paper, shadow, soak, or
  scheduled observation time.

`Description` is a short explanatory sentence shown on hover and keyboard
focus. It must explain the item rather than repeat its title.

`Current Milestone` must contain `Objective`, `Status`, and
`Completion signal` fields. `Roadmap Topics` must use this exact table header:

```markdown
| Topic | Status | Completion Signal | Next Transition |
|---|---|---|---|
```

`Latest Status Change` must contain `Topic`, `Change`, and
`Evidence or reason`. Use only the status values defined in `Roadmap Topic`.
Keep topic names stable unless a trigger explicitly requires restructuring.

## Multiple Roadmap Tracks

Split a roadmap only when a project contains independently prioritizable
workstreams with distinct milestones and status transitions. Do not create a
track merely for a source directory, service, programming language, or team
boundary.

A multi-track project must keep a concise repository-root `ROADMAP.md` as the
overall roadmap. It coordinates project direction, cross-track priority,
dependencies, and release-level status without copying every track topic. Each
detailed track uses the same canonical standard format and is declared in the
repository-root `ROADMAPS.json` manifest:

```json
{
  "schema_version": 1,
  "tracks": [
    {
      "slug": "game",
      "name": "Game",
      "path": "docs/roadmaps/game.md"
    },
    {
      "slug": "ai",
      "name": "AI",
      "path": "docs/roadmaps/ai.md"
    }
  ]
}
```

Track slugs must use lowercase letters, digits, and single hyphens. Track names
and paths must be unique, paths must be relative Markdown files inside the
project, and a manifest may declare at most eight tracks.

For work confined to one track, read and evaluate both the overall roadmap and
the affected track. Update the track when its state boundary changes. Update
the overall roadmap only when project direction, cross-track priority,
dependency, milestone, or release-level state also changes. A change spanning
multiple tracks evaluates each affected track and then the overall roadmap.

Existing detailed documents may remain as design evidence, operating guides,
history, or generated reports. Once a multi-track manifest is adopted, only
the root overview and declared track files are canonical roadmap state; other
documents must not claim a competing current roadmap status.

An established project-specific roadmap or generator may retain its native
format. It must expose equivalent standard fields through any roadmap web view
instead of creating a second manually maintained source of truth.

## Roadmap Web View

Every project with a browser-accessible application must provide a read-only
roadmap view at its normal access address followed by `/roadmap`.

The view must:

- Render the project's canonical roadmap rather than maintain a second copy.
- Show the update date, direction, current milestone, topic statuses,
  priorities, latest status change, next transitions, and risks or blockers.
- Work at both desktop and mobile widths.
- Escape or safely render roadmap content and never expose filesystem paths,
  credentials, private endpoints, personal data, or unrestricted raw files.
- Remain read-only on a public endpoint. Roadmap edits continue through the
  project repository and its normal review process.
- For a multi-track project, provide an `Overall` view and one clearly named
  view per manifest track without merging their detailed topic tables.
- Use the DeveloperOS roadmap presentation families consistently: green for
  done, blue for in progress, orange for blocked, and red for prohibited.
- Distinguish operator blockers with an attention animation, processing
  blockers with a gray-to-orange horizontal gradient, and future blockers with
  an orange-to-green horizontal gradient. Respect reduced-motion preferences.
- Render every declared detail item and expose its description on pointer hover
  and keyboard focus.
- Use the versioned presentation assets under `04_Tools/roadmap-web` or a
  verified project-native implementation with equivalent DOM, colors,
  interaction, escaping, responsiveness, and accessibility behavior.

Legacy roadmaps without `Roadmap Details` remain valid. A compatible renderer
may derive `Completion signal` and `Next transition` items temporarily, but a
project adopting the shared rich presentation must add explicit detail rows.

Projects without a browser-accessible application are exempt from a local
route. DeveloperOS may provide a derived cross-project view, but each project
remains the owner of its canonical roadmap. A project-specific format requires
an adapter from its canonical source to the standard fields; it does not
justify a duplicate roadmap document.

## Existing Project Automation

Project-specific roadmap automation controls its own filename, format, status
names, and generation command. This global policy controls only the minimum
transition-based lifecycle.

An explicit project rule may choose a different canonical artifact or a stricter
status model. It must not silently disable roadmap continuity. If the project's
roadmap mechanism is broken, record that as a blocker and repair it when doing
so is within the requested scope.

## Ownership Boundary

Roadmap content stays in the project repository. DeveloperOS may provide policy,
templates, derived inspection, and cross-project priority summaries, but it must
not copy or become the owner of project-local roadmap state.
