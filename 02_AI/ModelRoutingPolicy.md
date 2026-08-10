# Task-Based Model Routing Policy

## Purpose

DeveloperOS recommends an appropriate reasoning route before meaningful work.
The recommendation balances quality, cost, and rework risk without silently
forcing a specific model or provider.

The route is a collaboration instruction, not an automated model invocation.
The developer or Codex may raise the recommendation when project-local rules
or new evidence require a stricter route.

## Decision Inputs

At the start of meaningful work, evaluate:

- implementation complexity;
- safety, security, and data-boundary risk;
- requirement clarity;
- cost of rework if the first design is wrong; and
- available token or time budget.

Record the recommendation and a short reason before broad inspection or edits.

## Routes

### Luna

Use for low-risk, well-bounded work where the correct change is already clear:

- file discovery and focused inspection;
- simple UI or copy changes;
- repetitive or mechanical code changes;
- aggregation and routine reporting; and
- focused test additions or maintenance.

### Luna to Sol

Use when implementation can begin with a bounded plan, but the result needs a
stronger design or review boundary:

- complex feature implementation;
- data processing, state transitions, or backtesting logic;
- changes that cross several modules but have a clear contract; and
- token-sensitive work where a smaller model can implement while a stronger
  model reviews the design, boundary, or final result.

The handoff must state what Luna implemented, what Sol must review, and which
evidence is required before completion.

### Sol

Use when an incorrect first decision could cause material loss, exposure, or
expensive rework:

- security, secrets, privacy, or data-leak prevention;
- architecture or ownership-boundary changes;
- database canonical state, synchronization authority, or migration policy;
- transaction, promotion, release, or production deployment policy;
- model or artifact promotion with irreversible consequences; and
- unclear requirements where the design must be resolved before implementation.

Any explicit Sol trigger takes precedence over token-saving considerations.

## Required Startup Note

For meaningful work, begin the working note or response with:

```text
Model recommendation: Luna | Luna to Sol | Sol
Route sequence: <recommended route for each natural work stage>
Reason: <complexity, risk, clarity, and rework evidence>
Review boundary: <what must be checked before completion>
```

For trivial one-line or purely conversational requests, the note may be
omitted. A project-local rule may choose Sol as its minimum route.

## Interactive Handoff Workflow

When a request contains multiple work units or needs more than one route,
Codex should analyze the complete request first and present the most efficient
route sequence before implementation. Do not silently assume that the user
has changed the active model.

Use this interaction:

1. Recommend the first route and state the work that can be completed within
   that route.
2. Ask the developer to switch and confirm with `luna` or `sol` when the
   recommended route is not the active one.
3. Continue through all useful work for the confirmed route until a natural
   handoff boundary, without asking for confirmation at every small step.
4. At the boundary, summarize completed work, remaining work, evidence, and
   why the next route is needed. Ask for the next route confirmation.
5. After confirmation, continue from the handoff summary without repeating
   completed inspection or implementation.

Optimize for the shortest effective route sequence, not the fewest model
changes. If switching routes produces a clearer dependency order or prevents
the Luna phase from batching unrelated work and obscuring the next action,
request the switch earlier. Multiple Luna/Sol transitions are valid when the
project naturally alternates implementation and high-confidence review.

An explicit developer route request takes precedence over a lower route
recommendation, except where a safety or project-local rule requires Sol.
The confirmation word is a workflow gate; it does not itself prove which
underlying model is active.

## Project Baselines

Project baselines are defaults, not exemptions from the decision inputs:

- OA: Luna for narrow UI, documentation, and routine automation; Luna to Sol
  for cross-plugin state or workflow changes; Sol for credentials, external
  actions, or data authority.
- Gaia: Luna for presentation and content maintenance; Luna to Sol for game,
  simulation, persistence, or AI behavior; Sol for save-data authority,
  irreversible migration, or release policy.
- bTest: Luna for ordinary development and repetition; Luna to Sol for Elliott
  learning, ORS, backtesting, and data processing; Sol for Risk Kernel,
  database canonical state or data authority, model or data promotion, and
  paper- or live-trading-related work. When an Elliott or Ever task crosses a
  data-authority, promotion, or trading-impact boundary, raise it to Sol rather
  than preserving Luna for token savings.
- DeveloperOS: Luna for documentation and focused console presentation;
  Luna to Sol for shared parser or workflow changes; Sol for global policy,
  security, data synchronization authority, or deployment policy.

Projects may make a baseline stricter in their own `PROJECT_RULES.md` or
project-local AI guidance.
