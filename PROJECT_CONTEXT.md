# DeveloperOS Project Context

## Project Purpose

DeveloperOS is the long-term governance, shared tooling, safety, AI
collaboration, and operational management repository for projects under
`X:\Projects`.

It is also an active software project. Its browser console, terminal service,
deployment tooling, shared commands, blueprints, and policy documents require
the same disciplined project lifecycle that it defines for other repositories.

## Current Status

Status: Active

## Canonical Project State

- `README.md`: capabilities and operating instructions
- `ROADMAP.md`: current milestone, topic statuses, and next status transitions
- `00_Master/Backlog.md`: project backlog instead of a duplicate root `TODO.md`
- `00_Master/Decisions.md`: durable decisions instead of a duplicate root
  `Decisions.md`
- `PROJECT_RULES.md`: explicit self-application boundaries

## Governance

DeveloperOS applies its global policies to itself. The repository must follow
`BOOT.md`, roadmap continuity, Git safety, coding standards,
language policy, AI collaboration rules, and meaningful verification unless an
explicit structural exception is recorded in `PROJECT_RULES.md`.

## Main Implementation Surfaces

- `00_Master/`, `01_Knowledge/`, and `02_AI/`: governance and shared memory
- `03_Blueprints/`: reusable project starting points
- `04_Tools/`: shared workspace and Codex tooling
- `PROJECT_AREAS.json` and `04_Tools/context/`: task-scoped project navigation
  and the incremental local context index
- `console/`: browser console, private terminal, and usage collector
- `deployment/`: console deployment, project deployment guidance, backups, and
  workstation reporting

## Verification

- `make self-check`: verify DeveloperOS self-application and justified skips
- `make make-check`: verify the shared Make contract for DeveloperOS, OA, Gaia,
  and bTest
- `make console-test`: run the DeveloperOS console test suite
- `git diff --check`: detect whitespace errors

## Deployment

DeveloperOS uses its specialized `make console-deploy` path. Deployment requires
a clean, pushed `main` revision and installs the console and terminal as systemd
services on the Oracle host.
