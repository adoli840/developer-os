# Coding Standards

## Purpose

This document defines global coding standards for projects governed by DeveloperOS.

## General Principles

- Follow the existing style of the project being edited.
- Add abstractions only after repetition or real complexity is confirmed.
- Keep changes small, explicit, and easy to review.
- Do not mix unrelated refactoring into feature work.
- Update README, Decisions, Dashboard, or project context when the change affects operating knowledge.

## Language Choice

| Situation | Preferred Choice |
|---|---|
| Fast automation, scripting, data processing | Python |
| API servers, concurrency, single-binary deployment | Go |
| Web UI or desktop web UI | TypeScript |
| Local-first small applications | Python or TypeScript |
| High-performance system tools | Go or Rust |

## Database Choice

| Situation | Preferred Choice |
|---|---|
| Personal, local-first, single-user application | SQLite |
| Server application, multiple users, long-term scale | PostgreSQL |
| Cache, queue, session store | Redis |
| Text search or document search | PostgreSQL FTS or a dedicated search engine |

## AI-Ready Codebase

Maintain these properties so AI agents can work safely and efficiently:

- Clear README
- Small files with clear module boundaries
- Documented setup, run, and test commands
- Recorded decisions for important choices
- Blueprints for repeated workflows

