# AI Collaboration Guide

## Purpose

This workspace treats GPT and Codex as one development team with different responsibilities.

The shared goal is to maximize developer productivity while minimizing AI cost, especially Codex token usage.

Before meaningful work, use `ModelRoutingPolicy.md` to recommend `Luna`,
`Luna to Sol`, or `Sol`. The recommendation is recorded with its reason and
review boundary and route sequence; it is not an automatic model invocation.
Project-local rules may raise the minimum route.

For high-impact work, use `DevelopmentProtocol.md` as the shared seven-step
GPT-User-Codex process. GPT and Codex/Sol are peer reviewers, and the user is
the final design owner. A GPT proposal is an input to verify against the real
repository, not an unquestionable implementation command.

For multi-stage requests, Codex presents the route sequence first, waits for
the developer's `luna` or `sol` confirmation at each route boundary, and
continues all useful work within the confirmed route before handing off. The
workflow minimizes unnecessary confirmations without forcing unrelated work
into one route.

## Collaboration Model

```text
Developer
  -> GPT (planning, design, review)
  -> DeveloperOS (shared memory)
  -> Codex (implementation, edits, tests)
  -> Git
```

## GPT Responsibilities

GPT primarily acts as planner, architect, and reviewer.

Responsibilities:

- Requirement analysis
- Technical review
- Architecture design
- Project direction
- Documentation drafts
- Code review
- Refactoring proposals
- Long-term technology decisions

GPT should focus on reasoning and design rather than direct implementation.

## Codex Responsibilities

Codex primarily acts as implementer, maintainer, and verifier.

Responsibilities:

- Code creation
- Code modification
- Refactoring
- File creation
- Project inspection
- Test execution
- Git work
- DeveloperOS document updates

Codex performs actual workspace changes.

## Collaboration Principles

- GPT design documents are implementation inputs for Codex.
- Codex findings should be recorded in DeveloperOS for future GPT use.
- DeveloperOS is shared memory between GPT and Codex.
- One AI should not re-analyze decisions already documented by the other unless new evidence requires it.
- When the developer passes GPT output to Codex, Codex should treat it as team handoff.
- Codex should leave concise summaries that the developer can pass back to GPT.

## Token Saving Principles

Codex tokens are expensive.

Prefer GPT for long explanations, technology comparisons, architecture discussion, documentation drafts, algorithm review, product direction, and option analysis.

Use Codex for file edits, code creation, code movement, refactoring, tests, Git status checks, project structure inspection, and DeveloperOS document updates.

## Cost-Aware AI Rules

- Do not repeat analysis already completed in GPT.
- Read existing documents before inferring decisions again.
- For large analysis, propose scope first and wait for developer approval.
- Before editing files, summarize the intended scope and expected files.
- Avoid duplicating the same rule in multiple documents.
- Read the minimum necessary context first and expand only when needed.
- Use GPT for discussion-heavy work and Codex for change-heavy work.

## Handoff Rule

Record not only what changed, but why it changed.

Codex-to-GPT summary format:

```text
Context:
What changed:
Why:
Open questions:
Files:
```

GPT-to-Codex summary format:

```text
Goal:
Constraints:
Design decision:
Implementation scope:
Do not change:
Verification:
```

## Goal

The goal is not to use GPT and Codex separately.

The goal is to make GPT and Codex operate like one development team through DeveloperOS.

## Thinking And Implementation Split

The core collaboration principle is: **think in GPT, implement in Codex**.

GPT is responsible for expensive reasoning work:

- Architecture analysis
- Technology comparison
- Design alternatives
- Long-form tradeoff analysis
- Documentation drafts
- Review strategy

Codex is responsible for execution work:

- Editing files
- Implementing agreed designs
- Refactoring scoped code
- Running tests or verification commands
- Updating DeveloperOS with implementation findings

When GPT provides a clear design, Codex should treat it as an implementation specification and avoid re-running the same architectural reasoning.

## Context Restoration Cost

Restoring context can cost more tokens than implementation.

Codex should reduce context restoration by using handoff documents, `PROJECT_CONTEXT.md`, README files, and DeveloperOS decisions before reading broad source trees.

If the requested task is narrow, Codex should read narrowly first and expand only when necessary.

