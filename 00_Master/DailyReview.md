# Daily Review

## Purpose

This document defines the daily status review format for DeveloperOS.

DeveloperOS is not an always-running reminder system. It acts as a Project Manager when invoked by the developer or AI session.

## Daily Review Template

```text
Developer Daily Review

Today
- Primary recommendation:
- Reason:
- Suggested tasks:

Weekly Progress
- Goal completion:
- Roadmap alignment:
- Documentation:
- Verification:

Project Priorities
1.
2.
3.

Warnings
- Stale projects:
- Blockers:
- Missed weekly goals:

Recommendation
- Recommended next action:
- Alternative:
- Tradeoff:
```

## Soft Challenge Rule

If the developer chooses a lower-priority project while a higher-priority project is at risk, Codex should respond with a soft challenge.

Example:

```text
We can work on Memo today. However, Gaia is currently Critical priority and has the nearer deadline. Working on Gaia first would better match the weekly goal. Do you still want to continue with Memo?
```

The final decision always belongs to the developer.

## Review Inputs

Use these documents as inputs:

- `Dashboard.md`
- `WeeklyPlan.md`
- `Roadmap.md`
- `ProjectStatus.md`
- `Metrics.md`
- `Backlog.md`
- `Decisions.md`

