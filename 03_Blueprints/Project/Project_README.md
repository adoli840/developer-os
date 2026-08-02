# Project Name

## Project Governance

This project is governed by the DeveloperOS workspace.

Before making architectural or structural changes, always consult:

- `../DeveloperOS/00_Master/AI_Rules.md`
- `../DeveloperOS/00_Master/CodingStandards.md`
- `../DeveloperOS/00_Master/DockerImageBuildPolicy.md`, for Docker work
- `../DeveloperOS/00_Master/ProjectRoadmapPolicy.md`
- `../DeveloperOS/02_AI/LanguagePolicy.md`
- `../DeveloperOS/02_AI/AI_Collaboration.md`
- `../DeveloperOS/02_AI/AI_Workflow_Safety_Policy.md`
- `../DeveloperOS/00_Master/Architecture.md`, if applicable

Project-specific rules in this repository take precedence over DeveloperOS only when they explicitly override a global rule.

DeveloperOS provides the default engineering policies for all projects in this workspace.

## Purpose

Describe the purpose of this project.

## Status

Current status: Draft

## Tech Stack

- Language:
- Framework:
- Database:
- AI:
- Deployment:

## Getting Started

```bash
# setup command
```

## Run

```bash
# run command
```

Docker projects use `make run` or `make up` to reuse existing images. Use
`make b-run` only when an image is missing or a Docker build input changed.

## Test

```bash
# test command
```

## Project Context

See `PROJECT_CONTEXT.md`.

## Roadmap

See `ROADMAP.md`. Evaluate it after meaningful work and update it only at the
topic status boundaries defined by the DeveloperOS roadmap continuity policy.
If this project has a browser-accessible application, render the canonical
roadmap read-only at `/roadmap`; do not maintain separate web-only roadmap data.
If the project has independent workstreams, copy `ROADMAPS.example.json` to
`ROADMAPS.json`, replace the example tracks, and keep the root roadmap as the
cross-track overview.

## Project Rules

See `PROJECT_RULES.md` only when this project has explicit local exceptions.

## Decisions

Important design decisions should be recorded in `Decisions.md`.

