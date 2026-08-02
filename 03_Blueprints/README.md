# Blueprints

## Purpose

This directory stores project blueprints, not isolated document Blueprints.

A blueprint is a reusable project starting point that may include documentation, governance context, Docker files, Git defaults, prompts, and project structure.

## Rule

Do not copy DeveloperOS global policy documents into projects.

Blueprints should reference DeveloperOS through `PROJECT_CONTEXT.md` and use `PROJECT_RULES.md` only for explicit local exceptions.

## Available Blueprints

- `Project`: generic project blueprint
- `Project/ROADMAP.md`: default project-owned roadmap for repositories without an established roadmap mechanism
- `Project/ROADMAPS.example.json`: opt-in manifest example for independently prioritizable roadmap tracks
- `Project/DATA_SYNC.md`: optional project-owned contract for non-source data synchronization
- `ProjectBootstrapPrompt.md`: project-level prompt for invoking DeveloperOS through `BOOT.md`
- `GoWeb`: planned Go web service blueprint
- `PythonCLI`: planned Python command-line tool blueprint
- `AIProject`: planned AI-integrated project blueprint
- `WebApp`: planned web application blueprint

Browser projects should render the blueprint's `Roadmap Details` through the
shared assets documented in `04_Tools/roadmap-web/README.md` so project-local
and DeveloperOS roadmap views remain identical.

## Naming Rule

Use blueprint names that describe the project shape, not just a single file type.

