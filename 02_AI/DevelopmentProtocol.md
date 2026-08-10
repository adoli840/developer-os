# GPT-User-Codex Seven-Step Development Protocol

## Purpose

This protocol is the shared development method for projects governed by
DeveloperOS. It separates domain-level design, repository-grounded execution,
independent review, and final human judgment so that one AI does not silently
reinforce its own first assumption.

The protocol is the default for work with high failure cost, material design
judgment, or expensive reversal. It is not required for small, clear, and
low-risk changes.

## When To Use It

Use the full protocol for:

- core architecture changes;
- new data models or database migrations;
- recursive algorithms;
- automated-trading decision paths;
- production safety gates;
- authentication, authorization, security, or privacy changes;
- large refactors;
- changes to existing core contracts;
- irreversible or otherwise high-impact changes; and
- requirements with material ambiguity or competing interpretations.

The full protocol may be skipped for simple CSS changes, clear typo fixes,
already-designed repetitive work, focused test additions, and small reversible
changes with a narrow impact boundary. Codex should still inspect the relevant
context, run proportionate verification, and report the result.

## Seven Steps

1. **Problem and purpose definition**: State the user or domain problem,
   intended outcome, constraints, and success criteria.
2. **GPT design proposal**: GPT proposes the abstraction, domain principles,
   requirements, trade-offs, and candidate architecture.
3. **Codex implementation plan**: Codex inspects the repository and reports
   current state, interpretation, affected files, dependencies, reusable
   capabilities, risks, implementation plan, tests, migration or database
   impact, and production impact.
4. **Codex implementation and result report**: Codex implements the approved
   or explicitly requested work, runs tests and runtime checks, and reports
   evidence rather than assumed outcomes.
5. **Independent Sol review by Codex**: Sol looks for hidden assumptions,
   edge cases, identity or cache errors, data loss, migration, concurrency,
   security, safety, UNKNOWN or FAIL handling, missing tests, and requirement
   drift.
6. **Independent GPT review**: GPT reviews the self-contained result from a
   repository-independent perspective and challenges purpose or design drift.
7. **User final decision**: The user compares GPT and Codex/Sol evidence,
   resolves trade-offs, and decides whether to accept, revise, defer, or reject
   the design and result.

## Roles And Peer Review

The user is the final design owner and mediator. GPT is primarily responsible
for problem abstraction, domain principles, architecture, requirements, and
independent review. Codex is primarily responsible for repository inspection,
dependency and implementation reality, planning, edits, tests, migrations,
runtime checks, and evidence-based review of GPT proposals.

GPT and Codex/Sol are peer reviewers, not a command hierarchy. A GPT proposal
is an input to verify against the actual repository, existing contracts, and
tests. A Codex/Sol conclusion is also a reviewable implementation report, not
an unquestionable answer. Material disagreement is an open design issue for
the user's judgment.

## Planning And Result Reports

Before irreversible or high-impact implementation, Codex should report the
current state, request interpretation, affected files and boundaries,
dependencies, reusable features, risks and alternatives, implementation plan,
test plan, migration or database impact, and production impact.

After important work, Codex must report changed content and files, key design
decisions, tests and runtime evidence, problems found and resolved, remaining
scope, production/database/runtime impact, intentionally unperformed work, and
the Sol review result. Never invent metrics or claim checks that did not run;
use `unverified`, `environment constrained`, or `pending judgment` when needed.

## Review Limits

Sol review is an adversarial search for meaningful failure modes, not a ritual
approval. Focus cross-review on expensive-to-reverse decisions, data loss,
automated trading, migrations, core algorithms, long-term architecture,
security, safety, public behavior, and production behavior. Do not create
endless review cycles for file names, variable names, minor style, or other
low-cost decisions.

## Precedence And Scope

This is a DeveloperOS-wide default for every repository under `X:\Projects`,
including new projects. Explicit project rules and stricter safety policies
take precedence. When a conflict exists, report it clearly and follow the
stricter applicable rule.
