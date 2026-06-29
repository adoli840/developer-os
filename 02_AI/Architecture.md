# AI Architecture Rules

## Purpose

This document defines how AI should reason about architecture inside the DeveloperOS workspace.

## Principle

AI must consider the workspace-level architecture before implementing individual features.

## Before Choosing A Stack

Review these questions:

- Is the project local-first or server-based?
- Are there concurrent users?
- Does the data need long-term storage?
- Does the project require deployment?
- Is AI integration core or optional?
- Can the project reuse an existing project, module, or template?

## Preferred Defaults

- Local-first personal application: SQLite first
- Server application: PostgreSQL first
- Fast automation: Python first
- Stable API server: Go first
- Web UI: TypeScript first

## Constraint

Do not over-engineer early projects. Start with the simplest architecture that can be inspected, tested, and extended safely.

