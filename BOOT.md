# DeveloperOS Boot

## Purpose

`BOOT.md` is the single entry point for any AI agent working inside an individual project that belongs to this workspace.

Before using DeveloperOS from a project repository, read this file first.

## Core Model

DeveloperOS is the global engineering constitution for `X:\Projects`.

Individual projects are application repositories. They own their own README, TODO, roadmap, implementation state, architecture notes, and project-specific decisions.

DeveloperOS provides shared engineering principles, AI collaboration rules, safety policy, coding standards, language policy, and reusable project blueprints.

DeveloperOS is not a project dashboard, project database, or replacement for project-owned documentation.

## Reading Rule

Do not scan the entire DeveloperOS repository by default.

Read only the documents relevant to the current task. Expand the reading scope only when the task requires it or when project documents conflict with DeveloperOS policy.

Use this order when working from an individual project:

1. `X:\Projects\DeveloperOS\BOOT.md`
2. Current project `README.md`
3. Current project `PROJECT_CONTEXT.md`, if present
4. Current project `PROJECT_RULES.md`, if present
5. The canonical project roadmap resolved through
   `00_Master/ProjectRoadmapPolicy.md`
6. When the project owns `PROJECT_AREAS.json`, run
   `make context TASK="<current request>"` and inspect its selected entrypoints
7. Task-relevant DeveloperOS documents from the routing table below
8. Relevant project source files

## Precedence Rule

When rules conflict:

1. Explicit project-specific rules in `PROJECT_CONTEXT.md` or `PROJECT_RULES.md`
2. DeveloperOS global policies
3. Existing project codebase conventions
4. AI judgment

Project-specific documents override DeveloperOS only when the override is explicit. Otherwise, DeveloperOS remains the default global policy.

## Project Roadmap Rule

For meaningful project work, read and follow
`00_Master/ProjectRoadmapPolicy.md` even when the developer does not separately
request roadmap maintenance.

Use the project's existing canonical roadmap or generator. If the project has
none, create a root `ROADMAP.md` from the DeveloperOS project blueprint. When
`ROADMAPS.json` exists, read the root overview and every track affected by the
work. Before the final response, evaluate whether a roadmap topic changed
status, scope, priority, completion signal, or material blocker. Update the
affected track on its own boundary; update the overview only when project-wide
direction, priority, dependency, milestone, or release state also changed.

## Task Routing

| Task Type | Read These DeveloperOS Documents |
|---|---|
| Coding task | `00_Master/CodingStandards.md`, `02_AI/AI_Workflow_Safety_Policy.md`, `02_AI/AI_Collaboration.md`, `02_AI/ModelRoutingPolicy.md`, `02_AI/DevelopmentProtocol.md` |
| Bug fix | `00_Master/CodingStandards.md`, `02_AI/Review.md`, `02_AI/AI_Workflow_Safety_Policy.md` |
| Docker, Compose, image, or container lifecycle | `00_Master/DockerImageBuildPolicy.md`, `00_Master/CodingStandards.md`, `02_AI/AI_Workflow_Safety_Policy.md` |
| Dataset, database, model, or artifact synchronization | `00_Master/DataSynchronizationPolicy.md`, `00_Master/Architecture.md`, `02_AI/AI_Workflow_Safety_Policy.md` |
| Architecture task | `00_Master/Architecture.md`, `00_Master/Decisions.md`, `02_AI/AI_Collaboration.md`, `02_AI/DevelopmentProtocol.md` |
| Architecture review | `00_Master/ArchitectureReview.md`, `00_Master/Architecture.md`, `00_Master/Decisions.md`, `02_AI/DevelopmentProtocol.md` |
| Documentation task | `02_AI/LanguagePolicy.md`, `02_AI/Prompts.md`, `00_Master/GovernanceModel.md` |
| Project planning task | `00_Master/Dashboard.md`, `00_Master/Roadmap.md`, `00_Master/PM_Role.md` |
| AI collaboration or handoff | `02_AI/AI_Collaboration.md`, `02_AI/ModelRoutingPolicy.md`, `02_AI/DevelopmentProtocol.md`, `02_AI/Rules.md`, `02_AI/Memory.md` |
| High-risk refactoring | `02_AI/AI_Workflow_Safety_Policy.md`, `02_AI/DevelopmentProtocol.md`, then `00_Master/CodingStandards.md` and relevant architecture documents |
| Git recovery decision | `02_AI/AI_Workflow_Safety_Policy.md` |
| New project bootstrap | `03_Blueprints/README.md`, `03_Blueprints/ProjectBootstrapPrompt.md`, relevant blueprint folder |
| Governance question | `00_Master/GovernanceModel.md`, `00_Master/Decisions.md`, `README.md` |

## High-Risk Work Rule

Before high-risk work, read `02_AI/AI_Workflow_Safety_Policy.md` first.

High-risk work includes multi-file refactoring, file deletion, structural changes, database schema changes, changes over 100 lines, or changes across 3 or more files.

For high-impact work, apply `02_AI/DevelopmentProtocol.md`. Its seven-step
process is not required for small, clear, reversible, low-risk changes.

## Minimal Context Rule

DeveloperOS should reduce repeated reasoning, not create extra maintenance.

If a task can be completed by reading project-local context and one or two DeveloperOS documents, stop there. Do not continue reading just because more documents exist.

When `PROJECT_AREAS.json` exists, use the shared `make context` command before a
broad source search. Start with its selected area, entrypoints, related files,
and focused verification. Expand only when imports, shared contracts, database
or authentication boundaries, deployment behavior, safety rules, or failing
evidence cross that area. The generated index is advisory and never replaces
reading the selected source or the project's explicit instructions.

## Output Rule

When DeveloperOS affected the work, summarize which DeveloperOS documents were used and why.

For meaningful repository work, confirm that roadmap transition triggers were
evaluated. Create or update the project-owned roadmap only when required by
`00_Master/ProjectRoadmapPolicy.md`.

When a finding belongs to the project, update or recommend updating the project repository. When a finding affects future engineering decisions across projects, record or recommend recording it in DeveloperOS.
